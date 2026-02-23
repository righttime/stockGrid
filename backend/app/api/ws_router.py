from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.api.websocket import ws_manager
from app.services.kiwoom_client import kiwoom_client
import json
import logging
import asyncio

router = APIRouter()
logger = logging.getLogger(__name__)

# [Fix] 동시 차트 API 요청을 최대 3개로 제한 → 429 Rate Limit 방지
_chart_semaphore = asyncio.Semaphore(3)


async def _send_chart(websocket: WebSocket, symbol: str, timeframe: str):
    """차트 데이터를 Semaphore로 제한하며 백그라운드에서 조회 후 전송.
    WS 수신 루프를 블록하지 않아 16개 subscribe를 즉시 받을 수 있음."""
    async with _chart_semaphore:
        chart_data = await kiwoom_client.get_stock_chart(symbol, timeframe)
    try:
        await websocket.send_json({
            "type": "chart",
            "symbol": symbol,
            "data": chart_data
        })
        rows = len(chart_data.get('output', []))
        logger.info(f"차트 전송 완료: {symbol} (tf={timeframe}, rows={rows})")
    except Exception as e:
        logger.error(f"차트 전송 실패: {symbol} - {e}")


@router.websocket("/ws/stocks")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                msg_type = msg.get("type", "")

                # [Decision] subscribe: ① 차트 스냅샷 전송(background) → ② 실시간 REG 등록
                if msg_type == "subscribe":
                    symbol = msg.get("symbol", "")
                    timeframe = msg.get("timeframe", "D")
                    if symbol:
                        # ① 차트 요청을 background task로 → WS 루프 블록 없이 즉시 다음 메시지 처리
                        asyncio.create_task(_send_chart(websocket, symbol, timeframe))

                        # ② 실시간 구독 등록 (중복 방지) — subscribed_symbols는 _AL 코드로 관리됨
                        sor_symbol = symbol if symbol.endswith('_AL') else f"{symbol}_AL"
                        if sor_symbol not in kiwoom_client.subscribed_symbols:
                            await kiwoom_client.subscribe_symbol(symbol)
                            logger.info(f"실시간 구독 등록 (SOR): {sor_symbol}")

                # [Decision] requestChart: 타임프레임 변경 시 차트 데이터만 재전송
                elif msg_type == "requestChart":
                    symbol = msg.get("symbol", "")
                    timeframe = msg.get("timeframe", "D")
                    if symbol:
                        asyncio.create_task(_send_chart(websocket, symbol, timeframe))

                elif msg_type == "unsubscribe":
                    symbol = msg.get("symbol", "")
                    logger.info(f"클라이언트 구독 해제 요청: {symbol}")

                else:
                    logger.debug(f"미분류 클라이언트 메시지: {data[:200]}")

            except json.JSONDecodeError:
                logger.warning(f"JSON 파싱 실패 (클라이언트): {data[:200]}")

    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
        ws_manager.disconnect(websocket)
