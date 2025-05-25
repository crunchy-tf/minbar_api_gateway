from fastapi import Request, HTTPException, status
from collections import defaultdict
import time
from app.config import settings

request_counts = defaultdict(list)

async def rate_limit_dependency(request: Request):
    client_ip = request.client.host if request.client else "unknown_client"
    
    current_time = time.time()
    
    request_counts[client_ip] = [
        ts for ts in request_counts[client_ip] if ts > current_time - settings.RATE_LIMIT_WINDOW_SECONDS
    ]
    
    if len(request_counts[client_ip]) >= settings.RATE_LIMIT_REQUESTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many requests. Limit is {settings.RATE_LIMIT_REQUESTS} per {settings.RATE_LIMIT_WINDOW_SECONDS} seconds."
        )
    
    request_counts[client_ip].append(current_time)