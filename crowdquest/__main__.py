"""Run locally: uv run python -m crowdquest. Access logs deliberately disabled."""

import logging

import uvicorn

from .app import create_app
from .config import Settings

if __name__ == "__main__":
    # HTTP/client debug logging could disclose OAuth query strings or Authorization headers.
    for name in ("httpx", "httpcore", "websockets"):
        logging.getLogger(name).setLevel(logging.WARNING)
    settings = Settings.load()
    uvicorn.run(
        create_app(settings),
        host="127.0.0.1",
        port=settings.port,
        access_log=False,
        proxy_headers=False,
        workers=1,
    )
