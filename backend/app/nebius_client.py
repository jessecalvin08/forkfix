"""Small, secret-safe adapter for Nebius Token Factory.

This module loads the private backend/.env file only inside the local backend
process. It never returns, logs, or serializes the API key.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Literal

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from .guardrails import MANDATORY_GUARDRAILS
from .models import Policy


TOKEN_FACTORY_BASE_URL = "https://api.tokenfactory.nebius.com/v1/"
ENV_FILE = Path(__file__).resolve().parents[1] / ".env"

POLICY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "version": {"type": "string"},
        "rules": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "id": {"type": "string"},
                    "effect": {"type": "string", "enum": ["allow", "deny", "approval_required"]},
                    "tool": {"type": "string"},
                    "path_patterns": {"type": "array", "items": {"type": "string"}},
                    "reason": {"type": "string"},
                },
                "required": ["id", "effect", "tool", "path_patterns", "reason"],
            },
        },
    },
    "required": ["version", "rules"],
}

class NebiusConfigurationError(RuntimeError):
    """Raised when local Nebius configuration has not been completed."""


class GeneratedPolicyRule(BaseModel):
    """Require every field explicitly; missing paths must never grant all paths."""

    model_config = ConfigDict(extra="forbid", strict=True)
    id: str = Field(min_length=1)
    effect: Literal["allow", "deny", "approval_required"]
    tool: Literal["read_file", "write_file", "run_tests", "http_request", "delete_file"]
    path_patterns: list[str] = Field(min_length=1)
    reason: str

    @model_validator(mode="after")
    def require_safe_mvp_tool_targets(self) -> "GeneratedPolicyRule":
        """Keep generated policy within the MVP's non-shell tool contract."""
        if self.tool == "run_tests" and self.path_patterns != ["pytest"]:
            raise ValueError("run_tests must allow exactly pytest in this MVP")
        if any(
            not pattern
            or "\x00" in pattern
            or pattern.startswith(("/", "\\"))
            or "://" in pattern
            or ".." in pattern.replace("\\", "/").split("/")
            for pattern in self.path_patterns
        ):
            raise ValueError("policy paths must be safe repository-relative globs")
        return self


class GeneratedPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    version: Literal["1"]
    rules: list[GeneratedPolicyRule] = Field(min_length=1, max_length=40)


def load_local_configuration() -> None:
    """Load backend/.env without overriding intentionally supplied env vars."""
    load_dotenv(ENV_FILE, override=False)


def has_api_key() -> bool:
    load_local_configuration()
    return bool(os.environ.get("NEBIUS_API_KEY", "").strip())


def token_factory_client() -> OpenAI:
    load_local_configuration()
    api_key = os.environ.get("NEBIUS_API_KEY", "").strip()
    if not api_key:
        raise NebiusConfigurationError(
            "NEBIUS_API_KEY is missing. Add it only to backend/.env and restart the backend."
        )
    return OpenAI(base_url=TOKEN_FACTORY_BASE_URL, api_key=api_key, timeout=60, max_retries=0)


def configured_model() -> str:
    load_local_configuration()
    model = os.environ.get("NEBIUS_MODEL", "").strip()
    if not model:
        raise NebiusConfigurationError(
            "NEBIUS_MODEL is missing. Run the Token Factory preflight and copy the exact NVIDIA model ID into backend/.env."
        )
    if model.startswith("NEBIUS_MODEL="):
        raise NebiusConfigurationError(
            "NEBIUS_MODEL contains a repeated assignment. Use NEBIUS_MODEL=<model identifier> only once in backend/.env, then restart the backend."
        )
    return model


def available_models() -> list[str]:
    """Return only public model identifiers; never return account credentials."""
    models = token_factory_client().models.list()
    return sorted(model.id for model in models.data if model.id)


def nvidia_model_candidates(model_ids: list[str]) -> list[str]:
    """Find the current NVIDIA/Nemotron choices without hard-coding an old ID."""
    return [
        model_id
        for model_id in model_ids
        if "nvidia" in model_id.lower() or "nemotron" in model_id.lower()
    ]


def compile_policy(policy_text: str) -> tuple[Policy, str, str]:
    """Make one bounded schema request and validate a draft for human review."""
    model = configured_model()
    request = {
        "model": model,
        "temperature": 0,
        "max_tokens": 4096,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You compile a developer's plain-language coding-agent authority into RuleBranch policy JSON. "
                    "Return only the supplied schema. Preserve every explicit restriction. Never invent new authority. "
                    "Use the smallest practical tool vocabulary: read_file, write_file, run_tests, http_request, delete_file. "
                    "Unknown actions are denied by the local policy engine. "
                    "Use version '1' and give every rule a unique ID. Rules beginning 'rulebranch-' are reserved. "
                    "Paths are repository-relative globs: directories use src/** or tests/**. "
                    "CRITICAL: if, and only if, the developer permits tests, the complete run_tests rule must use "
                    "tool 'run_tests' and path_patterns exactly ['pytest']. Never use '*', '**', 'tests/**', "
                    "a shell command, or any other test target for run_tests. "
                    "Return concise JSON only. JSON Schema: " + json.dumps(POLICY_SCHEMA)
                ),
            },
            {"role": "user", "content": policy_text},
        ],
    }
    client = token_factory_client()
    completion = client.chat.completions.create(
        **request,
        response_format={
            "type": "json_schema",
            "json_schema": {"name": "rulebranch_policy", "strict": True, "schema": POLICY_SCHEMA},
        },
    )
    response_mode = "json_schema"
    if not completion.choices:
        raise ValueError("The selected model returned no choices; the current policy was kept.")
    if getattr(completion.choices[0], "finish_reason", None) == "length":
        raise ValueError("The response reached its output limit. No draft was accepted; do not keep retrying.")
    message = completion.choices[0].message
    if message.refusal:
        raise ValueError("The selected model refused to compile this policy.")
    if not message.content:
        raise ValueError("The selected model returned no policy content.")
    try:
        generated = GeneratedPolicy.model_validate_json(message.content)
        compiled = Policy.model_validate(generated.model_dump())
    except ValidationError as error:
        # Pydantic's raw errors can include model content. Return only a
        # deliberately chosen, non-sensitive explanation to the browser.
        messages = {str(item.get("msg", "")) for item in error.errors()}
        if any("run_tests must allow exactly pytest" in message for message in messages):
            raise ValueError(
                "The model tried to grant a test command other than pytest. RuleBranch rejected it; no draft was saved."
            ) from error
        if any("safe repository-relative globs" in message for message in messages):
            raise ValueError(
                "The model returned an unsafe path pattern. RuleBranch rejected it; no draft was saved."
            ) from error
        raise ValueError("The selected model returned an invalid policy shape. No draft was saved.") from error

    reserved_ids = {rule.id for rule in MANDATORY_GUARDRAILS}
    generated_rules = [rule for rule in compiled.rules if rule.id not in reserved_ids]
    if len({rule.id for rule in generated_rules}) != len(generated_rules):
        raise ValueError("The selected model returned duplicate rule IDs; the current policy was kept.")
    guards = [rule.model_copy(deep=True) for rule in MANDATORY_GUARDRAILS]
    return Policy(version=compiled.version, rules=[*guards, *generated_rules]), model, response_mode
