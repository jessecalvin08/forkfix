"""Secret-safe clients for Nebius Token Factory and Sandboxes.

Loads the private backend/.env only inside the local process. Nothing here
returns, logs, or serializes the API key.
"""

from __future__ import annotations

import os
from pathlib import Path

from contree_sdk import Contree
from contree_sdk.auth import IAMAuth
from contree_sdk.config import ContreeConfig
from dotenv import load_dotenv
from openai import AsyncOpenAI

TOKEN_FACTORY_BASE_URL = "https://api.tokenfactory.nebius.com/v1/"
ENV_FILE = Path(__file__).resolve().parents[1] / ".env"
REPORTS = Path(__file__).resolve().parents[1] / "reports"

DEFAULT_AGENT_MODEL = "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"
DEFAULT_JUDGE_MODEL = "nvidia/nemotron-3-super-120b-a12b"


class ConfigurationError(RuntimeError):
    pass


def _require(name: str) -> str:
    load_dotenv(ENV_FILE, override=False)
    value = os.environ.get(name, "").strip()
    if not value:
        raise ConfigurationError(f"{name} is missing. Add it only to backend/.env.")
    return value


def agent_model() -> str:
    load_dotenv(ENV_FILE, override=False)
    return os.environ.get("FORKFIX_AGENT_MODEL", "").strip() or DEFAULT_AGENT_MODEL


def judge_model() -> str:
    load_dotenv(ENV_FILE, override=False)
    return os.environ.get("FORKFIX_JUDGE_MODEL", "").strip() or DEFAULT_JUDGE_MODEL


def token_factory() -> AsyncOpenAI:
    return AsyncOpenAI(base_url=TOKEN_FACTORY_BASE_URL, api_key=_require("NEBIUS_API_KEY"), timeout=300, max_retries=5)


def sandboxes() -> Contree:
    return Contree(config=ContreeConfig(
        auth=IAMAuth(token=_require("NEBIUS_API_KEY"), project_id=_require("NEBIUS_PROJECT_ID")),
        transport_timeout=30,
        operation_run_timeout=900,
        operation_import_timeout=3600,
    ))
