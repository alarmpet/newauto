from fastapi import APIRouter, Query

from ..services.stock import search_stock_media
from ..types import StockSearchResponse

router = APIRouter(prefix="/api/stock", tags=["stock"])


@router.get("/search")
def stock_search(q: str = Query("")) -> StockSearchResponse:
    return search_stock_media(q)
