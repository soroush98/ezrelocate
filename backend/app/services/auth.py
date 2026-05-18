"""Auth helpers — Supabase JWT verification + client-IP extraction.

Supabase signs access tokens with HS256 using the project's JWT secret
(Project Settings → API → JWT Settings → JWT Secret). The browser sends
the token as `Authorization: Bearer <token>`; we verify it here.

We do NOT require auth on /api/query — anonymous callers fall through to
the IP-quota path. The auth dependency returns None for anonymous requests
and an AuthUser object for valid tokens.
"""

from dataclasses import dataclass

import jwt
from fastapi import Header, HTTPException, Request

from app.config import get_settings


@dataclass(frozen=True)
class AuthUser:
    user_id: str
    email: str | None


def get_client_ip(request: Request) -> str:
    """Best-effort client IP.

    Browser → Vercel (rewrite) → Fly → us. Vercel sets X-Forwarded-For with
    the real client IP as the first entry, then proxies append. We take the
    leftmost value. This is spoofable if someone hits the Fly URL directly,
    but for a portfolio-scale rate limit that's an acceptable risk.
    """
    xff = request.headers.get("x-forwarded-for")
    if xff:
        first = xff.split(",")[0].strip()
        if first:
            return first
    # Fly's own proxy header — used when bypassing Vercel
    fly_ip = request.headers.get("fly-client-ip")
    if fly_ip:
        return fly_ip
    return request.client.host if request.client else "unknown"


def optional_user(authorization: str | None = Header(default=None)) -> AuthUser | None:
    """FastAPI dependency: returns the authed user if a valid JWT is present, else None.

    Invalid / expired tokens raise 401 — we don't silently downgrade to anonymous
    because that would mask client bugs (e.g. an expired session token still being
    sent). Use this dependency on routes that allow both anonymous and authed access.
    """
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="invalid authorization header")

    secret = get_settings().supabase_jwt_secret
    if not secret:
        # Misconfigured server — fail loudly rather than treating everyone as anon.
        raise HTTPException(status_code=500, detail="auth not configured")

    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            audience="authenticated",
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="token expired") from None
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="invalid token") from None

    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status_code=401, detail="token missing sub")
    return AuthUser(user_id=sub, email=payload.get("email"))


def require_user(user: AuthUser | None) -> AuthUser:
    """For routes that require auth (e.g. billing endpoints)."""
    if user is None:
        raise HTTPException(status_code=401, detail="authentication required")
    return user
