"""Shared test setup.

These are hermetic unit tests — they never touch the DB or any upstream API.
We still set dummy credentials so that any accidental ``get_settings()`` during
import/collection constructs cleanly instead of raising on a missing env var.
"""

import os

os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-anthropic-key")
os.environ.setdefault("VOYAGE_API_KEY", "test-voyage-key")
