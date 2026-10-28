"""Bounded local OBS v5 adapter. Never exposed as a generic RPC endpoint."""

import logging
import os
import threading
import time
from pathlib import Path
from uuid import uuid4

import obsws_python
import websocket
from obsws_python.error import OBSSDKError, OBSSDKRequestError
from pydantic import BaseModel, ConfigDict, Field, SecretStr

from .secrets import WindowsVault

ERRORS = {
    "OBS_NOT_CONFIGURED": "Run python -m crowdquest.obs_setup privately, then start the server.",
    "OBS_UNAVAILABLE": "Open OBS. Check Tools > WebSocket Server Settings and port 4455.",
    "OBS_AUTH_FAILED": "Check the configured password privately. Keep OBS authentication enabled.",
    "OBS_AUTH_REQUIRED": "Enable OBS WebSocket authentication yourself; this app will not change it.",
    "OBS_PROTOCOL": "OBS returned an unsupported response. Check that obs-websocket v5 is enabled.",
    "OBS_REQUEST_REJECTED": "OBS rejected this operation. Check OBS locally, then refresh status.",
    "OBS_BUSY": "Another operation is in progress. Wait and refresh status.",
    "OBS_STALE": "This page state was already used. Refresh status before another operation.",
    "OBS_SCENE_INVALID": "Select an existing scene from the refreshed list.",
    "OBS_OVERLAY_INVALID": "Use the existing CrowdQuest Overlay browser input with the exact local overlay URL.",
    "OBS_STREAM_ACTIVE": "OBS is streaming. Admin changes are blocked until you stop it yourself.",
    "OBS_OUTCOME_UNKNOWN": "The outcome is uncertain. Inspect OBS and refresh status; no command was retried.",
}


