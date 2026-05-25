<p align="center">
  <img src="src/assets/logo.png" alt="Spaninsight" width="320" />
</p>

<p align="center">
  A high-performance, privacy-first data intelligence platform for smart data collection, analysis and reporting
</p>

<p align="center">
  <a href="#download"><img src="https://img.shields.io/badge/Windows-0078D6?style=flat-square&logo=windows11&logoColor=white" alt="Windows" /></a>
  <a href="#android"><img src="https://img.shields.io/badge/Android-3DDC84?style=flat-square&logo=android&logoColor=white" alt="Android" /></a>
  <br>
  <img src="https://img.shields.io/badge/Built%20with-Flet%200.85-00B0FF?style=flat-square" alt="Built with Flet" />
</p>

---

## Download

| Platform | Download | Notes |
|:--------:|:--------:|:------|
| 🪟 **Windows** | [**SpanInsight_Setup.exe**](https://github.com/Nwokike/spaninsight/releases/latest/download/SpanInsight_Setup.exe) | Windows 10/11 64-bit Installer |
| 🤖 **Android** | [![Play Store](https://img.shields.io/badge/Google_Play-414141?style=flat-square&logo=google-play&logoColor=white)](https://play.google.com/store/apps/details?id=com.spaninsight.app) | Recommended for most users |

### Android (APK direct download)

| Variant | Download | Notes |
|:--------|:--------:|:-----|
| 📱 **ARM64** (most phones) | [**spaninsight-arm64-v8a.apk**](https://github.com/Nwokike/spaninsight/releases/latest/download/spaninsight-arm64-v8a.apk) | Modern 64-bit devices |
| 📱 **ARMv7** (older phones) | [**spaninsight-armeabi-v7a.apk**](https://github.com/Nwokike/spaninsight/releases/latest/download/spaninsight-armeabi-v7a.apk) | 32-bit ARM devices |
| 💻 **x86_64** (emulators) | [**spaninsight-x86_64.apk**](https://github.com/Nwokike/spaninsight/releases/latest/download/spaninsight-x86_64.apk) | Chromebooks & emulators |

---

## Core Capabilities

| Capability | Description |
|:---|:---|
| **Collaborative Workspace** | Multi-collaborator workspaces grouped under secure 6-digit PIN keys. Sync analyses, reports, and survey forms in real-time. |
| **Recipe Re-execution** | Data residency is guaranteed. Raw datasets remain local to each collaborator. Shared analysis steps are processed as recipes that re-execute inside local sandboxes. |
| **Smart Surveys** | Natural language survey generation (Text/Voice) with real-time preview — great for student research and customer feedback. |
| **Autopilot Engine** | Multi-pass analysis orchestration for comprehensive automated report generation. |
| **Professional Export** | Export reports as PDF and PowerPoint with secure cloud sharing via ephemeral links. |
| **Local Security** | Sandbox-restricted Python execution environment ensuring 100% data residency. |

---

## Features

- **Privacy-First AI** — Analysis runs locally; only AI prompts touch the secure gateway, never your raw dataset files.
- **Dynamic Workspaces** — Create, join, and switch between separate project workspaces instantly via a top-right switcher drop-down.
- **Voice-to-Insight** — Use natural language voice commands to query your data or build survey forms.
- **Editable Code Blocks** — View, edit, and re-run the Python code behind every analysis result.
- **Local Sandbox** — Built-in Python runtime (`pandas`, `matplotlib`) runs in a restricted environment.
- **Credit-Based System** — AI tasks use a transparent credit system with generous daily free allowances.
- **Native Desktop & Mobile** — High-performance, optimized deployments across Windows and Android devices.
- **Google AdMob Integration** — Safe, buffered banner and interstitial advertising support for mobile app users.
- **Resilient Mobile Sandbox** — Hardened client environment utilizing sandboxed directory access (`FLET_APP_STORAGE_DATA`/`TEMP`) for maximum permission security and zero PermissionError crashes.

---

## Architecture

| Layer | Technology | Purpose |
|:---|:---|:---|
| **Frontend** | Flet | Reactive UI with vibrant styling, dark mode, and smooth transitions |
| **Compute** | Local Python Runtime | Pandas-based data processing & Matplotlib rendering |
| **Secure Edge Gateway** | Secure Gateway (api.spaninsight.com) | Private multi-model AI orchestration with automatic failover |
| **Edge Metadata Store** | Secure Edge Database | Workspace configurations, collaborative forms, and response indices |
| **Ephemeral Cache Store** | Ephemeral Secure Storage | Fast-loading shared interactive reports (7-day lifecycle) |
| **Local Storage** | Platform Keychain | Encrypted client-side credentials & offline project states |

### Visual Flow

```mermaid
graph TB
    subgraph SPANINSIGHT_APP ["📱 SPANINSIGHT CLIENT (Local-First APP)"]
        UI["🎨 Flet Reactive UI (Home | Analysis | Forms | Reports | Settings)"]
        Runtime["⚙️ Local Python Runtime (Pandas, Matplotlib)"]
        UI --> Runtime
    end

    subgraph SECURE_EDGE_GATEWAY ["🔒 SECURE EDGE GATEWAY (api.spaninsight.com)"]
        Inference["🤖 Autonomous AI Inference Engine"]
        D1["💾 Secure Edge Database"]
        R2["📦 Ephemeral Storage Bucket"]
        Verify["🔑 Cryptographic Challenge Verification"]
    end

    Runtime ==>|HTTPS TLS 1.3| SECURE_EDGE_GATEWAY
```

---

## Credit System

| Action                  | Credits     |
| ----------------------- | ----------- |
| AI Suggestion           | 1           |
| Custom Prompt / Voice   | 3           |
| Autopilot (Full Report) | 15          |
| **Daily Allowance**     | **50 FREE** |

---

## Privacy & Security

Spaninsight is designed with a **Privacy-First** philosophy.

1. **Local Execution**: Data processing (filtering, grouping, analysis) happens entirely on your device.
2. **Encryption**: All communication with the AI gateway is encrypted via TLS 1.3.
3. **Data Residency**: We do not store your uploaded CSV/Excel/JSON files. Insights are generated on the fly.
4. **Sandbox Isolation**: AI-generated code runs in a restricted Python environment with no file system or network access.

---

## Changelog

<details open>
<summary><b>v1.0.0</b> — Initial Release</summary>

<br>

Your personal data intelligence workspace. Import data, ask questions, get answers. No code required.

### Features

#### Intelligent Data Analysis
- Import CSV, Excel, JSON, XML, STATA, SAS, TSV, TXT, ZIP, Pickle, and SQL databases
- Describe your data in natural language — AI generates instant analysis suggestions
- Autopilot mode: AI plans and executes multi-step analyses (up to 8 iterations)
- Interactive charts powered by matplotlib with lightbox zoom
- Pin any chart or result to a report with one tap
- Voice input for hands-free interaction (60s recordings, auto-transcribed)
- Editable Code: View, edit, and re-run underlying Python code for all generated charts.

#### Smart Forms (Surveys)
- Describe your form in plain English — AI generates the schema instantly
- Supports text, textarea, number, email, select, radio, checkbox, date, phone, URL, and star ratings
- Publish with a shareable link (7-day expiry, renewable)
- Automatic response collection with CAPTCHA protection
- View and manage responses inline

#### Reports & Export
- Built-in report editor with drag-and-drop blocks
- Export to PDF, Microsoft Word, or PowerPoint
- Share reports via public link (7-day expiry, renewable)

#### Privacy & Security
- All data processing runs 100% locally on your device
- Only AI prompts travel over the network to api.spaninsight.com
- AI-generated code executes in a secure sandbox with strict resource limits
- No user accounts required — local-first with optional cloud sync

#### Workspaces & Sync
- Create multiple workspaces with recovery phrases
- Real-time collaboration with delta sync
- Auto-sync changes from teammates

#### Credits
- 50 free credits daily (resets at midnight UTC)
- 1 credit per suggestion · 3 credits per custom prompt · 15 credits for Autopilot
- Banner ads on mobile with optional interstitials after heavy analysis runs

### Platforms

- Windows desktop
- Android (APK)
- iOS (coming soon)

### Availability

Download from [spaninsight.com](https://spaninsight.com) or [GitHub Releases](https://github.com/Nwokike/spaninsight/releases).

</details>

---

## Legal Disclaimer

Spaninsight is a data analysis tool. While it uses advanced AI to suggest insights, users are responsible for verifying the accuracy of automated reports before making business decisions. Spaninsight does not take responsibility for data loss resulting from local sandbox execution errors.
