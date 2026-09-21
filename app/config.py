"""Application Configuration module for Investment Research Swarm.

Loads environment variables with robust validation and sensible fallbacks.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration settings for Investment Research Swarm."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM Settings (Groq)
    GROQ_API_KEY: str = Field(default="", description="API key for Groq Cloud")
    GROQ_MODEL: str = Field(
        default="openai/gpt-oss-120b",
        description="Groq model for multi-agent reasoning",
    )

    # Tavily Web Research
    TAVILY_API_KEY: str = Field(default="", description="API key for Tavily search")

    # SEC EDGAR Settings
    SEC_USER_AGENT: str = Field(
        default="InvestmentResearchSwarm analyst@swarmresearch.io",
        description="Required User-Agent header conforming to SEC EDGAR Fair Access policy",
    )

    # Database Settings
    MYSQL_URL: str = Field(
        default="mysql+pymysql://root:password@localhost:3306/investment_swarm",
        description="MySQL connection string",
    )
    FALLBACK_SQLITE_URL: str = Field(
        default="sqlite:///./investment_swarm.db",
        description="Fallback SQLite database connection if MySQL is unavailable",
    )

    # LangSmith Observability
    LANGSMITH_API_KEY: str = Field(default="", description="LangSmith API key")
    LANGSMITH_TRACING: bool = Field(default=False, description="Enable LangSmith tracing")
    LANGSMITH_PROJECT: str = Field(
        default="investment-research-swarm",
        description="LangSmith project name",
    )

    # Server Settings
    APP_ENV: str = Field(default="development", description="Application environment")
    DEBUG: bool = Field(default=True, description="Enable debug mode")
    HOST: str = Field(default="0.0.0.0", description="API bind address")
    PORT: int = Field(default=8000, description="API bind port")

    # Research Swarm Boundaries
    MAX_CRITIC_RETRIES: int = Field(
        default=2,
        description="Maximum bounded retries when evidence is deemed insufficient",
    )
    REQUEST_TIMEOUT_SECONDS: int = Field(
        default=30,
        description="Timeout for external API calls in seconds",
    )

    def is_groq_configured(self) -> bool:
        """Check if Groq API key is set and non-empty."""
        return bool(self.GROQ_API_KEY and self.GROQ_API_KEY.strip() and not self.GROQ_API_KEY.startswith("your_"))

    def is_tavily_configured(self) -> bool:
        """Check if Tavily API key is set and non-empty."""
        return bool(self.TAVILY_API_KEY and self.TAVILY_API_KEY.strip() and not self.TAVILY_API_KEY.startswith("your_"))

    def setup_langsmith(self) -> None:
        """Configure LangSmith environment variables if enabled."""
        if self.LANGSMITH_TRACING and self.LANGSMITH_API_KEY:
            os.environ["LANGCHAIN_TRACING_V2"] = "true"
            os.environ["LANGCHAIN_API_KEY"] = self.LANGSMITH_API_KEY
            os.environ["LANGCHAIN_PROJECT"] = self.LANGSMITH_PROJECT


@lru_cache()
def get_settings() -> Settings:
    """Return cached singleton instance of application settings."""
    settings = Settings()
    settings.setup_langsmith()
    return settings
