"""Billing routes — Stripe Checkout + webhook + user/subscription state.

Endpoints:
  POST /api/billing/checkout  → create a Stripe Checkout Session, return URL
  POST /api/billing/webhook   → handle subscription lifecycle events
  GET  /api/me                → return signed-in user + subscription state

The webhook is the source of truth: we never write subscription state from
the client. Even after a successful checkout redirect we wait for the
`checkout.session.completed` event before marking the user as active.
"""

from datetime import UTC, datetime

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request

from app.config import get_settings
from app.db import acquire
from app.services.auth import AuthUser, optional_user, require_user

router = APIRouter()


def _stripe_client() -> stripe.StripeClient:
    settings = get_settings()
    if not settings.stripe_secret_key:
        raise HTTPException(status_code=500, detail="stripe not configured")
    return stripe.StripeClient(settings.stripe_secret_key)


@router.get("/me")
async def me(user: AuthUser | None = Depends(optional_user)) -> dict:
    """Return the caller's identity + subscription state.

    Used by the frontend to decide whether to show "Sign up", "Subscribe", or
    the query UI. Returns 200 with `authenticated: false` for anonymous callers
    rather than 401 so the frontend can poll this freely on page load.
    """
    if user is None:
        return {"authenticated": False}

    async with acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT status, current_period_end
              FROM subscriptions
             WHERE user_id = $1
            """,
            user.user_id,
        )

    subscribed = False
    status_str = "none"
    period_end = None
    if row:
        status_str = row["status"]
        period_end = row["current_period_end"]
        if status_str == "active" and period_end and period_end > datetime.now(UTC):
            subscribed = True

    return {
        "authenticated": True,
        "user_id": user.user_id,
        "email": user.email,
        "subscribed": subscribed,
        "subscription_status": status_str,
        "current_period_end": period_end.isoformat() if period_end else None,
    }


@router.post("/billing/checkout")
async def create_checkout(user: AuthUser | None = Depends(optional_user)) -> dict:
    """Create a Stripe Checkout Session for the authed user."""
    auth_user = require_user(user)
    settings = get_settings()
    if not settings.stripe_price_id:
        raise HTTPException(status_code=500, detail="stripe price not configured")

    client = _stripe_client()

    # Reuse the customer if we've already seen them.
    async with acquire() as conn:
        existing = await conn.fetchrow(
            "SELECT stripe_customer_id FROM subscriptions WHERE user_id = $1",
            auth_user.user_id,
        )
    customer_id = existing["stripe_customer_id"] if existing else None

    session = client.checkout.sessions.create(
        params={
            "mode": "subscription",
            "line_items": [{"price": settings.stripe_price_id, "quantity": 1}],
            "success_url": f"{settings.public_app_url}?subscribed=1",
            "cancel_url": f"{settings.public_app_url}?subscribed=0",
            "customer": customer_id,
            "customer_email": auth_user.email if not customer_id else None,
            # Carry user_id through to the webhook so we can join Stripe → Supabase.
            "client_reference_id": auth_user.user_id,
            "metadata": {"user_id": auth_user.user_id},
            "subscription_data": {"metadata": {"user_id": auth_user.user_id}},
        }
    )
    return {"url": session.url}


@router.post("/billing/webhook")
async def stripe_webhook(request: Request) -> dict:
    """Handle Stripe lifecycle events. Verified via the webhook signing secret."""
    settings = get_settings()
    if not settings.stripe_webhook_secret:
        raise HTTPException(status_code=500, detail="webhook not configured")

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=sig_header,
            secret=settings.stripe_webhook_secret,
        )
    except (ValueError, stripe.SignatureVerificationError) as e:
        raise HTTPException(status_code=400, detail=f"invalid signature: {e}") from None

    event_type = event["type"]
    data = event["data"]["object"]

    if event_type == "checkout.session.completed":
        await _handle_checkout_completed(data)
    elif event_type in ("customer.subscription.updated", "customer.subscription.created"):
        await _handle_subscription_change(data)
    elif event_type == "customer.subscription.deleted":
        await _handle_subscription_deleted(data)
    # Other events are acknowledged but ignored.

    return {"received": True}


async def _handle_checkout_completed(session: dict) -> None:
    user_id = session.get("client_reference_id") or session.get("metadata", {}).get("user_id")
    if not user_id:
        return
    customer_id = session.get("customer")
    subscription_id = session.get("subscription")
    async with acquire() as conn:
        await conn.execute(
            """
            INSERT INTO subscriptions
              (user_id, stripe_customer_id, stripe_subscription_id, status, updated_at)
            VALUES ($1, $2, $3, 'incomplete', NOW())
            ON CONFLICT (user_id) DO UPDATE
              SET stripe_customer_id = EXCLUDED.stripe_customer_id,
                  stripe_subscription_id = EXCLUDED.stripe_subscription_id,
                  updated_at = NOW()
            """,
            user_id, customer_id, subscription_id,
        )


async def _handle_subscription_change(sub: dict) -> None:
    user_id = sub.get("metadata", {}).get("user_id")
    if not user_id:
        # Fall back to looking up by customer_id (events for existing subscriptions
        # may not carry the metadata if it wasn't set when the sub was created).
        customer_id = sub.get("customer")
        if not customer_id:
            return
        async with acquire() as conn:
            row = await conn.fetchrow(
                "SELECT user_id FROM subscriptions WHERE stripe_customer_id = $1",
                customer_id,
            )
        if not row:
            return
        user_id = str(row["user_id"])

    status = sub.get("status", "none")
    period_end_ts = sub.get("current_period_end")
    period_end = (
        datetime.fromtimestamp(period_end_ts, tz=UTC) if period_end_ts else None
    )

    async with acquire() as conn:
        await conn.execute(
            """
            INSERT INTO subscriptions
              (user_id, stripe_customer_id, stripe_subscription_id, status,
               current_period_end, updated_at)
            VALUES ($1, $2, $3, $4, $5, NOW())
            ON CONFLICT (user_id) DO UPDATE
              SET stripe_customer_id = EXCLUDED.stripe_customer_id,
                  stripe_subscription_id = EXCLUDED.stripe_subscription_id,
                  status = EXCLUDED.status,
                  current_period_end = EXCLUDED.current_period_end,
                  updated_at = NOW()
            """,
            user_id,
            sub.get("customer"),
            sub.get("id"),
            status,
            period_end,
        )


async def _handle_subscription_deleted(sub: dict) -> None:
    customer_id = sub.get("customer")
    if not customer_id:
        return
    async with acquire() as conn:
        await conn.execute(
            """
            UPDATE subscriptions
               SET status = 'canceled',
                   current_period_end = NULL,
                   updated_at = NOW()
             WHERE stripe_customer_id = $1
            """,
            customer_id,
        )
