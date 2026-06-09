# 📊 KPI Intelligence Reporter

A production-grade, self-healing SaaS analytics pipeline that converts raw metric data (CSVs) into mathematically verified, benchmark-grounded executive reports.

---

### 💡 The Problem
Modern businesses are flooded with raw metric spreadsheets but lack the resources to analyze them. 
* **Traditional BI suites** (Tableau, Power BI) cost upwards of $50,000/year and require dedicated analysts.
* **Basic LLM tools** (like raw ChatGPT uploads) lack mathematical rigor, frequently hallucinate numbers, and lack the industry context to tell if a metric is good or bad.

### 🛠️ The Solution
This application bridges the gap by wrapping a **deterministic analytical engine** around a **multi-agent AI pipeline**, delivering reliable, hallucination-free business intelligence at scale.

* **Hallucination-Free Math:** Runs local Least-Squares linear regression for forecasts. Projections are automatically constrained by actual statistical boundaries to prevent AI fantasy numbers.
* **Grounding & RAG:** Vector-embedded industry benchmarks (E-Commerce, SaaS, etc.) are injected dynamically based on the user's dataset to contextualize performance metrics.
* **Self-Healing Architecture:** Integrated with a `Codemender` self-healing pipeline that intercept errors, repair JSON structures in real-time, and stream status via Server-Sent Events (SSE).
* **SaaS Ready:** Features multi-user JWT authentication, multi-tier caching (L1 Memory → L2 Redis → L3 PostgreSQL), async Slack/Discord webhooks, Stripe subscription structures, and automated PDF builders.


# Multi-Agent AI Platform for KPI Intelligence

Architected and developed a production-ready, AI-driven Business Intelligence (BI) platform that automates the transformation of raw metric data (CSVs) into verified strategic insights. 

To eliminate the mathematical hallucinations common in standard LLMs and bypass the high costs of traditional BI tools, the backend was engineered with a local Least-Squares linear regression engine and a dynamic vector-based RAG pipeline. 

This setup grounds a 7-agent LLM analysis system with deterministic mathematical models and real-world industry benchmarks, guaranteeing 100% mathematically bounded projections. 

Additionally, response latency was minimized to under 15 milliseconds through a 3-tier cache waterfall (Memory ➔ Redis ➔ PostgreSQL), and system reliability was secured by building an asynchronous self-healing middleware pipeline that intercepts and auto-corrects malformed AI outputs in real-time.

