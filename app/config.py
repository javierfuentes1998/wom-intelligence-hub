from pathlib import Path
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[1]

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(ROOT.parent / "wom_chatbot" / ".env", ROOT / ".env"), env_prefix="WOM_", extra="ignore")
    env: str = "development"
    database_url: str = f"sqlite:///{(ROOT / 'data' / 'wom_hub.db').as_posix()}"
    secret_key: str = "demo-only-change-me"
    demo_admin_password: str | None = None
    llm_api_key: str | None = None
    gemini_api_key: str | None = Field(default=None, validation_alias=AliasChoices("GEMINI_API_KEY","WOM_GEMINI_API_KEY"))
    gemini_model: str = Field(default="gemini-2.5-flash", validation_alias=AliasChoices("GEMINI_MODEL","WOM_GEMINI_MODEL"))
    llm_timeout_seconds: int = 20
    llm_max_attempts: int = 2
    timezone: str = "Europe/Madrid"
    demo_seed: int = 20260929
    google_business_client_id: str | None = None
    google_business_client_secret: str | None = None
    google_business_refresh_token: str | None = None
    google_business_access_token: str | None = None
    google_business_redirect_uri: str = "http://127.0.0.1:8011/api/reviews/oauth/callback"
    google_business_account_id: str | None = None
    review_sync_interval_minutes: int = 360
    review_analyzer_version: str = "1.1.0"
    review_min_confidence: float = 0.55
    reviews_source: str = "demo"
    review_demo_seed: int = 2701
    review_demo_count: int = 720
    alerts_min_sample: int = 8
    alerts_revenue_deviation: float = 18.0
    alerts_cancellation_deviation: float = 35.0
    alerts_daily_summary_time: str = "09:00"

settings = Settings()
