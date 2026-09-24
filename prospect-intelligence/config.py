"""
Central configuration â€” all settings loaded from environment variables.
No secrets are ever hard-coded here.
"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- LLM (Gemini - free tier) ---
    gemini_api_key: str = "REPLACE_ME"
    gemini_model: str = "models/gemini-3.6-flash"           # fallback default
    gemini_llm_model: str = "models/gemini-3.5-flash-lite"
    gemini_embed_model: str = "models/gemini-embedding-001"

    # --- Web Search (Tavily - free tier) ---
    tavily_api_key: str = "REPLACE_ME"

    # --- Storage ---
    database_url: str = "sqlite+aiosqlite:///./data/prospect_intelligence.db"
    vector_store_path: str = "./data/vector_store"
    knowledge_base_path: str = "./data/knowledge_base"
    exports_path: str = "./data/exports"
    crm_sample_path: str = "./data/crm_sample/sample_crm.json"

    # --- Job settings ---
    duplicate_cooldown_hours: int = 24

    # --- Retry / backoff ---
    max_retries: int = 3
    backoff_base_seconds: float = 1.5

    # --- Logging ---
    log_level: str = "INFO"

    # --- Demo mode (no API keys required) ---
    demo_mode: bool = False

    # --- API Authentication ---
    api_key: str = ""


# Singleton â€” import `settings` everywhere
settings = Settings()
