"""
LangGraph Multi-Agent Orchestration Pipeline for KPI Intelligence Reporter.
Demonstrates state-graph node composition, state transitions, and deterministic grounding.
"""

from typing import TypedDict, Dict, Any, List
from langgraph.graph import StateGraph, END
from forecaster import run_regression_forecasting
from rag_engine import get_rag_context
import json

class AgentState(TypedDict):
    csv_summary: Dict[str, Any]
    question: str
    data_stats: Dict[str, Any]
    forecast_stats: Dict[str, Any]
    rag_context: str
    output: Dict[str, Any]

def data_grounding_node(state: AgentState) -> Dict[str, Any]:
    """Node 1: Extract verified numerical bounds from raw CSV."""
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
            nums = [parse_num(r.get(col)) for r in rows if parse_num(r.get(col)) is not None]
            if nums:
                stats[col] = {
                    "total": round(sum(nums), 2),
                    "average": round(sum(nums) / len(nums), 2),
                    "min": round(min(nums), 2),
                    "max": round(max(nums), 2),
                    "count": len(nums)
                }
        return stats

    csv = state.get("csv_summary", {})
    m_stats = get_col_stats(csv.get("marketing_data", []))
    p_stats = get_col_stats(csv.get("product_data", []))
    all_totals = [v["total"] for v in m_stats.values()] + [v["total"] for v in p_stats.values()]
    max_ref = max(all_totals) if all_totals else 100000

    data_stats = {
        "marketing_stats": m_stats,
        "product_stats": p_stats,
        "max_numeric_reference": max_ref
    }
    return {"data_stats": data_stats}

def forecasting_node(state: AgentState) -> Dict[str, Any]:
    """Node 2: Run mathematical least-squares linear regression."""
    csv = state.get("csv_summary", {})
    m_data = csv.get("marketing_data", [])
    p_data = csv.get("product_data", [])
    forecast = run_regression_forecasting(m_data, p_data)
    return {"forecast_stats": forecast}


def rag_retrieval_node(state: AgentState) -> Dict[str, Any]:
    """Node 3: Retrieve industry benchmark vectors using Cosine Similarity."""
    question = state.get("question", "")
    context = get_rag_context(question)
    return {"rag_context": context or "N/A"}

def build_langgraph_pipeline():
    """Construct and compile the LangGraph StateGraph workflow."""
    workflow = StateGraph(AgentState)

    workflow.add_node("grounding", data_grounding_node)
    workflow.add_node("forecasting", forecasting_node)
    workflow.add_node("rag_retrieval", rag_retrieval_node)

    workflow.set_entry_point("grounding")
    workflow.add_edge("grounding", "forecasting")
    workflow.add_edge("forecasting", "rag_retrieval")
    workflow.add_edge("rag_retrieval", END)

    return workflow.compile()

# Instantiated LangGraph App ready for execution
langgraph_app = build_langgraph_pipeline()
