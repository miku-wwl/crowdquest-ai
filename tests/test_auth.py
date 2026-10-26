from urllib.parse import parse_qs, urlsplit

import pytest

from crowdquest.auth import AuthError
from tests.support import make_auth


def state_for(auth):
    url, cookie = auth.begin()
    query = parse_qs(urlsplit(url).query)
    assert query["scope"] == ["user:read:chat"]
    assert query["redirect_uri"] == [auth.settings.redirect_uri]
    return query["state"][0], cookie


async def test_state_bound_one_use_and_no_token_exposure(tmp_path):
    _, auth, mock = make_auth(tmp_path)
    state, cookie = state_for(auth)
    identity = await auth.callback(state, cookie, "synthetic-code")
    assert identity.login == "fixture_owner"
    assert "synthetic-access" not in repr(auth.tokens)
    assert auth.vault.get("tokens")
    with pytest.raises(AuthError, match="OAUTH_STATE"):
        await auth.callback(state, cookie, "synthetic-code")
    assert len(mock.calls) == 2
    await auth.close()


@pytest.mark.parametrize("fault", ["wrong_state", "wrong_cookie", "expired"])
async def test_bad_oauth_state_never_exchanges(tmp_path, fault):
    clock = [100.0]
    _, auth, mock = make_auth(tmp_path, clock=lambda: clock[0])
    state, cookie = state_for(auth)
    if fault == "wrong_state":
        state = "wrong"
    if fault == "wrong_cookie":
        cookie = "wrong"
    if fault == "expired":
        clock[0] += 301
    with pytest.raises(AuthError, match="OAUTH_STATE"):
        await auth.callback(state, cookie, "synthetic-code")
    assert mock.calls == []
    await auth.close()


@pytest.mark.parametrize(
    "field,value",
    [
        ("scopes", []),
        ("scopes", ["user:read:chat", "user:write:chat"]),
        ("client_id", "wrong"),
        ("login", "other_owner"),
        ("user_id", "bad"),
        ("expires_in", 0),
    ],
)
async def test_wrong_owner_client_scope_expiry_rejected(tmp_path, field, value):
    _, auth, mock = make_auth(tmp_path)
    mock.validation[field] = value
    with pytest.raises(AuthError):
        await auth.callback(*state_for(auth), "synthetic-code")
    assert auth.identity is None
    assert auth.vault.get("tokens") is None
    await auth.close()


async def test_refresh_rotation_and_hourly_revocation(tmp_path):
    clock = [10000.0]
    _, auth, mock = make_auth(tmp_path, clock=lambda: clock[0])
    await auth.callback(*state_for(auth), "synthetic-code")
    clock[0] += 3541
    mock.token.update(access_token="rotated-access", refresh_token="rotated-refresh")
    assert await auth.ensure()
    assert auth.tokens.refresh == "rotated-refresh"
    assert "rotated-refresh" in auth.vault.get("tokens")
    assert len([r for r in mock.calls if r.url.path == "/oauth2/token"]) == 2
    mock.validate_status = 401
    clock[0] += 3601
    assert await auth.ensure() is None
    assert auth.vault.get("tokens") is None
    assert auth.reason == "REAUTHENTICATION_REQUIRED"
    await auth.close()


async def test_saved_token_revalidated_on_restart(tmp_path):
    _, auth, _ = make_auth(tmp_path)
    await auth.callback(*state_for(auth), "synthetic-code")
    _, restarted, mock = make_auth(tmp_path)
    restarted.vault = auth.vault
    mock.validation["login"] = "wrong"
    assert await restarted.ensure() is None
    assert restarted.vault.get("tokens") is None
    await auth.close()
    await restarted.close()
