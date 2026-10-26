"""Trusted local configuration. Secrets are never read from public frontend input."""

import json
import os
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

ROOT = Path(__file__).resolve().parents[1]


def default_state_dir() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local/share"))
    return Path(os.environ.get("CROWDQUEST_STATE_DIR", base / "CrowdQuestAI/phase1")).resolve()


class Settings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    state_dir: Path
    client_id: str = Field(default="", pattern=r"^[a-zA-Z0-9]{0,80}$")
    owner_login: str = Field(default="", pattern=r"^[a-z0-9_]{0,25}$")
    port: int = Field(default=8000, ge=1024, le=65535)

    @property
    def origin(self) -> str:
        return f"http://localhost:{self.port}"

    @property
    def redirect_uri(self) -> str:
        return self.origin + "/auth/twitch/callback"

    @property
    def configured(self) -> bool:
        return bool(self.client_id and self.owner_login)

    @classmethod
    def load(cls):
        directory = default_state_dir()
        if directory.is_relative_to(ROOT):
            raise ValueError("Private state must be outside the repository")
        path = directory / "config.json"
        values = json.loads(path.read_text("utf-8")) if path.exists() else {}
        return cls(state_dir=directory, **values)
