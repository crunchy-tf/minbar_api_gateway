import httpx
from typing import List, Dict, Any, Optional
from loguru import logger
from app.config import settings
from app.cache_manager import async_cache_decorator

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