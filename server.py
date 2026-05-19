import os
import json
import logging
import time
import asyncio
import hashlib
import random
import httpx
import base64

from dotenv import load_dotenv
from fpdf import FPDF

from google import genai
from google.genai import types as genai_types

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn

load_dotenv()
API_KEY = os.getenv('GEMINI_API_KEY')
if not API_KEY:
    API_KEY = "YOUR_API_KEY_HERE"

SUPABASE_URL = os.getenv('SUPABASE_URL', '')
SUPABASE_KEY = os.getenv('SUPABASE_KEY', '')

# Initialize Supabase client if credentials are available
try:
    from supabase import create_client
    supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None
except Exception:
    supabase_client = None

PORT = int(os.environ.get("PORT", 8000))
MODEL_NAME = "gemini-2.5-flash"

# Use the async client for non-blocking concurrent requests
client = genai.Client(api_key=API_KEY)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("decision_playbook")

# -------------------------------------------------------------------
# Keep-Alive: Ping self every 13 min to prevent Render cold starts
# -------------------------------------------------------------------
RENDER_URL = os.getenv("RENDER_EXTERNAL_URL", "")

async def keep_alive_ping():
    await asyncio.sleep(60)
    async with httpx.AsyncClient() as http:
        while True:
            try:
                if RENDER_URL:
                    await http.get(f"{RENDER_URL}/health", timeout=10)
                    logger.info("[Keep-Alive] Pinged self — server stays warm.")
            except Exception as e:
                logger.warning(f"[Keep-Alive] Ping failed: {e}")
            await asyncio.sleep(13 * 60)

@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.create_task(keep_alive_ping())
    yield

