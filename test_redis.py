import asyncio
import redis.asyncio as redis

async def ping():
    r = redis.from_url("redis://localhost:6379/0")
    ok = await r.ping()
    print("Ping Redis:", ok)

if __name__ == "__main__":
    asyncio.run(ping())
