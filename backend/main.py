from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio

from app.api.ws_router import router as ws_router

from app.api.stocks import router as stock_router



from app.services.streamer import multiplexer
from app.services.kiwoom_client import kiwoom_client
from app.services.stock_master import load_all_stocks_from_api

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. 실시간 데이터 멀티플렉서 시작
    await multiplexer.start()
    
    # 2. [가장 중요] 접근 토큰 발급 (사용자의 fn_au10001 로직)
    logger.info("Step 1: Obtaining Access Token (fn_au10001)...")
    token_success = await kiwoom_client.get_access_token()
    
    if token_success:
        # [Decision] 앱 시작 시 ka10099로 전체 종목 마스터 로딩
        logger.info("Step 2: Loading all stock master via ka10099...")
        await load_all_stocks_from_api(kiwoom_client.access_token, kiwoom_client.host)
        
        logger.info("Step 3: Starting Real-time WebSocket Connection...")
        # [Fix] Reload 시 task 중복 생성 방지
        if kiwoom_client._ws_task is None or kiwoom_client._ws_task.done():
            kiwoom_client._ws_task = asyncio.create_task(kiwoom_client.connect_websocket())
        else:
            logger.info("WebSocket task already running, skip.")
    else:
        logger.error("CRITICAL: Failed to obtain Access Token. Real-time features will be disabled.")
    
    yield
    # 서비스 종료 시 정리
    await multiplexer.stop()

def create_app() -> FastAPI:
    app = FastAPI(
        title="Kiwoom Trading WebApp API",
        description="Backend API for real-time stock chart and trading",
        version="0.1.0",
        lifespan=lifespan
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(ws_router)
    app.include_router(stock_router)

    @app.get("/health")
    async def health_check():
        return {"status": "ok", "version": "0.1.0"}

    return app

app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
