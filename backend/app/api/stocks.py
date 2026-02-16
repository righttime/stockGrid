from fastapi import APIRouter, HTTPException, Query
from app.services.kiwoom_client import kiwoom_client
from app.services.stock_master import search_stocks, get_all_stock_names
from typing import Any, Dict, List

router = APIRouter(prefix="/stocks", tags=["stocks"])

@router.get("/names")
async def get_stock_names():
    """전체 종목 코드→이름 매핑 반환"""
    return get_all_stock_names()

@router.get("/search")
async def search_stock_list(q: str = Query(..., min_length=1)):
    """종목 코드 또는 이름으로 검색"""
    return search_stocks(q)

@router.get("/{symbol}/chart")
async def get_chart_data(symbol: str, timeframe: str = "D"):
    """특정 종목의 차트 데이터를 조회합니다. (실시간 구독은 WS에서 처리)"""
    data = await kiwoom_client.get_stock_chart(symbol, timeframe)
        
    if "error" in data:
        raise HTTPException(status_code=500, detail=data["error"])
    return data
