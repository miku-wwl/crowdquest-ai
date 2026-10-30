"""Separate, narrowly authenticated worker process. Any uncertain HTTP outcome stops it."""

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

import httpx


class _WorkerConfigurationError(Exception):
    pass


class _WorkerProtocolError(Exception):
    pass


def _failure_fields(error):
    if isinstance(error, httpx.HTTPStatusError):
        status = error.response.status_code
        if status in (401, 403):
            return "AUTH_REJECTED", status, "NOT_RETRYABLE"
        if status == 409:
            return "WORKER_FENCED_OR_CONFLICT", status, "NOT_RETRYABLE"
        if status == 429:
            return "HTTP_RATE_LIMITED", status, "RETRYABLE"
        if status >= 500:
            return "HTTP_SERVER_ERROR", status, "RETRYABLE"
        if status == 408:
            return "HTTP_TIMEOUT", status, "RETRYABLE"
        return "HTTP_STATUS_ERROR", status, "NOT_RETRYABLE"
    if isinstance(error, httpx.TimeoutException):
        return "TIMEOUT", None, "RETRYABLE"
    if isinstance(error, httpx.ConnectError):
        return "CONNECTION_ERROR", None, "RETRYABLE"
    if isinstance(error, httpx.ProtocolError):
        return "HTTP_PROTOCOL_ERROR", None, "RETRYABLE"
    if isinstance(error, httpx.TransportError):
        return "HTTP_TRANSPORT_ERROR", None, "RETRYABLE"
    if isinstance(error, (OSError, UnicodeError)):
        return "LOCAL_CONFIGURATION_ERROR", None, "NOT_RETRYABLE"
    if isinstance(error, _WorkerConfigurationError):
        return "INVALID_CONFIGURATION", None, "NOT_RETRYABLE"
    if isinstance(error, _WorkerProtocolError):
        return "PROTOCOL_ERROR", None, "NOT_RETRYABLE"
    return "UNEXPECTED_EXCEPTION", None, "NOT_RETRYABLE"


def _write_diagnostic(
    *, event, category, stage, http_status, retryability, exit_classification, stream=None
):
    record = {
        "event": event,
        "error_category": category,
        "operation_stage": stage,
        "http_status": http_status,
        "retryability": retryability,
        "automatic_retry": False,
        "exit_classification": exit_classification,
        "timestamp_utc": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
    }
    destination = sys.stderr if stream is None else stream
    try:
        print(json.dumps(record, sort_keys=True, separators=(",", ":")), file=destination)
        destination.flush()
    except OSError:
        # A closed diagnostic stream must not change the fail-closed exit behavior.
        pass


def _shutdown_result(request_in_flight, stage, stream):
    if request_in_flight:
        _write_diagnostic(
            event="WORKER_STOPPED_UNCONFIRMED",
            category="REQUEST_INTERRUPTED",
            stage=stage,
            http_status=None,
            retryability="UNCONFIRMED",
            exit_classification="FAIL_CLOSED",
            stream=stream,
        )
        return 1
    _write_diagnostic(
        event="WORKER_STOPPED_GRACEFULLY",
        category="NONE",
        stage="SHUTDOWN",
        http_status=None,
        retryability="NOT_APPLICABLE",
        exit_classification="GRACEFUL",
        stream=stream,
    )
    return 0


async def run_worker(
    origin,
    token_path,
    *,
    client_factory=None,
    sleep=asyncio.sleep,
    diagnostic_stream=None,
):
    """Run one Worker session. Any uncertain request failure exits without retry."""
    stage = "SESSION"
    request_in_flight = False
    try:
        try:
            url = urlsplit(origin)
        except ValueError:
            raise _WorkerConfigurationError from None
        if (
            url.scheme != "http"
            or url.hostname != "localhost"
            or not url.port
            or url.path
            or url.query
            or url.fragment
            or url.username
            or url.password
        ):
            raise _WorkerConfigurationError
        token = Path(token_path).read_text("ascii")
        worker = str(uuid4())
        factory = client_factory or httpx.AsyncClient
        async with factory(
            timeout=3,
            trust_env=False,
            follow_redirects=False,
            headers={"Authorization": "Bearer " + token, "Origin": origin},
        ) as client:
            request_in_flight = True
            response = await client.get(origin + "/api/worker/session")
            response.raise_for_status()
            request_in_flight = False
            try:
                boot = response.json()["server_instance"]
            except (KeyError, TypeError, ValueError):
                raise _WorkerProtocolError from None
            stage = "TICK"
            while True:
                request_in_flight = True
                response = await client.post(
                    origin + "/api/worker/tick",
                    json={
                        "worker_instance": worker,
                        "server_instance": boot,
                    },
                )
                response.raise_for_status()
                request_in_flight = False
                await sleep(0.5)  # Heartbeat/state advance; never resends a marked effect.
    except (KeyboardInterrupt, asyncio.CancelledError):
        # asyncio.run translates the first Ctrl+C into task cancellation. Keep
        # an interrupted HTTP request distinct from an idle graceful shutdown.
        return _shutdown_result(request_in_flight, stage, diagnostic_stream)
    except Exception as error:  # noqa: BLE001 -- emit fixed categories, never exception text
        category, status, retryability = _failure_fields(error)
        _write_diagnostic(
            event="WORKER_STOPPED_UNCONFIRMED",
            category=category,
            stage=stage,
            http_status=status,
            retryability=retryability,
            exit_classification="FAIL_CLOSED",
            stream=diagnostic_stream,
        )
        return 1


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="CrowdQuest render worker, separate credential role"
    )
    parser.add_argument("--origin", default="http://localhost:8000")
    parser.add_argument("--token-file", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        return asyncio.run(run_worker(args.origin, args.token_file))
    except KeyboardInterrupt:
        # Defensive fallback for an interrupt outside run_worker. Its request
        # stage cannot be known here, so preserve the conservative outcome.
        _write_diagnostic(
            event="WORKER_STOPPED_UNCONFIRMED",
            category="REQUEST_INTERRUPTED",
            stage="SHUTDOWN",
            http_status=None,
            retryability="UNCONFIRMED",
            exit_classification="FAIL_CLOSED",
        )
        return 1
    except Exception as error:  # noqa: BLE001 -- fixed diagnostics only
        category, status, retryability = _failure_fields(error)
        _write_diagnostic(
            event="WORKER_STOPPED_UNCONFIRMED",
            category=category,
            stage="STARTUP",
            http_status=status,
            retryability=retryability,
            exit_classification="FAIL_CLOSED",
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
