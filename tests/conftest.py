from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient

from crowdquest.app import create_app
from crowdquest.intake import Store
from tests.support import PassiveEventSub, make_auth, notification


@pytest.fixture
def harness(tmp_path):
    clock = [1_800_000_000.0]
    settings, auth, mock = make_auth(tmp_path, clock=lambda: clock[0])
    store = Store(tmp_path / "intake.sqlite3")
    app = create_app(
        settings,
        auth=auth,
        store=store,
        eventsub_factory=PassiveEventSub,
        clock=lambda: clock[0],
        monotonic=lambda: clock[0],
    )
    with TestClient(
        app, base_url=settings.origin, follow_redirects=False, client=("127.0.0.1", 35000)
    ) as client:

        def login():
            start = client.get("/auth/twitch/start")
            state = parse_qs(urlsplit(start.headers["location"]).query)["state"][0]
            response = client.get(
                "/auth/twitch/callback", params={"state": state, "code": "synthetic-code"}
            )
            assert response.headers["location"] == "/"
            return client.get("/api/me").json()["csrf"]

        def seed(text="!quest Survive 60 seconds"):
            result = store.ingest(
                notification(text=text, now=clock[0]),
                owner_id="123",
                session_id="session-1",
                subscription_id="sub-1",
                now=clock[0],
                source="synthetic",
            )
            assert result == "ACCEPTED"
            return store.candidates("123")[0]["id"]

        yield {
            "client": client,
            "auth": auth,
            "mock": mock,
            "store": store,
            "clock": clock,
            "login": login,
            "seed": seed,
            "origin": settings.origin,
            "app": app,
        }
