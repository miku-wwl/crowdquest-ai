from uuid import uuid4

from crowdquest.app import WARNING


def headers(h, csrf):
    return {"Origin": h["origin"], "X-CSRF-Token": csrf}


def test_unauthed_preview_and_private_reads_rejected(harness):
    h = harness
    candidate = h["seed"]()
    assert h["client"].get("/api/candidates").status_code == 401
    response = h["client"].post(
        "/api/preview", json={"candidate_id": candidate}, headers=headers(h, "")
    )
    assert response.status_code == 401
    assert "synthetic-access" not in h["client"].get("/api/me").text


def test_csrf_origin_host_and_extra_fields(harness):
    h = harness
    csrf, candidate = h["login"](), h["seed"]()
    client = h["client"]
    assert (
        client.post(
            "/api/preview", json={"candidate_id": candidate}, headers=headers(h, "wrong")
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/preview",
            json={"candidate_id": candidate},
            headers={"Origin": "https://evil.example", "X-CSRF-Token": csrf},
        ).status_code
        == 403
    )
    assert client.post("/api/preview", json={"candidate_id": candidate}).status_code == 403
    assert client.get("/api/me", headers={"Host": "evil.example"}).status_code == 400
    assert (
        client.get("/auth/twitch/start", headers={"Sec-Fetch-Site": "cross-site"}).status_code
        == 403
    )
    assert (
        client.post(
            "/api/preview",
            json={"candidate_id": candidate, "channel_id": "999"},
            headers=headers(h, csrf),
        ).status_code
        == 422
    )
    assert (
        client.post("/api/preview", content="x" * 4097, headers=headers(h, csrf)).status_code == 413
    )


def test_callback_state_and_cookie_attributes(harness):
    h = harness
    start = h["client"].get("/auth/twitch/start")
    assert "HttpOnly" in start.headers["set-cookie"]
    assert "SameSite=lax" in start.headers["set-cookie"]
    response = h["client"].get("/auth/twitch/callback?state=bad&code=synthetic-code")
    assert "auth_error" in response.headers["location"]
    h["login"]()
    owner_cookie = next(c for c in h["client"].cookies.jar if c.name == "cq_owner")
    assert owner_cookie.has_nonstandard_attr("HttpOnly")
    assert owner_cookie.get_nonstandard_attr("SameSite") == "strict"
    assert h["client"].get("/api/me").json()["authenticated"]
    response = h["client"].get("/")
    assert "no-referrer" == response.headers["referrer-policy"]
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    # Twitch consent returns via cross-site navigation; the harmless landing page must load.
    assert h["client"].get("/", headers={"Sec-Fetch-Site": "cross-site"}).status_code in (200, 503)


def pair(h, csrf):
    client = h["client"]
    result = client.post("/api/overlay/pair", headers=headers(h, csrf)).json()
    assert (
        client.get("/api/overlay/current", headers={"X-Overlay-View": str(uuid4())}).status_code
        == 401
    )
    assert (
        client.post(
            "/api/overlays/authorize", json={"code": result["code"]}, headers=headers(h, csrf)
        ).status_code
        == 200
    )
    return {"X-Overlay-View": str(uuid4())}


def test_owner_selection_overlay_expiry_refresh_reconnect(harness):
    h = harness
    csrf = h["login"]()
    candidate = h["seed"]("!quest <img src=x onerror=alert(1)> Survive")
    view = pair(h, csrf)
    client = h["client"]
    assert client.get("/api/overlay/current", headers=view).json()["state"] == "waiting"
    assert (
        client.post(
            "/api/preview", json={"candidate_id": candidate}, headers=headers(h, csrf)
        ).status_code
        == 200
    )
    shown = client.get("/api/overlay/current", headers=view).json()
    assert shown["state"] == "preview" and shown["warning"] == WARNING
    assert shown["text"] == "<img src=x onerror=alert(1)> Survive"
    assert "csrf" not in shown and "token" not in shown and "user_id" not in shown
    assert (
        client.get("/api/overlay/current", headers={"X-Overlay-View": str(uuid4())}).json()["state"]
        == "waiting"
    )
    h["clock"][0] += 61
    assert client.get("/api/overlay/current", headers=view).json()["state"] == "expired"
    assert h["store"].candidates("123")[0]["state"] == "previewed"


def test_overlay_cookie_cannot_preview_or_list_candidates(harness):
    h = harness
    csrf = h["login"]()
    candidate = h["seed"]()
    pair(h, csrf)
    h["client"].cookies.delete("cq_owner")
    assert h["client"].get("/api/candidates").status_code == 401
    assert (
        h["client"]
        .post("/api/preview", json={"candidate_id": candidate}, headers=headers(h, csrf))
        .status_code
        == 401
    )


def test_revocation_invalidates_owner_and_overlay(harness):
    h = harness
    csrf = h["login"]()
    view = pair(h, csrf)
    h["mock"].validate_status = 401
    h["clock"][0] += 3601
    assert h["client"].get("/api/candidates").status_code == 401
    assert h["client"].get("/api/overlay/current", headers=view).status_code == 401


def test_logout_invalidates_preview_and_missing_candidate(harness):
    h = harness
    csrf = h["login"]()
    assert (
        h["client"]
        .post("/api/preview", json={"candidate_id": str(uuid4())}, headers=headers(h, csrf))
        .status_code
        == 404
    )
    assert h["client"].post("/api/logout", headers=headers(h, csrf)).status_code == 200
    assert not h["client"].get("/api/me").json()["authenticated"]
