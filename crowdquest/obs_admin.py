"""Session-bound loopback OBS administration, independent of Twitch/AIG credentials."""

import hashlib
import ipaddress
import secrets
import time
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import UUID

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from .config import ROOT
from .obs import ERRORS, ObsAdapter, ObsConfig, ObsError

PREFIX = "/api/obs-admin"
COOKIE = "cq_obs_admin"


def hashed(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def register_obs_admin(app, *, port, adapter=None, clock=time.monotonic):
    adapter = adapter or ObsAdapter(ObsConfig.load(), f"http://localhost:{port}/overlay")
    app.state.obs_adapter = adapter
    origin = f"http://localhost:{port}"
    sessions, failures = {}, []

    @app.middleware("http")
    async def local_boundary(request: Request, call_next):
        if request.url.path != "/obs-admin" and not request.url.path.startswith(PREFIX):
            return await call_next(request)
        error, code = None, 403
        try:
            if not request.client or not ipaddress.ip_address(request.client.host).is_loopback:
                error = "LOCAL_ADMIN_ONLY"
        except ValueError:
            error = "LOCAL_ADMIN_ONLY"
        if request.headers.get("host") != f"localhost:{port}":
            error, code = "HOST_REJECTED", 400
        if request.headers.get("origin") not in (None, origin):
            error = "ORIGIN_REJECTED"
        if request.headers.get("sec-fetch-site") in ("cross-site", "same-site"):
            error = "CROSS_SITE_REJECTED"
        if request.method not in ("GET", "POST"):
            error, code = "METHOD_REJECTED", 405
        if request.method == "POST":
            if request.headers.get("origin") != origin:
                error = "ORIGIN_REQUIRED"
            if request.headers.get("content-type", "").split(";")[0] != "application/json":
                error, code = "JSON_REQUIRED", 415
        if len(request.url.query) or len(request.url.path) > 256:
            error, code = "REQUEST_REJECTED", 400
        if error:
            response = JSONResponse({"detail": error}, status_code=code)
        else:
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

    def prune():
        for key in list(sessions):
            if sessions[key]["expires"] <= clock():
                del sessions[key]

    def session(request, *, authenticated=True, mutate=False):
        prune()
        value = sessions.get(hashed(request.cookies.get(COOKIE, "")))
        if not value or (authenticated and not value["authenticated"]):
            raise HTTPException(401, "ADMIN_AUTH_REQUIRED")
        if mutate and not secrets.compare_digest(
            hashed(request.headers.get("x-csrf-token", "")), hashed(value["csrf"])
        ):
            raise HTTPException(403, "CSRF_REJECTED")
        return value

    def new_session(authenticated):
        prune()
        if len(sessions) >= 16:
            raise HTTPException(429, "ADMIN_SESSION_CAPACITY")
        token = secrets.token_urlsafe(32)
        value = {
            "authenticated": authenticated,
            "csrf": secrets.token_urlsafe(32),
            "expires": clock() + (3600 if authenticated else 300),
        }
        sessions[hashed(token)] = value
        response = JSONResponse(
            {
                "authenticated": authenticated,
                "csrf": value["csrf"],
                "configured": adapter.config.configured,
            }
        )
        response.set_cookie(
            COOKIE,
            token,
            httponly=True,
            samesite="strict",
            path=PREFIX,
            max_age=3600 if authenticated else 300,
        )
        return response

    async def body(request, fields):
        data = bytearray()
        async for chunk in request.stream():
            data.extend(chunk)
            if len(data) > 2048:
                raise HTTPException(413, "REQUEST_SIZE")
        try:
            import json

            def unique(pairs):
                result = {}
                for key, value in pairs:
                    if key in result:
                        raise ValueError
                    result[key] = value
                return result

            value = json.loads(data, object_pairs_hook=unique)
            if not isinstance(value, dict) or set(value) != set(fields):
                raise ValueError
            return value
        except Exception:  # noqa: BLE001 -- never echo login or validation input
            # Do not return validation inputs (which may contain passwords).
            raise HTTPException(422, "ADMIN_INPUT_REJECTED") from None

    @app.get(PREFIX + "/session")
    async def get_session(request: Request):
        try:
            value = session(request, authenticated=False)
        except HTTPException:
            return new_session(False)
        return {
            "authenticated": value["authenticated"],
            "csrf": value["csrf"],
            "configured": adapter.config.configured,
        }

    @app.post(PREFIX + "/login")
    async def login(request: Request):
        session(request, authenticated=False, mutate=True)
        value = await body(request, ("password",))
        failures[:] = [at for at in failures if at > clock() - 60]
        if len(failures) >= 5:
            raise HTTPException(429, "ADMIN_LOGIN_RATE_LIMIT")
        password = value["password"]
        if not adapter.config.configured:
            raise HTTPException(503, "OBS_NOT_CONFIGURED")
        if not isinstance(password, str) or not secrets.compare_digest(
            hashed(password), hashed(adapter.config.admin_password.get_secret_value())
        ):
            failures.append(clock())
            raise HTTPException(401, "ADMIN_LOGIN_FAILED")
        sessions.pop(hashed(request.cookies.get(COOKIE, "")), None)
        return new_session(True)

    @app.post(PREFIX + "/logout")
    async def logout(request: Request):
        session(request, mutate=True)
        await body(request, ())
        sessions.pop(hashed(request.cookies.get(COOKIE, "")), None)
        response = JSONResponse({"ok": True})
        response.delete_cookie(COOKIE, path=PREFIX)
        return response

    @app.get(PREFIX + "/status")
    async def status(request: Request):
        session(request)
        try:
            return await run_in_threadpool(adapter.status)
        except ObsError as error:
            return JSONResponse(
                {"connected": False, "detail": error.code, "message": ERRORS[error.code]},
                status_code=503,
            )

    async def command(request, operation, fields=("revision",)):
        session(request, mutate=True)
        value = await body(request, fields)
        try:
            revision = value["revision"]
            if not isinstance(revision, str) or str(UUID(revision)) != revision:
                raise ValueError
            if "scene" in fields and (
                not isinstance(value["scene"], str)
                or not 1 <= len(value["scene"]) <= 256
                or any(ord(char) < 32 for char in value["scene"])
            ):
                raise ValueError
        except (ValueError, TypeError):
            raise HTTPException(422, "ADMIN_INPUT_REJECTED") from None
        try:
            return await run_in_threadpool(adapter.command, operation, revision, value.get("scene"))
        except ObsError as error:
            code = 409 if error.code in ("OBS_BUSY", "OBS_STALE", "OBS_OUTCOME_UNKNOWN") else 503
            return JSONResponse(
                {"detail": error.code, "message": ERRORS[error.code]}, status_code=code
            )

    @app.post(PREFIX + "/scene")
    async def scene(request: Request):
        return await command(request, "scene", ("revision", "scene"))

    @app.post(PREFIX + "/overlay/refresh")
    async def refresh(request: Request):
        return await command(request, "refresh")

    @app.post(PREFIX + "/record/start")
    async def start(request: Request):
        return await command(request, "start")

    @app.post(PREFIX + "/record/stop")
    async def stop(request: Request):
        return await command(request, "stop")

    return adapter


def create_admin_app(*, port=8000, adapter=None, frontend_directory=None):
    """Optional OBS-only entry point. Never opens a CrowdQuest DB or Twitch session."""

    @asynccontextmanager
    async def lifespan(app):
        yield
        app.state.obs_adapter.close()

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    register_obs_admin(app, port=port, adapter=adapter)
    directory = Path(frontend_directory) if frontend_directory else ROOT / "frontend/dist"
    if (directory / "assets").exists():
        app.mount("/assets", StaticFiles(directory=directory / "assets"))

    @app.get("/obs-admin")
    async def frontend():
        if not (directory / "index.html").exists():
            raise HTTPException(503, "FRONTEND_BUILD_REQUIRED")
        return FileResponse(directory / "index.html")

    return app


if __name__ == "__main__":
    import argparse

    import uvicorn

    parser = argparse.ArgumentParser(description="OBS-only local admin; no Twitch or AIG startup")
    parser.add_argument(
        "--port", type=int, default=8000, choices=range(1024, 65536), metavar="PORT"
    )
    parser.add_argument("--frontend-directory", type=Path)
    args = parser.parse_args()
    uvicorn.run(
        create_admin_app(port=args.port, frontend_directory=args.frontend_directory),
        host="127.0.0.1",
        port=args.port,
        access_log=False,
        proxy_headers=False,
        workers=1,
    )
