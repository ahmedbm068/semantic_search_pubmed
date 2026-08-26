"""Rate limiting that degrades gracefully when Redis is absent.

`fastapi-limiter`'s RateLimiter raises if it is used before `FastAPILimiter.init`
succeeded, which turns "Redis is down" into a 500 on every protected endpoint.
Wrapping it means a missing Redis costs us rate limiting, not availability.
"""
import logging

from fastapi import Request, Response
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter

from src.app.core.config import settings

logger = logging.getLogger("app.ratelimit")


class OptionalRateLimiter:
    """A RateLimiter that no-ops until FastAPILimiter has been initialised."""

    def __init__(self, times: int | None = None, seconds: int | None = None) -> None:
        self._times = times if times is not None else settings.rate_limit_times
        self._seconds = seconds if seconds is not None else settings.rate_limit_seconds
        self._limiter = RateLimiter(times=self._times, seconds=self._seconds)
        self._warned = False

    async def __call__(self, request: Request, response: Response) -> None:
        if getattr(FastAPILimiter, "redis", None) is None:
            if not self._warned:
                logger.warning(
                    "Rate limiting disabled (Redis unavailable); %s is unprotected",
                    request.url.path,
                )
                self._warned = True
            return
        await self._limiter(request, response)
