<p align="center">
  <img src="src/assets/logo.png" alt="Spaninsight" width="320" />
</p>

<h1 align="center">Spaninsight</h1>

<p align="center">
  <b>High-Performance Privacy-First Data Intelligence Platform</b>
</p>

<p align="center">
  Professional data analysis, AI-powered survey generation, and automated reporting.
  <br />
  Your data stays on your device — local execution, global intelligence.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Proprietary-Software-red?style=flat-square" alt="License" />
  <img src="https://img.shields.io/badge/Windows-0078D6?style=flat-square&logo=windows11&logoColor=white" alt="Windows" />
  <img src="https://img.shields.io/badge/Android-3DDC84?style=flat-square&logo=android&logoColor=white" alt="Android" />
  <img src="https://img.shields.io/badge/Python-3.13-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.13" />
</p>

---

## Core Capabilities

| Capability | Description |
|:---|:---|
| **Automated Analysis** | Intelligent data ingestion (CSV/Excel) with AI-suggested insights and local code execution. |
| **Smart Surveys** | Natural language survey generation (Text/Voice) with automated D1 schema deployment. |
| **Autopilot Engine** | Multi-pass analysis orchestration for comprehensive automated report generation. |
| **Enterprise Export** | Professional rendering of reports to PDF and PowerPoint formats with R2 cloud sharing. |
| **Local Security** | Sandbox-restricted Python execution environment ensuring 100% data residency. |

---

## Architecture

```mermaid
graph TD
    subgraph Client ["Flet Client (Android/Desktop/Web)"]
        UI["UI Layer (Home, Analysis, Forms, Settings)"]
        Engine["Local Python Engine (Pandas, Matplotlib)"]
        Sandbox["Restricted Execution Sandbox"]
    end

    subgraph Cloud ["Spaninsight Cloud (api.spaninsight.com)"]
        Worker["Cloudflare Worker Gateway"]
        D1[("Cloudflare D1 (SQL)")]
        R2[("Cloudflare R2 (Storage)")]
    end

    subgraph AI ["AI Inference Layer"]
        Groq["Groq API (Llama 3.3, Whisper)"]
        NVIDIA["NVIDIA NIM (Nemotron, Mistral)"]
    end

    UI <--> Engine
    Engine --> Sandbox
    UI <--> Worker
    Worker <--> D1
    Worker <--> R2
    Worker <--> AI
```

---

## Project Structure

```text
spaninsight/
├── gateway/
│   ├── index.js          # Cloudflare Worker (AI + D1 + R2)
│   └── schema.sql        # D1 database schema
├── src/
│   ├── main.py            # App entry point
│   ├── core/              # Global state, constants, and themes
│   ├── components/        # Reusable UI widgets
│   ├── services/          # Business logic (AI, Audio, Sandbox, DB)
│   └── views/             # Functional application screens
└── requirements.txt       # Production dependencies
```

---

## Getting Started

### Prerequisites
- Python 3.13+
- [uv](https://github.com/astral-sh/uv) (recommended)

### Installation
```bash
git clone https://github.com/Nwokike/spaninsight.git
cd spaninsight
uv venv
uv pip install -r requirements.txt
```

### Execution
```bash
flet run
```

---

## Infrastructure Configuration

The application requires the following Cloudflare Worker bindings for production functionality:

| Binding | Type | Required For |
|:---|:---|:---|
| `GROQ_API_KEYS` | Secret | Primary Inference (Llama/Whisper) |
| `NVIDIA_API_KEYS` | Secret | Fallback Reasoning & Vision |
| `DB` | D1 Database | Survey Management & Response Storage |
| `REPORTS` | R2 Bucket | Public Report Sharing & Persistence |

---

## Intelligence Fallback System

The Spaninsight Gateway implements a robust multi-model fallback strategy to ensure high availability:

1. **Tier 1 (Groq)**: Ultra-low latency inference for code generation and transcription.
2. **Tier 2 (NVIDIA NIM)**: High-fidelity reasoning for complex data interpretation and vision tasks.
3. **Tier 3 (Circuit Breaker)**: Graceful degradation and user-side notification on network/API failure.

---

## Compliance & Security

- **Data Residency**: No raw data files are transmitted to the cloud. Only metadata headers are used for AI context.
- **Execution Sandbox**: Strict AST-based filtering prevents unauthorized system calls within the local environment.
- **Authentication**: Stateless HMAC-based secret validation for all gateway communication.

---

## License

This project is proprietary software. All rights reserved.

---

<p align="center">
  <em>Developed by Spaninsight Engineering</em>
</p>
