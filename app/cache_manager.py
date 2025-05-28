# api_gateway_service/app/cache_manager.py
from cachetools import TTLCache
from functools import wraps
import asyncio
import inspect
from typing import Optional, List, Dict, Any, Set, Tuple # Added Optional and other common types for key generation
from app.config import settings
from loguru import logger # Added logger for debugging cache keys if needed

# This global api_cache is not used by the decorator as written,
# as each decorated function gets its own TTLCache instance.
# You can keep it if you have other uses for a shared cache, or remove it if unused.
api_cache = TTLCache(maxsize=100, ttl=settings.DEFAULT_CACHE_TTL_SECONDS)

def async_cache_decorator(ttl_seconds: Optional[int] = None):
    actual_ttl = ttl_seconds if ttl_seconds is not None else settings.DEFAULT_CACHE_TTL_SECONDS
    
    def decorator(func):
        # Create a new cache instance for each decorated function
        func_cache = TTLCache(maxsize=50, ttl=actual_ttl) 

        @wraps(func)
        async def wrapper(*args, **kwargs):
            key_parts = [func.__name__]
            
            sig = inspect.signature(func)
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()

            # Sort kwargs to ensure consistent key order for kwargs
            # and then combine with args for consistent overall order
            sorted_kwarg_items = sorted(kwargs.items())
            
            # Process positional arguments first
            for i, value in enumerate(args):
                param_name = list(sig.parameters.keys())[i]
                if param_name == 'request' and hasattr(value, 'url'): 
                    continue
                
                if isinstance(value, dict):
                    key_parts.append(f"{param_name}={tuple(sorted((str(k), str(v)) for k, v in value.items()))}")
                elif isinstance(value, (list, set)):
                    try:
                        key_parts.append(f"{param_name}={tuple(sorted(str(item) for item in value))}")
                    except TypeError: 
                        key_parts.append(f"{param_name}={tuple(str(item) for item in value)}")
                elif hasattr(value, 'model_dump_json') and callable(value.model_dump_json): # Check for Pydantic models
                    key_parts.append(f"{param_name}={value.model_dump_json()}")
                else:
                    key_parts.append(f"{param_name}={str(value)}")

            # Process keyword arguments (already sorted)
            for name, value in sorted_kwarg_items:
                # Avoid reprocessing if it was also a positional arg that got bound (though bind should handle this)
                # This loop is more about ensuring all explicitly passed kwargs are in the key
                if name == 'request' and hasattr(value, 'url'): 
                    continue # Already handled or should be skipped

                # Check if this kwarg was already processed as a positional argument
                # This is a bit defensive, inspect.Signature.bind should map them correctly.
                # However, if a default value for a positional arg is overridden by a kwarg,
                # we want the kwarg's value. `bound_args.arguments` (used below) is better.
                # For simplicity, let's rely on bound_args for the final key components if not already added.

            # A more robust way using bound_args which includes defaults and correctly mapped args/kwargs:
            key_parts_from_bound = [func.__name__] # Start fresh for this method
            for name, value in bound_args.arguments.items():
                if name == 'request' and hasattr(value, 'url'):
                    continue
                
                current_part = ""
                if isinstance(value, dict):
                    current_part = f"{name}={tuple(sorted((str(k), str(v)) for k, v in value.items()))}"
                elif isinstance(value, (list, set)):
                    try:
                        current_part = f"{name}={tuple(sorted(str(item) for item in value))}"
                    except TypeError:
                        current_part = f"{name}={tuple(str(item) for item in value)}"
                elif hasattr(value, 'model_dump_json') and callable(value.model_dump_json):
                    current_part = f"{name}={value.model_dump_json()}"
                else:
                    current_part = f"{name}={str(value)}"
                key_parts_from_bound.append(current_part)
            
            # Use the key generated from bound_args
            cache_key = ":".join(key_parts_from_bound)
            # logger.debug(f"Cache key for {func.__name__}: {cache_key}") # Uncomment for debugging

            if cache_key in func_cache:
                logger.trace(f"Cache HIT for {func.__name__} with key: {cache_key[:100]}...")
                return func_cache[cache_key]
            
            logger.trace(f"Cache MISS for {func.__name__} with key: {cache_key[:100]}...")
            result = await func(*args, **kwargs)
            func_cache[cache_key] = result
            return result
        return wrapper
    return decorator