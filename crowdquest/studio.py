"""Additional peer boundary for authenticated Studio routes; no media uploads or RPC."""

import ipaddress

from fastapi.responses import JSONResponse


def protect_studio(app):
    @app.middleware("http")
    async def studio_peer(request, call_next):
        if request.url.path == "/broadcast-studio" or request.url.path.startswith("/api/studio/"):
            try:
                allowed = request.client and ipaddress.ip_address(request.client.host).is_loopback
            except ValueError:
                allowed = False
            if not allowed:
                return JSONResponse(
                    {"detail": "LOCAL_STUDIO_ONLY"},
                    status_code=403,
                    headers={"Cache-Control": "no-store"},
                )
        return await call_next(request)
