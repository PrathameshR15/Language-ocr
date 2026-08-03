import time
from collections import defaultdict
from starlette.types import ASGIApp, Scope, Receive, Send
from starlette.responses import JSONResponse
from config import settings

class RateLimitMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app
        self.requests = defaultdict(list)
        self.max_requests = settings.RATE_LIMIT_PER_MINUTE
        self.window_seconds = 60

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if path.startswith("/css") or path.startswith("/js") or path == "/" or path.startswith("/static"):
            await self.app(scope, receive, send)
            return

        client_ip = scope.get("client", ("127.0.0.1", 0))[0] if scope.get("client") else "127.0.0.1"
        now = time.time()
        
        # Clean timestamps older than window
        timestamps = [t for t in self.requests[client_ip] if now - t < self.window_seconds]
        
        if len(timestamps) >= self.max_requests:
            response = JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Please wait a minute before sending more requests."}
            )
            await response(scope, receive, send)
            return

        timestamps.append(now)
        self.requests[client_ip] = timestamps
        
        await self.app(scope, receive, send)

