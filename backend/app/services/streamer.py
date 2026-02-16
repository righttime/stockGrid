import asyncio
import json
import logging
from app.api.websocket import ws_manager
from app.models.stock import StockTick

logger = logging.getLogger(__name__)

class DataMultiplexer:
    """실시간 데이터를 수집하여 멀티플렉싱하고 브로드캐스트하는 클래스"""
    def __init__(self):
        self.is_running = False
        self._task = None

    async def start(self):
        if self.is_running:
            return
        self.is_running = True
        self._task = asyncio.create_task(self._run())
        logger.info("Real-time Data Multiplexer started")

    async def stop(self):
        self.is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Real-time Data Multiplexer stopped")

    async def _run(self):
        """실제 데이터 수신 루프 (API 연결 시 활성화)"""
        logger.info("Real-time Data Multiplexer standby for Kiwoom API...")
        while self.is_running:
            await asyncio.sleep(1)

    async def handle_kiwoom_tick(self, tick_data: dict):
        """키움 API로부터 수신된 실제 데이터를 모든 웹소켓 클라이언트에 전송"""
        try:
            tick = StockTick(
                symbol=tick_data.get("symbol"),
                price=tick_data.get("price"),
                open=tick_data.get("open"),
                high=tick_data.get("high"),
                low=tick_data.get("low"),
                volume=tick_data.get("volume"),
                change_rate=tick_data.get("change_rate", 0.0),
                timestamp=tick_data.get("timestamp")
            )

            await ws_manager.broadcast({
                "type": "tick",
                "data": tick.model_dump()
            })
        except Exception as e:
            logger.error(f"Error broadcasting real-time tick: {str(e)}")

multiplexer = DataMultiplexer()
