"""Guardrails every compiled policy carries, whatever the model wrote.

Kept apart from ``nebius_client`` so the hand-written demo policy and the
validation matrix can share the same protected paths without importing the
provider SDK.
"""

from __future__ import annotations

from .models import PolicyRule, RuleEffect


# Secrets, credentials, key material and repository metadata. The same list
# guards reads and writes: an agent that may write `.env` or `.git/hooks/*` has
# the authority to plant credentials or code that runs outside the fixture.
PROTECTED_PATH_PATTERNS = [
    ".env",
    ".env.*",
    "**/.env",
    "**/.env.*",
    ".git/**",
    "**/.git/**",
    "*.pem",
    "*.key",
    "*.p12",
    "*.pfx",
    "**/id_rsa*",
    "**/id_ed25519*",
    ".ssh/**",
    "**/.ssh/**",
    ".aws/**",
    "**/.aws/**",
    ".netrc",
    "**/.netrc",
    "*credentials.json",
]

MANDATORY_GUARDRAILS = [
    PolicyRule(
        id="rulebranch-deny-secret-files",
        effect=RuleEffect.DENY,
        tool="read_file",
        path_patterns=list(PROTECTED_PATH_PATTERNS),
        reason="Secrets and repository metadata are outside the coding agent's authority.",
    ),
    PolicyRule(
        id="rulebranch-deny-protected-writes",
        effect=RuleEffect.DENY,
        tool="write_file",
        path_patterns=list(PROTECTED_PATH_PATTERNS),
        reason="The coding agent may not plant secrets or alter repository metadata.",
    ),
    PolicyRule(
        id="rulebranch-deny-network-egress",
        effect=RuleEffect.DENY,
        tool="http_request",
        path_patterns=["**"],
        reason="The coding-agent fixture has no authority to send network requests.",
    ),
    PolicyRule(
        id="rulebranch-approval-delete",
        effect=RuleEffect.APPROVAL_REQUIRED,
        tool="delete_file",
        path_patterns=["**"],
        reason="Destructive file actions require a developer approval checkpoint.",
    ),
]
