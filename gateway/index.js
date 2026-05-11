/**
 * -----------------------------------------------------------------------------
 * 📊 SPANINSIGHT AI GATEWAY — CLOUDFLARE WORKER (V-FINAL PRODUCTION + VISION)
 * 🌐 Gateway URL: https://api.spaninsight.com/
 * -----------------------------------------------------------------------------
 * 
 * =============================================================================
 * 🚀 DEPLOYMENT & SETUP INSTRUCTIONS (READ BEFORE CODING THE APP)
 * =============================================================================
 * 
 * 1. CLOUDFLARE SECRETS (Set these in your Cloudflare Worker Dashboard -> Variables):
 *    - GROQ_API_KEYS      : "key1, key2, key3" (Comma-separated string of your Groq keys)
 *    - NVIDIA_API_KEYS    : "key1, key2"       (Comma-separated string of your NVIDIA keys)
 *    - CLIENT_SECRET_KEY  : "spaninsight-mobile-v1" (Your secure app password)
 * 
 * =============================================================================
 */

// STRICTLY GROQ & NVIDIA ONLY (No Gemini)
// GROQ is prioritized first across all routes.
const ROUTES = {
  // Fast schema reading and action suggestions
  suggest: [ 
    { provider: "groq", id: "llama-3.1-8b-instant" },
    // NVIDIA Fallback
    { provider: "nvidia", id: "google/gemma-4-31b-it", extraParams: { max_tokens: 16384, chat_template_kwargs: { enable_thinking: true } } }
  ],
  
  // Heavy reasoning models for Pandas/Matplotlib Python code generation
  code: [
    { provider: "groq", id: "llama-3.3-70b-versatile" }, 
    { provider: "groq", id: "qwen/qwen3-32b" },          
    { provider: "groq", id: "openai/gpt-oss-120b" },
    // NVIDIA Fallbacks (with heavy token budgets)
    { provider: "nvidia", id: "nvidia/nemotron-3-super-120b-a12b", extraParams: { max_tokens: 16384, reasoning_budget: 16384, chat_template_kwargs: { enable_thinking: true } } },
    { provider: "nvidia", id: "mistralai/mistral-medium-3.5-128b", extraParams: { max_tokens: 16384, reasoning_effort: "high" } },
    { provider: "nvidia", id: "openai/gpt-oss-120b", extraParams: { max_tokens: 4096 } },
    { provider: "nvidia", id: "google/gemma-4-31b-it", extraParams: { max_tokens: 16384, chat_template_kwargs: { enable_thinking: true } } }
  ],
  
  // Fast models to turn local Pandas numerical results into human insights
  interpret: [
    { provider: "groq", id: "llama-3.3-70b-versatile" }, 
    { provider: "groq", id: "qwen/qwen3-32b" },
    { provider: "groq", id: "openai/gpt-oss-120b" },
    // NVIDIA Fallbacks
    { provider: "nvidia", id: "openai/gpt-oss-120b", extraParams: { max_tokens: 4096 } },
    { provider: "nvidia", id: "google/gemma-4-31b-it", extraParams: { max_tokens: 16384, chat_template_kwargs: { enable_thinking: true } } }
  ],

  // Visual data extraction and chart interpretation
  vision: [
    { provider: "groq", id: "meta-llama/llama-4-scout-17b-16e-instruct" },
    // NVIDIA Fallbacks
    { provider: "nvidia", id: "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning", extraParams: { max_tokens: 65536, reasoning_budget: 16384, chat_template_kwargs: { enable_thinking: true } } },
    { provider: "nvidia", id: "google/gemma-4-31b-it", extraParams: { max_tokens: 16384, chat_template_kwargs: { enable_thinking: true } } }
  ],
  
  // Audio transcription for app voice commands
  audio: [
    { provider: "groq", id: "whisper-large-v3" },
    { provider: "groq", id: "whisper-large-v3-turbo" }
  ]
};

