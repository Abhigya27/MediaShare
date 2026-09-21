import asyncio
import time
import uuid
from collections import defaultdict

from fastapi import Depends, HTTPException, status

from backend.db import User
from backend.users import current_active_user

POST_RATE_LIMIT = 15
POST_RATE_PERIOD_SECONDS = 60

_post_timestamps: dict[uuid.UUID, list[float]] = defaultdict(list)
_lock = asyncio.Lock()


async def enforce_post_rate_limit(user: User = Depends(current_active_user)) -> User:

    now = time.monotonic()
    async with _lock:
        timestamps = _post_timestamps[user.id]

        cutoff = now - POST_RATE_PERIOD_SECONDS
        while timestamps and timestamps[0] <= cutoff:
            timestamps.pop(0)

        if len(timestamps) >= POST_RATE_LIMIT:
            retry_after = POST_RATE_PERIOD_SECONDS - (now - timestamps[0])
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    f"Rate limit exceeded: max {POST_RATE_LIMIT} posts per "
                    f"{POST_RATE_PERIOD_SECONDS}s. Try again in "
                    f"{int(retry_after) + 1}s."
                ),
            )

        timestamps.append(now)

    return user