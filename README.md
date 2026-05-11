# 📊 Spaninsight

**Privacy-First Data Intelligence Platform**

Import data, create AI-powered surveys, and generate professional reports — all without your data ever leaving your device.

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Android%20%7C%20Desktop%20%7C%20Web-brightgreen.svg)]()
[![Python](https://img.shields.io/badge/python-3.13-blue.svg)]()

---

## What is Spaninsight?

Spaninsight is a zero-cost, privacy-first data analysis platform built for university students, academics, and small businesses. It combines AI-powered code generation with local execution — your data stays on your device while AI handles the heavy thinking.

### Key Features

| Feature | Description |
|---------|-------------|
| 🤖 **AI Analysis** | Import CSV/Excel → AI suggests insights → generates Python code → renders charts locally |
| 📝 **Smart Surveys** | Describe a survey in plain English (or voice) → AI generates the form → share a link → collect responses |
| 🚀 **Autopilot Mode** | One tap generates a complete analysis report with charts and descriptions |
| 📄 **Export** | Download reports as PDF or PowerPoint, or share a public link |
| 🎙️ **Voice Commands** | Describe analyses or surveys via 60-second voice notes |
| 🔒 **100% Privacy** | All data processing runs locally via embedded Python — nothing leaves your phone |
| 💰 **Free** | 50 daily credits, invite friends for +10 bonus credits per referral |

---

## Architecture

```
┌──────────────────────────────────────────────────────┐
│                    FLET APP (Client)                  │
│  ┌────────┐ ┌──────────┐ ┌───────┐ ┌──────────────┐ │
│  │  Home  │ │ Analysis │ │ Forms │ │   Settings   │ │
│  └────────┘ └──────────┘ └───────┘ └──────────────┘ │
│       │           │           │                      │
│  ┌────┴───────────┴───────────┴──────────────────┐   │
│  │        Local Python Engine (pandas, plt)       │   │
│  └────────────────────┬──────────────────────────┘   │
└───────────────────────┼──────────────────────────────┘
                        │ HTTPS (AI only)
                        ▼
┌──────────────────────────────────────────────────────┐
│         CLOUDFLARE WORKER (api.spaninsight.com)       │
│  ┌────────────┐  ┌──────┐  ┌────┐  ┌────────────┐   │
│  │  AI Routes │  │  D1  │  │ R2 │  │ Referrals  │   │
│  │ Groq+NVIDIA│  │Forms │  │Rpts│  │  Tracking  │   │
│  └────────────┘  └──────┘  └────┘  └────────────┘   │
└──────────────────────────────────────────────────────┘
```

### Zero-Cost Stack

- **Client**: Flet (Python) — Android, Desktop, Web
- **AI Gateway**: Cloudflare Workers (free tier)
- **Database**: Cloudflare D1 (serverless SQLite)
- **Storage**: Cloudflare R2 (public report sharing)
- **AI Models**: Groq (primary, fast) + NVIDIA NIM (fallback, heavy reasoning)

---

## Project Structure

```
spaninsight/
├── gateway/
│   ├── index.js          # Cloudflare Worker (AI + D1 + R2)
│   └── schema.sql        # D1 database schema
├── src/
│   ├── main.py            # App entry point
│   ├── core/
│   │   ├── constants.py   # API config, limits, security
│   │   ├── state.py       # Observable app state
│   │   ├── theme.py       # Design tokens
│   │   ├── tokens.py      # Spacing, sizing, radius
│   │   └── styles.py      # Reusable UI patterns
│   ├── components/
│   │   ├── chart_card.py       # Chart display card
│   │   ├── credit_badge.py     # Credits indicator
│   │   ├── data_preview.py     # DataTable preview
│   │   ├── file_import_card.py # File upload card
│   │   ├── stat_card.py        # Stat display
│   │   └── suggestion_chips.py # AI suggestion pills
│   ├── services/
│   │   ├── ai_service.py       # Gateway client (all AI routes)
│   │   ├── audio_service.py    # Voice recording
│   │   ├── camera_service.py   # Vision capture
│   │   ├── credit_service.py   # Credit management
│   │   ├── file_service.py     # CSV/Excel loading
│   │   ├── file_picker_service.py
│   │   ├── forms_service.py    # D1 forms CRUD
│   │   ├── sandbox.py          # Safe exec() environment
│   │   ├── uuid_service.py     # Identity management
│   │   └── ad_service.py       # AdMob integration
│   └── views/
│       ├── home_view.py        # Marketing landing
│       ├── analysis_view.py    # Block-chain analysis engine
│       ├── forms_view.py       # Survey creation + dashboard
│       ├── report_view.py      # Export + sharing
│       └── settings_view.py    # Account + preferences
└── requirements.txt
```

---

## Setup

### Prerequisites

- Python 3.13+
- [uv](https://github.com/astral-sh/uv) (recommended) or pip

### Install

```bash
git clone https://github.com/Nwokike/spaninsight.git
cd spaninsight
uv venv
uv pip install -r requirements.txt
```

### Run

```bash
flet run
```

### Cloudflare Infrastructure

The gateway requires these Cloudflare bindings:

| Binding | Type | Name |
|---------|------|------|
| `GROQ_API_KEYS` | Secret | Comma-separated Groq API keys |
| `NVIDIA_API_KEYS` | Secret | Comma-separated NVIDIA NIM keys |
| `CLIENT_SECRET_KEY` | Secret | `spaninsight-mobile-v1` |
| `DB` | D1 Database | `spaninsight-db` |
| `REPORTS` | R2 Bucket | `spaninsight-reports` |

Deploy the Worker:
1. Create D1 database and run `gateway/schema.sql`
2. Create R2 bucket
3. Bind both to the Worker
4. Deploy `gateway/index.js`

---

## AI Gateway Routes

| Route | Models (Priority Order) | Purpose |
|-------|------------------------|---------|
| `suggest` | Groq llama-3.1-8b → NVIDIA gemma-4-31b | Schema reading, suggestions |
| `code` | Groq llama-3.3-70b → qwen3-32b → gpt-oss-120b → NVIDIA nemotron/mistral | Python code generation |
| `interpret` | Groq llama-3.3-70b → qwen3-32b → NVIDIA gpt-oss-120b | Result interpretation |
| `vision` | Groq llama-4-scout → NVIDIA nemotron-omni → gemma-4 | Image analysis |
| `audio` | Groq whisper-large-v3 → whisper-large-v3-turbo | Voice transcription |

All routes use a **double fallback** pattern — if one model fails or rate-limits, the next one picks up automatically.

---

## Security

- **Sandbox**: AI-generated code runs in a restricted `exec()` with blocked terms (`import os`, `subprocess`, `open(`, etc.)
- **Auth**: All API requests require `X-App-Secret` + `User-Agent: SpaninsightApp/X.X.X`
- **Privacy**: Data files never leave the device — only schema summaries are sent to AI
- **Turnstile**: Public form submissions protected by Cloudflare CAPTCHA
- **File Limits**: Max 15MB uploads, 50-row preview pagination

---

## Credits Economy

| Action | Cost |
|--------|------|
| AI Suggestion | 1 credit |
| Custom Prompt / Voice | 3 credits |
| Autopilot (full report) | 15 credits |
| **Daily Free** | **50 credits** |
| Referral Bonus | +10 daily credits per invite |

---

## License

MIT © 2026 Spaninsight
