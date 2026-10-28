import base64
import hashlib
import json
import logging
import threading
from contextlib import contextmanager

import pytest
from websockets.sync.server import serve

from crowdquest.obs import ALLOWLIST, ObsAdapter, ObsConfig, ObsError, connect
from tests.obs_support import ADMIN_PASSWORD, PASSWORD, make_adapter


def test_unavailable_cooldown_and_connection_recovery():
    now, attempts = [100.0], []
    adapter, obs = make_adapter(clock=lambda: now[0])

    def factory(_):
        attempts.append(1)
        if len(attempts) == 1:
            raise ObsError("OBS_UNAVAILABLE")
        return obs

    adapter.factory = factory
    for _ in range(2):
        with pytest.raises(ObsError, match="OBS_UNAVAILABLE"):
            adapter.status()
    assert len(attempts) == 1
    now[0] += 5
    status = adapter.status()
    assert status["connected"] and len(attempts) == 2
    assert status["scenes"] == obs.scenes
    obs.fail = "GetRecordStatus"
    with pytest.raises(ObsError, match="OBS_UNAVAILABLE"):
        adapter.status()
    obs.fail = None
    assert adapter.status()["connected"]


def test_scene_switch_validation_and_confirmation():
    adapter, obs = make_adapter()
    assert adapter.status()["current_scene"] == obs.scenes[0]
    assert adapter.command("scene", adapter.revision, obs.scenes[1])["result"] == "VERIFIED"
    assert obs.current == obs.scenes[1]
    assert adapter.command("scene", adapter.revision, obs.current)["result"] == "ALREADY_CURRENT"
    with pytest.raises(ObsError, match="OBS_SCENE_INVALID"):
        adapter.command("scene", adapter.revision, "unknown scene")
    assert sum(name == "SetCurrentProgramScene" for name, _ in obs.calls) == 1


def test_exact_existing_browser_input_refresh_and_unsafe_url_redaction():
    adapter, obs = make_adapter()
    assert adapter.status()["overlay"]["enabled"] is True
    assert adapter.command("refresh", adapter.revision)["result"] == "REFRESH_REQUEST_ACKNOWLEDGED"
    obs.url += "?password=" + PASSWORD
    state = adapter.status()
    assert state["overlay"]["url"] is None
    assert PASSWORD not in json.dumps(state)
    with pytest.raises(ObsError, match="OBS_OVERLAY_INVALID"):
        adapter.command("refresh", adapter.revision)
    assert sum(name == "PressInputPropertiesButton" for name, _ in obs.calls) == 1


def test_recording_actual_state_duplicate_and_stale_request():
    adapter, obs = make_adapter()
    revision = adapter.status()["revision"]
    start = adapter.command("start", revision)
    assert start["recording"]["active"] and start["result"] == "VERIFIED"
    with pytest.raises(ObsError, match="OBS_STALE"):
        adapter.command("start", revision)
    assert adapter.command("start", adapter.revision)["result"] == "ALREADY_IN_STATE"
    stop = adapter.command("stop", adapter.revision)
    assert not stop["recording"]["active"]
    assert stop["recording"]["output_path"] == obs.output_path
    assert adapter.command("stop", adapter.revision)["result"] == "ALREADY_IN_STATE"
    assert sum(name == "StartRecord" for name, _ in obs.calls) == 1
    assert sum(name == "StopRecord" for name, _ in obs.calls) == 1


@pytest.mark.parametrize(
    "operation,rpc_name",
    [("start", "StartRecord"), ("stop", "StopRecord"), ("scene", "SetCurrentProgramScene")],
)
def test_lost_reply_queries_actual_state_without_retry(operation, rpc_name):
    adapter, obs = make_adapter()
    obs.active = operation == "stop"
    obs.lost = rpc_name
    result = adapter.command(operation, adapter.revision, obs.scenes[1])
    assert result["result"] == "STATE_RECONCILED"
    assert sum(name == rpc_name for name, _ in obs.calls) == 1
    if operation == "stop":
        assert (
            result["recording"]["output_path"] is None
        )  # lost StopRecord reply cannot prove a file


def test_uncertain_recording_and_refresh_fail_closed_without_retry():
    adapter, obs = make_adapter()
    obs.fail = "StartRecord"
    with pytest.raises(ObsError, match="OBS_OUTCOME_UNKNOWN"):
        adapter.command("start", adapter.revision)
    assert not obs.active
    assert sum(name == "StartRecord" for name, _ in obs.calls) == 1
    obs.fail = None
    obs.lost = "PressInputPropertiesButton"
    with pytest.raises(ObsError, match="OBS_OUTCOME_UNKNOWN"):
        adapter.command("refresh", adapter.revision)
    assert sum(name == "PressInputPropertiesButton" for name, _ in obs.calls) == 1


def test_reconciliation_unavailable_and_concurrent_requests():
    adapter, obs = make_adapter()
    original = obs.send

    def lose_both(name, data=None, raw=False):
        if name == "StartRecord":
            obs.lost = name
            obs.fail = "GetRecordStatus"
        return original(name, data, raw)

    obs.send = lose_both
    with pytest.raises(ObsError, match="OBS_OUTCOME_UNKNOWN"):
        adapter.command("start", adapter.revision)
    with adapter.lock:
        with pytest.raises(ObsError, match="OBS_BUSY"):
            adapter.command("stop", adapter.revision)
        with pytest.raises(ObsError, match="OBS_BUSY"):
            adapter.status()
    assert obs.active
    assert sum(name == "StartRecord" for name, _ in obs.calls) == 1