const ENDPOINTS = {
  groq_chat: "https://api.groq.com/openai/v1/chat/completions",
  groq_audio: "https://api.groq.com/openai/v1/audio/transcriptions",
  nvidia_chat: "https://integrate.api.nvidia.com/v1/chat/completions"
};

// SECURITY: Allowed origins for Web (App secret bypasses this for Mobile/Flet)
const ALLOWED_ORIGINS = ["https://spaninsight.com", "https://app.spaninsight.com"];

// HELPER: Key Rotation - picks a random key from the comma-separated environment variables
function getRandomKey(keysString) {
  if (!keysString) return null;
  const keys = keysString.split(',').map(key => key.trim()).filter(Boolean);
  return keys.length > 0 ? keys[Math.floor(Math.random() * keys.length)] : null;
}

// HELPER: Fetch with strict timeout to prevent Worker hangs
async function fetchWithTimeout(resource, options = {}, timeoutMs = 15000) {
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(resource, { ...options, signal: controller.signal });
    clearTimeout(id);
    return response;
  } catch (error) {
    clearTimeout(id);
    throw error;
  }
}

export default {
  async fetch(request, env) {
    const origin = request.headers.get("Origin");
    const clientSecret = request.headers.get("X-App-Secret");
    const userAgent = request.headers.get("User-Agent") || "";
    
    // SECURITY GATE
    const isValidSecret = clientSecret === env.CLIENT_SECRET_KEY;
    const isValidApp = isValidSecret && userAgent.includes("SpaninsightApp");

    // Preflight CORS
    if (request.method === "OPTIONS") {
      return new Response(null, { headers: corsHeaders(origin, isValidApp) });
    }

    // Block unauthorized requests
    if (!isValidApp && request.url.includes("/chat")) {
      console.warn(`Unauthorized access blocked. UA: ${userAgent}`);
      return json({ error: "Unauthorized Gateway Access. Check headers." }, 401, origin, false);
    }

    const url = new URL(request.url);

    // Healthcheck endpoint
    if (url.pathname === "/health") {
      return json({ 
        status: "ok", 
        message: "Spaninsight Gateway (Text+Vision+Audio) is secure and active.",
        active_routes: {
            suggest: ROUTES.suggest.map(m => m.id),
            code: ROUTES.code.map(m => m.id),
            interpret: ROUTES.interpret.map(m => m.id),
            vision: ROUTES.vision.map(m => m.id),
            audio: ROUTES.audio.map(m => m.id)
        }
      }, 200, origin, isValidApp);
    }

    // Main inference endpoint
    if (url.pathname === "/chat" && request.method === "POST") {
      return handleChat(request, env, origin, isValidApp);
    }

    return json({ error: "Not found" }, 404, origin, isValidApp);
  },
};

