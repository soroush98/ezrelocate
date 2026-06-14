# EZrelocate — Project Notes & Learnings

A running log of **empirical, non-obvious** things we've learned building this
project — model experiments (what was slow / inaccurate / expensive), decisions and
their rationale, and cross-cutting gotchas. The goal is to **not relearn the same
lesson twice**.

Keep entries dated and concrete. This is for things you can't recover by reading the
code or git history — write down the *why* and the *what we ruled out*, not the *what*.

---

## Models in use (current)

| Component | Model | Dim / params | Where set | Notes |
|---|---|---|---|---|
| Query parsing (NL → filters) | `claude-opus-4-7` | `max_tokens=512` | `ANTHROPIC_MODEL` (config.py / .env / workflows) | 30s request deadline |
| Recommendation generation | `claude-opus-4-7` | `max_tokens=900` | same | 45s request deadline |
| Embeddings (listing + query) | `voyage-3-large` | **1024-dim** | `VOYAGE_MODEL` | 20s deadline on the query path |

> ⚠️ **Embedding dimension is load-bearing.** `voyage-3-large` outputs 1024-dim
> vectors, which must match `desc_embed VECTOR(1024)` in `db/schema.sql`. Changing the
> embedding model means changing the column type **and** re-embedding every listing.

---

## Model experiments & evaluation log

Append a dated entry whenever we try a model/prompt/param and learn something —
especially when something was **slow, inaccurate, or too expensive** and we backed it
out. Template:

```
### YYYY-MM-DD — <what we tried>
- Context: <task — parsing / generation / embedding>
- Result: <slow? inaccurate? costly? how measured>
- Decision: <kept / reverted / switched to X>
- Why: <the reasoning so we don't retry it blindly>
```

### 2026-06-14 — Local Ollama model (self-hosted LLM)
- Context: evaluated running the LLM locally via Ollama instead of hosted Claude.
- Result: **too slow on Mac** — local inference latency wasn't acceptable for the
  interactive query path.
- Decision: reverted; use hosted Claude (`claude-opus-4-7`) for parsing + generation.
- Why: query latency is user-facing, and local Ollama on Mac dev hardware couldn't
  meet it. Don't retry a self-hosted LLM on the live request path on dev hardware.
  _(Which Ollama model + rough latency: fill in if remembered.)_

<!-- TODO: still to record — where Claude mis-parses queries, any embedding models
     that under-retrieved, cost/latency numbers. Tell me and I'll log them. -->

---

## Known inaccuracies & limitations

- _(to fill in)_ Query-parsing failure modes — phrasings the parser mis-maps
  (e.g. named-landmark vs. generic-amenity confusion, province/city edge cases).
- _(to fill in)_ Retrieval gaps — where the lifestyle embedding rerank under- or
  over-weights vs. the hard SQL filters.
- `get_client_ip` trusts the leftmost `X-Forwarded-For`; spoofable if someone hits
  the Fly URL directly instead of going through Vercel. Accepted for portfolio-scale
  rate limiting (`app/services/auth.py`).
- Supabase JWTs live in browser storage (XSS-readable), not httpOnly cookies — a
  known tradeoff for this app's scale.

---

## Cross-cutting seams — change these together

One concept, edited in more than one place. If you touch one, touch the others:

- **Amenity categories:** `app/models.py::AmenityCategory` ↔
  `etl/load_osm_pois_geofabrik.py::CATEGORIES` ↔ `frontend/src/lib/types.ts`.
- **Embedding dimension:** `db/schema.sql` (`VECTOR(1024)`) ↔ the Voyage model choice.
- **Default model ids:** `app/config.py` ↔ `.env.example` ↔ both GitHub workflows
  (`refresh.yml`, `osm-pois.yml`).

---

## Decisions & rationale

- **POI ingest is weekly (Geofabrik offline `.pbf`), not nightly.** The public
  Overpass API hard-rate-limits CI IPs; POIs are static infra that changes slowly, so
  the nightly run only recomputes distances against POIs already in the DB.
- **Quota gate runs before any LLM/embedding spend** so a rejected request costs zero
  tokens (`app/services/query.py` → `enforce_query_quota`).
- **Per-request deadlines on every model/embedding call** (added 2026-06-14) so a slow
  upstream returns a retryable 503 instead of hanging or 500ing.
