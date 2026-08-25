from fastapi import APIRouter, Depends
from fastapi_limiter.depends import RateLimiter

router = APIRouter(tags=["rate"])

@router.get("/rate-test", dependencies=[Depends(RateLimiter(times=5, seconds=60))])
async def rate_test():
    return {"ok": True}
