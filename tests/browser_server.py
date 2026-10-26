"""Private synthetic E2E fixture server: no real Twitch endpoints or public injection route."""

import asyncio
import json
import os
import sys
from functools import partial
from pathlib import Path

from crowdquest.app import create_app
from crowdquest.intake import Store
from tests.support import PassiveEventSub, make_auth, notification


def build(directory, port, *, phase3=False, phase4=False):
    settings, auth, _ = make_auth(directory, port=port)
    store = Store(directory / "intake.sqlite3")
    texts = (
        (
            "!quest Beat the next boss without healing",
            "!quest Survive for 60 seconds using only basic attacks",
        )
        if phase4
        else (
            "!quest <img src=x onerror=window.pwned=1> Survive 60 seconds",
            "!quest " + "Long untrusted viewer text " * 10,
        )
    )
    for number, text in enumerate(texts):
        store.ingest(
            notification(
                delivery=f"synthetic-delivery-{number}",
                message=f"synthetic-chat-{number}",
                viewer=str(400 + number),
                text=text,
            ),
            owner_id="123",
            session_id="session-1",
            subscription_id="sub-1",
            source="synthetic",
        )
    factory = None
    if phase3 or phase4:
        from crowdquest.phase3 import production_runtime, provision
        from tests.phase3_support import SyntheticProvider

        class BrowserProvider(SyntheticProvider):
            async def generate_plan(self, intent, **kwargs):
                value = json.loads(await super().generate_plan(intent, **kwargs))
                if "manual" not in json.loads(intent.text):
                    value["steps"][0]["arguments"].update(
                        title="SYNTHETIC TEST · Basic attacks only"
                        if phase4
                        else "SYNTHETIC TEST <img src=x onerror=window.pwned=1> Safe challenge",
                        description=json.loads(intent.text)["suggestion"][:240]
                        if phase4
                        else value["steps"][0]["arguments"]["description"],
                        duration_seconds=15,
                    )
                return json.dumps(value)

        profile = directory / "phase3"
        provision(profile, "123")
        factory = partial(
            production_runtime,
            profile,
            "123",
            predecessor_stopped=True,
            provider_factory=BrowserProvider,
        )

    class FixtureEvents(PassiveEventSub):
        def __init__(self, auth, store):
            self.store = store

        async def run(self):
            # Private file mailbox belongs only to this temporary fixture. There is
            # no production HTTP injection endpoint or call to Twitch.
            while True:
                for path in directory.glob("event-*.json"):
                    envelope = json.loads(path.read_text("utf-8"))
                    result = self.store.ingest(
                        envelope,
                        owner_id="123",
                        session_id="session-1",
                        subscription_id="sub-1",
                        source="synthetic",
                    )
                    (directory / ("result-" + path.name)).write_text(
                        json.dumps({"result": result}), encoding="utf-8"
                    )
                    path.unlink()
                await asyncio.sleep(0.05)

    app = create_app(
        settings,
        auth=auth,
        store=store,
        eventsub_factory=FixtureEvents if phase4 else PassiveEventSub,
        phase3_factory=factory,
        frontend_directory=os.environ.get("CROWDQUEST_TEST_FRONTEND"),
    )

    @app.get("/_test/health")
    async def fixture_identity():
        return {"fixture_id": directory.name}

    return app


if __name__ == "__main__":
    import threading
    import time

    import uvicorn

    directory = Path(sys.argv[1])
    server = uvicorn.Server(
        uvicorn.Config(
            build(
                directory,
                int(sys.argv[2]),
                phase3=len(sys.argv) > 3 and sys.argv[3] == "phase3",
                phase4=len(sys.argv) > 3 and sys.argv[3] == "phase4",
            ),
            host="127.0.0.1",
            port=int(sys.argv[2]),
            access_log=False,
            proxy_headers=False,
        )
    )

    def shutdown_monitor():
        while not (directory / "stop").exists():
            time.sleep(0.1)
        server.should_exit = True

    threading.Thread(target=shutdown_monitor, daemon=True).start()
    try:
        server.run()
    finally:
        (directory / "stopped").touch()
