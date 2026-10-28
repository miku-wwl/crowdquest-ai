import json

import pytest
from fastapi.testclient import TestClient

from crowdquest.obs_admin import COOKIE, PREFIX, create_admin_app
from tests.obs_support import ADMIN_PASSWORD, PASSWORD, make_adapter


@pytest.fixture
def admin():
    adapter, obs = make_adapter()
    now = [100.0]
    app = create_admin_app(adapter=adapter)
    with TestClient(app, base_url="http://localhost:8000", client=("127.0.0.1", 34567)) as client:
        yield client, adapter, obs, now


def login(client):
    csrf = client.get(PREFIX + "/session").json()["csrf"]
    response = client.post(
        PREFIX + "/login",
        json={"password": ADMIN_PASSWORD},
        headers={"Origin": "http://localhost:8000", "X-CSRF-Token": csrf},
    )
    assert response.status_code == 200
    return {"Origin": "http://localhost:8000", "X-CSRF-Token": response.json()["csrf"]}


def test_session_login_logout_rotation_and_unauthorized(admin):
    client, adapter, obs, _ = admin
    assert client.get(PREFIX + "/status").status_code == 401
    for operation in ("scene", "record/start", "record/stop", "overlay/refresh"):
        assert (
            client.post(
                PREFIX + "/" + operation, json={}, headers={"Origin": "http://localhost:8000"}
            ).status_code
            == 401
        )
    assert not obs.calls
    before = client.get(PREFIX + "/session")
    assert "HttpOnly" in before.headers["set-cookie"]
    assert "SameSite=strict" in before.headers["set-cookie"]
    old = client.cookies.get(COOKIE)
    headers = login(client)
    assert client.cookies.get(COOKIE) != old
    status = client.get(PREFIX + "/status")
    assert status.status_code == 200
    assert PASSWORD not in status.text and ADMIN_PASSWORD not in status.text
    assert client.post(
        PREFIX + "/record/start", json={"revision": adapter.revision}, headers=headers
    ).json()["recording"]["active"]
    assert client.post(PREFIX + "/logout", json={}, headers=headers).status_code == 200
    assert client.get(PREFIX + "/status").status_code == 401
    assert obs.active  # signing out never implicitly stops/starts recording


def test_csrf_host_origin_same_site_and_network_rejection(admin):
    client, adapter, obs, _ = admin
    headers = login(client)
    command = {"revision": adapter.revision}
    for bad in (
        {},
        {"Origin": "http://localhost:8000"},
        {**headers, "Origin": "https://evil.example"},
        {**headers, "X-CSRF-Token": "wrong"},
        {**headers, "Sec-Fetch-Site": "same-site"},
        {**headers, "Sec-Fetch-Site": "cross-site"},
    ):
        assert client.post(PREFIX + "/record/start", json=command, headers=bad).status_code == 403
    assert client.get(PREFIX + "/status", headers={"Host": "127.0.0.1:8000"}).status_code == 400
    with TestClient(
        client.app, base_url="http://localhost:8000", client=("192.168.1.99", 3)
    ) as remote:
        assert remote.get("/obs-admin").status_code == 403
        assert (
            remote.get(PREFIX + "/session", headers={"X-Forwarded-For": "127.0.0.1"}).status_code
            == 403
        )
    assert not obs.calls


def test_strict_shapes_duplicate_post_forbidden_proxy_and_input_redaction(admin):
    client, adapter, obs, _ = admin
    headers = login(client)
    revision = adapter.revision
    for payload in (
        {"revision": revision, "password": PASSWORD},
        {"revision": 1},
        {"revision": "x"},
        [],
    ):
        response = client.post(PREFIX + "/record/start", json=payload, headers=headers)
        assert response.status_code == 422 and PASSWORD not in response.text
    response = client.post(
        PREFIX + "/record/start",
        content='{"revision":"x","revision":"x"}',
        headers={**headers, "Content-Type": "application/json"},
    )
    assert response.status_code == 422
    assert (
        client.post(
            PREFIX + "/record/start", json={"revision": revision}, headers=headers
        ).status_code
        == 200
    )
    assert (
        client.post(
            PREFIX + "/record/start", json={"revision": revision}, headers=headers
        ).status_code
        == 409
    )
    for path in ("rpc", "StartStream", "StopStream", "stream/start", "stream/stop", "output/start"):
        assert client.post(PREFIX + "/" + path, json={}, headers=headers).status_code == 404
    assert (
        client.post(
            PREFIX + "/scene",
            json={"revision": adapter.revision, "scene": "arbitrary"},
            headers=headers,
        ).status_code
        == 503
    )
    assert sum(name == "StartRecord" for name, _ in obs.calls) == 1
    assert not any("Stream" in name for name, _ in obs.calls if name != "GetStreamStatus")


def test_login_rate_limit_body_size_and_password_never_echoed(admin):
    client = admin[0]
    csrf = client.get(PREFIX + "/session").json()["csrf"]
    headers = {"Origin": "http://localhost:8000", "X-CSRF-Token": csrf}
    response = client.post(
        PREFIX + "/login", json={"password": PASSWORD, "extra": PASSWORD}, headers=headers
    )
    assert response.status_code == 422 and PASSWORD not in response.text
    assert (
        client.post(
            PREFIX + "/login",
            content="x" * 2049,
            headers={**headers, "Content-Type": "application/json"},
        ).status_code
        == 413
    )
    for _ in range(5):
        assert (
            client.post(PREFIX + "/login", json={"password": PASSWORD}, headers=headers).status_code
            == 401
        )
    assert (
        client.post(
            PREFIX + "/login", json={"password": ADMIN_PASSWORD}, headers=headers
        ).status_code
        == 429
    )
    assert client.put(PREFIX + "/login", json={}, headers=headers).status_code == 405
    assert client.get(PREFIX + "/session?password=" + PASSWORD).status_code == 400
    assert PASSWORD not in json.dumps([response.headers.get("cache-control"), response.text])
