"""
Central configuration — all settings loaded from environment variables.
No secrets are ever hard-coded here.
"""
from __future__ import annotations

import os
from pydantic import Field, AliasChoices, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- LLM (Gemini - free tier) ---
    gemini_api_key: str = Field(
        default="REPLACE_ME",
        validation_alias=AliasChoices(
            "GEMINI_API_KEY", "GOOGLE_API_KEY", "GEMINI_KEY", "gemini_api_key", "google_api_key"
        ),
    )
    gemini_model: str = "gemini-flash-latest"
    gemini_llm_model: str = "gemini-flash-latest"
    gemini_embed_model: str = "text-embedding-004"

    # --- Web Search (Tavily - free tier) ---
    tavily_api_key: str = Field(
        default="REPLACE_ME",
        validation_alias=AliasChoices(
            "TAVILY_API_KEY", "TAVILY_KEY", "tavily_api_key", "tavily_key"
        ),
    )

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

    @field_validator("gemini_api_key", "tavily_api_key", mode="before")
    @classmethod
    def clean_secret_keys(cls, v: str | None) -> str:
        if v is None:
            return "REPLACE_ME"
        cleaned = str(v).strip().strip("'").strip('"').strip()
        return cleaned or "REPLACE_ME"


# Singleton — import `settings` everywhere
settings = Settings()
