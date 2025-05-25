from cachetools import TTLCache
from functools import wraps
import asyncio
import inspect
from app.config import settings

api_cache = TTLCache(maxsize=100, ttl=settings.DEFAULT_CACHE_TTL_SECONDS)

def async_cache_decorator(ttl_seconds: Optional[int] = None):
    actual_ttl = ttl_seconds if ttl_seconds is not None else settings.DEFAULT_CACHE_TTL_SECONDS
    
    def decorator(func):
        # Create a new cache instance for each decorated function to avoid key collisions if args are same
        # Or manage keys more carefully if using a single global api_cache
        func_cache = TTLCache(maxsize=50, ttl=actual_ttl) 

        @wraps(func)
        async def wrapper(*args, **kwargs):
            key_parts = [func.__name__]
            
            sig = inspect.signature(func)
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()

            for name, value in bound_args.arguments.items():
                if name == 'request' and hasattr(value, 'url'): # Skip FastAPI Request object
                    continue
                if isinstance(value, (list, dict, set)): # Convert mutable to immutable for key
                    key_parts.append(f"{name}={tuple(sorted(value.items())) if isinstance(value, dict) else tuple(value)}")
                else:
                    key_parts.append(f"{name}={value}")

            cache_key = ":".join(key_parts)

            if cache_key in func_cache:
                return func_cache[cache_key]
            
            result = await func(*args, **kwargs)
            func_cache[cache_key] = result
            return result
        return wrapper
    return decorator