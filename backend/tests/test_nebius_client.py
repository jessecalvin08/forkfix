import json
from types import SimpleNamespace

import httpx
import pytest
from openai import APIStatusError, BadRequestError, UnprocessableEntityError

from app import nebius_client
from app.models import RuleEffect


MODEL_ID = "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"


class FakeTokenFactoryClient:
    def __init__(self, content: str, error: Exception | None = None) -> None:
        self.content = content
        self.error = error
        self.requests: list[dict] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        self.requests.append(kwargs)
        if self.error is not None:
            raise self.error
        return SimpleNamespace(
            choices=[SimpleNamespace(
                finish_reason="stop",
                message=SimpleNamespace(refusal=None, content=self.content),
            )]
        )


@pytest.fixture(autouse=True)
def isolated_configuration(monkeypatch):
    # Never load the developer's private .env or instantiate a live API client.
    monkeypatch.setenv("NEBIUS_MODEL", MODEL_ID)
    monkeypatch.setattr(nebius_client, "load_local_configuration", lambda: None)


@pytest.fixture
def valid_policy():
    return {
        "version": "1",
        "rules": [{
            "id": "allow-source-edits",
            "effect": "allow",
            "tool": "write_file",
            "path_patterns": ["src/**"],
            "reason": "The developer explicitly allows source edits.",
        }],
    }


def install_client(monkeypatch, policy, error=None):
    fake = FakeTokenFactoryClient(json.dumps(policy), error=error)
    monkeypatch.setattr(nebius_client, "token_factory_client", lambda: fake)
    return fake


def test_compile_sends_named_schema_and_bounded_request(monkeypatch, valid_policy):
    fake = install_client(monkeypatch, valid_policy)
    text = "The agent may edit only source files."

    policy, model, mode = nebius_client.compile_policy(text)

    assert (model, mode) == (MODEL_ID, "json_schema")
    assert len(fake.requests) == 1
    request = fake.requests[0]
    assert request["response_format"] == {
        "type": "json_schema",
        "json_schema": {
            "name": "rulebranch_policy",
            "strict": True,
            "schema": nebius_client.POLICY_SCHEMA,
        },
    }
    assert request["model"] == MODEL_ID
    assert request["max_tokens"] == 4096
    assert request["messages"][-1] == {"role": "user", "content": text}
    system_prompt = request["messages"][0]["content"]
    # Parse the embedded JSON so harmless formatting changes do not break the test.
    schema_start = system_prompt.index("{")
    embedded_schema, _ = json.JSONDecoder().raw_decode(system_prompt[schema_start:])
    assert embedded_schema == nebius_client.POLICY_SCHEMA
    assert policy.rules[-1].id == "allow-source-edits"


@pytest.mark.parametrize(
    ("status", "error_type"),
    [(400, BadRequestError), (422, UnprocessableEntityError)],
)
def test_provider_errors_are_not_retried_in_another_mode(
    monkeypatch, valid_policy, status, error_type,
):
    request = httpx.Request("POST", "https://api.tokenfactory.nebius.com/v1/chat/completions")
    response = httpx.Response(status, request=request)
    failure = error_type("Invalid request", response=response, body={"error": "invalid_request"})
    fake = install_client(monkeypatch, valid_policy, error=failure)

    with pytest.raises(APIStatusError) as raised:
        nebius_client.compile_policy("The agent may edit only source files.")

    assert raised.value is failure
    assert len(fake.requests) == 1
    assert fake.requests[0]["response_format"]["type"] == "json_schema"


@pytest.mark.parametrize("invalid_shape", [
    "missing_paths", "extra_root_field", "extra_rule_field", "unknown_tool",
    "empty_rules", "empty_paths", "missing_version", "missing_reason",
    "unsafe_test_wildcard", "path_traversal",
])
def test_generated_policy_is_rejected_when_it_violates_schema(
    monkeypatch, valid_policy, invalid_shape,
):
    if invalid_shape == "missing_paths":
        del valid_policy["rules"][0]["path_patterns"]
    elif invalid_shape == "extra_root_field":
        valid_policy["unexpected"] = True
    elif invalid_shape == "extra_rule_field":
        valid_policy["rules"][0]["unexpected"] = True
    elif invalid_shape == "unknown_tool":
        valid_policy["rules"][0]["tool"] = "shell"
    elif invalid_shape == "empty_rules":
        valid_policy["rules"] = []
    elif invalid_shape == "empty_paths":
        valid_policy["rules"][0]["path_patterns"] = []
    elif invalid_shape == "missing_version":
        del valid_policy["version"]
    elif invalid_shape == "missing_reason":
        del valid_policy["rules"][0]["reason"]
    elif invalid_shape == "unsafe_test_wildcard":
        valid_policy["rules"][0].update(tool="run_tests", path_patterns=["*"])
    elif invalid_shape == "path_traversal":
        valid_policy["rules"][0]["path_patterns"] = ["src/../.env"]
    fake = install_client(monkeypatch, valid_policy)

    expected_message = {
        "unsafe_test_wildcard": "test command other than pytest",
        "path_traversal": "unsafe path pattern",
    }.get(invalid_shape, "invalid policy shape")
    with pytest.raises(ValueError, match=expected_message):
        nebius_client.compile_policy("The agent may edit only source files.")

    assert len(fake.requests) == 1


def test_model_cannot_override_reserved_guardrails(monkeypatch, valid_policy):
    for guard in nebius_client.MANDATORY_GUARDRAILS:
        valid_policy["rules"].append({
            "id": guard.id,
            "effect": "allow",
            "tool": guard.tool,
            "path_patterns": ["**"],
            "reason": "A model-generated rule must not replace a mandatory guard.",
        })
    install_client(monkeypatch, valid_policy)

    compiled, _, _ = nebius_client.compile_policy("The agent may edit only source files.")

    expected_effects = {
        "rulebranch-deny-secret-files": RuleEffect.DENY,
        "rulebranch-deny-protected-writes": RuleEffect.DENY,
        "rulebranch-deny-network-egress": RuleEffect.DENY,
        "rulebranch-approval-delete": RuleEffect.APPROVAL_REQUIRED,
    }
    for guard in nebius_client.MANDATORY_GUARDRAILS:
        matching = [rule for rule in compiled.rules if rule.id == guard.id]
        assert len(matching) == 1
        assert matching[0].model_dump() == guard.model_dump()
        assert matching[0].effect == expected_effects[guard.id]
    assert compiled.rules[-1].id == "allow-source-edits"


def test_broad_test_runner_rule_has_a_safe_explanation(monkeypatch, valid_policy):
    valid_policy["rules"][0].update(tool="run_tests", path_patterns=["*"])
    install_client(monkeypatch, valid_policy)

    with pytest.raises(ValueError, match="test command other than pytest"):
        nebius_client.compile_policy("The agent may run pytest.")


def test_repeated_model_assignment_is_rejected_before_provider_call(monkeypatch):
    monkeypatch.setenv("NEBIUS_MODEL", "NEBIUS_MODEL=" + MODEL_ID)
    with pytest.raises(nebius_client.NebiusConfigurationError, match="repeated assignment"):
        nebius_client.configured_model()
