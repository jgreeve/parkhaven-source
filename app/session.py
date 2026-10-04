"""Desktop-only authentication; the explicit browser development server is unchanged."""

import secrets

from starlette.datastructures import Headers
from starlette.responses import JSONResponse


class DesktopSessionMiddleware:
    def __init__(self, app, session):
        self.app = app
        self.session = session

    async def __call__(self, scope, receive, send):
        session = self.session()
        if scope["type"] != "http" or session is None:
            await self.app(scope, receive, send)
            return
        headers = Headers(scope=scope)
        provided = headers.get("x-parkhaven-session", "")
        # ASCII token; encode arbitrary untrusted input rather than raising on Unicode.
        authenticated = secrets.compare_digest(provided.encode("utf-8"), session["token"].encode("ascii"))
        if not authenticated:
            response = JSONResponse({"detail": "Ongeldige desktopsessie."}, status_code=401)
        elif headers.get("host") != session["authority"] or (
            headers.get("origin") is not None and headers["origin"] != session["origin"]
        ):
            response = JSONResponse({"detail": "Ongeldige lokale oorsprong."}, status_code=403)
        else:
            # Do not expose the session token to endpoint code, exception output or providers.
            scope = {**scope, "headers": [(key, value) for key, value in scope["headers"]
                                         if key.lower() != b"x-parkhaven-session"]}

            async def no_store(message):
                if message["type"] == "http.response.start":
                    message = {**message, "headers": [
                        (key, value) for key, value in message.get("headers", []) if key.lower() != b"cache-control"
                    ] + [(b"cache-control", b"no-store"), (b"referrer-policy", b"no-referrer")]}
                await send(message)

            await self.app(scope, receive, no_store)
            return
        response.headers["Cache-Control"] = "no-store"
        await response(scope, receive, send)
