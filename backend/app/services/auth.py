"""Auth helpers — Supabase JWT verification + client-IP extraction.

Supabase signs access tokens with either:
  - HS256 (legacy) using the project's shared JWT secret, or
  - RS256 / ES256 (default for newer projects) using asymmetric keys, with
    public keys published at <project>/auth/v1/.well-known/jwks.json.

We support both: parse the JWT header to detect the algorithm, then verify
with the shared secret (HS) or via JWKS (asymmetric). PyJWKClient caches
the public keys, so verification is one round-trip on first use and cached
in-process afterward.

We do NOT require auth on /api/query — anonymous callers fall through to
the IP-quota path. The auth dependency returns None for anonymous requests
and an AuthUser object for valid tokens.
"""

from dataclasses import dataclass

import jwt
from fastapi import Header, HTTPException, Request
from jwt import PyJWKClient

from app.config import get_settings

_jwks_client: PyJWKClient | None = None


def _get_jwks_client() -> PyJWKClient | None:
    """Lazy singleton — only build the JWKS client if SUPABASE_URL is set."""
    global _jwks_client
    if _jwks_client is not None:
        return _jwks_client
    url = get_settings().supabase_url.rstrip("/")
    if not url:
        return None
    _jwks_client = PyJWKClient(f"{url}/auth/v1/.well-known/jwks.json")
    return _jwks_client


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

    # Peek at the JWT header to pick the right verification path.
    try:
        unverified = jwt.get_unverified_header(token)
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="malformed token") from None
    alg = unverified.get("alg", "")

    settings = get_settings()
    try:
        if alg == "HS256":
            secret = settings.supabase_jwt_secret
            if not secret:
                raise HTTPException(
                    status_code=500,
                    detail="auth not configured (need SUPABASE_JWT_SECRET)",
                )
            payload = jwt.decode(
                token, secret, algorithms=["HS256"], audience="authenticated"
            )
        elif alg in ("RS256", "ES256"):
            jwks = _get_jwks_client()
            if jwks is None:
                raise HTTPException(
                    status_code=500,
                    detail="auth not configured (asymmetric JWT received but SUPABASE_URL unset)",
                )
            signing_key = jwks.get_signing_key_from_jwt(token)
            payload = jwt.decode(
                token, signing_key.key, algorithms=[alg], audience="authenticated"
            )
        else:
            raise HTTPException(status_code=401, detail=f"unsupported alg: {alg}")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="token expired") from None
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=f"invalid token: {e}") from None

    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status_code=401, detail="token missing sub")
    return AuthUser(user_id=sub, email=payload.get("email"))


def require_user(user: AuthUser | None) -> AuthUser:
    """For routes that require auth (e.g. billing endpoints)."""
    if user is None:
        raise HTTPException(status_code=401, detail="authentication required")
    return user
