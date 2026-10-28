"""Run locally: uv run python -m crowdquest. Access logs deliberately disabled."""

import argparse
import logging
from functools import partial
from pathlib import Path

import uvicorn

from .app import create_app
from .config import Settings

if __name__ == "__main__":
    # HTTP/client debug logging could disclose OAuth query strings or Authorization headers.
    for name in ("httpx", "httpcore", "websockets"):
        logging.getLogger(name).setLevel(logging.WARNING)
    settings = Settings.load()
    parser = argparse.ArgumentParser(description="Local CrowdQuest development server")
    parser.add_argument("--phase2-directory", type=Path)
    parser.add_argument("--phase2-owner-id")
    parser.add_argument("--phase3-directory", type=Path)
    parser.add_argument("--phase3-owner-id")
    parser.add_argument("--predecessor-stopped", action="store_true")
    parser.add_argument(
        "--obs-admin",
        action="store_true",
        help="Optional OBS compatibility; requires the obs extra",
    )
    args = parser.parse_args()
    phase2_factory = None
    phase3_factory = None
    if args.phase3_directory is not None:
        if (
            args.phase2_directory
            or args.phase2_owner_id
            or not args.phase3_owner_id
            or not args.predecessor_stopped
        ):
            parser.error("Phase 3 requires its own identity and verified predecessor shutdown")
        from .phase3 import production_runtime

        phase3_factory = partial(
            production_runtime,
            args.phase3_directory,
            args.phase3_owner_id,
            predecessor_stopped=True,
        )
    elif args.phase2_directory is not None:
        if args.phase3_owner_id or not args.phase2_owner_id or not args.predecessor_stopped:
            parser.error("Phase 2 requires owner identity and verified predecessor shutdown")
        from .phase2 import challenge_runtime

        phase2_factory = partial(
            challenge_runtime, args.phase2_directory, args.phase2_owner_id, predecessor_stopped=True
        )
    elif args.phase2_owner_id or args.phase3_owner_id or args.predecessor_stopped:
        parser.error("Phase 2 arguments require --phase2-directory")
    uvicorn.run(
        create_app(
            settings,
            phase2_factory=phase2_factory,
            phase3_factory=phase3_factory,
            obs_admin_enabled=args.obs_admin,
        ),
        host="127.0.0.1",
        port=settings.port,
        access_log=False,
        proxy_headers=False,
        workers=1,
    )
