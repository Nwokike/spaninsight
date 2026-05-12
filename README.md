<p align="center">
  <img src="src/assets/logo.png" alt="Spaninsight" width="320" />
</p>

<p align="center">
  A high-performance, privacy-first data intelligence platform for smart data collection, analysis and reporting; built with 
  Python and Flet.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Windows-0078D6?style=flat-square&logo=windows11&logoColor=white" alt="Windows" />
  <img src="https://img.shields.io/badge/Android-3DDC84?style=flat-square&logo=android&logoColor=white" alt="Android" />
  <img src="https://img.shields.io/badge/Linux-FCC624?style=flat-square&logo=linux&logoColor=black" alt="Linux" />
  <img src="https://img.shields.io/badge/Web-4285F4?style=flat-square&logo=google-chrome&logoColor=white" alt="Web" />
  <br>
  <img src="https://img.shields.io/badge/Built%20with-Flet%200.85-00B0FF?style=flat-square" alt="Built with Flet" />
</p>

---

## Download

| Platform | Download | Notes |
|:--------:|:--------:|:------|
| 🤖 **Android (Universal)** | [**spaninsight.apk**](https://github.com/Nwokike/spaninsight/releases/latest/download/spaninsight.apk) | All-in-one APK for mobile and tablets |
| 🪟 **Windows** | [**SpanInsight_Setup.exe**](https://github.com/Nwokike/spaninsight/releases/latest/download/SpanInsight_Setup.exe) | Windows 10/11 64-bit Installer |
| 🐧 **Linux** | [**spaninsight.zip**](https://github.com/Nwokike/spaninsight/releases/latest/download/spaninsight.zip) | Binary for x86_64 Linux distributions |

---

## Core Capabilities

| Capability | Description |
|:---|:---|
| **Automated Analysis** | Intelligent data ingestion (CSV/Excel) with AI-suggested insights and local code execution. |
| **Smart Surveys** | Natural language survey generation (Text/Voice) with real-time preview. |
| **Autopilot Engine** | Multi-pass analysis orchestration for comprehensive automated report generation. |
| **Enterprise Export** | Professional rendering of reports to PDF and PowerPoint formats with cloud sharing. |
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
    <td><img src="screenshots/export_options.png" width="100%" alt="Enterprise Export" /></td>
  </tr>
  <tr>
    <td align="center"><em>Generate surveys from voice or text prompts</em></td>
    <td align="center"><em>Export to PDF, PPTX, or Share via Secure Link</em></td>
  </tr>
</table>

---

## Features

- **Privacy-First AI** — Analysis is performed locally or via secure, encrypted channels with zero data retention.
- **Voice-to-Insight** — Use natural language voice commands to query your data or build complex survey forms.
- **Local Sandbox** — Built-in Python runtime (`pandas`, `matplotlib`) runs in a restricted environment for secure data processing.
- **Credit-Based Orchestration** — Advanced AI tasks utilize a transparent credit system with generous daily free allowances.
- **Cross-Platform Sync** — Seamlessly transition between Android, Windows, and Linux while maintaining project state.

---

## Architecture

| Layer | Technology | Purpose |
|:---|:---|:---|
| **Frontend** | Flet (Python/Flutter) | Reactive UI with 120Hz smooth animations |
| **Compute** | Local Python Runtime | Pandas-based data processing & Matplotlib rendering |
| **AI Engine** | SpanInsight Cloud | High-speed orchestration and NLP understanding |
| **Storage** | Secure Storage API | AES-256 encrypted local credential & config storage |
| **PDF/PPTX** | fpdf2 & python-pptx | Enterprise-grade report generation |

### Visual Flow

```text
┌──────────────────────────────────────────────────────┐
│                    SPANINSIGHT APP                    │
│  ┌────────┐ ┌──────────┐ ┌───────┐ ┌──────────────┐ │
│  │  Home  │ │ Analysis │ │ Forms │ │   Settings   │ │
│  └────────┘ └──────────┘ └───────┘ └──────────────┘ │
│       │           │           │                      │
│  ┌────┴───────────┴───────────┴──────────────────┐   │
│  │        Local Python Runtime (pandas, plt)      │   │
│  └────────────────────┬──────────────────────────┘   │
└───────────────────────┼──────────────────────────────┘
                        │ HTTPS (api.spaninsight.com)
                        ▼
┌──────────────────────────────────────────────────────┐
│                  SPANINSIGHT CLOUD                   │
│  ┌────────────┐  ┌──────┐  ┌────┐  ┌────────────┐   │
│  │ AI Engine  │  │Data  │  │Vault │  │ Orchestration│   │
│  │            │  │Sync  │  │Storage│  │   Service    │   │
│  └────────────┘  └──────┘  └────┘  └────────────┘   │
└──────────────────────────────────────────────────────┘
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

SpanInsight is designed with a **Privacy-First** philosophy.
1. **Local Execution**: Heavy data processing (filtering, grouping, math) happens on your device.
2. **Encryption**: All communication with the AI Engine is encrypted via TLS 1.3.
3. **Data Residency**: We do not store your uploaded CSV/Excel files on our servers. Insights are generated on the fly.

---

## Legal Disclaimer

SpanInsight is a data analysis tool. While it uses advanced AI to suggest insights, users are responsible for verifying the accuracy of automated reports before making business decisions. SpanInsight does not take responsibility for data loss resulting from local sandbox execution errors.
