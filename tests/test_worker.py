"""Worker diagnostics are sanitized and fail closed; only fake HTTP is used."""

import asyncio
import io
import json
import re
from uuid import uuid4

import httpx
import pytest

from crowdquest.worker import run_worker

BOOT = str(uuid4())
TOKEN = "synthetic-worker-token-not-a-credential"
RESPONSE_SECRET = "synthetic-response-secret-not-a-credential"
SAFE_ORIGIN = "http://localhost:8000"


class FakeClient:
    def __init__(self, outcomes, **kwargs):
        self.outcomes = list(outcomes)
        self.headers = kwargs["headers"]
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    async def get(self, url):
        return await self._next("GET", url)

    async def post(self, url, *, json):
        return await self._next("POST", url)

    async def _next(self, method, url):
        self.calls.append((method, url))
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        status, body = outcome
        request = httpx.Request(method, url)
        return httpx.Response(status, json=body, request=request)


def response(status, body=None):
    return status, body or {"detail": RESPONSE_SECRET}


async def run(tmp_path, outcomes, *, sleep=None):
    token_path = tmp_path / "worker-token"
    token_path.write_text(TOKEN, encoding="ascii")
    client = FakeClient(outcomes, headers={"Authorization": "Bearer " + TOKEN})
    output = io.StringIO()
    result = await run_worker(
        SAFE_ORIGIN,
        token_path,
        client_factory=lambda **kwargs: client,
        sleep=sleep or _no_wait,
        diagnostic_stream=output,
    )
    record = json.loads(output.getvalue()) if output.getvalue() else None
    return result, record, output.getvalue(), client


async def _no_wait(_):
    raise AssertionError("A failing or graceful fixture must not sleep again")


@pytest.mark.parametrize("status", [401, 403])
async def test_session_auth_rejections_are_classified_without_response_body(tmp_path, status):
    code, record, output, client = await run(tmp_path, [response(status)])

    assert code == 1
    assert record["event"] == "WORKER_STOPPED_UNCONFIRMED"
    assert record["error_category"] == "AUTH_REJECTED"
    assert record["operation_stage"] == "SESSION"
    assert record["http_status"] == status
    assert record["retryability"] == "NOT_RETRYABLE"
    assert record["automatic_retry"] is False
    assert record["exit_classification"] == "FAIL_CLOSED"
    assert len(client.calls) == 1
    assert RESPONSE_SECRET not in output and TOKEN not in output


@pytest.mark.parametrize("stage", ["SESSION", "TICK"])
async def test_http_409_is_worker_fencing_or_conflict_and_is_not_retried(tmp_path, stage):
    outcomes = (
        [response(409)]
        if stage == "SESSION"
        else [response(200, {"server_instance": BOOT}), response(409)]
    )
    code, record, output, client = await run(tmp_path, outcomes)

    assert code == 1
    assert record["error_category"] == "WORKER_FENCED_OR_CONFLICT"
    assert record["operation_stage"] == stage
    assert record["http_status"] == 409
    assert record["automatic_retry"] is False
    assert len(client.calls) == (1 if stage == "SESSION" else 2)
    assert RESPONSE_SECRET not in output and TOKEN not in output


@pytest.mark.parametrize("status", [500, 503])
async def test_tick_server_http_status_is_retained_without_retry(tmp_path, status):
    code, record, output, client = await run(
        tmp_path, [response(200, {"server_instance": BOOT}), response(status)]
    )

    assert code == 1
    assert record["error_category"] == "HTTP_SERVER_ERROR"
    assert record["operation_stage"] == "TICK"
    assert record["http_status"] == status
    assert record["retryability"] == "RETRYABLE"
    assert record["automatic_retry"] is False
    assert len(client.calls) == 2
    assert RESPONSE_SECRET not in output and TOKEN not in output


@pytest.mark.parametrize(
    ("error", "category"),
    [
        (
            httpx.ConnectError(
                "Authorization Bearer " + TOKEN,
                request=httpx.Request("POST", SAFE_ORIGIN + "/api/worker/tick"),
            ),
            "CONNECTION_ERROR",
        ),
        (
            httpx.ReadTimeout(
                "Bearer " + TOKEN,
                request=httpx.Request("POST", SAFE_ORIGIN + "/api/worker/tick"),
            ),
            "TIMEOUT",
        ),
    ],
)
async def test_connection_and_timeout_failures_are_sanitized_and_not_retried(
    tmp_path, error, category
):
    code, record, output, client = await run(
        tmp_path, [response(200, {"server_instance": BOOT}), error]
    )

    assert code == 1
    assert record["error_category"] == category
    assert record["operation_stage"] == "TICK"
    assert record["http_status"] is None
    assert record["retryability"] == "RETRYABLE"
    assert record["automatic_retry"] is False
    assert len(client.calls) == 2
    assert TOKEN not in output and "Authorization" not in output


async def test_unexpected_exception_does_not_print_exception_text(tmp_path):
    error = RuntimeError("raw exception includes Bearer " + TOKEN)
    code, record, output, client = await run(
        tmp_path, [response(200, {"server_instance": BOOT}), error]
    )

    assert code == 1
    assert record["error_category"] == "UNEXPECTED_EXCEPTION"
    assert record["operation_stage"] == "TICK"
    assert record["exit_classification"] == "FAIL_CLOSED"
    assert len(client.calls) == 2
    assert TOKEN not in output and "raw exception" not in output


@pytest.mark.parametrize("interruption", [KeyboardInterrupt(), asyncio.CancelledError()])
async def test_interrupted_inflight_tick_is_unconfirmed_not_graceful(tmp_path, interruption):
    code, record, output, client = await run(
        tmp_path,
        [response(200, {"server_instance": BOOT}), interruption],
    )

    assert code == 1
    assert record["event"] == "WORKER_STOPPED_UNCONFIRMED"
    assert record["error_category"] == "REQUEST_INTERRUPTED"
    assert record["operation_stage"] == "TICK"
    assert record["retryability"] == "UNCONFIRMED"
    assert record["automatic_retry"] is False
    assert record["exit_classification"] == "FAIL_CLOSED"
    assert len(client.calls) == 2
    assert TOKEN not in output


@pytest.mark.parametrize("interruption", [KeyboardInterrupt(), asyncio.CancelledError()])
async def test_graceful_shutdown_is_distinct_and_returns_success(tmp_path, interruption):
    async def interrupt(_):
        raise interruption

    code, record, output, client = await run(
        tmp_path,
        [response(200, {"server_instance": BOOT}), response(200)],
        sleep=interrupt,
    )

    assert code == 0
    assert record["event"] == "WORKER_STOPPED_GRACEFULLY"
    assert record["error_category"] == "NONE"
    assert record["operation_stage"] == "SHUTDOWN"
    assert record["exit_classification"] == "GRACEFUL"
    assert len(client.calls) == 2
    assert TOKEN not in output and RESPONSE_SECRET not in output
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", record["timestamp_utc"])


async def test_default_diagnostic_destination_is_stderr(tmp_path, capsys):
    token_path = tmp_path / "worker-token"
    token_path.write_text(TOKEN, encoding="ascii")
    client = FakeClient([response(503)], headers={"Authorization": "Bearer " + TOKEN})

    assert (
        await run_worker(
            SAFE_ORIGIN,
            token_path,
            client_factory=lambda **kwargs: client,
            sleep=_no_wait,
        )
        == 1
    )
    captured = capsys.readouterr()
    assert not captured.out
    assert json.loads(captured.err)["error_category"] == "HTTP_SERVER_ERROR"
    assert TOKEN not in captured.err and RESPONSE_SECRET not in captured.err
