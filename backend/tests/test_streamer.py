import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from app.services.streamer import DataMultiplexer

@pytest.mark.asyncio
async def test_multiplexer_start_stop():
    with patch("app.api.websocket.ws_manager.broadcast", new_callable=AsyncMock) as mock_broadcast:
        m = DataMultiplexer()
        await m.start()
        assert m.is_running is True
        
        # 데이터가 최소 한 번은 브로드캐스트될 때까지 대기
        await asyncio.sleep(0.7)
        await m.stop()
        
        assert m.is_running is False
        assert mock_broadcast.called
