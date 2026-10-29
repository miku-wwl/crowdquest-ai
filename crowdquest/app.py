"""Local manual previews, with separately opt-in authenticated Phase 2 routes."""

import asyncio
import secrets
import time
from contextlib import ExitStack, asynccontextmanager, closing, suppress
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from filelock import FileLock
from pydantic import BaseModel, ConfigDict, Field

from .auth import AuthError, TwitchAuth, digest
from .config import ROOT, Settings
from .eventsub import EventSub
from .intake import Store
from .secrets import WindowsVault

WARNING = "DEVELOPMENT PREVIEW — NOT APPROVED / NOT EXECUTED"


class Selection(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    candidate_id: str = Field(min_length=36, max_length=36)


class PairCode(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    code: str = Field(pattern=r"^[A-F0-9]{16}$")


class RenderAck(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    render_id: str = Field(min_length=36, max_length=36)
    delivery_id: str = Field(min_length=36, max_length=36)


class StudioClaim(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    presentation_id: str = Field(min_length=36, max_length=36)


@dataclass
class Session:
    generation: int
    csrf: str
    expires: float


def create_app(
    settings=None,
    *,
    auth=None,
    store=None,
    eventsub_factory=EventSub,
    clock=time.time,
    monotonic=time.monotonic,
    phase2_factory=None,
    phase3_factory=None,
    frontend_directory=None,
    obs_admin_enabled=False,
    studio_evidence="REAL_APPLICATION_STATE",
):
    if phase2_factory is not None and phase3_factory is not None:
        raise ValueError("SELECT_ONE_WORKFLOW")
    settings = settings or Settings.load()
    settings.state_dir.mkdir(parents=True, exist_ok=True)
    store = store or Store(settings.state_dir / "intake.sqlite3")
    auth = auth or TwitchAuth(settings, WindowsVault(settings.state_dir))
    eventsub = eventsub_factory(auth, store)
    sessions, overlays, views = {}, {}, {}
    pairing_failures = []
    preview = {"revision": 0, "expires": 0, "deadline": 0, "text": "", "source": ""}

    @asynccontextmanager
    async def lifespan(app):
        lock = FileLock(settings.state_dir / "phase1.lock")
        lock.acquire(timeout=0)
        task = None
        with ExitStack() as contexts:
            try:
                app.state.phase2_service = (
                    contexts.enter_context(phase2_factory()) if phase2_factory else None
                )
                app.state.phase3_service = (
                    contexts.enter_context(phase3_factory()) if phase3_factory else None
                )
                if app.state.phase3_service is not None:
                    app.state.phase3_service.voting = store.voting
                task = asyncio.create_task(eventsub.run())
                yield
            finally:
                if task is not None:
                    task.cancel()
                    with suppress(asyncio.CancelledError):
                        await task
                app.state.phase2_service = None
                app.state.phase3_service = None
                if app.state.obs_adapter is not None:
                    app.state.obs_adapter.close()
                await auth.close()
                lock.release()

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.auth, app.state.store, app.state.eventsub = auth, store, eventsub
    app.state.phase2_service = None
    app.state.phase3_service = None

    app.state.obs_adapter = None
    if obs_admin_enabled:
        from .obs_admin import register_obs_admin

        register_obs_admin(app, port=settings.port)

    @app.middleware("http")
    async def security(request: Request, call_next):
        if request.headers.get("host") != f"localhost:{settings.port}":
            return JSONResponse({"detail": "HOST_REJECTED"}, status_code=400)
        origin = request.headers.get("origin")
        if origin is not None and origin != settings.origin:
            return JSONResponse({"detail": "ORIGIN_REJECTED"}, status_code=403)
        if request.method == "POST":
            if origin != settings.origin:
                return JSONResponse({"detail": "ORIGIN_REQUIRED"}, status_code=403)
            if len(await request.body()) > 4096:
                return JSONResponse({"detail": "REQUEST_SIZE"}, status_code=413)
        if len(request.url.query) > 8192:
            return JSONResponse({"detail": "REQUEST_SIZE"}, status_code=413)
        if request.headers.get("sec-fetch-site") == "cross-site" and request.url.path not in (
            "/auth/twitch/callback",
            "/",
            "/overlay",
        ):
            return JSONResponse({"detail": "CROSS_SITE_REJECTED"}, status_code=403)
        response = await call_next(request)
        response.headers.update(
            {
                "Cache-Control": "no-store",
                "Referrer-Policy": "no-referrer",
                "X-Content-Type-Options": "nosniff",
                "X-Frame-Options": "DENY",
                "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; "
                "connect-src 'self'; img-src 'self'; media-src 'self' blob:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'",
            }
        )
        return response

    async def owner(request, mutate=False):
        identity = await auth.ensure()
        session = sessions.get(digest(request.cookies.get("cq_owner", "")))
        if (
            identity is None
            or session is None
            or session.expires <= monotonic()
            or session.generation != auth.generation
        ):
            raise HTTPException(401, "OWNER_AUTH_REQUIRED")
        if mutate and not secrets.compare_digest(
            request.headers.get("x-csrf-token", ""), session.csrf
        ):
            raise HTTPException(403, "CSRF_REJECTED")
        return identity, session

    @app.get("/api/me")
    async def me(request: Request):
        try:
            identity, session = await owner(request)
        except HTTPException:
            return {
                "authenticated": False,
                "configured": settings.configured,
                "connection": "auth_unavailable"
                if auth.reason == "TWITCH_AUTH_TEMPORARILY_UNAVAILABLE"
                else "unauthenticated",
                "reason": auth.reason,
                "workflow": "production" if phase3_factory else "development",
            }
        return {
            "authenticated": True,
            "login": identity.login,
            "csrf": session.csrf,
            "connection": eventsub.status,
            "reason": eventsub.reason,
            "last_event_at": eventsub.last_event_at,
            "eventsub": eventsub.snapshot() if hasattr(eventsub, "snapshot") else None,
            "warning": WARNING,
            "workflow": "production" if phase3_factory else "development",
            "features": ["crowd_voting", "owner_outcomes"] if phase3_factory else [],
        }

    @app.get("/auth/twitch/start")
    async def login():
        try:
            url, browser = auth.begin()
        except AuthError:
            raise HTTPException(503, "SETUP_OR_OAUTH_RATE_LIMIT") from None
        response = RedirectResponse(url, status_code=303)
        response.set_cookie(
            "cq_oauth", browser, httponly=True, samesite="lax", max_age=300, path="/auth/twitch"
        )
        return response

    @app.get("/auth/twitch/callback")
    async def callback(request: Request):
        # Query strings contain one-use authorization codes. Access logging is disabled.
        try:
            if any(len(request.query_params.getlist(k)) != 1 for k in ("state", "code")):
                raise AuthError("OAUTH_PARAMETERS")
            await auth.callback(
                request.query_params.get("state", ""),
                request.cookies.get("cq_oauth", ""),
                request.query_params.get("code", ""),
            )
        except (AuthError, RuntimeError):
            response = RedirectResponse("/?auth_error=AUTHENTICATION_FAILED", status_code=303)
        else:
            now = monotonic()
            expired = [key for key, value in sessions.items() if value.expires <= now]
            for key in expired:
                del sessions[key]
            if len(sessions) >= 8:
                sessions.clear()
            token = secrets.token_urlsafe(32)
            sessions[digest(token)] = Session(
                auth.generation, secrets.token_urlsafe(32), now + 8 * 3600
            )
            response = RedirectResponse("/", status_code=303)
            response.set_cookie(
                "cq_owner", token, httponly=True, samesite="strict", max_age=8 * 3600, path="/"
            )
        response.delete_cookie("cq_oauth", path="/auth/twitch")
        return response

    @app.post("/api/logout")
    async def logout(request: Request):
        await owner(request, True)
        if app.state.phase3_service is not None:
            renderer = app.state.phase3_service.renderer
            renderer.store.recover(renderer.boot)
        auth.invalidate("SIGNED_OUT")
        sessions.clear()
        overlays.clear()
        views.clear()
        preview["expires"] = 0
        preview["deadline"] = 0
        pairing_failures.clear()
        response = JSONResponse({"ok": True})
        response.delete_cookie("cq_owner", path="/")
        return response

    @app.get("/api/candidates")
    async def candidates(request: Request):
        identity, _ = await owner(request)
        session, visible = store.dashboard_candidates(identity.user_id)
        return {"session": session, "candidates": visible}

    @app.post("/api/studio/connect")
    async def connect_studio(request: Request):
        await owner(request, True)
        prune_overlays()
        key = digest(request.cookies.get("cq_studio", ""))
        previous = overlays.get(key)
        if previous and previous.get("studio") and previous["approved"]:
            return {"connected": True}
        if len(overlays) >= 8:
            raise HTTPException(429, "DISPLAY_CAPACITY")
        token = secrets.token_urlsafe(32)
        overlays[digest(token)] = {
            "code": "",
            "approved": True,
            "studio": True,
            "generation": auth.generation,
            "expires": monotonic() + 6 * 3600,
            "ready": None,
        }
        response = JSONResponse({"connected": True})
        response.set_cookie(
            "cq_studio",
            token,
            httponly=True,
            samesite="strict",
            max_age=6 * 3600,
            path="/api/studio",
        )
        return response

    @app.get("/api/studio/status")
    async def studio_status(request: Request):
        identity, _ = await owner(request)
        current = app.state.phase3_service
        worker, lifecycle, last_outcome = "not_enabled", None, None
        if current is not None:
            if current.owner_id != identity.user_id:
                raise HTTPException(403, "WORKFLOW_OWNER_REQUIRED")
            try:
                from contextlib import closing

                rendering = current.renderer.store
                with closing(rendering.connect()) as db:
                    leader = db.execute("SELECT boot,deadline FROM leader").fetchone()
                    worker = (
                        "ready"
                        if leader[0] == current.renderer.boot and leader[1] > rendering.monotonic()
                        else "unavailable"
                    )
                    row = db.execute(
                        "SELECT effect_key,state FROM renders ORDER BY rowid DESC LIMIT 1"
                    ).fetchone()
                    lifecycle = row["state"] if row else "WAITING"
                    outcome = db.execute(
                        "SELECT kind,state FROM challenge_outcomes ORDER BY rowid DESC LIMIT 1"
                    ).fetchone()
                    last_outcome = (
                        {"kind": outcome[0], "presentation": outcome[1]} if outcome else None
                    )
            except Exception:  # noqa: BLE001 -- no private storage errors at HTTP boundary
                raise HTTPException(503, "STUDIO_STATE_UNAVAILABLE") from None
        return {
            "backend": "connected",
            "eventsub": eventsub.status,
            "worker": worker,
            "challenge_state": lifecycle,
            "last_outcome": last_outcome,
            "workflow": "production" if current is not None else "development",
            "obs_required": False,
            "evidence": studio_evidence,
        }

    @app.post("/api/preview")
    async def select(request: Request, value: Selection):
        identity, _ = await owner(request, True)
        if phase3_factory is not None:
            raise HTTPException(403, "DEVELOPMENT_PREVIEW_DISABLED")
        try:
            UUID(value.candidate_id)
        except ValueError:
            raise HTTPException(422, "CANDIDATE_ID") from None
        candidate = store.select(value.candidate_id, identity.user_id)
        if candidate is None:
            raise HTTPException(404, "CANDIDATE_NOT_FOUND")
        preview.update(
            revision=preview["revision"] + 1,
            expires=clock() + 60,
            deadline=monotonic() + 60,
            text=candidate["suggestion"],
            source=candidate["source"],
        )
        return {"ok": True, "expires_at": preview["expires"], "warning": WARNING}

    @app.post("/api/preview/clear")
    async def clear(request: Request):
        await owner(request, True)
        if phase3_factory is not None:
            raise HTTPException(403, "DEVELOPMENT_PREVIEW_DISABLED")
        preview["expires"] = 0
        preview["deadline"] = 0
        return {"ok": True}

    def prune_overlays():
        now = monotonic()
        for key in list(overlays):
            value = overlays[key]
            if (
                value["expires"] <= now
                or value.get("generation", auth.generation) != auth.generation
            ):
                del overlays[key]
        for key in list(views):
            if views[key]["expires"] <= now:
                del views[key]

    @app.post("/api/overlay/pair")
    async def pair(request: Request):
        prune_overlays()
        old = overlays.get(digest(request.cookies.get("cq_overlay", "")))
        if old:
            return {"code": old["code"], "approved": old["approved"]}
        if len(overlays) >= 8:
            raise HTTPException(429, "PAIRING_CAPACITY")
        token = secrets.token_urlsafe(32)
        code = secrets.token_hex(8).upper()
        overlays[digest(token)] = {"code": code, "approved": False, "expires": monotonic() + 300}
        response = JSONResponse({"code": code, "approved": False})
        response.set_cookie(
            "cq_overlay",
            token,
            httponly=True,
            samesite="strict",
            max_age=6 * 3600,
            path="/api/overlay",
        )
        return response

    @app.get("/api/overlays")
    async def pending(request: Request):
        await owner(request)
        prune_overlays()
        return {
            "pending": [v["code"] for v in overlays.values() if not v["approved"]],
            "ready": sum(
                v["ready"] is not None and v["ready"] > monotonic() - 10
                for v in overlays.values()
                if v["approved"]
            ),
        }

    @app.post("/api/overlays/authorize")
    async def approve_pair(request: Request, value: PairCode):
        await owner(request, True)
        prune_overlays()
        now = monotonic()
        pairing_failures[:] = [at for at in pairing_failures if at > now - 60]
        if len(pairing_failures) >= 5:
            raise HTTPException(429, "PAIRING_RATE_LIMIT")
        found = next(
            (v for v in overlays.values() if secrets.compare_digest(v["code"], value.code)), None
        )
        if found is None:
            pairing_failures.append(now)
            raise HTTPException(404, "PAIRING_EXPIRED")
        if found["approved"]:
            pairing_failures.append(now)
            raise HTTPException(409, "PAIRING_CODE_ALREADY_USED")
        found.update(
            approved=True, generation=auth.generation, expires=monotonic() + 6 * 3600, ready=None
        )
        return {"ok": True}

    @app.get("/api/studio/current")
    @app.get("/api/overlay/current")
    async def current(request: Request):
        studio = request.url.path.startswith("/api/studio/")
        if studio:
            await owner(request)
        prune_overlays()
        overlay_key = digest(request.cookies.get("cq_studio" if studio else "cq_overlay", ""))
        pairing = overlays.get(overlay_key)
        if not pairing or not pairing["approved"]:
            raise HTTPException(401, "OVERLAY_PAIRING_REQUIRED")
        if not await auth.ensure():
            if auth.reason == "TWITCH_AUTH_TEMPORARILY_UNAVAILABLE":
                raise HTTPException(503, "TWITCH_AUTH_TEMPORARILY_UNAVAILABLE")
            raise HTTPException(401, "OVERLAY_PAIRING_REQUIRED")
        view = request.headers.get("x-overlay-view", "")
        try:
            if str(UUID(view)) != view:
                raise ValueError
        except ValueError:
            raise HTTPException(422, "VIEW_ID") from None
        if phase3_factory is not None:
            try:
                result = app.state.phase3_service.renderer.store.current(
                    overlay_key, view, consume=not studio
                )
                from .phase4_routes import voting_presentation

                result = voting_presentation(
                    store,
                    app.state.phase3_service,
                    auth.identity.user_id,
                    result,
                    clock(),
                    round_after=store.dashboard_session(auth.identity.user_id)["round_after"],
                )
            except Exception:  # noqa: BLE001 -- fixed code, no raw SQLite/credential errors
                raise HTTPException(503, "RENDER_STATE_UNAVAILABLE") from None
            pairing["ready"] = monotonic()
            return result
        key = (overlay_key, view)
        if key not in views:
            if sum(k[0] == overlay_key for k in views) >= 8:
                raise HTTPException(429, "VIEW_CAPACITY")
            views[key] = {"baseline": preview["revision"], "expires": monotonic() + 120}
        views[key]["expires"] = monotonic() + 120
        pairing["ready"] = monotonic()
        if preview["deadline"] <= monotonic():
            return {"state": "waiting", "reason": "PREVIEW_ENDED", "warning": WARNING}
        if preview["revision"] <= views[key]["baseline"]:
            return {"state": "waiting", "warning": WARNING}
        return {
            "state": "preview",
            "warning": WARNING,
            "text": preview["text"],
            "expires_at": preview["expires"],
            "remaining_seconds": max(0, preview["deadline"] - monotonic()),
            "source": preview["source"],
        }

    if phase3_factory is not None:
        from .phase3_routes import register_phase3

        register_phase3(app, owner, store)
        from .phase4_routes import register_phase4

        register_phase4(app, owner, store, clock)

        def demo_reset_blocked(service):
            """Fail closed while an old workflow or browser delivery is still active."""
            with service.lock:
                if service.model_active:
                    return True
                with closing(service.proposals.connect()) as db:
                    candidates = db.execute("SELECT current_run,status FROM candidates").fetchall()
                if any(status in ("GENERATING", "EDITING") for _, status in candidates):
                    return True
                for run_id, _ in candidates:
                    if not run_id:
                        continue
                    for action in service.base.actions_for_run(run_id):
                        if action.state.value not in ("Succeeded", "Failed", "Unknown"):
                            return True
                with closing(service.base.store.connect()) as db:
                    eligible = {
                        row[0]
                        for row in db.execute("SELECT effect_key FROM jobs WHERE state='ELIGIBLE'")
                    }
                with closing(service.renderer.store.connect()) as db:
                    rendered = {row[0] for row in db.execute("SELECT effect_key FROM renders")}
                    if eligible - rendered:
                        return True
                    if db.execute(
                        "SELECT 1 FROM renders WHERE state IN ('CLAIMED','SENT','RENDERED') LIMIT 1"
                    ).fetchone():
                        return True
            return False

        @app.get("/api/demo/session")
        async def demo_session(request: Request):
            identity, _ = await owner(request)
            service = app.state.phase3_service
            if service is None or service.owner_id != identity.user_id:
                raise HTTPException(403, "WORKFLOW_OWNER_REQUIRED")
            return {"session": store.dashboard_session(identity.user_id)}

        @app.post("/api/demo/session/clear")
        async def clear_demo_session(request: Request):
            identity, _ = await owner(request, True)
            service = app.state.phase3_service
            if service is None or service.owner_id != identity.user_id:
                raise HTTPException(403, "WORKFLOW_OWNER_REQUIRED")
            try:
                if demo_reset_blocked(service):
                    raise HTTPException(409, "DEMO_HISTORY_RESET_BUSY")
            except HTTPException:
                raise
            except Exception:  # noqa: BLE001 -- fail closed on private state read errors
                raise HTTPException(503, "DEMO_HISTORY_STORAGE_UNAVAILABLE") from None
            try:
                session = store.clear_dashboard_history(identity.user_id, now=clock())
            except ValueError as error:
                if str(error) == "DEMO_HISTORY_RESET_VOTING_ACTIVE":
                    raise HTTPException(409, "DEMO_HISTORY_RESET_BUSY") from None
                raise HTTPException(409, "DEMO_HISTORY_RESET_DENIED") from None
            except Exception:  # noqa: BLE001 -- never expose private storage details
                raise HTTPException(503, "DEMO_HISTORY_STORAGE_UNAVAILABLE") from None
            return {"session": session}

        @app.post("/api/studio/claim")
        async def studio_claim(request: Request, value: StudioClaim):
            await owner(request, True)
            prune_overlays()
            key = digest(request.cookies.get("cq_studio", ""))
            pairing = overlays.get(key)
            if not pairing or not pairing["approved"] or not await auth.ensure():
                raise HTTPException(401, "OVERLAY_PAIRING_REQUIRED")
            view = request.headers.get("x-overlay-view", "")
            from .admission import uuid4_string

            if not all(uuid4_string(v) for v in (view, value.presentation_id)):
                raise HTTPException(422, "RENDER_CLAIM_IDENTITY")
            try:
                return app.state.phase3_service.renderer.store.current(
                    key, view, expected_id=value.presentation_id
                )
            except Exception:  # noqa: BLE001 -- no storage/credential errors at HTTP boundary
                raise HTTPException(503, "RENDER_STATE_UNAVAILABLE") from None

        @app.post("/api/studio/ack")
        @app.post("/api/overlay/ack")
        async def render_ack(request: Request, value: RenderAck):
            studio = request.url.path.startswith("/api/studio/")
            if studio:
                await owner(request, True)
            prune_overlays()
            key = digest(request.cookies.get("cq_studio" if studio else "cq_overlay", ""))
            pairing = overlays.get(key)
            if not pairing or not pairing["approved"] or not await auth.ensure():
                raise HTTPException(401, "OVERLAY_PAIRING_REQUIRED")
            view = request.headers.get("x-overlay-view", "")
            from .admission import uuid4_string

            if not all(uuid4_string(v) for v in (view, value.render_id, value.delivery_id)):
                raise HTTPException(422, "RENDER_ACK_IDENTITY")
            try:
                app.state.phase3_service.renderer.store.acknowledge(
                    key, view, value.render_id, value.delivery_id
                )
            except ValueError:
                raise HTTPException(409, "RENDER_ACK_UNCONFIRMED") from None
            return {"ok": True, "evidence": "BROWSER_ACK_ONLY"}

    elif phase2_factory is not None:
        from .phase2_routes import register_phase2

        register_phase2(app, owner)

    from .studio import protect_studio

    protect_studio(app)

    frontend_directory = Path(frontend_directory) if frontend_directory else ROOT / "frontend/dist"
    assets = frontend_directory / "assets"
    if assets.exists():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/")
    @app.get("/overlay")
    @app.get("/obs-admin")
    @app.get("/broadcast-studio")
    async def frontend():
        index = frontend_directory / "index.html"
        if not index.exists():
            raise HTTPException(503, "FRONTEND_BUILD_REQUIRED")
        return FileResponse(index)

    return app
