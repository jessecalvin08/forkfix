import asyncio

import pytest
from contree_sdk.sdk.exceptions.api import ContreeTransportError, ForbiddenError

from forkfix.workspace import InfraError, with_retries


def flaky(failures, error=ContreeTransportError):
    calls = {"n": 0}

    async def call():
        calls["n"] += 1
        if calls["n"] <= failures:
            raise error()
        return "done"
    return call, calls


def test_network_blips_are_retried_until_the_call_succeeds():
    call, calls = flaky(2)
    assert asyncio.run(with_retries(call, attempts=4, delay=0)) == "done" and calls["n"] == 3


def test_retries_give_up_after_the_last_attempt_as_an_infrastructure_failure():
    call, calls = flaky(9)
    with pytest.raises(InfraError):
        asyncio.run(with_retries(call, attempts=3, delay=0))
    assert calls["n"] == 3


def test_permission_errors_are_not_retried():
    call, calls = flaky(1, ForbiddenError)
    with pytest.raises(ForbiddenError):
        asyncio.run(with_retries(call, attempts=4, delay=0))
    assert calls["n"] == 1
