import time
from starlette.requests import Request
from starlette.responses import Response

async def metrics_middleware(request: Request, call_next):
    start = time.perf_counter()
    response: Response = await call_next(request)
    duration = f"{(time.perf_counter() - start)*1000:.2f}ms"
    response.headers["X-Process-Time"] = duration
    return response
