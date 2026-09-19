from app.demo_data import DEMO_POLICY
from app.models import Policy, PolicyRule, RuleEffect
from app.policy_validation import VALIDATION_FIXTURES, validate_policy


def expected_policy() -> Policy:
    return Policy(
        version=DEMO_POLICY.version,
        rules=[rule.model_copy(deep=True) for rule in DEMO_POLICY.rules],
    )


def test_validation_suite_passes_a_policy_with_intended_authority() -> None:
    result = validate_policy(expected_policy())
    assert result.passed is True
    assert result.status == "passed"
    assert result.passed_checks == result.total_checks == len(VALIDATION_FIXTURES) == 23
    assert all(case.passed for case in result.cases)
    assert "No agent, command, file, or network action was executed" in result.message


def test_validation_suite_identifies_missing_useful_capability() -> None:
    policy = expected_policy()
    policy.rules = [rule for rule in policy.rules if rule.id != "allow-tests"]
    result = validate_policy(policy)
    failed = [case for case in result.cases if not case.passed]
    assert result.passed is False
    assert result.status == "failed"
    assert [case.id for case in failed] == ["run-pytest"]
    assert failed[0].actual.value == "deny"


def _delete_case(effect: RuleEffect):
    policy = expected_policy()
    policy.rules = [
        rule.model_copy(update={"effect": effect}) if rule.id == "approval-for-delete" else rule
        for rule in policy.rules
    ]
    result = validate_policy(policy)
    return result, next(case for case in result.cases if case.id == "delete")


def test_delete_may_be_denied_or_held_for_approval_but_never_allowed() -> None:
    # The mandatory guardrail requires approval to delete; that must satisfy the
    # matrix, or no compiled policy could ever pass without an extra deny rule.
    for effect, actual in ((RuleEffect.DENY, "deny"), (RuleEffect.APPROVAL_REQUIRED, "approval_required")):
        result, deletion = _delete_case(effect)
        assert (result.passed, deletion.passed, deletion.actual.value) == (True, True, actual)
    result, deletion = _delete_case(RuleEffect.ALLOW)
    assert (result.passed, deletion.passed, deletion.actual.value) == (False, False, "allow")
    assert deletion.expected.value == "deny"


def test_a_compiled_policy_of_guardrails_plus_ordinary_allows_passes_the_matrix() -> None:
    from app.guardrails import MANDATORY_GUARDRAILS

    def allow(id, tool, patterns):
        return PolicyRule(id=id, effect=RuleEffect.ALLOW, tool=tool, path_patterns=patterns)

    policy = Policy(rules=[
        *MANDATORY_GUARDRAILS,
        allow("a", "read_file", ["README.md", "src/**", "tests/**"]),
        allow("b", "write_file", ["src/**"]),
        allow("c", "run_tests", ["pytest"]),
    ])
    assert validate_policy(policy).passed is True


def test_matrix_rejects_a_policy_that_lets_the_agent_write_secrets_or_git() -> None:
    policy = expected_policy()
    policy.rules = [rule for rule in policy.rules if rule.id != "deny-protected-writes"]
    policy.rules.append(PolicyRule(id="w", effect=RuleEffect.ALLOW, tool="write_file", path_patterns=[".env", ".git/**"]))
    failed = {case.id for case in validate_policy(policy).cases if not case.passed}
    assert failed == {"write-env", "write-git"}


def test_matrix_rejects_narrow_secret_lists_that_miss_variants_keys_and_case() -> None:
    policy = expected_policy()
    for rule in policy.rules:
        if rule.id == "deny-secret-files":
            rule.path_patterns = [".env", "**/.env", ".git/**", "**/.git/**", "*.pem", "*.key"]
    policy.rules.append(PolicyRule(id="wide", effect=RuleEffect.ALLOW, tool="read_file", path_patterns=["**"]))
    failed = {case.id for case in validate_policy(policy).cases if not case.passed}
    assert failed == {"env-variant", "ssh-key"}
