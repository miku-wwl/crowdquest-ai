"""Owner voting/outcomes and presentation helpers. Voting supplies no execution grant."""

import sqlite3
from contextlib import closing
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .admission import uuid4_string
from .product import GenerationBusy


class RoundCreate(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    candidate_ids: list[str] = Field(min_length=2, max_length=2)
    duration_seconds: Literal[15, 30, 60] = 30
    idempotency_key: str

    @field_validator("duration_seconds", mode="before")
    @classmethod
    def integer_duration(cls, value):
        if type(value) is not int:
            raise ValueError("INTEGER_DURATION_REQUIRED")
        return value


class RoundCommand(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    expected_version: int = Field(ge=1)
    idempotency_key: str
    choice: int | None = Field(default=None, ge=1, le=2)


class WinnerPlan(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    expected_version: int = Field(ge=1)


class OutcomeCommand(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    kind: Literal["Completed", "Failed", "Skipped"]
    expected_version: int = Field(ge=1)
    idempotency_key: str


def voting_presentation(intake, service, channel, result, now):
    if result["state"] not in ("waiting", "expired"):
        return result
    if result["state"] == "expired":
        return result
    round_ = intake.voting.current(channel, now=now)
    if not round_ or round_["state"] in ("Draft", "Cancelled"):
        return result
    state = "voting" if round_["state"] == "Open" else "winner"
    if round_["winner"]:
        candidate_id = round_["choices"][round_["winner"] - 1]["candidate_id"]
        proposal = service.view(candidate_id)
        if proposal["action"] and proposal["action"]["state"] in ("Succeeded", "Unknown", "Failed"):
            return result
        if proposal["run"]:
            state = "pending_approval"
    # No candidate/Run/Action IDs, voter pseudonyms, identity keys or credentials.
    safe = {
        key: value
        for key, value in round_.items()
        if key in ("state", "remaining_seconds", "winner", "total_votes", "evidence")
    }
    safe["choices"] = [
        {key: value for key, value in choice.items() if key != "candidate_id"}
        for choice in round_["choices"]
    ]
    return {"mode": "production", "state": state, "round": safe}


def register_phase4(app, owner, intake, clock):
    routes = APIRouter(prefix="/api/phase4")

    async def service(request, mutate=False):
        identity, _ = await owner(request, mutate)
        current = app.state.phase3_service
        if not current or current.owner_id != identity.user_id:
            raise HTTPException(403, "WORKFLOW_OWNER_REQUIRED")
        return current

    def check(*identifiers):
        if not all(uuid4_string(value) for value in identifiers):
            raise HTTPException(422, "VOTING_IDENTIFIER")

    def denied(error):
        return HTTPException(
            503 if isinstance(error, sqlite3.OperationalError) else 409,
            "PRODUCT_STATE_UNAVAILABLE"
            if isinstance(error, sqlite3.OperationalError)
            else "PRODUCT_TRANSITION_DENIED",
        )

    @routes.get("/voting")
    async def current(request: Request):
        current = await service(request)
        try:
            return {
                "round": intake.voting.current(current.owner_id, now=clock()),
                "audit": intake.voting.audit(current.owner_id),
            }
        except Exception as error:  # noqa: BLE001 -- redact private runtime/storage errors at HTTP boundary
            raise denied(error) from None

    @routes.post("/rounds")
    async def create(request: Request, value: RoundCreate):
        current = await service(request, True)
        check(*value.candidate_ids, value.idempotency_key)
        try:
            with current.lock:
                if any(current.proposals.item(c) for c in value.candidate_ids):
                    raise ValueError("CANDIDATE_ALREADY_PLANNED")
                round_ = intake.voting.create(
                    current.owner_id,
                    value.candidate_ids,
                    value.duration_seconds,
                    value.idempotency_key,
                    now=clock(),
                )
            return {"round": round_}
        except Exception as error:  # noqa: BLE001 -- redact private runtime/storage errors at HTTP boundary
            raise denied(error) from None

    @routes.post("/rounds/{round_id}/plan")
    async def plan(round_id: str, request: Request, value: WinnerPlan):
        current = await service(request, True)
        check(round_id)
        try:
            with current.lock:
                if current.model_active:
                    raise GenerationBusy("GENERATION_BUSY")
                snapshot = intake.voting.current(current.owner_id, now=clock())
                if not snapshot or snapshot["id"] != round_id or not snapshot["winner"]:
                    raise ValueError("CURRENT_WINNER_REQUIRED")
                winner = snapshot["choices"][snapshot["winner"] - 1]["candidate_id"]
                if current.proposals.item(winner):
                    raise ValueError("WINNER_ALREADY_PLANNED")
                candidate = intake.voting.bind_winner(
                    current.owner_id, round_id, value.expected_version, now=clock()
                )
            proposal = await current.generate(candidate)
            return {"candidate_id": candidate["id"], "proposal": proposal}
        except GenerationBusy:
            raise HTTPException(429, "GENERATION_BUSY") from None
        except Exception as error:  # noqa: BLE001 -- redact private runtime/storage errors at HTTP boundary
            raise denied(error) from None

    @routes.post("/rounds/{round_id}/{operation}")
    async def transition(
        round_id: str,
        operation: Literal["start", "close", "cancel", "winner"],
        request: Request,
        value: RoundCommand,
    ):
        current = await service(request, True)
        check(round_id, value.idempotency_key)
        try:
            if operation == "start":
                current.renderer.store.maintain()
                with closing(current.renderer.store.connect()) as db:
                    if db.execute(
                        "SELECT 1 FROM renders WHERE state IN ('CLAIMED','SENT','RENDERED')"
                    ).fetchone():
                        raise ValueError("CHALLENGE_ALREADY_ACTIVE")
            return {
                "round": intake.voting.transition(
                    current.owner_id,
                    round_id,
                    operation,
                    value.expected_version,
                    value.idempotency_key,
                    choice=value.choice,
                    now=clock(),
                )
            }
        except Exception as error:  # noqa: BLE001 -- redact private runtime/storage errors at HTTP boundary
            raise denied(error) from None

    @routes.post("/actions/{action_id}/outcome")
    async def outcome(action_id: str, request: Request, value: OutcomeCommand):
        current = await service(request, True)
        check(action_id, value.idempotency_key)
        try:
            action = current.base.refresh(action_id)
            if action.version != value.expected_version:
                raise ValueError("STALE_ACTION")
            return current.record_outcome(action_id, value.kind, value.idempotency_key)
        except Exception as error:  # noqa: BLE001 -- redact private runtime/storage errors at HTTP boundary
            raise denied(error) from None

    app.include_router(routes)
