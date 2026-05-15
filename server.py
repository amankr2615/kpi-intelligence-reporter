import os
import json
import logging
import time
import asyncio
import hashlib
import random

from dotenv import load_dotenv
from fpdf import FPDF

from google import genai
from google.genai import types as genai_types

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

load_dotenv()
API_KEY = os.getenv('GEMINI_API_KEY')
if not API_KEY:
    API_KEY = "YOUR_API_KEY_HERE"

PORT = int(os.environ.get("PORT", 8000))
MODEL_NAME = "gemini-2.5-flash"

# Use the async client for non-blocking concurrent requests
client = genai.Client(api_key=API_KEY)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("decision_playbook")

app = FastAPI(title="KPI Intelligence Reporter")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs("reports", exist_ok=True)
app.mount("/reports", StaticFiles(directory="reports"), name="reports")

# -------------------------------------------------------------------
# Aggressive Hashed Caching (0-Second Trick)
# -------------------------------------------------------------------
REPORT_CACHE = {}

def get_cache_key(csv_summary: dict, question: str) -> str:
    raw_str = json.dumps(csv_summary, sort_keys=True) + question
    return hashlib.sha256(raw_str.encode('utf-8')).hexdigest()

# -------------------------------------------------------------------
# Utilities
# -------------------------------------------------------------------
def extract_text(resp) -> str:
    t = getattr(resp, "text", None)
    if t:
        return t
    parts = []
    for cand in getattr(resp, "candidates", []):
        content = getattr(cand, "content", None)
        if content:
            for part in getattr(content, "parts", []):
                txt = getattr(part, "text", None)
                if txt:
                    parts.append(txt)
    return "\n".join(parts).strip()

def safe_parse_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        parts = text.split("```")
        if len(parts) >= 3:
            if parts[1].strip().lower().startswith("json"):
                text = parts[2].strip()
            else:
                text = parts[1].strip()
    try:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(text[start : end + 1])
    except Exception:
        pass
    return {"raw_text": text}

# Elastic Jitter Backoff
async def safe_generate_async(prompt, model=MODEL_NAME, max_retries=6):
    for attempt in range(max_retries):
        try:
            resp = await client.aio.models.generate_content(
                model=model,
                contents=prompt,
                config=genai_types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
            )
            return resp
        except Exception as e:
            err_str = str(e).lower()
            if "429" in err_str or "503" in err_str or "too many requests" in err_str or "overloaded" in err_str:
                # Random jitter between 2 to 6 seconds prevents "thundering herd" problem
                jitter = random.uniform(2.0, 6.0)
                logger.warning(f"Google Rate Limited (Attempt {attempt+1}/{max_retries}). Waiting {jitter:.2f}s...")
                await asyncio.sleep(jitter)
            else:
                raise e
    raise RuntimeError("Failed after maximum retries due to Google's strict Free-Tier rate limits.")

# -------------------------------------------------------------------
# Core Single-Pass Agent (Chain of Thought)
# -------------------------------------------------------------------
async def run_elastic_pipeline(csv_summary: dict, question: str):
    logger.info("-> Starting Single-Pass Chain-of-Thought Agent")
    
    prompt = f"""
You are a committee of expert AI agents (Data Analyst, Strategist, Decision Maker, Playbook Creator, Devil's Advocate, Financial Projector, and Board Member).
You must deeply analyze the data and answer the question by simulating all 7 agents sequentially.
Return EXACTLY one JSON object with this exact structure:
{{
  "analysis_summary": {{ "key_metrics": [{{"name": "str", "reason": "str"}}], "insights": ["str"], "risks_or_gaps": ["str"] }},
  "options": {{ "options": [ {{ "name": "str", "description": "str", "pros": ["str"], "cons": ["str"], "data_support": "str" }} ] }},
  "decision": {{ "recommended_option_name": "str", "rationale": "str", "notes_for_team": "str" }},
  "playbook": {{ "days": [ {{ "day": 1, "focus": "str", "tasks": ["str"] }} ], "monitoring_plan": "str", "early_warning_signals": ["str"] }},
  "devils_advocate": {{ "main_criticisms": ["str"], "potential_failure_modes": ["str"] }},
  "projections": {{ "projected_marketing_revenue": <number>, "projected_product_revenue": <number>, "optimized_marketing_spend": <number> }},
  "board_memo": "Write a 400-700 word executive memo in plain text summarizing all the findings, decisions, and execution plans."
}}

IMPORTANT: Do not skip any nested JSON keys. Provide a deep, thoughtful response for 'board_memo'.

CRITICAL PROJECTION GUIDELINES:
- The "projections" numbers MUST be realistic and mathematically grounded in the provided Data.
- DO NOT hallucinate massive revenue spikes. Assume a realistic AI optimization impact of 5% to 25% maximum improvement over the current metrics.

Data: {json.dumps(csv_summary)}
Question: {question}
"""
    resp = await safe_generate_async(prompt)
    parsed = safe_parse_json(extract_text(resp))
    
    # Safely construct the final state dictionary exactly as the PDF generator expects it
    state = {
        "csv_summary": csv_summary,
        "question": question,
        "analysis_summary": parsed.get("analysis_summary", {}),
        "options": parsed.get("options", {}),
        "decision": parsed.get("decision", {}),
        "playbook": parsed.get("playbook", {}),
        "devils_advocate": parsed.get("devils_advocate", {}),
        "projections": parsed.get("projections", {}),
        "board_memo": parsed.get("board_memo", "No memo generated.")
    }
    return state

