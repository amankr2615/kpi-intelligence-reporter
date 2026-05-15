import os
import json
import logging
import time

from dotenv import load_dotenv
from fpdf import FPDF

from google import genai
from google.genai import types as genai_types
from google.genai.errors import ServerError

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

client = genai.Client(api_key=API_KEY)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("decision_playbook")

app = FastAPI(title="KPI Intelligence Reporter")

# Allow CORS for deployment flexibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure reports directory exists
os.makedirs("reports", exist_ok=True)
app.mount("/reports", StaticFiles(directory="reports"), name="reports")

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

def safe_generate(prompt, model=MODEL_NAME, max_retries=3):
    for attempt in range(max_retries):
        try:
            return client.models.generate_content(
                model=model,
                contents=prompt,
                config=genai_types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
            )
        except ServerError as e:
            if "503" in str(e):
                logger.warning("503 Model overloaded. Retrying...")
                time.sleep(2)
            else:
                raise
    raise RuntimeError("Failed after retries")

# -------------------------------------------------------------------
# Core Agents
# -------------------------------------------------------------------

def analysis_agent(state: dict):
    logger.info("-> Analysis Agent")
    prompt = f"""
You are a data analyst. Review the data and question.
Return JSON:
{{ "key_metrics": [{{"name": "str", "reason": "str"}}], "insights": ["str"], "risks_or_gaps": ["str"] }}
Data: {json.dumps(state['csv_summary'])}
Question: {state['question']}
"""
    state["analysis_summary"] = safe_parse_json(extract_text(safe_generate(prompt)))

def options_agent(state: dict):
    logger.info("-> Options Agent")
    prompt = f"""
Generate 2-3 strategic options as JSON:
{{ "options": [ {{ "name": "str", "description": "str", "pros": ["str"], "cons": ["str"], "data_support": "str" }} ] }}
Analysis: {json.dumps(state['analysis_summary'])}
Question: {state['question']}
"""
    state["options"] = safe_parse_json(extract_text(safe_generate(prompt)))

def decision_agent(state: dict):
    logger.info("-> Decision Agent")
    prompt = f"""
Choose ONE option and justify it. Return JSON:
{{ "recommended_option_name": "str", "rationale": "str", "notes_for_team": "str" }}
Analysis: {json.dumps(state['analysis_summary'])}
Options: {json.dumps(state['options'])}
"""
    state["decision"] = safe_parse_json(extract_text(safe_generate(prompt)))

def playbook_agent(state: dict):
    logger.info("-> Playbook Agent")
    prompt = f"""
Create a 7-day action playbook as JSON. MUST HAVE EXACTLY 7 days:
{{ "days": [ {{ "day": 1, "focus": "str", "tasks": ["str"] }} ], "monitoring_plan": "str", "early_warning_signals": ["str"] }}
Decision: {json.dumps(state['decision'])}
Analysis: {json.dumps(state['analysis_summary'])}
"""
    state["playbook"] = safe_parse_json(extract_text(safe_generate(prompt)))

def devils_advocate_agent(state: dict):
    logger.info("-> Devil's Advocate Agent")
    prompt = f"""
Critique the decision. Return JSON:
{{ "main_criticisms": ["str"], "potential_failure_modes": ["str"] }}
Decision: {json.dumps(state['decision'])}
Playbook: {json.dumps(state['playbook'])}
"""
    state["devils_advocate"] = safe_parse_json(extract_text(safe_generate(prompt)))

def projection_agent(state: dict):
    logger.info("-> Projection Agent (Dashboards)")
    prompt = f"""
You are a financial projection engine. Based on the data and the chosen strategy, mathematically project the future metrics.
Return EXACTLY this JSON structure with integer values:
{{
  "projected_marketing_revenue": <number>,
  "projected_product_revenue": <number>,
  "optimized_marketing_spend": <number>
}}
IMPORTANT: Do not just invent random numbers. Look at the CURRENT totals in the data, and project realistic growth (e.g., +10% to +25%) based on your strategic decision.
Data: {json.dumps(state['csv_summary'])}
Decision: {json.dumps(state['decision'])}
"""
    state["projections"] = safe_parse_json(extract_text(safe_generate(prompt)))


def board_memo_agent(state: dict):
    logger.info("-> Board Memo Agent")
    prompt = f"""
Write a 400-700 word executive memo. Return PLAIN TEXT.
Sections:
1. Context & Question
2. Data-Backed Insights
3. Options Considered
4. Recommended Decision & Why
5. Execution Plan (7-day summary)
6. Risks & Dissent (From Devil's Advocate)
Question: {state['question']}
Data: {json.dumps(state)}
"""
    resp = client.models.generate_content(model=MODEL_NAME, contents=prompt)
    state["board_memo"] = extract_text(resp)

# -------------------------------------------------------------------
# Core Loop
# -------------------------------------------------------------------
def run_full_pipeline(csv_summary: dict, question: str):
    state = {"csv_summary": csv_summary, "question": question}
    analysis_agent(state)
    options_agent(state)
    decision_agent(state)
    playbook_agent(state)
    devils_advocate_agent(state)
    projection_agent(state)
    board_memo_agent(state)
    return state

# -------------------------------------------------------------------
# PDF Generation
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

        logger.info("Starting Full Multi-Agent Decision Pipeline (Quality Mode)...")
        start_time = time.time()
        
        state = run_full_pipeline(csv_summary, question)

        logger.info("Exporting PDF...")
        pdf_url = export_full_report(state, filename=f"report_{int(time.time())}.pdf")

        logger.info(f"Pipeline finished in {time.time() - start_time:.2f} seconds.")

        return {
            "board_memo": state.get("board_memo", ""),
            "pdf_url": pdf_url,
            "projections": state.get("projections", {})
        }
                
    except Exception as e:
        logger.error(f"Error during generation: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

if __name__ == '__main__':
    uvicorn.run("server:app", host="0.0.0.0", port=PORT, reload=False)
