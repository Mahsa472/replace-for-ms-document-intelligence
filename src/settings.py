"""Central configuration.

Sources (real environment variables always win):
- .devcontainer/.devcontainer.env -> Docling URL / API key (compose also injects
  these into the container; read here too so it works outside the container)
- src/credentials.env              -> LLM model, API key, base URL
"""

from __future__ import annotations

from functools import cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

SRC_DIR = Path(__file__).resolve().parent
REPO_DIR = SRC_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(
            REPO_DIR / ".devcontainer" / ".devcontainer.env",
            SRC_DIR / "credentials.env",
        ),
        env_file_encoding="utf-8",
        extra="ignore",
        env_ignore_empty=True,  # "LLM_BASE_URL=" counts as unset
    )

    # ---- LLM (credentials.env; any OpenAI-compatible endpoint) ----
    llm_model: str
    llm_api_key: SecretStr
    llm_base_url: str | None = None  # None -> api.openai.com

    # ---- Docling (.devcontainer.env) ----
    docling_base_url: str = "http://docling:5001"
    docling_api_key: SecretStr | None = None
    docling_timeout: float = 620  # a bit longer than DOCLING_SERVE_MAX_SYNC_WAIT (600)

    # ---- Paths ----
    data_dir: Path = SRC_DIR / "data"
    prompts_dir: Path = SRC_DIR / "prompts"

    @property
    def input_dir(self) -> Path:
        return self.data_dir / "input" / "pdf"

    @property
    def output_dir(self) -> Path:
        return self.data_dir / "output"

    @property
    def cache_dir(self) -> Path:
        return self.data_dir / "cache"

    @property
    def logs_dir(self) -> Path:
        return self.data_dir / "logs"


@cache
def get_settings() -> Settings:
    """Load settings once; fails fast with a clear error if a required value is missing."""
    return Settings()
