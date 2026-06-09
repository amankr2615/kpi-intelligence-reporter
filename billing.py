"""
Stripe Billing Module — Subscription gating for premium features.

Setup:
  1. Create a Stripe account at https://stripe.com
  2. Get your API keys from the Stripe Dashboard
  3. Set STRIPE_SECRET_KEY and STRIPE_WEBHOOK_SECRET in your .env
  4. Create a Product + Price in Stripe Dashboard
  5. Set STRIPE_PRICE_ID in your .env

Free Tier:  5 reports/month (no Stripe required)
Pro Tier:   Unlimited reports ($49/month)
"""

import os
import logging
from datetime import datetime, timedelta

logger = logging.getLogger("billing")

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "").strip()
STRIPE_PRICE_ID = os.getenv("STRIPE_PRICE_ID", "").strip()

# In-memory usage tracker (replace with Supabase in production)
# Format: { "user_email": { "count": 3, "reset_date": datetime } }
FREE_TIER_USAGE = {}
FREE_TIER_LIMIT = 5  # reports per month


def check_usage_allowed(user_email: str) -> dict:
    """
    Checks if a user can generate a report.
    Returns: { "allowed": bool, "remaining": int, "tier": str, "message": str }
    """
    # If Stripe is not configured, allow unlimited (development mode)
    if not STRIPE_SECRET_KEY:
        return {
            "allowed": True,
            "remaining": 999,
            "tier": "development",
            "message": "Stripe not configured — unlimited access."
        }

    # Check if user has an active Stripe subscription
    if _has_active_subscription(user_email):
        return {
            "allowed": True,
            "remaining": 999,
            "tier": "pro",
            "message": "Pro subscriber — unlimited reports."
        }

    # Free tier: enforce monthly limit
    now = datetime.utcnow()
    usage = FREE_TIER_USAGE.get(user_email)

    if not usage or now > usage["reset_date"]:
        # New month — reset counter
        FREE_TIER_USAGE[user_email] = {
            "count": 0,
            "reset_date": now.replace(day=1) + timedelta(days=32)
        }
        FREE_TIER_USAGE[user_email]["reset_date"] = FREE_TIER_USAGE[user_email]["reset_date"].replace(day=1)
        usage = FREE_TIER_USAGE[user_email]

    remaining = FREE_TIER_LIMIT - usage["count"]

    if remaining <= 0:
        return {
            "allowed": False,
            "remaining": 0,
            "tier": "free",
            "message": f"Free tier limit reached ({FREE_TIER_LIMIT}/month). Upgrade to Pro for unlimited reports."
        }

    return {
        "allowed": True,
        "remaining": remaining,
        "tier": "free",
        "message": f"{remaining} free reports remaining this month."
    }


def record_usage(user_email: str):
    """Records that a user consumed one report generation."""
    if user_email in FREE_TIER_USAGE:
        FREE_TIER_USAGE[user_email]["count"] += 1


def _has_active_subscription(user_email: str) -> bool:
    """
    Checks Stripe for an active subscription.
    Returns True if the user is a paying Pro customer.
    """
    if not STRIPE_SECRET_KEY:
        return False

    try:
        import stripe
        stripe.api_key = STRIPE_SECRET_KEY

        # Search for customer by email
        customers = stripe.Customer.list(email=user_email, limit=1)
        if not customers.data:
            return False

        customer_id = customers.data[0].id

        # Check for active subscriptions
        subscriptions = stripe.Subscription.list(
            customer=customer_id,
            status="active",
            limit=1
        )
        return len(subscriptions.data) > 0

    except Exception as e:
        logger.warning(f"Stripe check failed for {user_email}: {e}")
        return False


def create_checkout_url(user_email: str) -> str:
    """
    Creates a Stripe Checkout Session URL for the user to subscribe.
    Returns the URL to redirect the user to.
    """
    if not STRIPE_SECRET_KEY or not STRIPE_PRICE_ID:
        return ""

    try:
        import stripe
        stripe.api_key = STRIPE_SECRET_KEY

        session = stripe.checkout.Session.create(
            customer_email=user_email,
            payment_method_types=["card"],
            line_items=[{
                "price": STRIPE_PRICE_ID,
                "quantity": 1,
            }],
            mode="subscription",
            success_url=os.getenv("RENDER_EXTERNAL_URL", "http://localhost:8000") + "/?payment=success",
            cancel_url=os.getenv("RENDER_EXTERNAL_URL", "http://localhost:8000") + "/?payment=cancelled",
        )
        return session.url

    except Exception as e:
        logger.error(f"Stripe checkout creation failed: {e}")
        return ""
