"""Application configuration loader and settings management.

Supports Streamlit Cloud (st.secrets) with fallback to .env for local development.
"""

import os
from typing import Optional

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

import streamlit as st


def _get_secret(key: str, default: str = "") -> str:
    """Read a config value from st.secrets first, then os.environ/.env."""
    # 1. Streamlit Cloud secrets (highest priority)
    try:
        val = st.secrets.get(key, None)
        if val:
            return str(val).strip()
    except Exception:
        pass
    # 2. Environment variable / .env fallback
    return (os.getenv(key) or default).strip()


class AppConfig:
    """Central dynamic configuration class."""

    @staticmethod
    def _reload_env():
        # Load .env for local dev; no-op if python-dotenv is missing (Streamlit Cloud)
        if load_dotenv is not None:
            load_dotenv(override=True)

    @property
    def GEMINI_API_KEY(self) -> str:
        self._reload_env()
        return _get_secret("GEMINI_API_KEY") or _get_secret("GOOGLE_API_KEY")

    @property
    def GEMINI_MODEL(self) -> str:
        self._reload_env()
        return _get_secret("GEMINI_MODEL", "gemini-flash-lite-latest")

    @property
    def SUPABASE_URL(self) -> str:
        self._reload_env()
        return _get_secret("SUPABASE_URL") or _get_secret("NEXT_PUBLIC_SUPABASE_URL")

    @property
    def SUPABASE_KEY(self) -> str:
        self._reload_env()
        return (
            _get_secret("SUPABASE_KEY")
            or _get_secret("SUPABASE_ANON_KEY")
            or _get_secret("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY")
        )

    @property
    def SUPABASE_SERVICE_ROLE_KEY(self) -> str:
        self._reload_env()
        return _get_secret("SUPABASE_SERVICE_ROLE_KEY")

    @property
    def APP_ENV(self) -> str:
        return _get_secret("APP_ENV", "production")

    @property
    def MAX_UPLOAD_SIZE_MB(self) -> int:
        try:
            return int(_get_secret("MAX_UPLOAD_SIZE_MB", "15"))
        except ValueError:
            return 15

    @property
    def MAX_CHAT_CONTEXT_MESSAGES(self) -> int:
        try:
            return int(_get_secret("MAX_CHAT_CONTEXT_MESSAGES", "10"))
        except ValueError:
            return 10

    @property
    def DEFAULT_QUIZ_QUESTION_COUNT(self) -> int:
        try:
            return int(_get_secret("DEFAULT_QUIZ_QUESTION_COUNT", "5"))
        except ValueError:
            return 5

    def is_gemini_configured(self) -> bool:
        """Returns True if Gemini API key is configured."""
        k = self.GEMINI_API_KEY
        return bool(k and k != "your-gemini-api-key-here" and len(k) > 10)

    def is_supabase_configured(self) -> bool:
        """Returns True if Supabase URL and Key are configured."""
        u = self.SUPABASE_URL
        k = self.SUPABASE_KEY
        return bool(
            u
            and k
            and "your-project" not in u
            and "your-anon" not in k
            and u.startswith("https://")
        )

    def get_status_summary(self) -> dict:
        """Returns configuration status for dashboard / diagnostics."""
        return {
            "gemini_ready": self.is_gemini_configured(),
            "gemini_model": self.GEMINI_MODEL,
            "supabase_ready": self.is_supabase_configured(),
            "environment": self.APP_ENV,
            "max_upload_size_mb": self.MAX_UPLOAD_SIZE_MB,
        }


config = AppConfig()
