# EZrelocate

Canada-wide rental recommender: FastAPI backend (Postgres + PostGIS + pgvector,
Claude + Voyage embeddings) and a Next.js frontend. Deployed on Fly.io (backend) —
deploy is manual via `flyctl deploy`.

## Before working here, read

- **[docs/PROJECT_NOTES.md](docs/PROJECT_NOTES.md)** — running log of empirical
  learnings: model experiments (what was slow / inaccurate / costly), known
  limitations, cross-cutting seams that must change together, and key decisions.
  **Check it before model/prompt/schema work, and append to it when you learn
  something worth remembering.**

## Conventions

- Engineering practices live in [.claude/skills/](.claude/skills/) — the
  project-local copies take precedence over the user-level skills.
