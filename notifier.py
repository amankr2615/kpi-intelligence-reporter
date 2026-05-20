import httpx
import asyncio
import logging

logger = logging.getLogger(__name__)

async def trigger_webhook_alert(webhook_url: str, message: str, payload: dict = None):
    """
    Sends an asynchronous HTTP POST request to a given webhook URL.
    Does not block the main application thread.
    """
    if not webhook_url or not webhook_url.startswith("http"):
        return
        
    data = {
        "text": message,
        "payload": payload or {}
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(webhook_url, json=data, timeout=5.0)
            if response.status_code >= 400:
                logger.warning(f"Webhook alert failed with status {response.status_code}")
            else:
                logger.info(f"Successfully dispatched webhook alert to {webhook_url}")
    except Exception as e:
        logger.error(f"Failed to dispatch webhook alert: {e}")

def check_and_fire_alerts(state: dict, forecast_stats: dict, webhook_url: str):
    """
    Evaluates the current state and forecast, firing a webhook if dangerous trends are detected.
    """
    if not webhook_url:
        return
        
    alerts = []
    
    # Example Condition 1: Projected Revenue Trajectory is Negative
    marketing = forecast_stats.get("marketing_metrics", {})
    rev_slope = marketing.get("revenue_trend_slope", 0)
    
    if rev_slope < 0:
        alerts.append(f"🚨 ALERT: Revenue trajectory is negative (${rev_slope:.2f}/day).")
        
    # Example Condition 2: High CAC detected by AI in Board Memo
    board_memo = state.get("board_memo", "").lower()
    if "high cac" in board_memo or "unsustainable cac" in board_memo:
         alerts.append("⚠️ WARNING: AI detected potentially unsustainable Customer Acquisition Costs.")

    if alerts:
        combined_message = "KPI Intelligence Engine Alert:\n" + "\n".join(alerts)
        asyncio.create_task(trigger_webhook_alert(webhook_url, combined_message, state.get("projections", {})))
