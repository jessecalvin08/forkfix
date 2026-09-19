from __future__ import annotations

from fnmatch import fnmatchcase
from typing import Any

from .models import Decision, Policy, PolicyRule, RuleEffect, ToolCall


def _normalise_repository_path(value: Any) -> str | None:
    """Return a safe, repository-relative path, or fail closed."""
    if not isinstance(value, str) or not value or "\x00" in value:
        return None
    path = value.replace("\\", "/")
    if path.startswith("/") or path.startswith("//") or "://" in path or (len(path) >= 2 and path[1] == ":"):
        return None
    parts = path.split("/")
    if any(part == ".." for part in parts):
        return None
    normalised = "/".join(part for part in parts if part not in {"", "."})
    return normalised or None


def _normalise_pattern(value: Any) -> str | None:
    """Validate a repository-relative policy glob without resolving traversal."""
    if not isinstance(value, str) or not value or "\x00" in value:
        return None
    pattern = value.replace("\\", "/")
    if pattern.startswith("/") or pattern.startswith("//") or "://" in pattern or (len(pattern) >= 2 and pattern[1] == ":"):
        return None
    if any(part == ".." for part in pattern.split("/")):
        return None
    return pattern


def _path_matches(pattern: str, path: str) -> bool:
    """Support simple repository-relative policy globs for the MVP.

    ``fnmatchcase`` keeps the answer identical on every operating system;
    ``fnmatch`` would fold case on Windows only.
    """
    if pattern == "**":
        return True
    if fnmatchcase(path, pattern):
        return True
    return pattern.startswith("**/") and fnmatchcase(path, pattern[3:])


def _rule_matches(rule: PolicyRule, call: ToolCall) -> bool:
    if rule.tool != call.tool:
        return False
    argument_name = "url" if call.tool == "http_request" else "path"
    raw_target = call.arguments.get(argument_name)
    if call.tool == "http_request":
        target = raw_target if isinstance(raw_target, str) and raw_target else None
    else:
        target = _normalise_repository_path(raw_target)
    if target is None:
        return False
    patterns = [
        pattern
        for raw_pattern in rule.path_patterns
        if (pattern := _normalise_pattern(raw_pattern)) is not None
    ]
    # The MVP exposes a named test runner, not a general shell capability.
    # Enforce the same contract at runtime even if a policy came from somewhere
    # other than the validated Token Factory compiler.
    if call.tool == "run_tests":
        return target == "pytest" and patterns == ["pytest"]
    # Allow rules match exactly: `SRC/x` is a different path on a case-sensitive
    # filesystem, so it must not inherit `src/**`. Deny and approval rules fold
    # case so `.ENV` or `.Git/config` cannot slip past a restriction on a
    # case-insensitive filesystem. Both directions fail closed.
    if rule.effect != RuleEffect.ALLOW:
        target = target.lower()
        patterns = [pattern.lower() for pattern in patterns]
    return any(_path_matches(pattern, target) for pattern in patterns)


def evaluate(policy: Policy, call: ToolCall) -> tuple[Decision, PolicyRule | None]:
    """Return a deterministic decision. Deny and approval rules take priority."""
    matches = [rule for rule in policy.rules if _rule_matches(rule, call)]
    if not matches:
        return Decision.DENY, None

    for effect, decision in (
        (RuleEffect.DENY, Decision.DENY),
        (RuleEffect.APPROVAL_REQUIRED, Decision.APPROVAL_REQUIRED),
        (RuleEffect.ALLOW, Decision.ALLOW),
    ):
        for rule in matches:
            if rule.effect == effect:
                return decision, rule
    return Decision.DENY, None
