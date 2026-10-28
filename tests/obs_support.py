"""SYNTHETIC OBS v5 fixture. Never connects to installed OBS or records media."""

from copy import deepcopy

from obsws_python.error import OBSSDKRequestError

from crowdquest.obs import ObsAdapter, ObsConfig

PASSWORD = "synthetic-websocket-password"
ADMIN_PASSWORD = "synthetic-separate-admin-password"


class SyntheticObs:
    def __init__(self):
        self.scenes = ["CrowdQuest Demo", "Other existing scene"]
        self.current = self.scenes[0]
        self.active = False
        self.streaming = False
        self.enabled = True
        self.url = "http://localhost:8000/overlay"
        self.calls = []
        self.fail = None
        self.lost = None
        self.reject = None
        self.duration = 1234
        self.output_path = "C:/synthetic-recordings/test.mkv"

    def send(self, name, data=None, raw=False):
        assert raw
        self.calls.append((name, deepcopy(data)))
        if self.fail == name:
            raise TimeoutError(PASSWORD)
        if self.reject == name:
            raise OBSSDKRequestError(name, 500, PASSWORD)
        value = {}
        if name == "GetVersion":
            value = {"obsVersion": "32.2.2", "obsWebSocketVersion": "5.6.3"}
        elif name == "GetSceneList":
            value = {
                "scenes": [{"sceneName": scene} for scene in self.scenes],
                "currentProgramSceneName": self.current,
            }
        elif name == "GetCurrentProgramScene":
            value = {"currentProgramSceneName": self.current}
        elif name == "GetStreamStatus":
            value = {"outputActive": self.streaming}
        elif name == "GetRecordStatus":
            value = {
                "outputActive": self.active,
                "outputPaused": False,
                "outputDuration": self.duration,
            }
        elif name == "GetInputSettings":
            assert data == {"inputName": "CrowdQuest Overlay"}
            value = {"inputKind": "browser_source", "inputSettings": {"url": self.url}}
        elif name == "GetSceneItemList":
            value = {
                "sceneItems": [
                    {
                        "sourceName": "CrowdQuest Overlay",
                        "sceneItemId": 7,
                        "sceneItemEnabled": self.enabled,
                    }
                ]
            }
        elif name == "SetCurrentProgramScene":
            self.current = data["sceneName"]
        elif name == "StartRecord":
            self.active = True
        elif name == "StopRecord":
            self.active = False
            value = {"outputPath": self.output_path}
        elif name == "PressInputPropertiesButton":
            assert data == {"inputName": "CrowdQuest Overlay", "propertyName": "refreshnocache"}
        else:
            raise AssertionError(name)
        if name == self.lost:
            self.lost = None
            raise TimeoutError(PASSWORD)
        return value

    def disconnect(self):
        pass


def make_adapter(*, clock=None, config=None):
    obs = SyntheticObs()
    adapter = ObsAdapter(
        config or ObsConfig(password=PASSWORD, admin_password=ADMIN_PASSWORD),
        obs.url,
        factory=lambda _: obs,
        **({"clock": clock} if clock else {}),
    )
    return adapter, obs
