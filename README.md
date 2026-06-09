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

<img width="1278" height="651" alt="Screenshot 2026-06-09 at 10 50 34 PM" src="https://github.com/user-attachments/assets/e90f6a2d-7b33-443d-8db8-15e7b6ac508c" />


<img width="1248" height="696" alt="Screenshot 2026-06-09 at 10 06 35 PM" src="https://github.com/user-attachments/assets/b5f7ddc2-a9c0-43bd-ad9d-3b70821cae94" />

<img width="1248" height="475" alt="Screenshot 2026-06-09 at 10 26 05 PM" src="https://github.com/user-attachments/assets/26ae979e-9dd6-4345-b8e7-a36e70729a94" />

<img width="1242" height="470" alt="Screenshot 2026-06-09 at 10 52 47 PM" src="https://github.com/user-attachments/assets/03c306ed-b9aa-440c-926b-7e2aa4bd8401" />

# KPI INTELLIGENCE REPORTER — FULL SYSTEM ARCHITECTURE

**<img width="446" height="287" alt="Screenshot 2026-06-09 at 10 42 09 PM" src="https://github.com/user-attachments/assets/3a7bfc98-ddb9-4364-8a6e-b07159a77628" />**

**<img width="446" height="338" alt="Screenshot 2026-06-09 at 10 43 43 PM" src="https://github.com/user-attachments/assets/554d42dd-5e2c-405e-b938-1f43d08b2bfc" />**

**<img width="446" height="396" alt="Screenshot 2026-06-09 at 10 45 38 PM" src="https://github.com/user-attachments/assets/bf32fd0b-b753-4fcf-8615-b93f486b9ee4" />**

**<img width="446" height="358" alt="Screenshot 2026-06-09 at 10 46 22 PM" src="https://github.com/user-attachments/assets/7b58e323-1ea7-4d46-bd5f-5756b742e558" />**



# CI/CD Pipeline Flow 

**<img width="429" height="249" alt="Screenshot 2026-06-09 at 10 47 09 PM" src="https://github.com/user-attachments/assets/072a3f5b-394a-41d7-bcaf-86219eec194f"/>**

# Directory Structure Overview

**<img width="493" height="249" alt="Screenshot 2026-06-09 at 10 47 39 PM" src="https://github.com/user-attachments/assets/4942ab0c-22f7-42e9-80a7-fdc135dcd9e2"/>**

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
