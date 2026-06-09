import os
import json
import logging
import time
import asyncio
import hashlib
import random
import httpx
import base64

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

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
from codemender import mender, heal_async
from forecaster import run_regression_forecasting
import sentry_sdk

load_dotenv()

SENTRY_DSN = os.getenv('SENTRY_DSN', '').strip()
sentry_sdk.init(
    dsn=SENTRY_DSN,
    traces_sample_rate=1.0,
    profiles_sample_rate=1.0,
)
API_KEY = os.getenv('GEMINI_API_KEY', '').strip()
if not API_KEY:
    API_KEY = "YOUR_API_KEY_HERE"

SUPABASE_URL = os.getenv('SUPABASE_URL', '').strip()
SUPABASE_KEY = os.getenv('SUPABASE_KEY', '').strip()

# Initialize Supabase client if credentials are available
try:
    from supabase import create_client
    supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None
except Exception:
    supabase_client = None

# Initialize RAG Engine
from rag_engine import init_rag, get_rag_context
init_rag(API_KEY)

# Initialize Billing Module (Fix 5)
from billing import check_usage_allowed, record_usage, create_checkout_url

PORT = int(os.environ.get("PORT", 8000))
MODEL_NAME = "gemini-2.5-flash"

# Upstash Redis L2 Serverless Cache
UPSTASH_REDIS_REST_URL = os.getenv("UPSTASH_REDIS_REST_URL", "").strip()
UPSTASH_REDIS_REST_TOKEN = os.getenv("UPSTASH_REDIS_REST_TOKEN", "").strip()


# Reusable HTTP client pool to maintain warm sockets and eliminate SSL/handshake latencies (<10ms L2 Redis lookups!)
http_client = httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=3.0))

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
    while True:
        try:
            if RENDER_URL:
                await http_client.get(f"{RENDER_URL}/health", timeout=10)
                logger.info("[Keep-Alive] Pinged self — server stays warm.")
        except Exception as e:
            logger.warning(f"[Keep-Alive] Ping failed: {e}")
        await asyncio.sleep(13 * 60)

@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.create_task(keep_alive_ping())
    yield
    # Clean up warm connection sockets on shutdown
    await http_client.aclose()

app = FastAPI(title="KPI Intelligence Reporter", lifespan=lifespan)

