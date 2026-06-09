from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import close_pool, init_pool
from app.routes import billing as billing_routes
from app.routes import nearby as nearby_routes
from app.routes import query as query_routes
from app.routes import stats as stats_routes


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_pool()
    yield
    await close_pool()


app = FastAPI(title="EZrelocate", version="0.1.0", lifespan=lifespan)

# CORS is here for direct browser hits to the backend (e.g. local dev calling
# http://localhost:8000 from http://localhost:3000). In prod the Next.js rewrite
# proxies server-side, so the browser only ever talks to the Vercel origin and
# CORS isn't exercised. Set CORS_ORIGINS as a comma-separated env var if you
# ever bypass the rewrite.
import os
cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in cors_origins if o.strip()],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(query_routes.router, prefix="/api")
app.include_router(nearby_routes.router, prefix="/api")
app.include_router(billing_routes.router, prefix="/api")
app.include_router(stats_routes.router, prefix="/api")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