# -------------------------------------------------------------------
# PDF Generation (Moved to background thread)
# -------------------------------------------------------------------
def export_full_report(state, filename="decision_playbook_report.pdf"):
    pdf_path = os.path.join("reports", filename)
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    
    def section(title, text):
        pdf.set_font("Helvetica", "B", 14)
        pdf.multi_cell(0, 10, title.encode('latin-1', 'replace').decode('latin-1'))
        pdf.ln(2)
        pdf.set_font("Helvetica", "", 11)
        pdf.multi_cell(0, 6, text.encode('latin-1', 'replace').decode('latin-1'))
        pdf.ln(5)

    section("Executive Memo", state.get("board_memo", "No memo."))
    
    if "before_image" in state and os.path.exists(state["before_image"]):
        pdf.add_page()
        section("Dashboard Visualizations", "Performance Projections before and after AI Optimization.")
        pdf.image(state["before_image"], w=180)
        pdf.ln(10)
        pdf.image(state["after_image"], w=180)

    for key, label in [("analysis_summary", "Analysis"), ("options", "Options"), ("decision", "Decision"), ("playbook", "Playbook")]:
        raw = json.dumps(state.get(key, {}), indent=2)
        body = raw[:1000] + ("\n...\n[truncated]" if len(raw) > 1000 else "")
        section(label, body)

    pdf.output(pdf_path)
    return f"/reports/{filename}"

# -------------------------------------------------------------------
# FastAPI Endpoints
# -------------------------------------------------------------------

@app.get("/")
async def serve_index():
    return FileResponse("index.html")

@app.get("/styles.css")
async def serve_css():
    return FileResponse("styles.css")

@app.get("/script.js")
async def serve_js():
    return FileResponse("script.js")

@app.post("/api/generate")
async def generate_endpoint(request: Request):
    try:
        body = await request.json()
        m_data = body.get('marketingData', [])
        p_data = body.get('productData', [])
        question = body.get('question', 'Analyze the given data.')

        if not API_KEY or API_KEY == "YOUR_API_KEY_HERE":
            return JSONResponse(status_code=500, content={"error": "Server misconfiguration: GEMINI_API_KEY is not set in backend."})
        
        csv_summary = {"marketing_data": m_data, "product_data": p_data}
        
        # 1. Hashed Caching (O-second retrieval for duplicates)
        cache_key = get_cache_key(csv_summary, question)
        if cache_key in REPORT_CACHE:
            logger.info("🔥 CACHE HIT: Returning report instantly in 0 seconds.")
            return REPORT_CACHE[cache_key]["response_data"]

        logger.info("Starting Elastic Chain-of-Thought Pipeline...")
        start_time = time.time()
        
        # 2. Async Execution + Jitter Backoff (FastAPI won't block)
        state = await run_elastic_pipeline(csv_summary, question)

        logger.info(f"Pipeline finished successfully in {time.time() - start_time:.2f} seconds.")

        response_data = {
            "cache_key": cache_key,
            "board_memo": state.get("board_memo", ""),
            "projections": state.get("projections", {})
        }
        
        # Save to memory cache for future users
        REPORT_CACHE[cache_key] = {"state": state, "response_data": response_data}
        return response_data
                
    except Exception as e:
        logger.error(f"Error during generation: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

import base64

@app.post("/api/build_pdf")
async def build_pdf_endpoint(request: Request):
    try:
        body = await request.json()
        cache_key = body.get('cache_key')
        before_b64 = body.get('before_image')
        after_b64 = body.get('after_image')

        cached = REPORT_CACHE.get(cache_key)
        if not cached:
            return JSONResponse(status_code=400, content={"error": "Session expired or invalid cache key."})
        
        state = cached["state"]

        def decode_b64(b64_str, filename):
            if b64_str and "base64," in b64_str:
                b64_str = b64_str.split("base64,")[1]
                with open(filename, "wb") as f:
                    f.write(base64.b64decode(b64_str))

        if before_b64 and after_b64:
            before_path = f"reports/before_{cache_key}.png"
            after_path = f"reports/after_{cache_key}.png"
            decode_b64(before_b64, before_path)
            decode_b64(after_b64, after_path)
            state["before_image"] = before_path
            state["after_image"] = after_path

        logger.info("Building PDF with charts...")
        pdf_url = await asyncio.to_thread(export_full_report, state, f"report_{cache_key}.pdf")
        
        return {"pdf_url": pdf_url}
    except Exception as e:
        logger.error(f"Error during PDF build: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

if __name__ == '__main__':
    uvicorn.run("server:app", host="0.0.0.0", port=PORT, reload=False)
