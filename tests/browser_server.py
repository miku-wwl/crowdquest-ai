"""Private synthetic E2E fixture server: no real Twitch endpoints or public injection route."""

import sys
from pathlib import Path

from crowdquest.app import create_app
from crowdquest.intake import Store
from tests.support import PassiveEventSub, make_auth, notification


def build(directory, port):
    settings, auth, _ = make_auth(directory, port=port)
    store = Store(directory / "intake.sqlite3")
    for number, text in enumerate(
        (
            "!quest <img src=x onerror=window.pwned=1> Survive 60 seconds",
            "!quest " + "Long untrusted viewer text " * 10,
        )
    ):
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
    app = create_app(settings, auth=auth, store=store, eventsub_factory=PassiveEventSub)

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
            build(directory, int(sys.argv[2])),
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
