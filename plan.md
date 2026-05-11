📊 Spaninsight: Master Project Blueprint V14

The Zero-Cost, Privacy-First Data Intelligence Platform

Document Version: 14.0
Date: May 2026
Primary Target: Android (via Flet), with Web & Desktop scalability.
Core Infrastructure: 100% Serverless / Client-Side Edge (Compute Cost: $0)

1. Executive Vision & Philosophy

Spaninsight democratizes data science for university students, academics, and small businesses. It allows users to effortlessly create forms, collect responses, and use AI to write Python code that analyzes data locally on their device.

The Core Philosophies:

100% Free to Run (Zero-Server): We utilize Edge Computing (Cloudflare) and Client-Side Processing (User's Phone). Compute costs are strictly $0.

Privacy as a Feature: User data (CSVs, Excel files) never touches our servers. Flet's embedded Python engine crunches the numbers locally. Marketed as: "100% Privacy-First Analytics."

Frictionless Onboarding (No Accounts): Users download the app and start immediately. A local secure UUID acts as their identity.

Viral Growth Engine: Forms have "Powered by Spaninsight" watermarks. App sharing grants referral credits. Publicly shared reports display Google AdSense ads to monetize viewers.

Generous Freemium: Supported by non-intrusive ads. Premium features (Pro Tier) are teased as "Coming Soon."

2. Global Architecture (The Zero-Cost Stack)

A. The Client (Flet App)

Platforms: Android (Primary, monetized via AdMob), Web, Desktop.

Engine: Flet utilizes native embedded Python on Android/Desktop.

Libraries: pandas (data manipulation), numpy, matplotlib (charting), fpdf2 (PDF export), python-pptx (PowerPoint export).

B. The Edge Infrastructure (Cloudflare)

API Gateway: Cloudflare Workers (Deployed at api.spaninsight.com. Handles AI routing, API versioning, CORS, App-Secret validation).

Database (Forms/Referrals): Cloudflare D1 (Serverless SQLite).

Hot Storage (Public Reports): Cloudflare R2 (10GB Free Storage, prevents size limit issues with Base64 charts).

Static Assets: Cloudflare Pages (Hosts the web version of the app and the public HTML forms/reports).

C. The AI Routing (Groq + NVIDIA NIM)

Gateway Protocol: Double Fallback architecture rotating API keys and models to prevent rate-limit crashes.

Suggest Route: Groq (llama-3.1-8b-instant) — Fast schema reading.

Code Route: NVIDIA NIM (nemotron-3-super, mistral-medium, etc.) — High reasoning for Pandas coding (28-second timeout buffer).

Interpret Route: Groq / NVIDIA (qwen3-32b, etc.) — Explains local results.

Audio Route: Groq (whisper-large-v3) — Transcribes voice commands (Max 25MB file size).

3. Security, Stability & Edge-Case Mitigation (The "Foolproof" Layer)

To ensure the platform survives scale, abuse, and mobile hardware limits, we enforce these strict protocols:

The "Lost UUID" Recovery System:

Risk: If a user clears App Data or uninstalls, they lose their UUID and all forms/credits.

Fix: A mandatory UI banner: "Warning: Spaninsight is privacy-first. Backup your account key in settings." The settings page provides a copyable "Backup Phrase". The launch screen features a "Restore Account" button.

Form Spam Protection (Cloudflare Turnstile):

Risk: Bots spamming public forms exhausting D1's 100k daily write limit.

Fix: Every public form hosted on Cloudflare Pages includes a hidden Turnstile CAPTCHA. The Cloudflare Worker rejects any submission without a valid token.

The exec() Sandbox Security:

Risk: AI generates malicious Python code that crashes the app or accesses device files.

Fix: Flet enforces a strict blocked terms list: ["import os", "import sys", "subprocess", "open(", "shutil"]. Code runs in a highly restricted dictionary namespace.

Data Table Pagination (Mobile UI Freeze Prevention):

Risk: If a form has 5,000 responses, rendering a Flet DataTable with 5,000 rows will freeze an Android phone instantly.

Fix: The "View Responses" UI strictly limits the display to a preview of the first 50 rows. To see the rest, the user must use the "Download CSV" feature.

Mobile File Size Limits (OOM Prevention):

Risk: Uploading a 500MB CSV will cause Pandas to crash the Android OS out of memory.

Fix: Flet FilePicker logic strictly rejects datasets larger than 15MB.

API Versioning:

Risk: Changing the Cloudflare API breaks older Android app versions.

Fix: Flet requests include User-Agent: SpaninsightApp/1.0. The Worker can return {"error": "update_required"} to trigger a forced-update UI in the app.

4. The User Journey (Step-by-Step)

Scenario A: Form Creation, Management & Data Extraction

Create: User describes a questionnaire via text or a 60s voice note.

Deploy: Groq generates a JSON schema. Flet sends schema + UUID to Cloudflare D1. D1 sets an expires_at date (7 days).

Share: App returns a shortlink (f.spaninsight.com/xyz). Respondents open the link, pass Turnstile, and submit data.

Manage (The Form Dashboard): Inside the app, users tap a specific form to view:

Live Response Count: Queries D1 for total rows.

View Responses: A preview Flet DataTable showing the latest 50 responses.

Download CSV Button: Flet pulls the full JSON from D1, converts it to a Pandas DataFrame, and uses FilePicker.save_file to save it directly to the Android Downloads folder as .csv.

Analyze Button: Instantly loads the data into the Spaninsight Analysis Engine.

Renew Button: Extends expiry date by 7 days.

Scenario B: Data Analysis (Manual & Autopilot)

Import: User clicks "Analyze" from a form OR uploads a local CSV (<15MB).

Local Describe: Pandas runs df.describe() locally. Flet converts the summary to JSON.

Suggest (AI): JSON summary sent to the suggest API. Returns 3 action buttons.

Execute (AI -> Local): User clicks a suggestion. The code API returns Pandas/Matplotlib code. Flet verifies it against the sandbox, executes it, and renders the chart.

Interpret (AI): The numerical output is sent to the interpret API to generate human insights below the chart.

Autopilot: Automatically loops steps 3-5 five times to build an instant dashboard.

Scenario C: Exporting & Ad Monetization

Local Export: Python generates PDF/PPTX natively. Flet triggers Android's native share sheet. Interstitial AdMob ad plays during generation.

Public URL Sharing: * Flet bundles the report into a JSON object (Base64 images + insights).

Sends to Cloudflare Worker -> Saves to Cloudflare R2.

App returns report.spaninsight.com/123.

Monetization: When non-users open this link, the web page displays Google AdSense banners between the charts. R2 object auto-deletes after 30 days.

5. Monetization, Referrals & Credit Economy

All tracking happens locally (backed up by the UUID in the cloud).

The Economy:

Suggest = 1 credit.

Custom Prompt / Voice Prompt = 3 credits.

Autopilot = 15 credits.

Daily Refresh: App checks local device date. Resets to 50 free credits daily.

The Viral Referral Loop: * User shares their invite code (UUID-snippet).

New user installs app, enters code. Cloudflare logs the referral.

Referring user gets a permanent +10 Daily Credits upgrade.

Revenue Streams:

AdMob Banners (bottom of Flet app).

AdMob Interstitials (on CSV Download, PDF export & Autopilot).

AdSense (on public shared report URLs).

"Pro Tier" Tease: A greyed-out settings menu for "Spaninsight Pro" (Zero Ads, Priority Processing) says "Coming Soon" to prime users.

6. Step-by-Step Execution Plan

Phase 1: The Core Infrastructure (COMPLETED)

[x] Deploy the Double Fallback AI Gateway to Cloudflare Workers (api.spaninsight.com).

[ ] Setup Cloudflare D1 Database (Tables: Forms, Responses, Referrals).

[ ] Setup Cloudflare R2 Bucket for public reports.

[ ] Create the Worker endpoints for Database/R2 CRUD operations.

Phase 2: The Flet App Foundation (START HERE)

[ ] Build basic UI (Navigation Tabs: Forms, Analysis, Settings).

[ ] Implement UUID Generation, Storage, and the "Backup/Restore" UI.

[ ] Implement Local File Uploads (CSV/Excel -> Pandas DataFrame) with 15MB strict limit.

[ ] Build the Safe Execution Sandbox (exec with blocked_terms filter).

Phase 3: Forms & Data Extraction UI

[ ] Build the Form Management Dashboard (View Count, Preview 50 Rows, Renew).

[ ] Implement the "Download CSV" logic using Flet's FilePicker.

[ ] Build the HTML/JS frontend on Cloudflare Pages to render public forms with Turnstile.

Phase 4: The AI Integration

[ ] Connect the Flet UI to the AI Gateway /chat endpoints (using Secret Headers).

[ ] Implement the Audio Recorder widget (60s UI limit -> Gateway).

[ ] Build the 3-step loop: Suggest -> Code (Generate Chart) -> Interpret.

[ ] Add the "Autopilot" loop.

Phase 5: Exporting, Sharing, & Monetization

[ ] Integrate fpdf2 and python-pptx for local exports.

[ ] Build the R2 upload logic for public URL sharing.

[ ] Inject AdSense into the Cloudflare Pages report viewer.

[ ] Inject AdMob into the Android Flet App.

[ ] Launch to Google Play Store.