### 🎥 Live Dashboard Demo
**
[https://drive.google.com/file/d/1Knx_QsChJcaW4YccVu10r0fvXtwMdlOm/view?usp=share_link)]

---

### 💻 Executive Access Portal & UI
<img width="1248" height="690" alt="Screenshot 2026-06-09 at 10 02 11 PM" src="https://github.com/user-attachments/assets/67770a3f-c4b6-422f-8c7e-ea692cafacc9" />

<img width="1248" height="690" alt="Screenshot 2026-06-09 at 10 02 46 PM" src="https://github.com/user-attachments/assets/69bb2efa-3099-423a-a22b-ba42cb7a7007" />

<img width="1248" height="696" alt="Screenshot 2026-06-09 at 10 03 44 PM" src="https://github.com/user-attachments/assets/576a1712-28ee-4697-a528-c022d5600c6e" />

<img width="1248" height="696" alt="Screenshot 2026-06-09 at 10 04 06 PM" src="https://github.com/user-attachments/assets/61b5262f-9602-41b0-bed2-2d5bc4f8fabe" />

<img width="1248" height="696" alt="Screenshot 2026-06-09 at 10 06 35 PM" src="https://github.com/user-attachments/assets/b5f7ddc2-a9c0-43bd-ad9d-3b70821cae94" />

<img width="1248" height="475" alt="Screenshot 2026-06-09 at 10 26 05 PM" src="https://github.com/user-attachments/assets/26ae979e-9dd6-4345-b8e7-a36e70729a94" />

<img width="1248" height="696" alt="Screenshot 2026-06-09 at 10 07 09 PM" src="https://github.com/user-attachments/assets/85a4451c-f810-404c-a23d-e8eb032055a4" />

# KPI INTELLIGENCE REPORTER — FULL SYSTEM ARCHITECTURE
  USER (Browser: Chrome/Safari/Edge)
    │
    │  HTTPS (TLS 1.3)
    ▼
  ┌────────────────────────────────────────────────────────────────────────┐
  │                        FRONTEND (Static Files)                         │
  │                                                                        │
  │  index.html ─── Premium Dark UI (Glassmorphism + Neon Accents)         │
  │  styles.css ─── CSS Design System                                      │
  │  script.js ──── Client Logic                                           │
  │                                                                        │
  │  Libraries (CDN):                                                      │
  │    • PapaParse 5.4.1 ── CSV parsing in-browser                         │
  │    • Chart.js ────────── Before/After bar chart rendering              │
  │    • Marked.js ───────── Markdown → HTML for board memos               │
  │                                                                        │
  │  Auth Flow:                                                            │
  │    ┌──────────────┐    ┌─────────────────────────────┐                 │
  │    │ Login Portal │───►│ Supabase Auth (HTTPS POST)  │                 │
  │    │ Email + Pass │    │ bcrypt hash → JWT token     │                 │
  │    │ Guest bypass │    │ MFA/OTP: toggle in dashboard│                 │
  │    └──────────────┘    └─────────────────────────────┘                 │
  └───────────────────────────────┬────────────────────────────────────────┘
                                  │
                                  │  POST /api/generate
                                  │  { marketingData[], productData[],
                                  │    question, webhookUrl }
                                  ▼
  ┌════════════════════════════════════════════════════════════════════════┐
  ║                 FASTAPI BACKEND (server.py)                            ║
  ║                 Python 3.9 + Uvicorn + Render.com                      ║
  ╠════════════════════════════════════════════════════════════════════════╣
  ║                                                                        ║
  ║  STEP 1: CACHE WATERFALL ─────────────────────────────────────────     ║
  ║                                                                        ║
  ║    SHA-256(data + question) = cache_key                                ║
  ║         │                                                              ║
  ║         ▼                                                              ║
  ║    L1 Memory Dict ────── HIT? → Return (0ms)                           ║
  ║         │ MISS                                                         ║
  ║         ▼                                                              ║
  ║    L2 Upstash Redis ──── HIT? → Return (<15ms) → warm L1               ║
  ║         │ MISS                                                         ║
  ║         ▼                                                              ║
  ║    L3 Supabase DB ────── HIT? → Return → warm L1 + L2                  ║
  ║         │ MISS                                                         ║
  ║         ▼                                                              ║
  ║                                                                        ║
  ║  STEP 2: DATA GROUNDING (compute_data_stats) ────────────────────      ║
  ║    • Extracts totals, averages, min, max from raw CSV                  ║
  ║    • Calculates max_numeric_reference for clamping                     ║
  ║                                                                        ║
  ║  STEP 3: FORECASTER ENGINE (forecaster.py)──────────                   ║
  ║    • run_least_squares(x, y) → slope, intercept, R²                    ║
  ║    • 30-day projected spend + revenue trajectories                     ║
  ║    • Execution time: <0.2 milliseconds (pure math, no API call)        ║
  ║                                                                        ║
  ║  STEP 4: RAG ENGINE (rag_engine.py) ─────────────────                  ║
  ║    • Pre-embedded 4 industry benchmarks via gemini-embedding-001       ║
  ║    • Cosine similarity search against user's question                  ║
  ║    • Injects relevant benchmarks (E-Commerce/SaaS/Marketing/HW)        ║
  ║                                                                        ║
  ║  STEP 5: GEMINI 2.5 FLASH (7-AGENT PIPELINE) ───────────────────       ║
  ║    ┌──────────────────────────────────────────────────────────────┐    ║
  ║    │  Prompt Context Injected:                                    │    ║
  ║    │    • Verified Data Stats                                     │    ║
  ║    │    • Mathematical Forecasts                                  │    ║
  ║    │    • Industry Benchmarks                                     │    ║
  ║    │    • Raw CSV Data                                            │    ║
  ║    │    • Projection Clamping Rules                               │    ║
  ║    │                                                              │    ║
  ║    │  7 Agent Personas (single-pass Chain-of-Thought):            │    ║
  ║    │    1. Data Analyst       → metrics + insights                │    ║
  ║    │    2. Strategist         → strategic options                 │    ║
  ║    │    3. Decision Maker     → recommended action                │    ║
  ║    │    4. Playbook Creator   → day-by-day plan                   │    ║
  ║    │    5. Devil's Advocate   → criticisms + failure modes        │    ║
  ║    │    6. Financial Projector → before/after numbers             │    ║
  ║    │    7. Board Member       → 400-700 word executive memo       │    ║
  ║    │                                                              │    ║
  ║    │  Config: temperature=0.0, top_k=1 (deterministic output)     │    ║
  ║    │  Schema: Pydantic OutputSchema (guaranteed valid JSON)       │    ║
  ║    └──────────────────────────────────────────────────────────────┘    ║
  ║                                                                        ║
  ║  STEP 6: FACT-VALIDATOR (validate_and_clamp_projections) ────────      ║
  ║    • Clamps all projections to max 2× actual data reference            ║
  ║    • Prevents AI hallucination of unrealistic numbers                  ║
  ║                                                                        ║
  ║  STEP 7: CODEMENDER (codemender.py ) ─────────────────                 ║
  ║    • @heal_async decorator wraps entire pipeline                       ║
  ║    • If JSON parse fails → auto-repairs via Gemini at temp=0           ║
  ║    • SSE stream → real-time telemetry to frontend dev console          ║
  ║                                                                        ║
  ║  STEP 8: WEBHOOK NOTIFIER (notifier.py) ──────────────                 ║
  ║    • If revenue_slope < 0 → fires Slack/Discord alert                  ║
  ║    • If "high CAC" in memo → fires cost warning                        ║
  ║    • Async HTTP POST (non-blocking)                                    ║
  ║                                                                        ║
  ║  STEP 9: PERSIST + RESPOND ──────────────────────────────────────      ║
  ║    • Save to L1 (memory) + L2 (Redis) + L3 (Supabase DB)               ║
  ║    • Return JSON → browser renders memo + charts + stats               ║
  ║                                                                        ║
  ╠════════════════════════════════════════════════════════════════════════╣
  ║  ALL ENDPOINTS:                                                        ║
  ║    GET  /                         → index.html                         ║
  ║    GET  /health                   → { status: "ok" }                   ║
  ║    GET  /styles.css               → CSS (no-cache headers)             ║
  ║    GET  /script.js                → JS (no-cache headers)              ║
  ║    GET  /api/auth/config          → Supabase keys for frontend         ║
  ║    POST /api/generate             → Main AI pipeline                   ║
  ║    POST /api/build_pdf            → PDF generation + upload            ║
  ║    POST /api/integrations/sync    → Shopify/GA4 data connector         ║
  ║    GET  /api/codemender/stream    → SSE telemetry stream               ║
  ║    POST /api/codemender/simulate  → Demo self-healing                  ║
  ╚════════════════════════════════════════════════════════════════════════╝
           │                    │                    │
           ▼                    ▼                    ▼
  ┌────────────────┐  ┌─────────────────┐  ┌─────────────────┐
  │ GOOGLE GEMINI  │  │ SUPABASE        │  │ UPSTASH REDIS   │
  │                │  │                 │  │                 │
  │ • 2.5 Flash    │  │ • PostgreSQL DB │  │ • Serverless    │
  │   (LLM Agent)  │  │   (L3 cache)    │  │   (L2 cache)    │
  │ • embedding-001│  │ • Storage       │  │ • <15ms lookups │
  │   (RAG vectors)│  │   (PDF hosting) │  │ • 24h TTL       │
  │ • Free tier    │  │ • Auth (JWT)    │  │ • REST API      │
  └────────────────┘  └─────────────────┘  └─────────────────┘
                               │
           ┌───────────────────┼───────────────────┐
           ▼                   ▼                   ▼
  ┌────────────────┐  ┌─────────────────┐  ┌─────────────────┐
  │ RENDER.COM     │  │ GITHUB          │  │ SENTRY          │
  │                │  │                 │  │                 │
  │ • Hosting      │  │ • Source code   │  │ • Error capture │
  │ • Auto-deploy  │  │ • Actions CI/CD │  │ • Perf tracing  │
  │ • Keep-alive   │  │ • Secrets vault │  │ • Async (0 lag) │
  │   (13min ping) │  │ • Pytest gate   │  │ • Free tier     │
  └────────────────┘  └─────────────────┘  └─────────────────┘


# CI/CD Pipeline Flow 
  git push origin main
       │
       ▼
  GitHub Actions (deploy.yml)
       │
       ├── 1. Checkout code
       ├── 2. Setup Python 3.9
       ├── 3. pip install requirements.txt
       ├── 4. pytest tests/ (10 tests)
       │       │
       │       ├── FAIL → ❌ Deploy BLOCKED
       │       └── PASS → ✅ Continue
       │
       └── 5. curl RENDER_DEPLOY_HOOK → Live in ~2 min

# Directory Structure Overview


  kpi-intelligence-reporter/
  ├── index.html          ← Frontend UI
  ├── styles.css          ← Design system (CSS Custom Properties)
  ├── script.js           ← Frontend dynamic UI & API calls
  ├── server.py           ← FastAPI backend endpoints, security & decorators
  ├── forecaster.py       ← Mathematical linear forecasting
  ├── rag_engine.py       ← Industry-specific vector search grounding
  ├── codemender.py       ← Self-healing validation & recovery pipeline
  ├── notifier.py         ← Webhook alerting system (Slack/Discord)
  ├── billing.py          ← Stripe subscriptions & monetization logic
  └── tests/
      └── test_engine.py  ← Unit test coverage





# KPI Intelligence Reporter

This application is an AI-powered strategic business analysis tool that generates Executive Decision Memos based on marketing performance and product sales data.

## Getting Started

To securely connect to the Gemini API while keeping your key hidden from the frontend, this app uses a lightweight Python backend server.

1. **Configure API Key**
   Make sure you have a `.env` file in the root directory with your Gemini API key:
   ```env
   GEMINI_API_KEY="your_secure_api_key_here"
   ```

2. **Run the Secure Application**
   Start the backend server using Python (no complex installations required):
   ```bash
   python3 server.py
   ```
   
   The server will serve your files securely and proxy the AI requests.
   Open your browser and navigate to: **[http://localhost:8000/](http://localhost:8000/)**
