"""Distinct authenticated owner operations and a separate worker credential role."""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from .admission import uuid4_string
from .challenges import Challenge
from .phase2_routes import Command, Decision
from .product import GenerationBusy


class Manual(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    expected_version: int = Field(ge=0)
    challenge: Challenge


class WorkerTick(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    worker_instance: str = Field(min_length=36, max_length=36)
    server_instance: str = Field(min_length=36, max_length=36)


class GenerateRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")


def register_phase3(app, owner, intake):
    routes = APIRouter()

    async def service(request, mutate=False):
        identity, _ = await owner(request, mutate)
        current = app.state.phase3_service
        if not current or current.owner_id != identity.user_id:
            raise HTTPException(403, "WORKFLOW_OWNER_REQUIRED")
        return current

    def identifier(value):
        if not uuid4_string(value):
            raise HTTPException(422, "WORKFLOW_IDENTIFIER")
        return value

    def candidate(current, candidate_id):
        identifier(candidate_id)
        found = next(
            (c for c in intake.candidates(current.owner_id) if c["id"] == candidate_id), None
        )
        if found is None:
            raise HTTPException(404, "CANDIDATE_NOT_FOUND")
        return found

    def denied():
        return HTTPException(409, "WORKFLOW_DENIED_OR_UNCONFIRMED")

    @routes.get("/api/phase3/status")
    async def status(request: Request):
        current = await service(request)
        return {
            "provider": current.provider_name,
            "audit": current.proposals.audit(),
            "receipt_scope": "Admission and browser acknowledgement are separate; OBS requires visual verification",
        }

    @routes.get("/api/phase3/candidates/{candidate_id}")
    async def view(candidate_id: str, request: Request):
        current = await service(request)
        candidate(current, candidate_id)
        try:
            return current.view(candidate_id)
        except Exception:  # noqa: BLE001 -- fixed safe API errors, no retry
            raise denied() from None

    @routes.post("/api/phase3/candidates/{candidate_id}/generate")
    async def generate(candidate_id: str, request: Request, value: GenerateRequest):
        current = await service(request, True)
        value = candidate(current, candidate_id)
        try:
            intake.voting.require_plannable(current.owner_id, candidate_id)
            return await current.generate(value)
        except GenerationBusy:
            raise HTTPException(429, "GENERATION_BUSY") from None
        except Exception:  # noqa: BLE001 -- fixed safe API errors, no retry
            raise denied() from None

    @routes.post("/api/phase3/candidates/{candidate_id}/manual")
    async def manual(candidate_id: str, request: Request, value: Manual):
        current = await service(request, True)
        candidate(current, candidate_id)
        try:
            intake.voting.require_plannable(current.owner_id, candidate_id)
            return await current.manual(
                candidate_id, value.challenge.model_dump(), value.expected_version
            )
        except Exception:  # noqa: BLE001 -- fixed safe API errors, no retry
            raise denied() from None

    @routes.post("/api/phase3/runs/{run_id}/decision")
    async def decide(run_id: str, request: Request, value: Decision):
        current = await service(request, True)
        identifier(run_id)
        try:
            return {
                "run": current.decide(
                    run_id, value.expected_version, value.decision, current.owner_id
                ).to_dict()
            }
        except Exception:  # noqa: BLE001 -- fixed safe API errors, no retry
            raise denied() from None

    @routes.post("/api/phase3/runs/{run_id}/admit")
    async def admit(run_id: str, request: Request, value: Command):
        current = await service(request, True)
        identifier(run_id)
        identifier(value.idempotency_key)
        try:
            return current.snapshot(
                current.admit(run_id, value.expected_version, value.idempotency_key)
            )
        except Exception:  # noqa: BLE001 -- fixed safe API errors, no retry
            raise denied() from None

    @routes.post("/api/phase3/actions/{action_id}/authorize")
    async def authorize(action_id: str, request: Request, value: Command):
        current = await service(request, True)
        identifier(action_id)
        identifier(value.idempotency_key)
        try:
            return current.snapshot(
                current.authorize(action_id, value.expected_version, value.idempotency_key)
            )
        except Exception:  # noqa: BLE001 -- fixed safe API errors, no retry
            raise denied() from None

    @routes.post("/api/phase3/actions/{action_id}/execute")
    async def execute(action_id: str, request: Request, value: Command):
        current = await service(request, True)
        identifier(action_id)
        identifier(value.idempotency_key)
        try:
            return current.snapshot(
                await current.execute(action_id, value.expected_version, value.idempotency_key)
            )
        except Exception:  # noqa: BLE001 -- fixed safe API errors, no retry
            raise denied() from None

    async def worker(request):
        current = app.state.phase3_service
        try:
            current.renderer.require_worker(request.headers.get("Authorization", ""))
        except (ValueError, AttributeError):
            raise HTTPException(401, "WORKER_AUTH_REQUIRED") from None
        identity = await app.state.auth.ensure()
        if identity is None or identity.user_id != current.owner_id:
            raise HTTPException(401, "WORKER_CHANNEL_AUTH_REQUIRED")
        return current.renderer

    @routes.get("/api/worker/session")
    async def worker_session(request: Request):
        return {"server_instance": (await worker(request)).boot}

    @routes.post("/api/worker/tick")
    async def tick(request: Request, value: WorkerTick):
        current = await worker(request)
        try:
            return current.tick(value.worker_instance, value.server_instance)
        except Exception:  # noqa: BLE001 -- fixed safe API errors, no retry
            raise HTTPException(409, "WORKER_FENCED_OR_UNCONFIRMED") from None

    app.include_router(routes)
