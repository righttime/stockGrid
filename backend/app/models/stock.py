from pydantic import BaseModel, Field
from typing import List, Optional, Any

class StockTick(BaseModel):
    """실시간 체결 데이터 모델"""
    symbol: str = Field(..., description="종목코드")
    price: int = Field(..., description="현재가")
    open: int = Field(..., description="시가")
    high: int = Field(..., description="고가")
    low: int = Field(..., description="저가")
    volume: int = Field(..., description="누적거래량")
    change_rate: float = Field(..., description="전일대비율")
    timestamp: str = Field(..., description="체결시간(HHMMSS)")

class CandleData(BaseModel):
    """차트용 캔들 데이터 모델"""
    time: str = Field(..., description="시간(YYYYMMDDHHMMSS)")
    open: int
    high: int
    low: int
    close: int
    volume: int

class APIResponse(BaseModel):
    """공통 API 응답 규격 (Architecture Principles 준수)"""
    success: bool
    data: Optional[Any] = None
    error: Optional[dict] = None # {"code": str, "message": str}

class StockInfo(BaseModel):
    """종목 기본 정보"""
    symbol: str
    name: str
    market: str # KOSPI, KOSDAQ 등
