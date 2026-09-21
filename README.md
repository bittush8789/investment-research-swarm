# Investment Research Swarm 🐝📈

[![Python 3.12+](https://img.shields.io/badge/Python-3.12%2B%20%7C%203.13-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688.svg?logo=fastapi)](https://fastapi.tiangolo.com)
[![LangGraph](https://img.shields.io/badge/Orchestration-LangGraph-FF4F00.svg)](https://www.langchain.com/langgraph)
[![Groq Model](https://img.shields.io/badge/Model-openai%2Fgpt--oss--120b-f55036.svg)](https://console.groq.com)
[![Tests](https://img.shields.io/badge/Tests-18%2F18%20Passed-brightgreen.svg)](#7-testing--quality-assurance)
[![Database](https://img.shields.io/badge/DB-MySQL%20%7C%20SQLite%20Fallback-4479A1.svg?logo=mysql)](app/db/mysql.py)

> **An institutional-grade, multi-agent financial research and decision-support platform with a ChatGPT-style UI, persistent conversational memory, and direct auditable source URLs.**

The system enables investment analysts and developers to conduct automated research on publicly traded companies by uniting:
- 🏛️ **Official Regulatory Filings**: SEC EDGAR API (10-K, 10-Q, XBRL disclosures).
- 📊 **Market Telemetry**: `yfinance` real-time pricing, momentum, and interactive Chart.js visualizations.
- 🌐 **Web Intelligence**: Tavily search for corporate events, news, and earnings with injection sanitization.
- 🧮 **Deterministic Quant Arithmetic**: Pure Python (Pandas/NumPy) ratio calculation — zero LLM hallucination.
- 🧠 **Multi-Turn Chat Memory**: Thread continuity via relational persistence (`chat_messages`).
- 🔗 **Direct Auditable URLs**: Every citation in Sections 9 & 10 links directly to SEC filings, Yahoo Finance, and news sources.
- 🛡️ **Dual-Stage AI Guardrails**: Rigorous input screening and financial advice compliance boundaries.

📖 **Looking for system architecture diagrams?** See the exhaustive [System Design Document](system-design.md).

---

## Table of Contents

- [1. System Architecture](#1-system-architecture)
- [2. Project Directory Structure](#2-project-directory-structure)
- [3. Quickstart (60 Seconds)](#3-quickstart-60-seconds)
- [4. Environment Configuration](#4-environment-configuration)
- [5. Agent Swarm Breakdown](#5-agent-swarm-breakdown)
- [6. API Reference & `curl` Examples](#6-api-reference--curl-examples)
- [7. Testing & Quality Assurance](#7-testing--quality-assurance)
- [8. Developer Guide: Extending the Swarm](#8-developer-guide-extending-the-swarm)
- [9. Docker & Container Deployment](#9-docker--container-deployment)
- [10. Troubleshooting & FAQs](#10-troubleshooting--faqs)
- [11. License & Disclaimer](#11-license--disclaimer)

---

## 1. System Architecture

```
                                  ┌─────────────────────────────┐
                                  │   ChatGPT-Style Client UI   │
                                  │  (Vanilla HTML5 / CSS3 / JS)│
                                  └──────────────┬──────────────┘
                                                 │
                                                 │ HTTP REST / Server-Sent Events (SSE)
                                                 ▼
                                  ┌─────────────────────────────┐
                                  │      FastAPI Gateway        │
                                  │   (Async SSE Event Queue)   │
                                  └──────────────┬──────────────┘
                                                 │
                                                 ▼
                                  ┌─────────────────────────────┐
                                  │   Input Security Guardrail  │
                                  │ (Prompt Injection / PII /   │
                                  │   Domain Relevance Check)   │
                                  └──────────────┬──────────────┘
                                                 │
                                                 ▼
                                  ┌─────────────────────────────┐
                                  │  LangGraph Orchestrator     │
                                  │  (7-Step Execution Plan)    │
                                  └──────────────┬──────────────┘
                                                 │
                ┌────────────────────────────────┼────────────────────────────────┐
                ▼                                ▼                                ▼
   ┌─────────────────────────┐      ┌─────────────────────────┐      ┌─────────────────────────┐
   │        SEC Agent        │      │       Market Agent      │      │      Research Agent     │
   │      (SEC EDGAR)        │      │        (yfinance)       │      │         (Tavily)        │
   └────────────┬────────────┘      └────────────┬────────────┘      └────────────┬────────────┘
                │                                │                                │
                └────────────────────────────────┼────────────────────────────────┘
                                                 ▼
                                  ┌─────────────────────────────┐
                                  │         Quant Agent         │
                                  │ (Deterministic Pandas/NumPy)│
                                  └──────────────┬──────────────┘
                                                 │
                                                 ▼
                                  ┌─────────────────────────────┐
                                  │          Risk Agent         │
                                  │ (8 Risk Vector Dimensions)  │
                                  └──────────────┬──────────────┘
                                                 │
                                                 ▼
                                  ┌─────────────────────────────┐
                     ┌───────────►│        Critic Agent         │
                     │            │  (Audits Claims & Citations)│
                     │            └──────────────┬──────────────┘
                     │                           │
          Retry loop │                           ▼
      (Missing data) │                 PASS [or Max Retries]
                     └───────────────────────────┤
                                                 ▼
                                  ┌─────────────────────────────┐
                                  │        Report Agent         │
                                  │  (10 Sections + Direct URLs)│
                                  └──────────────┬──────────────┘
                                                 │
                                                 ▼
                                  ┌─────────────────────────────┐
                                  │   Output Security Guardrail │
                                  │ (Advice Boundaries / Scrubber)
                                  └──────────────┬──────────────┘
                                                 │
                                                 ▼
                                  ┌─────────────────────────────┐
                                  │  MySQL / SQLite Persistence │
                                  │ (Dossiers, Metrics, Memory) │
                                  └─────────────────────────────┘
```

---

## 2. Project Directory Structure

```text
├── app/
│   ├── agents/                   # Autonomous Swarm Agents
│   │   ├── orchestrator.py       # Plan formulation & entity resolution
│   │   ├── sec.py                # SEC EDGAR 10-K extraction
│   │   ├── market.py             # yfinance price metrics & historical closes
│   │   ├── research.py           # Tavily web intelligence with sanitization
│   │   ├── quant.py              # Pure Python mathematical calculation engine
│   │   ├── risk.py               # 8-dimensional risk synthesis
│   │   ├── critic.py             # Fact verification & audit loop
│   │   └── report.py             # 10-section report & direct URL synthesis
│   ├── config.py                 # Pydantic Settings & model config
│   ├── db/
│   │   └── mysql.py              # SQLAlchemy models, SQLite fallback, chat memory
│   ├── graph/
│   │   └── workflow.py           # LangGraph StateGraph orchestration definition
│   ├── guardrails/
│   │   ├── input.py              # Injection, jailbreak & PII filtering
│   │   └── output.py             # Advice neutralization & credential scrubbing
│   ├── mcp/                      # Model Context Protocol layer
│   │   ├── client.py             # Unified MCP gateway with telemetry
│   │   ├── finance.py            # Financial MCP server
│   │   ├── sec.py                # Regulatory filing MCP server
│   │   └── research.py           # Web research MCP server
│   ├── services/
│   │   └── research.py           # ResearchService (SSE queues & multi-turn memory)
│   └── main.py                   # FastAPI application & static mount
├── frontend/                     # ChatGPT-Style Client
│   ├── index.html                # App shell, responsive sidebar & chat viewport
│   ├── style.css                 # Dark/Light theme, glassmorphism & typography
│   └── app.js                    # SSE event listener, Chart.js & chat controller
├── infra/                        # Deployment Configurations
│   ├── Dockerfile                # Multi-stage production container build
│   └── docker-compose.yml        # MySQL + FastAPI stack orchestration
├── tests/                        # Test Suite
│   ├── test_agents.py            # Unit tests for agents & quant math
│   ├── test_guardrails.py        # Adversarial guardrail test cases
│   ├── test_workflow.py          # LangGraph state machine workflow tests
│   └── test_live_memory_swarm.py # Live end-to-end multi-turn verification
├── requirements.txt              # Core project dependencies
├── system-design.md              # In-depth architectural design specification
└── README.md                     # Developer documentation (this file)
```

---

## 3. Quickstart (60 Seconds)

### Prerequisites
- **Python 3.12+** or **3.13** installed.
- Free API keys from:
  - [Groq Cloud](https://console.groq.com) (for `openai/gpt-oss-120b` or `llama-3.3-70b-versatile`)
  - [Tavily AI](https://tavily.com) (for verified web search)

---

### Step 1: Clone & Setup Environment

#### On Windows (PowerShell):
```powershell
git clone <repo_url>
cd "Investment Research Swarm"

python -m venv venv
.\venv\Scripts\Activate.ps1

pip install -r requirements.txt
```

#### On Linux / macOS (Bash):
```bash
git clone <repo_url>
cd "Investment Research Swarm"

python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt
```

---

### Step 2: Configure Environment Variables

Copy the template configuration file:
```bash
cp .env.example .env
```

Open `.env` in your editor and add your API keys:
```ini
GROQ_API_KEY=gsk_your_groq_api_key_here
GROQ_MODEL=openai/gpt-oss-120b

TAVILY_API_KEY=tvly-your_tavily_api_key_here

# SEC EDGAR requires a custom User-Agent in the format: "SampleApp user@domain.com"
SEC_USER_AGENT=InvestmentResearchSwarm analyst@swarmresearch.io
```

> [!TIP]
> **Zero-Config Database**: If you don't have MySQL running locally, leave `MYSQL_URL` as is or empty. The application **automatically falls back to a local SQLite database** (`investment_swarm.db`), enabling instant local testing without configuring MySQL.

---

### Step 3: Run the Application

Start the FastAPI server with hot reload:
```bash
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open your browser at:
👉 **[http://127.0.0.1:8000](http://127.0.0.1:8000)**

---

## 4. Environment Configuration

| Variable | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `GROQ_API_KEY` | `string` | *(Required)* | Groq Cloud API Key for ultra-fast LLM reasoning. |
| `GROQ_MODEL` | `string` | `openai/gpt-oss-120b` | Target reasoning model. Alternatives: `llama-3.3-70b-versatile`, `deepseek-r1-distill-llama-70b`. |
| `TAVILY_API_KEY` | `string` | *(Required)* | Tavily Search API Key for real-time web intelligence. |
| `SEC_USER_AGENT` | `string` | `InvestmentResearchSwarm analyst@example.com` | Declared User-Agent sent in all SEC EDGAR API requests. |
| `MYSQL_URL` | `string` | `mysql+pymysql://root:password@localhost:3306/investment_swarm` | MySQL connection string. Defaults to SQLite if unreachable. |
| `LANGSMITH_TRACING` | `bool` | `false` | Enable LangSmith tracing for LangGraph workflow execution. |
| `LANGSMITH_API_KEY` | `string` | `""` | Optional LangSmith API key for telemetry. |
| `APP_ENV` | `string` | `development` | Environment mode (`development`, `staging`, `production`). |
| `PORT` | `int` | `8000` | HTTP port for the FastAPI server. |

---

## 5. Agent Swarm Breakdown

Each agent in the swarm is designed with a single responsibility, producing auditable artifacts in the shared graph state:

```mermaid
graph TD
    A[User Request] --> B[Input Guardrails]
    B --> C[Orchestrator Agent]
    C --> D[SEC Agent]
    C --> E[Market Agent]
    C --> F[Research Agent]
    D & E & F --> G[Quant Agent]
    G --> H[Risk Agent]
    H --> I[Critic Agent]
    I -->|PASS| J[Report Agent]
    I -->|RETRY| F
    J --> K[Output Guardrails]
    K --> L[Storage & SSE Stream]
```

1. **Input Guardrail** (`app/guardrails/input.py`): Rejects prompt injections, jailbreaks, and scrubs PAN/Aadhaar/SSN PII.
2. **Orchestrator** (`app/agents/orchestrator.py`): Resolves company ticker, fiscal period, and formulates a 7-step roadmap.
3. **SEC Agent** (`app/agents/sec.py`): Fetches 10-K/10-Q XBRL filings and GAAP balance sheet/income data from SEC EDGAR.
4. **Market Agent** (`app/agents/market.py`): Collects price telemetry, 52-week bounds, moving averages, volatility, and max drawdown.
5. **Research Agent** (`app/agents/research.py`): Gathers verified news articles via Tavily; sanitizes external HTML to neutralize indirect prompt injections.
6. **Quant Agent** (`app/agents/quant.py`): Computes margins (Gross, Operating, Net, FCF), ROE, ROA, and Debt/Equity deterministically in Python using Pandas & NumPy. **Zero LLM calculation hallucinations.**
7. **Risk Agent** (`app/agents/risk.py`): Dissects 8 distinct risk vectors (Regulatory, Business, Competition, Market, Financial, Supply Chain, Revenue Concentration, Macroeconomic).
8. **Critic Agent** (`app/agents/critic.py`): Cross-checks citations, numerical accuracy, and sources. Triggers a bounded retry loop if evidence is incomplete.
9. **Report Agent** (`app/agents/report.py`): Compiles the mandatory 10-section dossier and guarantees direct clickable URLs for all sources.
10. **Output Guardrail** (`app/guardrails/output.py`): Rephrases any personalized advice ("buy/sell") into objective research and appends the regulatory disclaimer.

---

## 6. API Reference & `curl` Examples

### 1. Health Check
```bash
curl -X GET http://127.0.0.1:8000/health
```
**Response:**
```json
{
  "status": "healthy",
  "database": "connected",
  "groq_configured": true,
  "groq_model": "openai/gpt-oss-120b",
  "tavily_configured": true,
  "environment": "development"
}
```

---

### 2. Start Research Swarm
```bash
curl -X POST http://127.0.0.1:8000/api/research \
  -H "Content-Type: application/json" \
  -d '{"query": "Analyze MSFT for the last 12 months"}'
```
**Response:**
```json
{
  "session_id": "32063107-a6d4-4f6a-afd5-a83b412d07c3",
  "status": "INITIATED",
  "ticker": "MSFT",
  "company_name": "Microsoft Corporation"
}
```

---

### 3. Stream Real-Time Execution (SSE)
```bash
curl -N http://127.0.0.1:8000/api/research/stream/32063107-a6d4-4f6a-afd5-a83b412d07c3
```
*Emits live agent progression checklist events and the final report markdown.*

---

### 4. Ask Context-Aware Follow-Up (Conversational Memory)
```bash
curl -X POST http://127.0.0.1:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "32063107-a6d4-4f6a-afd5-a83b412d07c3",
    "message": "What is the Gross Margin and where can I view the SEC filing?"
  }'
```
**Response:**
```json
{
  "answer": "Microsoft reports a **Gross Margin of 67.94%**.\n\nYou can review the complete filing directly on SEC EDGAR: [SEC 10-K Filing](https://www.sec.gov/Archives/edgar/data/789019/...)",
  "allowed": true,
  "session_id": "32063107-a6d4-4f6a-afd5-a83b412d07c3",
  "memory_turns": 4
}
```

---

### 5. Fetch Full Dossier with Conversation History
```bash
curl -X GET http://127.0.0.1:8000/api/research/32063107-a6d4-4f6a-afd5-a83b412d07c3
```
*Returns the complete research report, quantitative metrics, market telemetry, audited sources, and all `chat_messages` turns.*

---

## 7. Testing & Quality Assurance

The codebase features comprehensive unit, guardrail, workflow, and live integration tests:

### Running Unit & Guardrail Tests
```bash
python -m pytest tests/test_agents.py tests/test_guardrails.py tests/test_workflow.py -v
```

### Running Live End-to-End Swarm & Memory Tests
Validates real-time SSE streaming, Groq `openai/gpt-oss-120b` synthesis, multi-turn conversational memory, and direct clickable source URLs:
```bash
python tests/test_live_memory_swarm.py
```

**Expected output:**
```text
>>> [Step 1] Checking /health...
    Health status: healthy, Model: openai/gpt-oss-120b
>>> [Step 2] Initiating new research swarm for MSFT...
>>> [Step 3] Streaming research swarm SSE events...
    [Agent] Orchestrator Agent: Completed
    [Agent] SEC Agent: Completed
    [Agent] Market Agent: Completed
    [Agent] Research Agent: Completed
    [Agent] Quant Agent: Completed
    [Agent] Risk Agent: Completed
    [Agent] Critic Agent: Completed
    [Agent] Report Agent: Completed
>>> [Step 4] Conversational memory seeding verified in DB!
>>> [Step 5] Validating direct clickable URLs in Report Section 10 & 9... PASSED
>>> [Step 6] Follow-up Question 1 with memory... PASSED
>>> [Step 7] Follow-up Question 2 requesting direct links... PASSED
>>> [Step 8] Verifying 6 chat memory turns in DB... PASSED
>>> ALL MULTI-TURN MEMORY AND DIRECT URL VERIFICATIONS PASSED 100%!
```

---

## 8. Developer Guide: Extending the Swarm

### Adding a New Agent Node

To add a new specialized agent (e.g. `ESG_Agent` or `Competitor_Agent`):

1. **Create the Agent**:
   Create `app/agents/esg.py`:
   ```python
   from typing import Dict, Any

   class ESGAgent:
       @classmethod
       def execute(cls, state: Dict[str, Any]) -> Dict[str, Any]:
           ticker = state.get("ticker")
           # Retrieve ESG ratings or metrics
           esg_data = {"esg_score": 82, "status": "Strong"}
           return {"esg_data": esg_data}
   ```

2. **Add Node to Graph Workflow**:
   In `app/graph/workflow.py`:
   ```python
   from app.agents.esg import ESGAgent

   # Define node function
   def esg_node(state: ResearchState) -> Dict[str, Any]:
       return ESGAgent.execute(state)

   # Register node in graph
   workflow.add_node("esg_agent", esg_node)

   # Wire parallel or sequential edge
   workflow.add_edge("orchestrator", "esg_agent")
   workflow.add_edge("esg_agent", "quant_agent")
   ```

3. **Update State Definition**:
   Add `esg_data: Dict[str, Any]` to `ResearchState` in `app/graph/workflow.py`.

---

### Adding a New MCP Tool

To expose a new data source via the Model Context Protocol:

1. Add the tool implementation inside `app/mcp/finance.py` or create a new server file `app/mcp/custom.py`.
2. Register the tool wrapper in `app/mcp/client.py`.
3. Invoke it seamlessly from any agent with built-in latency tracking and error fallback.

---

## 9. Docker & Container Deployment

To launch the complete production stack (FastAPI server + MySQL 8.0) via Docker Compose:

```bash
cd infra
docker compose up -d --build
```

Verify service health:
```bash
docker compose ps
curl http://localhost:8000/health
```

To stop containers:
```bash
docker compose down
```

---

## 10. Troubleshooting & FAQs

### 1. `pymysql.err.OperationalError: Access denied for user 'root'@'localhost'`
* **Solution**: You don't need to install or run MySQL locally! The application detects connection failures and **automatically falls back to SQLite** (`investment_swarm.db`) seamlessly. To use MySQL, configure valid credentials in `MYSQL_URL` inside `.env`.

### 2. `UnicodeEncodeError: 'charmap' codec can't encode character...` on Windows
* **Solution**: Windows PowerShell/CMD may default to `cp1252`. Set your terminal encoding to UTF-8:
  ```powershell
  $env:PYTHONIOENCODING="utf-8"
  ```

### 3. Groq API Rate Limits
* **Solution**: If you hit TPM/RPM limits during peak hours, switch to another model in `.env`:
  ```ini
  GROQ_MODEL=llama-3.3-70b-versatile
  ```

### 4. Direct URLs in Markdown
* All links generated in Section 10 and Section 9 are enriched automatically by `renderMarkdownSafely()` in `frontend/app.js` with `target="_blank"`, `rel="noopener noreferrer"`, and an external link indicator `↗`.

---

## 11. License & Disclaimer

### Academic & Research Use
This project is open-source and intended for institutional research, quantitative decision support, and academic evaluation.

### Financial Disclaimer
> **IMPORTANT REGULATORY DISCLOSURE**: This platform is an automated artificial intelligence research tool designed strictly for institutional research and decision-support. It does **NOT** provide personalized investment advice, endorsements, or buy/sell recommendations. Past financial performance and quantitative indicators do not guarantee future market returns. Always perform independent due diligence with certified financial professionals before executing transactions.
