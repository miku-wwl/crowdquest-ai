"""Local manual previews, with separately opt-in authenticated Phase 2 routes."""

import asyncio
import secrets
import time
from contextlib import ExitStack, asynccontextmanager, suppress
from dataclasses import dataclass
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
):
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
                task = asyncio.create_task(eventsub.run())
                yield
            finally:
                if task is not None:
                    task.cancel()
                    with suppress(asyncio.CancelledError):
                        await task
                app.state.phase2_service = None
                await auth.close()
                lock.release()

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.auth, app.state.store, app.state.eventsub = auth, store, eventsub
    app.state.phase2_service = None

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
                "connect-src 'self'; img-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'",
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
        return {"candidates": store.candidates(identity.user_id)}

    @app.post("/api/preview")
    async def select(request: Request, value: Selection):
        identity, _ = await owner(request, True)
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

    @app.get("/api/overlay/current")
    async def current(request: Request):
        prune_overlays()
        overlay_key = digest(request.cookies.get("cq_overlay", ""))
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

    if phase2_factory is not None:
        from .phase2_routes import register_phase2

        register_phase2(app, owner)

    assets = ROOT / "frontend/dist/assets"
    if assets.exists():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/")
    @app.get("/overlay")
    async def frontend():
        index = ROOT / "frontend/dist/index.html"
        if not index.exists():
            raise HTTPException(503, "FRONTEND_BUILD_REQUIRED")
        return FileResponse(index)

    return app
