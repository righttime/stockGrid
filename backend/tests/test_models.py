import pytest
from app.models.stock import StockTick, APIResponse

def test_stock_tick_validation():
    # 정상 데이터
    valid_data = {
        "symbol": "005930",
        "price": 72000,
        "open": 71000,
        "high": 73000,
        "low": 70500,
        "volume": 1500000,
        "change_rate": 1.41,
        "timestamp": "123000"
    }
    tick = StockTick(**valid_data)
    assert tick.symbol == "005930"
    assert tick.price == 72000

def test_api_response_structure():
    response = APIResponse(success=True, data={"result": "ok"})
    assert response.success is True
    assert response.data["result"] == "ok"
    
    error_response = APIResponse(success=False, error={"code": "429", "message": "Rate limit exceeded"})
    assert error_response.success is False
    assert error_response.error["code"] == "429"
