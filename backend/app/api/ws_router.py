from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.api.websocket import ws_manager
from app.services.kiwoom_client import kiwoom_client
import json
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.websocket("/ws/stocks")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                msg_type = msg.get("type", "")

                # [Decision] subscribe: ① 차트 스냅샷 전송 → ② 실시간 REG 등록
                if msg_type == "subscribe":
                    symbol = msg.get("symbol", "")
                    timeframe = msg.get("timeframe", "D")
                    if symbol:
                        # ① 차트 데이터를 해당 클라이언트에게 먼저 전송
                        chart_data = await kiwoom_client.get_stock_chart(symbol, timeframe)
                        await websocket.send_json({
                            "type": "chart",
                            "symbol": symbol,
                            "data": chart_data
                        })
                        logger.info(f"차트 스냅샷 전송 완료: {symbol} (tf={timeframe}, rows={len(chart_data.get('output', []))})")

                        # ② 실시간 구독 등록 (중복 방지)
                        if symbol not in kiwoom_client.subscribed_symbols:
                            kiwoom_client.subscribed_symbols.add(symbol)
                            await kiwoom_client.subscribe_symbol(symbol)
                            logger.info(f"실시간 구독 등록: {symbol}")

                # [Decision] requestChart: 타임프레임 변경 시 차트 데이터만 재전송 (실시간 재등록 불필요)
                elif msg_type == "requestChart":
                    symbol = msg.get("symbol", "")
                    timeframe = msg.get("timeframe", "D")
                    if symbol:
                        chart_data = await kiwoom_client.get_stock_chart(symbol, timeframe)
                        await websocket.send_json({
                            "type": "chart",
                            "symbol": symbol,
                            "data": chart_data
                        })
                        logger.info(f"차트 재전송: {symbol} (tf={timeframe})")

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
