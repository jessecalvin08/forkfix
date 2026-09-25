import asyncio

import httpx
import pytest
from openai import APIConnectionError

from forkfix.agent import Action, TokenFactoryAgent
from forkfix.run_day2 import summarize
from forkfix.search import Search, SearchConfig
from forkfix.workspace import InfraError, Meter

from fakes import FakeAgent, FakeWorkspace, fake_openai, make_task

VALID = Action(tool="submit").model_dump_json()


def dropped():
    return APIConnectionError(request=httpx.Request("POST", "https://example.invalid"))


def no_wait():
    waits = []

    async def sleep(seconds):
        waits.append(seconds)
    return sleep, waits


def test_connection_drops_are_waited_out_without_using_up_model_attempts():
    client, completions = fake_openai([dropped(), dropped(), dropped(), ("stop", VALID)])
    sleep, waits = no_wait()
    action = asyncio.run(TokenFactoryAgent(client, "m", sleep=sleep).act([], 0.0, Meter()))
    assert action.tool == "submit" and waits == [5.0, 10.0, 20.0]
    # Still the first attempt: thinking on, original temperature.
    assert "extra_body" not in completions.kwargs[-1] and completions.kwargs[-1]["temperature"] == 0.0


def test_a_service_that_stays_down_is_reported_as_infrastructure_not_agent_failure():
    client, _ = fake_openai([dropped() for _ in range(20)])
    sleep, waits = no_wait()
    with pytest.raises(InfraError):
        asyncio.run(TokenFactoryAgent(client, "m", sleep=sleep).act([], 0.0, Meter()))
    assert sum(waits) >= 300


def test_an_infrastructure_stop_is_labelled_so_the_task_can_be_rerun():
    class DownAgent(FakeAgent):
        async def act(self, messages, temperature, meter):
            raise InfraError("Model service unreachable (APIConnectionError).")

    result = asyncio.run(Search(make_task(), DownAgent(None), None, SearchConfig.linear(), Meter())
                         .run(FakeWorkspace({})))
    assert result.all_trajectories[0].stop_reason.startswith("infra:")


def test_the_summary_marks_a_task_invalid_when_any_mode_hit_infrastructure_trouble():
    ok = {"selected_resolved": False, "any_candidate_resolved": False, "infra_stops": 0,
          "spend": {"prompt_tokens": 1, "completion_tokens": 1, "sandbox_spawns": 1}}
    record = {"instance_id": "t", "modes": {"linear": ok, "branching": {**ok, "infra_stops": 2}}}
    assert summarize(record)["valid"] is False
    assert summarize({"instance_id": "t", "modes": {"linear": ok}})["valid"] is True
    assert summarize({"instance_id": "t", "modes": {"linear": {"mode": "linear", "error": "X"}}})["valid"] is False
