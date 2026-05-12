<p align="center">
  <img src="src/assets/logo.png" alt="Spaninsight" width="320" />
</p>

<p align="center">
  Autonomous data intelligence platform — smart data collection, analysis and reporting for everyone.
  Built with Python and Flet.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Windows-0078D6?style=flat-square&logo=windows11&logoColor=white" alt="Windows" />
  <img src="https://img.shields.io/badge/Android-3DDC84?style=flat-square&logo=android&logoColor=white" alt="Android" />
  <img src="https://img.shields.io/badge/Web-4285F4?style=flat-square&logo=google-chrome&logoColor=white" alt="Web" />
  <br>
  <img src="https://img.shields.io/badge/Built%20with-Flet%200.85-00B0FF?style=flat-square" alt="Built with Flet" />
</p>

---

## Download

| Platform | Download | Notes |
|:--------:|:--------:|:------|
| 🌐 **Web** | [**app.spaninsight.com**](https://app.spaninsight.com) | Works in any modern browser |
| 🤖 **Android** | [**spaninsight.apk**](https://github.com/Nwokike/spaninsight/releases/latest/download/spaninsight.apk) | Universal APK for phones and tablets |
| 🪟 **Windows** | [**SpanInsight_Setup.exe**](https://github.com/Nwokike/spaninsight/releases/latest/download/SpanInsight_Setup.exe) | Windows 10/11 64-bit Installer |

---

## Core Capabilities

| Capability | Description |
|:---|:---|
| **Automated Analysis** | Intelligent data ingestion (CSV/Excel/JSON) with AI-suggested insights and local code execution. |
| **Smart Surveys** | Natural language survey generation (Text/Voice) with real-time preview — great for student research and customer feedback. |
| **Autopilot Engine** | Multi-pass analysis orchestration for comprehensive automated report generation. |
| **Professional Export** | Render reports to PDF and PowerPoint formats with cloud sharing via secure links. |
| **Local Security** | Sandbox-restricted Python execution environment ensuring 100% data residency. |

---

## Screenshots

### Data Intelligence Hub

<p align="center">
  <img src="screenshots/analysis_dashboard.png" width="90%" alt="Analysis Dashboard" />
</p>
<p align="center"><em>Real-time data visualization with AI-driven trend detection</em></p>

<table>
  <tr>
    <td><img src="screenshots/survey_builder.png" width="100%" alt="Smart Survey Builder" /></td>
    <td><img src="screenshots/export_options.png" width="100%" alt="Professional Export" /></td>
  </tr>
  <tr>
    <td align="center"><em>Generate surveys from voice or text prompts</em></td>
    <td align="center"><em>Export to PDF, PPTX, or share via secure link</em></td>
  </tr>
</table>

---

## Features

- **Privacy-First AI** — Analysis runs locally; only AI prompts touch the cloud, never your raw data.
- **Voice-to-Insight** — Use natural language voice commands to query your data or build survey forms.
- **Editable Code Blocks** — View, edit, and re-run the Python code behind every analysis result.
- **Local Sandbox** — Built-in Python runtime (`pandas`, `matplotlib`) runs in a restricted environment.
- **Credit-Based System** — AI tasks use a transparent credit system with generous daily free allowances.
- **Cross-Platform** — Works on Android, Windows, and Web with the same experience.

---

## Architecture

| Layer | Technology | Purpose |
|:---|:---|:---|
| **Frontend** | Flet (Python/Flutter) | Reactive UI with smooth animations |
| **Compute** | Local Python Runtime | Pandas-based data processing & Matplotlib rendering |
| **AI Gateway** | Cloudflare Worker | Multi-model AI orchestration (Groq + NVIDIA) with automatic failover |
| **Database** | Cloudflare D1 | Forms, responses, referrals, UUID recovery |
| **Storage** | Cloudflare R2 | Public report hosting with 30-day auto-cleanup |
| **Local Storage** | Secure Storage API | AES-256 encrypted credentials & config |
| **PDF/PPTX** | fpdf2 & python-pptx | Professional report generation |

### Visual Flow

```text
┌──────────────────────────────────────────────────────────┐
│                     SPANINSIGHT APP                       │
│  ┌──────┐ ┌──────────┐ ┌───────┐ ┌────────┐ ┌────────┐ │
│  │ Home │ │ Analysis │ │ Forms │ │ Report │ │Settings│ │
│  └──────┘ └──────────┘ └───────┘ └────────┘ └────────┘ │
│       │         │           │         │                  │
│  ┌────┴─────────┴───────────┴─────────┴──────────────┐  │
│  │         Local Python Runtime (pandas, plt)         │  │
│  └───────────────────────┬───────────────────────────┘  │
└──────────────────────────┼──────────────────────────────┘
                           │ HTTPS (api.spaninsight.com)
                           ▼
┌──────────────────────────────────────────────────────────┐
│              CLOUDFLARE EDGE (Gateway Worker)            │
│  ┌──────────────┐  ┌────────┐  ┌─────┐  ┌───────────┐  │
│  │ AI Inference  │  │ D1 SQL │  │ R2  │  │ Turnstile │  │
│  │ Groq + NVIDIA │  │  Forms │  │Rpts │  │   Verify  │  │
│  └──────────────┘  └────────┘  └─────┘  └───────────┘  │
└──────────────────────────────────────────────────────────┘
```

---

## Credit System

| Action | Credits |
|--------|---------|
| AI Suggestion | 1 |
| Custom Prompt / Voice | 3 |
| Autopilot (Full Report) | 15 |
| **Daily Allowance** | **50 FREE** |

---

## Privacy & Security

Spaninsight is designed with a **Privacy-First** philosophy.
1. **Local Execution**: Data processing (filtering, grouping, analysis) happens entirely on your device.
2. **Encryption**: All communication with the AI gateway is encrypted via TLS 1.3.
3. **Data Residency**: We do not store your uploaded CSV/Excel/JSON files. Insights are generated on the fly.
4. **Sandbox Isolation**: AI-generated code runs in a restricted Python environment with no file system or network access.

---

## Legal Disclaimer

Spaninsight is a data analysis tool. While it uses advanced AI to suggest insights, users are responsible for verifying the accuracy of automated reports before making business decisions. Spaninsight does not take responsibility for data loss resulting from local sandbox execution errors.
