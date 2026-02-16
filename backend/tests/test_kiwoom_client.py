import pytest
import respx
from httpx import Response
from app.services.kiwoom_client import KiwoomClient
from app.core.config import settings

@pytest.mark.asyncio
@respx.mock
async def test_get_access_token_success():
    client = KiwoomClient()
    # Mock OAuth2 Response
    respx.post(f"{settings.KIWOOM_API_URL}/oauth2/tokenP").mock(return_value=Response(200, json={"access_token": "mock_token_123"}))
    
    success = await client.get_access_token()
    assert success is True
    assert client.access_token == "mock_token_123"

@pytest.mark.asyncio
@respx.mock
async def test_get_current_price_logic():
    client = KiwoomClient()
    client.access_token = "valid_token"
    
    # Mock Price Response
    url = f"{settings.KIWOOM_API_URL}/uapi/domestic-stock/v1/quotations/inquire-price"
    respx.get(url).mock(return_value=Response(200, json={"output": {"stck_prpr": "50000"}}))
    
    result = await client.get_current_price("005930")
    assert result["output"]["stck_prpr"] == "50000"
