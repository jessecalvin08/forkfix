"""Feasibility check 0 (free): Sandbox token limits and available NVIDIA models.

Makes two read-only calls: ConTree ``get_token_info()`` and Token Factory
``models.list()``. Neither spawns a sandbox or generates tokens. Prints no
credentials.

    .\\.venv\\Scripts\\python.exe -m feasibility.check_access
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from openai import OpenAI

from forkfix.config import TOKEN_FACTORY_BASE_URL

from dotenv import load_dotenv

from forkfix.config import ENV_FILE

from ._common import sandbox_sync


def main() -> None:
    info = sandbox_sync().get_token_info()
    expiry = None
    if info.token_expiration:
        expiry = datetime.fromtimestamp(info.token_expiration, tz=timezone.utc).isoformat()
    print(json.dumps({
        "token_expires_utc": expiry,
        "permissions": info.permissions,
        "limits": info.limits,
        "operations_stat": info.operations_stat,
    }, indent=2, default=str))
    load_dotenv(ENV_FILE, override=False)
    client = OpenAI(base_url=TOKEN_FACTORY_BASE_URL, api_key=os.environ["NEBIUS_API_KEY"].strip())
    models = sorted(m.id for m in client.models.list().data if "nvidia" in m.id.lower() or "nemotron" in m.id.lower())
    print("NVIDIA models:", json.dumps(models, indent=2))


if __name__ == "__main__":
    main()