class ObsError(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def admin_directory():
    return (
        Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local/share"))
        / "CrowdQuestAI/obs-admin"
    )


class ObsConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", hide_input_in_errors=True)
    host: str = Field(default="127.0.0.1", pattern=r"^127\.0\.0\.1$")
    port: int = Field(default=4455, ge=1024, le=65535)
    password: SecretStr = Field(default=SecretStr(""), repr=False)
    admin_password: SecretStr = Field(default=SecretStr(""), repr=False)

    @property
    def configured(self):
        password = self.password.get_secret_value()
        admin = self.admin_password.get_secret_value()
        return bool(password) and 16 <= len(admin) <= 256 and admin != password

    @classmethod
    def load(cls):
        try:
            vault = WindowsVault(admin_directory())
            password = os.environ.get("OBS_WS_PASSWORD")
            admin = os.environ.get("OBS_ADMIN_PASSWORD")
            # No access to Twitch or runtime credentials; names and vault identity are separate.
            if password is None:
                password = vault.get("obs_ws_password") or ""
            if admin is None:
                admin = vault.get("admin_password") or ""
            return cls(
                host=os.environ.get("OBS_WS_HOST", "127.0.0.1"),
                port=int(os.environ.get("OBS_WS_PORT", "4455")),
                password=password,
                admin_password=admin,
            )
        except Exception:  # noqa: BLE001 -- never expose credential-store or input values
            # Credential store and validation errors must not include supplied values.
            return cls()


def safe_text(value, limit=256):
    if not isinstance(value, str) or not 1 <= len(value) <= limit:
        raise ObsError("OBS_PROTOCOL")
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ObsError("OBS_PROTOCOL")
    return value


ALLOWLIST = frozenset(
    {
        "GetVersion",
        "GetSceneList",
        "GetCurrentProgramScene",
        "GetRecordStatus",
        "GetStreamStatus",
        "GetSceneItemList",
        "GetInputSettings",
        "SetCurrentProgramScene",
        "PressInputPropertiesButton",
        "StartRecord",
        "StopRecord",
    }
)


def connect(config):
    # This SDK logs passwords at INFO and full response/error payloads at other levels.
    # Suppress every imported package logger, including the child loggers it constructs.
    for name in (
        "obsws_python",
        "obsws_python.baseclient",
        "obsws_python.baseclient.ObsClient",
        "obsws_python.reqs",
        "obsws_python.reqs.ReqClient",
        "websocket",
    ):
        logging.getLogger(name).disabled = True
    websocket.enableTrace(False)
    try:
        client = obsws_python.ReqClient(
            host=config.host,
            port=config.port,
            password=config.password.get_secret_value(),
            timeout=2,
            subs=0,
        )
        if "authentication" not in client.base_client.server_hello.get("d", {}):
            client.disconnect()
            raise ObsError("OBS_AUTH_REQUIRED")
        return client
    except ObsError:
        raise
    except OBSSDKError:
        raise ObsError("OBS_AUTH_FAILED") from None
    except Exception:  # noqa: BLE001 -- fixed public connection error only
        raise ObsError("OBS_UNAVAILABLE") from None


class ObsAdapter:
    def __init__(self, config, overlay_url, *, factory=connect, clock=time.monotonic):
        self.config, self.overlay_url = config, overlay_url
        self.factory, self.clock = factory, clock
        self.client = None
        self.lock = threading.Lock()
        self.revision = str(uuid4())
        self.last_path = None
        self.next_connect = 0
        self.connection_error = "OBS_UNAVAILABLE"

    def close(self):
        client, self.client = self.client, None
        if client is not None:
            try:
                client.disconnect()
            except Exception:  # noqa: BLE001, S110 -- never log credential-bearing SDK errors
                pass

    def _rpc(self, name, data=None):
        if name not in ALLOWLIST:
            raise ObsError("OBS_REQUEST_REJECTED")
        if not self.config.configured:
            raise ObsError("OBS_NOT_CONFIGURED")
        if self.client is None:
            if self.clock() < self.next_connect:
                raise ObsError(self.connection_error)
            try:
                self.client = self.factory(self.config)
            except ObsError as error:
                self.connection_error = error.code
                self.next_connect = self.clock() + 5
                raise
        try:
            value = self.client.send(name, data, raw=True)
            if value is not None and not isinstance(value, dict):
                raise ObsError("OBS_PROTOCOL")
            return value or {}
        except OBSSDKRequestError:
            raise ObsError("OBS_REQUEST_REJECTED") from None
        except Exception:  # noqa: BLE001 -- SDK failures can contain raw private response data
            # Close before any reconciliation so a late response cannot answer a new request.
            self.close()
            raise ObsError("OBS_UNAVAILABLE") from None

    def _record(self):
        value = self._rpc("GetRecordStatus")
        if (
            type(value.get("outputActive")) is not bool
            or type(value.get("outputPaused")) is not bool
        ):
            raise ObsError("OBS_PROTOCOL")
        elapsed = value.get("outputDuration")
        if type(elapsed) not in (int, float) or not 0 <= elapsed <= 10**12:
            raise ObsError("OBS_PROTOCOL")
        return {
            "active": value["outputActive"],
            "paused": value["outputPaused"],
            "elapsed_seconds": elapsed / 1000,
            "output_path": self.last_path,
        }

    def _text(self, value, limit=256):
        value = safe_text(value, limit)
        if any(
            secret and secret in value
            for secret in (
                self.config.password.get_secret_value(),
                self.config.admin_password.get_secret_value(),
            )
        ):
            raise ObsError("OBS_PROTOCOL")
        return value

    def _scenes(self):
        value = self._rpc("GetSceneList")
        rows = value.get("scenes")
        if not isinstance(rows, list) or not 1 <= len(rows) <= 64:
            raise ObsError("OBS_PROTOCOL")
        scenes = [self._text(row.get("sceneName")) for row in rows if isinstance(row, dict)]
        current = self._text(value.get("currentProgramSceneName"))
        if len(scenes) != len(rows) or current not in scenes or len(set(scenes)) != len(scenes):
            raise ObsError("OBS_PROTOCOL")
        return scenes, current

    def _overlay(self, current):
        try:
            value = self._rpc("GetInputSettings", {"inputName": "CrowdQuest Overlay"})
        except ObsError as error:
            if error.code == "OBS_REQUEST_REJECTED":
                return {"found": False, "valid": False, "enabled": None, "url": None}
            raise
        settings = value.get("inputSettings", {})
        valid = (
            value.get("inputKind") == "browser_source"
            and isinstance(settings, dict)
            and settings.get("url") == self.overlay_url
            and not settings.get("is_local_file", False)
        )
        if not valid:
            return {"found": True, "valid": False, "enabled": None, "url": None}
        rows = self._rpc("GetSceneItemList", {"sceneName": current}).get("sceneItems")
        if not isinstance(rows, list) or len(rows) > 256:
            raise ObsError("OBS_PROTOCOL")
        items = [row for row in rows if row.get("sourceName") == "CrowdQuest Overlay"]
        if any(type(row.get("sceneItemEnabled")) is not bool for row in items):
            raise ObsError("OBS_PROTOCOL")
        return {
            "found": True,
            "valid": True,
            "enabled": any(row["sceneItemEnabled"] for row in items) if items else None,
            "url": self.overlay_url,
        }

    def _snapshot(self):
        version = self._rpc("GetVersion")
        scenes, current = self._scenes()
        streaming = self._rpc("GetStreamStatus").get("outputActive")
        if type(streaming) is not bool:
            raise ObsError("OBS_PROTOCOL")
        obs_version = self._text(version.get("obsVersion"), 64)
        websocket_version = self._text(version.get("obsWebSocketVersion"), 64)
        if not websocket_version.startswith("5."):
            raise ObsError("OBS_PROTOCOL")
        return {
            "connected": True,
            "revision": self.revision,
            "obs_version": obs_version,
            "websocket_version": websocket_version,
            "scenes": scenes,
            "current_scene": current,
            "streaming": streaming,
            "recording": self._record(),
            "overlay": self._overlay(current),
        }

    def status(self):
        if not self.lock.acquire(blocking=False):
            raise ObsError("OBS_BUSY")
        try:
            # Status alone can reconnect, at most once per request and once per 5s on failure.
            return self._snapshot()
        except ObsError:
            raise
        except Exception:  # noqa: BLE001 -- malformed SDK responses must fail closed
            self.close()
            raise ObsError("OBS_PROTOCOL") from None
        finally:
            self.lock.release()

    def command(self, operation, revision, scene=None):
        if not self.lock.acquire(blocking=False):
            raise ObsError("OBS_BUSY")
        try:
            if revision != self.revision:
                raise ObsError("OBS_STALE")
            self.revision = str(uuid4())  # consumed even on failure; never retry a mutation
            if self._rpc("GetStreamStatus").get("outputActive") is not False:
                raise ObsError("OBS_STREAM_ACTIVE")
            if operation == "scene":
                scenes, current = self._scenes()
                if scene not in scenes:
                    raise ObsError("OBS_SCENE_INVALID")
                if current == scene:
                    return {"ok": True, "result": "ALREADY_CURRENT", "current_scene": current}
                request, data = "SetCurrentProgramScene", {"sceneName": scene}
            elif operation == "refresh":
                _, current = self._scenes()
                if not self._overlay(current)["valid"]:
                    raise ObsError("OBS_OVERLAY_INVALID")
                request, data = (
                    "PressInputPropertiesButton",
                    {
                        "inputName": "CrowdQuest Overlay",
                        "propertyName": "refreshnocache",
                    },
                )
            elif operation in ("start", "stop"):
                active = self._record()["active"]
                if active == (operation == "start"):
                    return {"ok": True, "result": "ALREADY_IN_STATE", "recording": self._record()}
                if operation == "start":
                    self.last_path = None
                request, data = ("StartRecord" if operation == "start" else "StopRecord"), None
            else:
                raise ObsError("OBS_REQUEST_REJECTED")
            uncertain = False
            try:
                response = self._rpc(request, data)
                if operation == "stop" and response.get("outputPath"):
                    self.last_path = self._text(response["outputPath"], 2048)
            except ObsError as error:
                if error.code == "OBS_REQUEST_REJECTED":
                    raise
                uncertain = True
            # Never resend a mutation. A fresh connection can only re-query actual state.
            try:
                if operation in ("start", "stop"):
                    record = self._record()
                    if record["active"] != (operation == "start"):
                        raise ObsError("OBS_OUTCOME_UNKNOWN")
                    return {
                        "ok": True,
                        "result": "STATE_RECONCILED" if uncertain else "VERIFIED",
                        "recording": record,
                    }
                if operation == "scene":
                    current = self._rpc("GetCurrentProgramScene").get("currentProgramSceneName")
                    if current != scene:
                        raise ObsError("OBS_OUTCOME_UNKNOWN")
                    return {
                        "ok": True,
                        "result": "STATE_RECONCILED" if uncertain else "VERIFIED",
                        "current_scene": current,
                    }
            except ObsError:
                raise ObsError("OBS_OUTCOME_UNKNOWN") from None
            if uncertain:
                raise ObsError("OBS_OUTCOME_UNKNOWN")
            # Button ACK is not proof of OBS rendering or a challenge being shown.
            return {"ok": True, "result": "REFRESH_REQUEST_ACKNOWLEDGED"}
        except ObsError:
            raise
        except Exception:  # noqa: BLE001 -- uncertain mutation, never echo raw error or retry
            self.close()
            raise ObsError("OBS_OUTCOME_UNKNOWN") from None
        finally:
            self.lock.release()
