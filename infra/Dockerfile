# Postgres 17 + PostGIS 3 + pgvector, multi-arch (amd64 + arm64).
#
# Why this approach: the upstream `postgis/postgis` image is amd64-only, and the
# combined community images (imresamu/postgis, etc.) either lack arm64 or don't
# bundle pgvector. The official `postgres:17-bookworm` image is multi-arch and
# the PGDG apt repo it pulls from carries both `postgresql-17-postgis-3` and
# `postgresql-17-pgvector`, so we just install them.
FROM postgres:17-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        postgresql-17-postgis-3 \
        postgresql-17-pgvector \
    && rm -rf /var/lib/apt/lists/*