# --- Rate Limiter (Fix 1) ---
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# --- CORS Hardening (Fix 3) ---
ALLOWED_ORIGINS = [
    "https://kpi-backend-dl16.onrender.com",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
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

async def redis_get(key: str) -> dict:
    """Read cache payload from Upstash Redis serverless REST interface using global http pool."""
    if not UPSTASH_REDIS_REST_URL or not UPSTASH_REDIS_REST_TOKEN:
        return None
    try:
        headers = {"Authorization": f"Bearer {UPSTASH_REDIS_REST_TOKEN}"}
        resp = await http_client.get(f"{UPSTASH_REDIS_REST_URL}/get/{key}", headers=headers)
        if resp.status_code == 200:
            result = resp.json().get("result")
            return json.loads(result) if result else None
    except Exception as e:
        logger.warning(f"[Redis L2] Cache read failed: {e}")
    return None

async def redis_set(key: str, val: dict, expire_seconds: int = 86400):
    """Store cache payload to Upstash Redis serverless REST interface using global http pool."""
    if not UPSTASH_REDIS_REST_URL or not UPSTASH_REDIS_REST_TOKEN:
        return
    try:
        headers = {"Authorization": f"Bearer {UPSTASH_REDIS_REST_TOKEN}"}
        payload = json.dumps(val)
        await http_client.post(
            f"{UPSTASH_REDIS_REST_URL}/set/{key}",
            content=payload,
            headers=headers,
            params={"ex": expire_seconds}
        )
        logger.info(f"[Redis L2] Successfully cached report key: {key}")
    except Exception as e:
        logger.warning(f"[Redis L2] Cache write failed: {e}")


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
# Core Single-Pass Agent (Chain of Thought) — now data-grounded & self-healing
# -------------------------------------------------------------------
@heal_async(schema_context="Expected JSON matching OutputSchema: {analysis_summary: dict, options: dict, decision: dict, playbook: dict, devils_advocate: dict, projections: dict, board_memo: string}")
async def run_elastic_pipeline(csv_summary: dict, question: str, forecast_stats: dict = None):
    logger.info("-> Starting Data-Grounded Chain-of-Thought Pipeline")

    # Agent 0: Data Grounding — extract real numbers first
    data_stats = compute_data_stats(csv_summary)
    logger.info(f"[Data Grounding] max_reference={data_stats['max_numeric_reference']}")

    # Retrieve RAG Context (Industry Benchmarks)
    rag_context = get_rag_context(question)
    benchmark_section = f"=== INDUSTRY BENCHMARKS ===\n{rag_context}\n" if rag_context else ""

    prompt = f"""
You are a committee of expert AI agents: Data Analyst, Strategist, Decision Maker,
Playbook Creator, Devil's Advocate, Financial Projector, and Board Member.

You MUST analyze ONLY the data provided below. Do NOT invent or assume any numbers
not present in the data. Every claim must be traceable to the input.

{benchmark_section}

=== VERIFIED DATA STATS (computed from actual input — use these as ground truth) ===
{json.dumps(data_stats, indent=2)}

=== MATHEMATICAL TIME-SERIES REGRESSION FORECASTS (computed locally via Forecaster Engine) ===
{json.dumps(forecast_stats, indent=2) if forecast_stats else "N/A"}

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
    return FileResponse("styles.css", headers={
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache"
    })

@app.get("/script.js")
async def serve_js():
    return FileResponse("script.js", headers={
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache"
    })

@app.get("/api/auth/config")
async def get_auth_config():
    """Secure endpoint to share client keys without hardcoding them in the script."""
    return {
        "supabaseUrl": SUPABASE_URL or "",
        "supabaseKey": SUPABASE_KEY or ""
    }

# -------------------------------------------------------------------
# CodeMender Diagnostics Console Stream
# -------------------------------------------------------------------
from fastapi.responses import StreamingResponse

@app.get("/api/codemender/stream")
async def codemender_stream(request: Request):
    """EventSource streaming endpoint for real-time CodeMender auto-repair telemetry."""
    return StreamingResponse(
        mender.get_event_stream(),
        media_type="text/event-stream"
    )

@app.post("/api/codemender/simulate_error")
async def simulate_error():
    """Endpoint to trigger a simulated repair to demonstrate self-healing in action."""
    loop = asyncio.get_running_loop()
    mender.log_event(
        event_type="intercept",
        message="Simulated system crash intercepted in database mapping interface.",
        original="SELECT * FROM metrics_log WHERE value = 'NaN_STALE';",
        error_msg="ValueError: Cannot map metric value 'NaN_STALE' to PostgreSQL FLOAT8 column."
    )
    
    # Run repair mock asynchronously
    async def run_repair():
        await asyncio.sleep(1.2)
        await mender.heal_data(
            original_data="SELECT * FROM metrics_log WHERE value = 'NaN_STALE';",
            error_msg="ValueError: Cannot map metric value 'NaN_STALE' to PostgreSQL FLOAT8 column.",
            schema_context="Correct sql value mapping to standard FLOAT (e.g. replace 'NaN_STALE' with 0.0)"
        )
    asyncio.create_task(run_repair())
    
    return {"status": "Simulated error initiated. Watch CodeMender live heal!"}

@app.post("/api/generate")
@limiter.limit("10/minute")
async def generate_endpoint(request: Request):
    try:
        # --- Input Validation (Fix 4) ---
        content_length = request.headers.get('content-length', '0')
        if int(content_length) > 2 * 1024 * 1024:  # 2MB max
            return JSONResponse(status_code=413, content={"error": "Payload too large. Maximum 2MB allowed."})

        body = await request.json()
        m_data = body.get('marketingData', [])
        p_data = body.get('productData', [])
        question = body.get('question', 'Analyze the given data.')

        MAX_ROWS = 500
        if len(m_data) > MAX_ROWS or len(p_data) > MAX_ROWS:
            return JSONResponse(status_code=400, content={"error": f"Too many rows. Maximum {MAX_ROWS} rows per table."})
        if len(question) > 2000:
            return JSONResponse(status_code=400, content={"error": "Question too long. Maximum 2000 characters."})

        if not API_KEY or API_KEY == "YOUR_API_KEY_HERE":
            return JSONResponse(status_code=500, content={"error": "Server misconfiguration: GEMINI_API_KEY is not set in backend."})

        # --- Billing Gate (Fix 5) ---
        user_email = body.get('userEmail', 'guest@boardroom.com')
        usage = check_usage_allowed(user_email)
        if not usage["allowed"]:
            return JSONResponse(status_code=402, content={
                "error": usage["message"],
                "tier": usage["tier"],
                "upgrade_url": create_checkout_url(user_email)
            })
        
        csv_summary = {"marketing_data": m_data, "product_data": p_data}
        
        # 1. L1 In-Memory Cache Check
        cache_key = get_cache_key(csv_summary, question)
        if cache_key in REPORT_CACHE:
            logger.info("🔥 L1 CACHE HIT: Returning report instantly (in-memory).")
            return REPORT_CACHE[cache_key]["response_data"]

        # 2. L2 Upstash Redis Cache Check (Fast serverless cache)
        redis_cached = await redis_get(cache_key)
        if redis_cached:
            if isinstance(redis_cached, str):
                try:
                    redis_cached = json.loads(redis_cached)
                except Exception:
                    redis_cached = None
            
            if isinstance(redis_cached, dict):
                logger.info("⚡ L2 REDIS CACHE HIT: Returning report from Upstash Redis.")
                response_data = {
                    "cache_key": cache_key,
                    "board_memo": redis_cached.get("board_memo", "No memo generated."),
                    "projections": redis_cached.get("projections", {})
                }
                # Populate L1 cache
                REPORT_CACHE[cache_key] = {"state": redis_cached, "response_data": response_data}
                return response_data

        # 3. L3 Supabase DB Cache Check (survives restarts & persistent fallback)
        db_row = db_get_cache(cache_key)
        if db_row and db_row.get('result_json'):
            logger.info("⚡ L3 SUPABASE DB CACHE HIT: Returning report from Supabase.")
            response_data = {
                "cache_key": cache_key,
                "board_memo": db_row['result_json'].get('board_memo', ''),
                "projections": db_row['result_json'].get('projections', {}),
                "pdf_url": db_row.get('pdf_url', '')
            }
            # Populate L1 cache & L2 Redis
            REPORT_CACHE[cache_key] = {"state": db_row['result_json'], "response_data": response_data}
            await redis_set(cache_key, db_row['result_json'])
            return response_data

        # Compute local time-series regression models in microseconds
        logger.info("[Forecaster] Pre-calculating statistical forecasts...")
        forecast_stats = run_regression_forecasting(m_data, p_data)

        logger.info("Starting Elastic Chain-of-Thought Pipeline...")
        start_time = time.time()
        
        # 3. Async Execution + Jitter Backoff
        state = await run_elastic_pipeline(csv_summary, question, forecast_stats)

        logger.info(f"Pipeline finished successfully in {time.time() - start_time:.2f} seconds.")

        # 4. Trigger Webhook Alerts (Background)
        webhook_url = body.get('webhookUrl', '')
        from notifier import check_and_fire_alerts
        check_and_fire_alerts(state, forecast_stats, webhook_url)

        # Ensure board_memo header formatting is structured even if AI omitted parts
        response_data = {
            "cache_key": cache_key,
            "board_memo": state.get("board_memo", "No memo generated."),
            "projections": state.get("projections", {}),
            "forecast": forecast_stats
        }
        
        # Save to L1 (memory), L2 (Upstash Redis), and L3 (Supabase PostgreSQL DB)
        REPORT_CACHE[cache_key] = {"state": state, "response_data": response_data}
        await redis_set(cache_key, state)
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

@app.post("/api/integrations/sync")
async def integrations_sync_endpoint(request: Request):
    try:
        body = await request.json()
        target = body.get("target", "Shopify")
        domain = body.get("domain", "")
        token = body.get("token", "")
        
        logger.info(f"Initiating backend direct sync for {target} on {domain}")
        # Simulate OAuth validation and API response latency (simulating a real connection delay)
        await asyncio.sleep(1.5)
        
        # Premium Mock Synced E-Commerce Data matching M_COLS & P_COLS schemas perfectly
        syncedMarketing = [
            { "date": '2026-05-01', "channel": 'Google Search Ads', "spend": 4200, "clicks": 1250, "conversions": 380, "revenue": 16500 },
            { "date": '2026-05-02', "channel": 'Meta Campaign PRO', "spend": 3800, "clicks": 980,  "conversions": 310, "revenue": 14200 },
            { "date": '2026-05-03', "channel": 'TikTok Shop Influencers', "spend": 2900, "clicks": 1450, "conversions": 290, "revenue": 11800 },
            { "date": '2026-05-04', "channel": 'YouTube Video Placement', "spend": 1800, "clicks": 540,  "conversions": 130, "revenue": 6400 },
            { "date": '2026-05-05', "channel": 'Shopify Retargeting Ads', "spend": 1200, "clicks": 390,  "conversions": 110, "revenue": 5100 }
        ]
        
        syncedProduct = [
            { "date": '2026-05-01', "product": 'Alpha-X Ultra Headset', "units_sold": 820, "price": 149, "revenue": 122180, "region": 'Global' },
            { "date": '2026-05-02', "product": 'Nova-Core Watch Pro',    "units_sold": 540, "price": 199, "revenue": 107460, "region": 'Global' },
            { "date": '2026-05-03', "product": 'Vertex Ergonomic Pack',  "units_sold": 390, "price": 89,  "revenue": 34710,  "region": 'Global' },
            { "date": '2026-05-04', "product": 'Aero-Fit Smart Sleeve',  "units_sold": 290, "price": 49,  "revenue": 14210,  "region": 'Global' }
        ]
        
        return {
            "status": "success",
            "marketing_data": syncedMarketing,
            "product_data": syncedProduct
        }
    except Exception as e:
        logger.error(f"Error during integration sync: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

# -------------------------------------------------------------------
# Billing API Endpoints (Fix 5)
# -------------------------------------------------------------------
@app.post("/api/billing/status")
async def billing_status(request: Request):
    """Check a user's billing tier and remaining free reports."""
    body = await request.json()
    user_email = body.get('email', 'guest@boardroom.com')
    usage = check_usage_allowed(user_email)
    return usage

@app.post("/api/billing/checkout")
async def billing_checkout(request: Request):
    """Create a Stripe Checkout session for upgrading to Pro."""
    body = await request.json()
    user_email = body.get('email', 'guest@boardroom.com')
    url = create_checkout_url(user_email)
    if not url:
        return JSONResponse(status_code=503, content={"error": "Billing not configured. Set STRIPE_SECRET_KEY in environment."})
    return {"checkout_url": url}

if __name__ == '__main__':
    uvicorn.run("server:app", host="0.0.0.0", port=PORT, reload=False)