def test_streaming_controls_forbidden_and_redaction():
    adapter, obs = make_adapter()
    for name in ("StartStream", "StopStream", "ToggleStream", "StartOutput", "CallVendorRequest"):
        assert name not in ALLOWLIST
        with pytest.raises(ObsError, match="OBS_REQUEST_REJECTED"):
            adapter._rpc(name)
    obs.streaming = True
    with pytest.raises(ObsError, match="OBS_STREAM_ACTIVE"):
        adapter.command("start", adapter.revision)
    obs.streaming = False
    obs.reject = "StartRecord"
    with pytest.raises(ObsError, match="^OBS_REQUEST_REJECTED$"):
        adapter.command("start", adapter.revision)
    assert PASSWORD not in repr(adapter.config)
    obs.scenes[0] = PASSWORD
    obs.current = PASSWORD
    with pytest.raises(ObsError, match="OBS_PROTOCOL"):
        adapter.status()


def test_config_numeric_loopback_and_environment_redaction(monkeypatch):
    for host in ("0.0.0.0", "localhost", "192.168.1.4", "example.com", "127.0.0.1@evil"):
        monkeypatch.setenv("OBS_WS_HOST", host)
        monkeypatch.setenv("OBS_WS_PASSWORD", PASSWORD)
        monkeypatch.setenv("OBS_ADMIN_PASSWORD", ADMIN_PASSWORD)
        assert not ObsConfig.load().configured
    monkeypatch.setenv("OBS_WS_HOST", "127.0.0.1")
    assert ObsConfig.load().configured


@contextmanager
def wire_server(password=PASSWORD, authentication=True):
    calls = []

    def handler(ws):
        hello = {"obsWebSocketVersion": "5.6.3", "rpcVersion": 1}
        if authentication:
            hello["authentication"] = {"challenge": "synthetic-challenge", "salt": "synthetic-salt"}
        ws.send(json.dumps({"op": 0, "d": hello}))
        identify = json.loads(ws.recv())
        if authentication:
            secret = base64.b64encode(
                hashlib.sha256((password + "synthetic-salt").encode()).digest()
            )
            expected = base64.b64encode(
                hashlib.sha256(secret + b"synthetic-challenge").digest()
            ).decode()
            if identify["d"].get("authentication") != expected:
                ws.close(4009, "Authentication failed")
                return
        ws.send(json.dumps({"op": 2, "d": {"negotiatedRpcVersion": 1}}))
        for raw in ws:
            data = json.loads(raw)["d"]
            calls.append(data["requestType"])
            ws.send(
                json.dumps(
                    {
                        "op": 7,
                        "d": {
                            "requestId": data["requestId"],
                            "requestType": data["requestType"],
                            "requestStatus": {"result": True, "code": 100},
                            "responseData": {
                                "obsVersion": "32.2.2",
                                "obsWebSocketVersion": "5.6.3",
                            },
                        },
                    }
                )
            )

    with serve(handler, "127.0.0.1", 0, logger=logging.getLogger("synthetic_obs_wire")) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield server.socket.getsockname()[1], calls
        finally:
            server.shutdown()
            thread.join(timeout=5)


def test_real_sdk_v5_handshake_wrong_password_noauth_and_logging(caplog):
    caplog.set_level(logging.DEBUG)
    with wire_server() as (port, calls):
        config = ObsConfig(port=port, password=PASSWORD, admin_password=ADMIN_PASSWORD)
        client = connect(config)
        assert client.send("GetVersion", raw=True)["obsVersion"] == "32.2.2"
        client.disconnect()
        assert calls == ["GetVersion"]
        with pytest.raises(ObsError, match="OBS_AUTH_FAILED"):
            connect(
                config.model_copy(
                    update={"password": type(config.password)("wrong-private-password")}
                )
            )
    with (
        wire_server(authentication=False) as (port, _),
        pytest.raises(ObsError, match="OBS_AUTH_REQUIRED"),
    ):
        connect(ObsConfig(port=port, password=PASSWORD, admin_password=ADMIN_PASSWORD))
    assert PASSWORD not in caplog.text
    assert "wrong-private-password" not in caplog.text
    assert ADMIN_PASSWORD not in caplog.text


def test_unconfigured_never_connects():
    adapter = ObsAdapter(
        ObsConfig(), "http://localhost:8000/overlay", factory=lambda _: pytest.fail()
    )
    with pytest.raises(ObsError, match="OBS_NOT_CONFIGURED"):
        adapter.status()


def test_setup_refuses_noninteractive_password_entry(monkeypatch, capsys):
    import sys

    from crowdquest import obs_setup

    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    monkeypatch.setattr(obs_setup, "getpass", lambda _: pytest.fail("Must not read a password"))
    monkeypatch.setattr(
        obs_setup, "WindowsVault", lambda _: pytest.fail("Must not touch credentials")
    )
    assert obs_setup.main() == 1
    assert "INTERACTIVE_TERMINAL_REQUIRED" in capsys.readouterr().out
