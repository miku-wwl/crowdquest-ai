"""Authenticated consumer API; browser input never selects runtime authority."""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from .challenges import Challenge


class Decision(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    expected_version: int = Field(ge=1)
    decision: Literal["APPROVE", "REJECT"]


class Command(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    expected_version: int = Field(ge=1)
    idempotency_key: str = Field(min_length=36, max_length=36)


def register_phase2(app, owner):
    routes = APIRouter(prefix="/api/phase2")

    async def service(request, mutate=False):
        identity, _ = await owner(request, mutate)
        current = app.state.phase2_service
        if current is None:
            raise HTTPException(503, "PHASE2_NOT_ACTIVE")
        if identity.user_id != current.owner_id:
            raise HTTPException(403, "PHASE2_OWNER_MISMATCH")
        return current

    def identifier(value):
        try:
            if str(UUID(value)) != value:
                raise ValueError
        except ValueError:
            raise HTTPException(422, "PHASE2_IDENTIFIER") from None
        return value

    def denied():
        # Never propagate provider/store exceptions, token values or untrusted text.
        return HTTPException(409, "PHASE2_OPERATION_DENIED_OR_UNCONFIRMED")

    @routes.post("/runs")
    async def create(request: Request, value: Challenge):
        current = await service(request, True)
        try:
            run = await current.create(value.model_dump())
            return {"run": run.to_dict(), "planning_mode": "OFFLINE_MANUAL"}
        except Exception:  # noqa: BLE001 -- fixed safe response, no automatic retry
            raise denied() from None

    @routes.get("/runs/{run_id}")
    async def get_run(run_id: str, request: Request):
        current = await service(request)
        identifier(run_id)
        try:
            return {"run": current.run(run_id).to_dict(), "planning_mode": "OFFLINE_MANUAL"}
        except Exception:  # noqa: BLE001
            raise denied() from None

    @routes.post("/runs/{run_id}/decision")
    async def decide(run_id: str, request: Request, value: Decision):
        current = await service(request, True)
        identifier(run_id)
        try:
            return {
                "run": current.decide(
                    run_id, value.expected_version, value.decision, reviewer_id=current.owner_id
                ).to_dict()
            }
        except Exception:  # noqa: BLE001
            raise denied() from None

    @routes.post("/runs/{run_id}/admit")
    async def admit(run_id: str, request: Request, value: Command):
        current = await service(request, True)
        identifier(run_id)
        identifier(value.idempotency_key)
        try:
            return current.snapshot(
                current.admit(run_id, value.expected_version, value.idempotency_key)
            )
        except Exception:  # noqa: BLE001
            raise denied() from None

    @routes.get("/actions/{action_id}")
    async def get_action(action_id: str, request: Request):
        current = await service(request)
        identifier(action_id)
        try:
            return current.snapshot(current.refresh(action_id))
        except Exception:  # noqa: BLE001
            raise denied() from None

    @routes.post("/actions/{action_id}/authorize")
    async def authorize(action_id: str, request: Request, value: Command):
        current = await service(request, True)
        identifier(action_id)
        identifier(value.idempotency_key)
        try:
            return current.snapshot(
                current.authorize(action_id, value.expected_version, value.idempotency_key)
            )
        except Exception:  # noqa: BLE001
            raise denied() from None

    @routes.post("/actions/{action_id}/execute")
    async def execute(action_id: str, request: Request, value: Command):
        current = await service(request, True)
        identifier(action_id)
        identifier(value.idempotency_key)
        try:
            action = await current.execute(action_id, value.expected_version, value.idempotency_key)
            return current.snapshot(action)
        except Exception:  # noqa: BLE001
            raise denied() from None

    app.include_router(routes)
