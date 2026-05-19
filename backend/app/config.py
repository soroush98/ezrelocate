from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = Field(alias="DATABASE_URL")

    anthropic_api_key: str = Field(alias="ANTHROPIC_API_KEY")
    anthropic_model: str = Field(default="claude-opus-4-7", alias="ANTHROPIC_MODEL")

    voyage_api_key: str = Field(alias="VOYAGE_API_KEY")
    voyage_model: str = Field(default="voyage-3-large", alias="VOYAGE_MODEL")

    app_env: str = Field(default="dev", alias="APP_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # --- Auth (Supabase) -----------------------------------------------------
    # Supabase project URL (e.g. https://abcd.supabase.co). Used to fetch the
    # JWKS endpoint for asymmetric-key projects (RS256 / ES256).
    supabase_url: str = Field(default="", alias="SUPABASE_URL")

    # JWT secret from Supabase project settings → API → JWT Settings → JWT Secret.
    # Used for legacy HS256 projects. Newer projects use asymmetric keys (RS256/
    # ES256) and don't need this — the backend fetches the public key via JWKS.
    supabase_jwt_secret: str = Field(default="", alias="SUPABASE_JWT_SECRET")

    # --- Stripe --------------------------------------------------------------
    stripe_secret_key: str = Field(default="", alias="STRIPE_SECRET_KEY")
    stripe_webhook_secret: str = Field(default="", alias="STRIPE_WEBHOOK_SECRET")
    stripe_price_id: str = Field(default="", alias="STRIPE_PRICE_ID")

    # --- Quotas --------------------------------------------------------------
    anon_ip_lifetime_limit: int = Field(default=5, alias="ANON_IP_LIFETIME_LIMIT")
    subscriber_daily_limit: int = Field(default=50, alias="SUBSCRIBER_DAILY_LIMIT")

    # --- URLs (for Stripe Checkout redirects) --------------------------------
    public_app_url: str = Field(default="http://localhost:3000", alias="PUBLIC_APP_URL")


@lru_cache
def get_settings() -> Settings:
    return Settings()
