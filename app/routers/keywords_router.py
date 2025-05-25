from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import List, Optional
from loguru import logger

from app.security import get_current_username
from app.external_services import get_top_keywords_from_manager
from app.models import KeywordManagerKeywordInfo
from app.cache_manager import async_cache_decorator

router = APIRouter(
    prefix="/keywords",
    tags=["Keyword Insights"],
    dependencies=[Depends(get_current_username)]
)

@router.get("/top_managed", response_model=Optional[List[KeywordManagerKeywordInfo]])
@async_cache_decorator(ttl_seconds=1800)
async def get_top_managed_keywords(
    lang: str = Query("en", pattern="^(en|fr|ar)$"),
    limit: int = Query(20, ge=1, le=100)
):
    logger.info(f"API Gateway: Fetching top {limit} managed keywords for language '{lang}' from Keyword Manager.")
    keywords_data = await get_top_keywords_from_manager(limit=limit, lang=lang)
    
    if keywords_data is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, 
            detail="Could not fetch data from Keyword Manager service."
        )
    
    return [KeywordManagerKeywordInfo(**kw) for kw in keywords_data]