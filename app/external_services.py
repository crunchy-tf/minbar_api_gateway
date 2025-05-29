# api_gateway_service/app/external_services.py
import httpx
from typing import List, Dict, Any, Optional
from loguru import logger
from app.config import settings
from app.cache_manager import async_cache_decorator # Keep if get_top_keywords_from_manager uses it

@async_cache_decorator(ttl_seconds=3600)
async def get_top_keywords_from_manager(limit: int = 20, lang: str = "en") -> Optional[List[Dict[str, Any]]]:
    url = f"{str(settings.KEYWORD_MANAGER_API_URL).rstrip('/')}/keywords"
    params = {"lang": lang, "limit": limit, "min_score": 0.5}

    logger.info(f"Calling Keyword Manager: {url} with params: {params}")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            logger.debug(f"Keyword Manager response: {data}")
            return data
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error fetching keywords from Keyword Manager: {e.response.status_code} - {e.response.text}")
    except httpx.RequestError as e:
        logger.error(f"Request error fetching keywords from Keyword Manager: {e}")
    except Exception as e:
        logger.error(f"Unexpected error calling Keyword Manager: {e}", exc_info=True)
    return None

async def check_keyword_manager_health() -> bool:
    """
    Checks the health of the Keyword Manager service by calling its root or health endpoint.
    Returns True if healthy, False otherwise.
    """
    # Assuming Keyword Manager has a root "/" or a "/health" endpoint
    # Adjust the endpoint_to_check if KM has a specific health endpoint
    health_url_root = str(settings.KEYWORD_MANAGER_API_URL).rstrip('/api/v1') # Get base URL
    endpoint_to_check = f"{health_url_root}/health" # Prefer a dedicated /health endpoint
    # Fallback to root if /health is not standard on KM:
    # endpoint_to_check = health_url_root + "/"


    logger.debug(f"Checking Keyword Manager health at: {endpoint_to_check}")
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(endpoint_to_check)
            # A successful health check could be 200 OK, or specific content.
            # For simplicity, we'll check for a 2xx status code.
            if 200 <= response.status_code < 300:
                logger.trace(f"Keyword Manager health check successful (Status: {response.status_code})")
                return True
            else:
                logger.warning(f"Keyword Manager health check failed. Status: {response.status_code}, Response: {response.text[:200]}")
                return False
    except httpx.RequestError as e:
        logger.warning(f"Keyword Manager health check failed (Request Error): {e}")
        return False
    except Exception as e:
        logger.warning(f"Keyword Manager health check failed (Unexpected Error): {e}", exc_info=True)
        return False