"""Bounded display proposals. Authority is supplied only by trusted host composition."""

import json
import unicodedata
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Challenge(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")
    title: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=1, max_length=240)
    duration_seconds: int = Field(ge=15, le=120)
    difficulty: Literal["Easy", "Medium", "Hard"]

    @field_validator("title", "description")
    @classmethod
    def display_text(cls, value):
        if not value.strip() or any(unicodedata.category(c).startswith("C") for c in value):
            raise ValueError("DISPLAY_TEXT")
        value.encode("utf-8")
        return value


ARGUMENT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["title", "description", "duration_seconds", "difficulty"],
    "properties": {
        "title": {"type": "string", "minLength": 1, "maxLength": 80},
        "description": {"type": "string", "minLength": 1, "maxLength": 240},
        "duration_seconds": {"type": "integer", "minimum": 15, "maximum": 120},
        "difficulty": {
            "type": "string",
            "minLength": 4,
            "maxLength": 6,
            "pattern": "^(Easy|Medium|Hard)$",
        },
    },
}


def challenge_semantics(arguments, target):
    # A non-None result rejects through AIG's public capability contract.
    try:
        Challenge.model_validate(dict(arguments))
    except ValueError:
        return "DISPLAY_TEXT_REJECTED"
    return None


class OfflineChallengeProvider:
    """Explicit manual/offline proposal scaffold, never a real AI inference claim."""

    def __init__(self, binding):
        self.binding = binding

    async def generate_plan(self, intent, **kwargs):
        challenge = Challenge.model_validate_json(intent.text)
        return json.dumps(
            {
                "goal": "Display one owner-reviewed audience challenge",
                "target": self.binding.target,
                "steps": [
                    {
                        "tool_name": self.binding.tool_name,
                        "tool_version": self.binding.tool_version,
                        "arguments": challenge.model_dump(),
                    }
                ],
                "risk_class": "SIDE_EFFECT",
            }
        )