async function handleChat(request, env, origin, isValidApp) {
  let body;
  let isFormData = request.headers.get("content-type")?.includes("multipart/form-data");

  // PREVENT OOM (Out Of Memory) ERRORS ON WHISPER UPLOADS
  const contentLength = request.headers.get("content-length");
  if (isFormData && contentLength && parseInt(contentLength) > 25 * 1024 * 1024) {
    return json({ error: "Audio file too large. Please keep voice commands under 25MB." }, 413, origin, isValidApp);
  }

  try {
    body = isFormData ? await request.formData() : await request.json();
  } catch {
    return json({ error: "Invalid payload format" }, 400, origin, isValidApp);
  }

  // Extract task_type
  let taskType = isFormData ? (body.get("task_type") || "audio") : (body.task_type || "suggest");
  let isStreaming = isFormData ? false : (body.stream || false);

  if (isFormData) body.delete("task_type");
  else delete body.task_type;

  if (taskType === "audio" && !isFormData) {
    return json({ error: "Audio processing requires multipart/form-data with a file payload." }, 400, origin, isValidApp);
  }

  const modelsToTry = ROUTES[taskType];
  if (!modelsToTry) return json({ error: `Invalid task_type: ${taskType}` }, 400, origin, isValidApp);

  let lastError = null;

  // ---------------------------------------------------------------------------
  // THE DOUBLE FALLBACK LOOP
  // ---------------------------------------------------------------------------
  for (const modelConfig of modelsToTry) {
    try {
      let apiKey = modelConfig.provider === "groq" ? getRandomKey(env.GROQ_API_KEYS) : getRandomKey(env.NVIDIA_API_KEYS);
      
      if (!apiKey) {
        lastError = `[${modelConfig.provider}] Missing API Keys in CF environment.`;
        continue; 
      }

      let endpoint = ENDPOINTS[`${modelConfig.provider}_chat`];
      let fetchOptions = { method: "POST", headers: { "Authorization": `Bearer ${apiKey}` } };

      // AUDIO HANDLING
      if (modelConfig.id.includes("whisper")) {
        endpoint = ENDPOINTS.groq_audio;
        const formDataPayload = new FormData();
        
        for (const [key, value] of body.entries()) formDataPayload.append(key, value);
        formDataPayload.set("model", modelConfig.id);
        
        fetchOptions.body = formDataPayload;
      } 
      // TEXT / VISION CHAT HANDLING
      else {
        fetchOptions.headers["Content-Type"] = "application/json";
        const safePayload = {
          ...body, 
          stream: isStreaming,
          model: modelConfig.id,
          ...(modelConfig.extraParams || {}) 
        };
        fetchOptions.body = JSON.stringify(safePayload);
      }

      const timeoutMs = (taskType === "code" || taskType === "vision") ? 28000 : 15000;
      const resp = await fetchWithTimeout(endpoint, fetchOptions, timeoutMs);

      if (resp.ok) {
        if (isStreaming && !isFormData) {
          const { readable, writable } = new TransformStream();
          const writer = writable.getWriter();
          const reader = resp.body.getReader();

          (async () => {
            try {
              while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                await writer.write(value);
              }
              await writer.close();
            } catch (err) {
              console.error(`[${modelConfig.provider}] Stream crashed:`, err);
              const enc = new TextEncoder();
              await writer.write(enc.encode('\ndata: {"error": "Stream interrupted mid-flight"}\n\n'));
              await writer.close();
            }
          })();

          const headers = new Headers(resp.headers);
          const cHeaders = corsHeaders(origin, isValidApp);
          for (const [key, value] of Object.entries(cHeaders)) headers.set(key, value);
          
          return new Response(readable, { status: 200, headers });
        }

        const data = await resp.json();
        data._spaninsight_model_used = modelConfig.id; 
        return json(data, 200, origin, isValidApp);
      }

      // HANDLE FAILURES (INCLUDING 429 RATE LIMITS)
      const status = resp.status;
      const errText = await resp.text().catch(() => "");
      
      let errorLog = `[${modelConfig.provider}] ${modelConfig.id} HTTP ${status} — ${errText.slice(0, 150)}`;
      
      // Check for Rate Limit Headers
      if (status === 429) {
          const retryAfter = resp.headers.get("retry-after");
          errorLog += ` (Rate Limited! Retry After: ${retryAfter || 'unknown'}s)`;
      }
      
      lastError = errorLog;
      console.warn(`Fallback triggered: ${lastError}`); 
      
      // Loop continues to next model...
      
    } catch (err) {
      lastError = `[${modelConfig.provider}] ${modelConfig.id}: Timeout/Network Error`;
      console.error(lastError);
      // Loop continues to next model...
      continue;
    }
  }

  // IF ALL MODELS FAIL
  return json({ error: `All fallback models for '${taskType}' exhausted.`, last_error: lastError }, 503, origin, isValidApp);
}

function corsHeaders(origin, isValidApp = false) {
  const allowOrigin = isValidApp ? (origin || "*") : (ALLOWED_ORIGINS.includes(origin) ? origin : "null");
  
  return {
    "Access-Control-Allow-Origin": allowOrigin,
    "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, X-App-Secret, User-Agent",
    "Access-Control-Max-Age": "86400",
  };
}

function json(data, status = 200, origin = null, isValidApp = false) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      "Content-Type": "application/json",
      ...corsHeaders(origin, isValidApp),
    },
  });
}