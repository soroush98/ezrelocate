---
name: fastapi-practices
description: >-
  Production FastAPI idioms — app/router structure, dependency injection,
  lifespan & resource pools, pydantic request/response models, async correctness,
  error handling, auth, and testing. Apply when writing, reviewing, or refactoring
  FastAPI services: routers, endpoints, Depends, lifespan, pydantic-settings, or
  ASGI apps. Complements python-practices (language idioms) and
  engineering-principles (stack-agnostic rules); this is the FastAPI layer.
---

# FastAPI Practices

Production-grade FastAPI (target **0.115+**, Pydantic **v2**, Python 3.12+). Defer
to `python-practices` for language idioms and `engineering-principles` for the
stack-agnostic rules. Match the existing app's conventions first.

## Structure

- **Routers per domain** (`APIRouter`), mounted with a `prefix` and `tags` from a
  thin `main.py`. Keep route functions as transport glue: parse/validate → call a
  service → shape the response. Business logic lives in `services/`, not in the
  route.
- **Settings via `pydantic-settings`** (`BaseSettings`) behind an
  `@lru_cache get_settings()`. Read env once; never scatter `os.getenv` through the
  code. Provide a `Depends(get_settings)` seam so tests can override it.

## Lifespan & shared resources

- **Use the `lifespan` async context manager**, not the deprecated
  `@app.on_event`. Open pools/clients on startup, close them on shutdown.
- **Create DB/HTTP pools once** (e.g. `asyncpg.create_pool`) and store on
  `app.state` or a module-level pool with an `acquire()` context manager. One pool
  per process; size it to the real connection budget.

## Dependency injection (the testability seam)

- **Inject collaborators with `Depends`** — auth, DB handles, settings, external
  clients. This is what lets a unit test run without the network.
- **Prefer DI over module-level singletons** for anything you'd want to fake in a
  test. A lazy client singleton is fine for a process-wide SDK, but expose it
  through a dependency so `app.dependency_overrides[get_client] = fake` works.
- **`yield` dependencies** for setup/teardown (a transaction per request, a scoped
  client). Cleanup after `yield` runs even on error.
- **B008 is a false positive here.** `def route(x = Depends(...))` /
  `Header(...)` / `Query(...)` in defaults is correct FastAPI — add them to ruff's
  `flake8-bugbear.extend-immutable-calls`, don't "fix" them.

## Request / response contracts

- **Pydantic models for every request body and a `response_model` for output.**
  Validate at the boundary with `Field` constraints (`min_length`, `ge`, `le`,
  enums) and reject early — don't hand-check in the body.
- **`response_model` filters the output** — never leak internal/ORM fields or
  secrets by returning raw rows. Use a separate read model.
- **Type `Query`/`Path`/`Header` params** with constraints; let FastAPI generate
  the OpenAPI schema, and generate the client's types from that spec.

## Async correctness

- **`async def` routes for I/O**, with async drivers (asyncpg, httpx) — a blocking
  call in an async route stalls the whole event loop. If you must call sync/CPU
  work, hand it to a threadpool (`run_in_threadpool`) or a process pool.
- **Propagate deadlines and bound concurrency** on every downstream call (see
  engineering-principles). A request that fans out must cap fan-out and time out.

## Errors

- **Raise `HTTPException` with a structured `detail`** (`{"code", "message"}`) so
  clients branch on a stable code, not prose. Map domain errors to status codes at
  the boundary; **don't leak stack traces or internals** to the client.
- **Register exception handlers** for your typed domain exceptions instead of
  try/except in every route. A timed-out/refused upstream is a 502/503, not a 500.

## Security

- **Authn/authz in a dependency, enforced server-side.** Authentication ≠
  authorization — check the caller may do *this* operation, fail closed. Never
  trust that the client gated it.
- **Lock down CORS** to known origins and methods; `allow_origins=["*"]` with
  credentials is a bug. Keep secrets server-side; validate webhooks' signatures.

## Testing

- **`httpx.AsyncClient` with `ASGITransport`** (or `TestClient`) against the app;
  override DB/external-client dependencies with `app.dependency_overrides` so tests
  don't hit the network.
- **Pure service/SQL-builder functions get plain unit tests** — keep the
  network-free core (filter building, parsing, validation) testable without the ASGI
  stack. `pytest-asyncio` for async paths; a regression test per bug fix.
