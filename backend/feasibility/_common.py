"""Shared setup for the feasibility probes. Loads backend/.env; never prints it."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from contree_sdk import Contree, ContreeSync
from contree_sdk.auth import IAMAuth
from contree_sdk.config import ContreeConfig
from dotenv import load_dotenv

from forkfix.config import ENV_FILE

RAW = {"stdout": bytes, "stderr": bytes}
REPORTS = Path(__file__).resolve().parents[1] / "reports" / "feasibility"


def _config() -> ContreeConfig:
    load_dotenv(ENV_FILE, override=False)
    project_id = os.environ.get("NEBIUS_PROJECT_ID", "").strip()
    api_key = os.environ.get("NEBIUS_API_KEY", "").strip()
    if not project_id or not api_key:
        raise SystemExit("Set NEBIUS_PROJECT_ID and NEBIUS_API_KEY in backend/.env first.")
    return ContreeConfig(
        auth=IAMAuth(token=api_key, project_id=project_id),
        transport_timeout=30,
        operation_run_timeout=900,
        operation_import_timeout=3600,
    )


def sandbox_sync() -> ContreeSync:
    return ContreeSync(config=_config())


def sandbox_async() -> Contree:
    return Contree(config=_config())


def text(output: bytes | str | None) -> str:
    if output is None:
        return ""
    return output.decode("utf-8", errors="replace") if isinstance(output, bytes) else output


def save_report(name: str, data: dict) -> Path:
    """Write evidence to ignored reports/feasibility/ so results are not only in scrollback."""
    REPORTS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = REPORTS / f"{stamp}-{name}.json"
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    return path
