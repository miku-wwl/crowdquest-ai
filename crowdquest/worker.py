"""Separate, narrowly authenticated worker process. Any uncertain HTTP outcome stops it."""

import argparse
import asyncio
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

import httpx


async def work(origin, token_path):
    url = urlsplit(origin)
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
        raise ValueError("WORKER_ORIGIN")
    token = token_path.read_text("ascii")
    worker = str(uuid4())
    async with httpx.AsyncClient(
        timeout=3,
        trust_env=False,
        follow_redirects=False,
        headers={"Authorization": "Bearer " + token, "Origin": origin},
    ) as client:
        response = await client.get(origin + "/api/worker/session")
        response.raise_for_status()
        boot = response.json()["server_instance"]
        while True:
            response = await client.post(
                origin + "/api/worker/tick",
                json={
                    "worker_instance": worker,
                    "server_instance": boot,
                },
            )
            response.raise_for_status()
            await asyncio.sleep(0.5)  # Heartbeat/state advance; never resends a marked effect.


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="CrowdQuest render worker, separate credential role"
    )
    parser.add_argument("--origin", default="http://localhost:8000")
    parser.add_argument("--token-file", required=True, type=Path)
    args = parser.parse_args()
    try:
        asyncio.run(work(args.origin, args.token_file))
    except KeyboardInterrupt:
        pass
    except Exception:  # noqa: BLE001 -- no headers/URLs/private paths in errors; never retry
        print("WORKER_STOPPED_UNCONFIRMED; inspect durable state; no automatic retry")
        raise SystemExit(1) from None