app = FastAPI(title="KPI Intelligence Reporter", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs("reports", exist_ok=True)
app.mount("/reports", StaticFiles(directory="reports"), name="reports")

@app.get("/health")
async def health_check():
    return {"status": "ok"}

# -------------------------------------------------------------------
# Caching: In-memory (fast) + Supabase DB (persistent across restarts)
# -------------------------------------------------------------------
REPORT_CACHE = {}  # In-memory L1 cache

def get_cache_key(csv_summary: dict, question: str) -> str:
    raw_str = json.dumps(csv_summary, sort_keys=True) + question
    return hashlib.sha256(raw_str.encode('utf-8')).hexdigest()

def db_get_cache(cache_key: str):
    """Look up a cached report from Supabase DB."""
    if not supabase_client:
        return None
    try:
        res = supabase_client.table('reports').select('*').eq('cache_key', cache_key).single().execute()
        return res.data
    except Exception:
        return None

def db_set_cache(cache_key: str, question: str, result_json: dict, pdf_url: str = None):
    """Store a report result in Supabase DB."""
    if not supabase_client:
        return
    try:
        supabase_client.table('reports').upsert({
            'cache_key': cache_key,
            'question': question,
            'result_json': result_json,
            'pdf_url': pdf_url or ''
        }).execute()
    except Exception as e:
        logger.warning(f"[DB] Cache write failed: {e}")

def upload_to_storage(local_path: str, storage_path: str) -> str:
    """Upload a file to Supabase Storage and return its public URL."""
    if not supabase_client:
        return f"/{local_path}"
    try:
        with open(local_path, 'rb') as f:
            content = f.read()
        mime = 'application/pdf' if local_path.endswith('.pdf') else 'image/png'
        supabase_client.storage.from_('reports').upload(
            path=storage_path,
            file=content,
            file_options={"content-type": mime, "upsert": "true"}
        )
        public_url = f"{SUPABASE_URL}/storage/v1/object/public/reports/{storage_path}"
        logger.info(f"[Storage] Uploaded {storage_path} → {public_url}")
        return public_url
    except Exception as e:
        logger.warning(f"[Storage] Upload failed: {e}")
        return f"/{local_path}"

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

from pydantic import BaseModel

class Metric(BaseModel):
    name: str
    reason: str

class AnalysisSummary(BaseModel):
    key_metrics: list[Metric]
    insights: list[str]
    risks_or_gaps: list[str]

class Option(BaseModel):
    name: str
    description: str
    pros: list[str]
    cons: list[str]
    data_support: str

class Options(BaseModel):
    options: list[Option]

class Decision(BaseModel):
    recommended_option_name: str
    rationale: str
    notes_for_team: str

class DayTask(BaseModel):
    day: int
    focus: str
    tasks: list[str]

class Playbook(BaseModel):
    days: list[DayTask]
    monitoring_plan: str
    early_warning_signals: list[str]

class DevilsAdvocate(BaseModel):
    main_criticisms: list[str]
    potential_failure_modes: list[str]

class Projections(BaseModel):
    projected_marketing_revenue: float
    projected_product_revenue: float
    optimized_marketing_spend: float

class OutputSchema(BaseModel):
    analysis_summary: AnalysisSummary
    options: Options
    decision: Decision
    playbook: Playbook
    devils_advocate: DevilsAdvocate
    projections: Projections
    board_memo: str

# Elastic Jitter Backoff
async def safe_generate_async(prompt, model=MODEL_NAME, max_retries=6, response_schema=None):
    for attempt in range(max_retries):
        try:
            config_kwargs = {
                "response_mime_type": "application/json",
                "temperature": 0.0,   # DETERMINISTIC — eliminates hallucination variance
                "top_p": 1.0,
                "top_k": 1,
            }
            if response_schema:
                config_kwargs["response_schema"] = response_schema

            resp = await client.aio.models.generate_content(
                model=model,
                contents=prompt,
                config=genai_types.GenerateContentConfig(**config_kwargs)
            )
            return resp
        except Exception as e:
            err_str = str(e).lower()
            if "429" in err_str or "503" in err_str or "too many requests" in err_str or "overloaded" in err_str:
                jitter = random.uniform(2.0, 6.0)
                logger.warning(f"Google Rate Limited (Attempt {attempt+1}/{max_retries}). Waiting {jitter:.2f}s...")
                await asyncio.sleep(jitter)
            else:
                raise e
    raise RuntimeError("Failed after maximum retries due to Google's strict Free-Tier rate limits.")

# -------------------------------------------------------------------
# Agent 0: Data Grounding Agent — pre-computes REAL stats from CSV
# (prevents hallucination by anchoring projections to actual numbers)
# -------------------------------------------------------------------
def compute_data_stats(csv_summary: dict) -> dict:
    """Extract verified numeric totals/averages from raw CSV data."""
    def parse_num(val):
        try:
            return float(str(val).replace(',', '').replace('$', '').replace('₹', '').replace('%', '').strip())
        except:
            return None

    def get_col_stats(rows):
        if not rows:
            return {}
        stats = {}
        for col in rows[0].keys():
            nums = [parse_num(r.get(col)) for r in rows]
            nums = [n for n in nums if n is not None]
            if nums:
                stats[col] = {
                    "total": round(sum(nums), 2),
                    "average": round(sum(nums) / len(nums), 2),
                    "min": round(min(nums), 2),
                    "max": round(max(nums), 2),
                    "count": len(nums)
                }
        return stats

    marketing_stats = get_col_stats(csv_summary.get("marketing_data", []))
    product_stats   = get_col_stats(csv_summary.get("product_data", []))

    # Compute overall revenue reference (largest total across all numeric cols)
    all_totals = (
        [v["total"] for v in marketing_stats.values()] +
        [v["total"] for v in product_stats.values()]
    )
    max_reference = max(all_totals) if all_totals else 100_000

    return {
        "marketing_stats": marketing_stats,
        "product_stats":   product_stats,
        "max_numeric_reference": max_reference,
    }


# -------------------------------------------------------------------
# Agent 8: Fact-Validator — post-clamps projections to realistic bounds
# (second layer of hallucination prevention)
# -------------------------------------------------------------------
def validate_and_clamp_projections(projections: dict, data_stats: dict) -> dict:
    """Ensure all projections are mathematically grounded in actual data."""
    ref = data_stats.get("max_numeric_reference", 100_000)
    MAX_MULTIPLIER = 2.0   # projections can be AT MOST 2× the biggest actual number
    MIN_FLOOR      = 0.0

    validated = {}
    for key, val in projections.items():
        if isinstance(val, (int, float)):
            clamped = max(MIN_FLOOR, min(float(val), ref * MAX_MULTIPLIER))
            if clamped != float(val):
                logger.warning(f"[Fact-Validator] Clamped '{key}': {val} → {clamped} (ref={ref})")
            validated[key] = round(clamped, 2)
        else:
            validated[key] = val
    return validated


# -------------------------------------------------------------------
# Core Single-Pass Agent (Chain of Thought) — now data-grounded
# -------------------------------------------------------------------
async def run_elastic_pipeline(csv_summary: dict, question: str):
    logger.info("-> Starting Data-Grounded Chain-of-Thought Pipeline")

    # Agent 0: Data Grounding — extract real numbers first
    data_stats = compute_data_stats(csv_summary)
    logger.info(f"[Data Grounding] max_reference={data_stats['max_numeric_reference']}")

    prompt = f"""
You are a committee of expert AI agents: Data Analyst, Strategist, Decision Maker,
Playbook Creator, Devil's Advocate, Financial Projector, and Board Member.

You MUST analyze ONLY the data provided below. Do NOT invent or assume any numbers
not present in the data. Every claim must be traceable to the input.

=== VERIFIED DATA STATS (computed from actual input — use these as ground truth) ===
{json.dumps(data_stats, indent=2)}

=== RAW DATA ===
{json.dumps(csv_summary, indent=2)}

=== BUSINESS QUESTION ===
{question}

=== PROJECTION RULES (MANDATORY — violations = invalid response) ===
- projected_marketing_revenue: MUST be between 0 and {round(data_stats['max_numeric_reference'] * 1.3, 2)}
- projected_product_revenue:   MUST be between 0 and {round(data_stats['max_numeric_reference'] * 1.3, 2)}
- optimized_marketing_spend:   MUST be between 0 and {round(data_stats['max_numeric_reference'] * 1.1, 2)}
- Maximum realistic improvement from AI optimization: 5% to 25% over current actuals
- Use the verified stats above as the baseline, not assumptions

Return EXACTLY one JSON object with this structure:
{{
  "analysis_summary": {{ "key_metrics": [{{"name": "str", "reason": "str"}}], "insights": ["str"], "risks_or_gaps": ["str"] }},
  "options": {{ "options": [ {{ "name": "str", "description": "str", "pros": ["str"], "cons": ["str"], "data_support": "str" }} ] }},
  "decision": {{ "recommended_option_name": "str", "rationale": "str", "notes_for_team": "str" }},
  "playbook": {{ "days": [ {{ "day": 1, "focus": "str", "tasks": ["str"] }} ], "monitoring_plan": "str", "early_warning_signals": ["str"] }},
  "devils_advocate": {{ "main_criticisms": ["str"], "potential_failure_modes": ["str"] }},
  "projections": {{ "projected_marketing_revenue": <number>, "projected_product_revenue": <number>, "optimized_marketing_spend": <number> }},
  "board_memo": "Write a 400-700 word executive memo referencing specific numbers from the data."
}}
"""

    resp = await safe_generate_async(prompt, response_schema=OutputSchema)
    try:
        parsed = json.loads(extract_text(resp))
    except Exception:
        parsed = {}

    # Agent 8: Fact-Validator — clamp projections to realistic bounds
    raw_projections = parsed.get("projections", {})
    validated_projections = validate_and_clamp_projections(raw_projections, data_stats)

    state = {
        "csv_summary":      csv_summary,
        "question":         question,
        "analysis_summary": parsed.get("analysis_summary", {}),
        "options":          parsed.get("options", {}),
        "decision":         parsed.get("decision", {}),
        "playbook":         parsed.get("playbook", {}),
        "devils_advocate":  parsed.get("devils_advocate", {}),
        "projections":      validated_projections,
        "board_memo":       parsed.get("board_memo", "No memo generated.")
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
        
        # 1. L1 In-Memory Cache
        cache_key = get_cache_key(csv_summary, question)
        if cache_key in REPORT_CACHE:
            logger.info("🔥 L1 CACHE HIT: Returning report instantly (in-memory).")
            return REPORT_CACHE[cache_key]["response_data"]

        # 2. L2 Supabase DB Cache (survives server restarts)
        db_row = db_get_cache(cache_key)
        if db_row and db_row.get('result_json'):
            logger.info("⚡ L2 CACHE HIT: Returning report from Supabase DB.")
            response_data = {
                "cache_key": cache_key,
                "board_memo": db_row['result_json'].get('board_memo', ''),
                "projections": db_row['result_json'].get('projections', {}),
                "pdf_url": db_row.get('pdf_url', '')
            }
            REPORT_CACHE[cache_key] = {"state": db_row['result_json'], "response_data": response_data}
            return response_data

        logger.info("Starting Elastic Chain-of-Thought Pipeline...")
        start_time = time.time()
        
        # 3. Async Execution + Jitter Backoff
        state = await run_elastic_pipeline(csv_summary, question)

        logger.info(f"Pipeline finished successfully in {time.time() - start_time:.2f} seconds.")

        response_data = {
            "cache_key": cache_key,
            "board_memo": state.get("board_memo", ""),
            "projections": state.get("projections", {})
        }
        
        # Save to both L1 (memory) and L2 (Supabase DB)
        REPORT_CACHE[cache_key] = {"state": state, "response_data": response_data}
        db_set_cache(cache_key, question, state)
        return response_data
                
    except Exception as e:
        logger.error(f"Error during generation: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

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
        pdf_filename = f"report_{cache_key}.pdf"
        pdf_local_url = await asyncio.to_thread(export_full_report, state, pdf_filename)

        # Upload PDF and charts to Supabase Storage for permanent hosting
        pdf_local_path = f"reports/{pdf_filename}"
        pdf_public_url = await asyncio.to_thread(upload_to_storage, pdf_local_path, pdf_filename)
        if before_b64 and after_b64:
            await asyncio.to_thread(upload_to_storage, before_path, f"before_{cache_key}.png")
            await asyncio.to_thread(upload_to_storage, after_path, f"after_{cache_key}.png")

        # Update DB cache with the permanent PDF URL
        db_set_cache(cache_key, cached.get('state', {}).get('question', ''), state, pdf_public_url)

        # Return Supabase public URL if available, otherwise local fallback
        return {"pdf_url": pdf_public_url}
    except Exception as e:
        logger.error(f"Error during PDF build: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

if __name__ == '__main__':
    uvicorn.run("server:app", host="0.0.0.0", port=PORT, reload=False)
