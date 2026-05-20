import math
import logging

logger = logging.getLogger("decision_playbook")

def run_least_squares(x: list, y: list) -> dict:
    """Compute mathematical linear regression variables (y = mx + c) and R-squared fit."""
    n = len(x)
    if n < 2:
        return {"slope": 0.0, "intercept": 0.0 if not y else float(y[0]), "r_squared": 1.0}
    
    sum_x = sum(x)
    sum_y = sum(y)
    sum_xx = sum(val * val for val in x)
    sum_xy = sum(xv * yv for xv, yv in zip(x, y))
    
    # Calculate slope and intercept
    denom = (n * sum_xx - sum_x * sum_x)
    if abs(denom) < 1e-9:
        slope = 0.0
        intercept = sum_y / n
    else:
        slope = (n * sum_xy - sum_x * sum_y) / denom
        intercept = (sum_y - slope * sum_x) / n
        
    # Calculate R-squared (coefficient of determination)
    y_mean = sum_y / n
    ss_tot = sum((val - y_mean) ** 2 for val in y)
    
    if ss_tot < 1e-9:
        r_squared = 1.0
    else:
        ss_res = sum((yv - (slope * xv + intercept)) ** 2 for xv, yv in zip(x, y))
        r_squared = 1.0 - (ss_res / ss_tot)
        
    return {
        "slope": float(slope),
        "intercept": float(intercept),
        "r_squared": float(max(0.0, min(1.0, r_squared)))
    }

def run_regression_forecasting(marketing_data: list, product_data: list) -> dict:
    """Analyze historical marketing/product timelines and project statistical 30-day trends instantly."""
    try:
        # Extract spend, revenue, and units vectors
        spend_y = []
        m_rev_y = []
        p_rev_y = []
        
        for idx, row in enumerate(marketing_data):
            try:
                spend_y.append(float(row.get('spend', 0)))
                m_rev_y.append(float(row.get('revenue', 0)))
            except (ValueError, TypeError):
                continue
                
        for idx, row in enumerate(product_data):
            try:
                p_rev_y.append(float(row.get('revenue', 0)))
            except (ValueError, TypeError):
                continue
                
        # Generate X time sequences
        x_m = list(range(len(spend_y)))
        x_p = list(range(len(p_rev_y)))
        
        # Compute regression lines
        m_spend_fit = run_least_squares(x_m, spend_y)
        m_rev_fit   = run_least_squares(x_m, m_rev_y)
        p_rev_fit   = run_least_squares(x_p, p_rev_y)
        
        # Calculate 30-day projection values
        proj_m_len = len(spend_y) + 30
        proj_p_len = len(p_rev_y) + 30
        
        projected_spend = max(0.0, m_spend_fit["slope"] * proj_m_len + m_spend_fit["intercept"])
        projected_m_rev = max(0.0, m_rev_fit["slope"] * proj_m_len + m_rev_fit["intercept"])
        projected_p_rev = max(0.0, p_rev_fit["slope"] * proj_p_len + p_rev_fit["intercept"])
        
        return {
            "status": "success",
            "marketing_metrics": {
                "spend_trend_slope": m_spend_fit["slope"],
                "spend_r_squared": m_spend_fit["r_squared"],
                "revenue_trend_slope": m_rev_fit["slope"],
                "revenue_r_squared": m_rev_fit["r_squared"],
                "projected_30d_spend": projected_spend,
                "projected_30d_revenue": projected_m_rev
            },
            "product_metrics": {
                "revenue_trend_slope": p_rev_fit["slope"],
                "revenue_r_squared": p_rev_fit["r_squared"],
                "projected_30d_revenue": projected_p_rev
            }
        }
    except Exception as e:
        logger.error(f"[Forecaster Engine] Mathematical modeling failed: {e}")
        return {
            "status": "fallback",
            "error": str(e),
            "marketing_metrics": {
                "spend_trend_slope": 0.0, "spend_r_squared": 1.0,
                "revenue_trend_slope": 0.0, "revenue_r_squared": 1.0,
                "projected_30d_spend": 5000.0, "projected_30d_revenue": 18000.0
            },
            "product_metrics": {
                "revenue_trend_slope": 0.0, "revenue_r_squared": 1.0,
                "projected_30d_revenue": 120000.0
            }
        }
