import httpx
import logging
import asyncio
import websockets
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List, Set
from app.core.config import settings
from app.services.streamer import multiplexer

logger = logging.getLogger(__name__)

class KiwoomClient:
    """SOR(_AL) 지원 및 실시간 WebSocket 시세 수신 클라이언트"""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(KiwoomClient, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized: return
        self.host = 'https://api.kiwoom.com'
        self.ws_url = settings.KIWOOM_WS_URL
        self.api_key = settings.KIWOOM_API_KEY
        self.secret_key = settings.KIWOOM_SECRET_KEY
        self.access_token = None
        self._token_lock = asyncio.Lock()
        self.ws_connection = None
        self._http_client = None
        self.subscribed_symbols: Set[str] = set()
        # [Decision] 실시간 등록 대기열: WS 연결 전 요청된 종목을 큐잉
        self._pending_symbols: Set[str] = set()
        self._ws_logged_in = False
        self._initialized = True

    async def get_http_client(self) -> httpx.AsyncClient:
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(timeout=15.0, verify=False)
        return self._http_client

    async def get_access_token(self) -> bool:
        if self.access_token: return True
        async with self._token_lock:
            if self.access_token: return True
            url = f"{self.host}/oauth2/token"
            payload = {'grant_type': 'client_credentials', 'appkey': self.api_key, 'secretkey': self.secret_key}
            client = await self.get_http_client()
            try:
                resp = await client.post(url, json=payload)
                if resp.status_code == 200:
                    self.access_token = resp.json().get("token")
                    logger.info(f"Access Token 발급 성공: {self.access_token[:20]}...")
                    return True
                logger.error(f"Access Token 발급 실패: {resp.status_code} {resp.text}")
                return False
            except Exception as e:
                logger.error(f"Access Token 요청 에러: {e}")
                return False

    def clean_val(self, val: Any) -> float:
        if not val: return 0.0
        cleaned = re.sub(r'[^\d.]', '', str(val))
        return float(cleaned) if cleaned else 0.0

    async def get_stock_chart(self, stock_code: str, timeframe: str = "D") -> Dict[str, Any]:
        """SOR 대응 및 거래량 포함 데이터 반환"""
        if not self.access_token: await self.get_access_token()
        url = f"{self.host}/api/dostk/chart"
        kst = timezone(timedelta(hours=9))
        base_dt = datetime.now(kst).strftime('%Y%m%d')
        
        payload = {'stk_cd': stock_code, 'upd_stkpc_tp': '1', 'base_dt': base_dt}
        if timeframe in ["1", "3", "5", "10", "15", "30", "45", "60"]:
            api_id = "ka10080"; payload['tic_scope'] = timeframe
        elif timeframe == "W": api_id = "ka10082"
        else: api_id = "ka10081"

        headers = {'Content-Type': 'application/json', 'authorization': f'Bearer {self.access_token}', 'api-id': api_id}
        client = await self.get_http_client()
        try:
            resp = await client.post(url, headers=headers, json=payload)
            data = resp.json()
            raw_list = data.get("stk_min_pole_chart_qry") or data.get("stk_dt_pole_chart_qry") or data.get("stk_stk_pole_chart_qry", [])
            
            return {"output": [{
                "dt": d.get("cntr_tm") or d.get("dt"),
                "open": self.clean_val(d.get("open_pric") or d.get("stck_oprc")),
                "high": self.clean_val(d.get("high_pric") or d.get("stck_hgpr")),
                "low": self.clean_val(d.get("low_pric") or d.get("stck_lwpr")),
                "close": self.clean_val(d.get("cur_prc") or d.get("stck_prpr") or d.get("stck_clpr")),
                "volume": self.clean_val(d.get("trde_qty") or d.get("acc_trde_qty"))
            } for d in raw_list]}
        except: return {"output": []}

    # ──────────────────────────────────────────────────────────
    # [Decision] 키움 WebSocket 실시간 시세: LOGIN → REG → 수신 루프
    # 사용자 제공 프로토콜: trnm=LOGIN/REG/PING, type='00'(주식체결)
    # ──────────────────────────────────────────────────────────

    async def connect_websocket(self):
        """키움 실시간 WebSocket 연결 및 시세 수신 루프"""
        while True:
            if not self.access_token:
                await self.get_access_token()
                await asyncio.sleep(1)
                continue
            try:
                logger.info(f"키움 WebSocket 연결 시도: {self.ws_url}")
                async with websockets.connect(self.ws_url, ping_interval=20, ping_timeout=30) as ws:
                    self.ws_connection = ws
                    self._ws_logged_in = False

                    # Step 1: LOGIN
                    login_msg = {
                        'trnm': 'LOGIN',
                        'token': self.access_token
                    }
                    await ws.send(json.dumps(login_msg))
                    logger.info("키움 WebSocket LOGIN 패킷 전송")

                    # 수신 루프
                    async for raw_msg in ws:
                        try:
                            msg = json.loads(raw_msg)
                        except json.JSONDecodeError:
                            logger.warning(f"JSON 파싱 실패: {raw_msg[:200]}")
                            continue

                        trnm = msg.get('trnm', '')

                        # LOGIN 응답 처리
                        if trnm == 'LOGIN':
                            if msg.get('return_code') == 0:
                                self._ws_logged_in = True
                                logger.info("키움 WebSocket LOGIN 성공")
                                # 대기 중인 종목 등록
                                await self._flush_pending_symbols()
                            else:
                                logger.error(f"키움 WebSocket LOGIN 실패: {msg.get('return_msg')}")
                                break

                        # PING 응답 (keep-alive)
                        elif trnm == 'PING':
                            await ws.send(raw_msg)

                        # REG 등록 응답
                        elif trnm == 'REG':
                            logger.info(f"실시간 등록 응답: return_code={msg.get('return_code')}, msg={msg.get('return_msg')}")

                        # 실시간 체결 데이터 수신
                        else:
                            await self._handle_realtime_data(msg)

            except websockets.ConnectionClosed as e:
                logger.warning(f"키움 WebSocket 연결 종료: {e}")
            except Exception as e:
                logger.error(f"키움 WebSocket 에러: {e}")
            finally:
                self.ws_connection = None
                self._ws_logged_in = False
                logger.info("키움 WebSocket 재연결 대기 (5초)...")
                await asyncio.sleep(5)

    async def _flush_pending_symbols(self):
        """LOGIN 성공 후 대기열의 종목을 일괄 등록"""
        # 기존 subscribed + pending 합산
        all_symbols = self.subscribed_symbols | self._pending_symbols
        self._pending_symbols.clear()

        if all_symbols:
            await self._register_symbols(all_symbols)

    async def _register_symbols(self, symbols: Set[str]):
        """종목 코드 집합을 REG 메시지로 등록"""
        if not self.ws_connection or not self._ws_logged_in:
            self._pending_symbols.update(symbols)
            return

        # [Decision] type='00' = 주식체결, item = 종목코드 리스트
        reg_msg = {
            'trnm': 'REG',
            'grp_no': '1',
            'refresh': '0',  # 기존 등록 유지
            'data': [{
                'item': list(symbols),
                'type': ['00']  # 주식체결
            }]
        }
        try:
            await self.ws_connection.send(json.dumps(reg_msg))
            logger.info(f"실시간 REG 등록 전송: {list(symbols)}")
        except Exception as e:
            logger.error(f"REG 등록 전송 실패: {e}")
            self._pending_symbols.update(symbols)

    async def subscribe_symbol(self, symbol: str):
        """개별 종목 실시간 구독 등록"""
        self.subscribed_symbols.add(symbol)
        if self._ws_logged_in and self.ws_connection:
            await self._register_symbols({symbol})
        else:
            self._pending_symbols.add(symbol)
            logger.info(f"종목 {symbol} 대기열에 추가 (WebSocket 미연결)")

    async def _handle_realtime_data(self, msg: dict):
        """
        실시간 체결 데이터를 파싱하여 multiplexer로 브로드캐스트.
        키움 REST WebSocket 응답 필드명 매핑:
        - stk_cd: 종목코드
        - cur_prc / stck_prpr: 현재가
        - open_pric / stck_oprc: 시가
        - high_pric / stck_hgpr: 고가
        - low_pric / stck_lwpr: 저가
        - trde_qty: 체결수량  /  acc_trde_qty: 누적거래량
        - cntr_tm: 체결시간
        - fluc_rt: 등락률
        """
        try:
            # 다양한 필드명에 대응
            symbol = msg.get('stk_cd') or msg.get('mksc_shrn_iscd') or msg.get('item', '')
            if not symbol:
                # data 배열 형태인 경우
                data_list = msg.get('data', [])
                if isinstance(data_list, list):
                    for item in data_list:
                        if isinstance(item, dict):
                            await self._parse_and_broadcast(item)
                return

            await self._parse_and_broadcast(msg)

        except Exception as e:
            logger.debug(f"실시간 데이터 처리 에러: {e} | msg={str(msg)[:300]}")

    async def _parse_and_broadcast(self, d: dict):
        """개별 체결 데이터를 파싱하고 브로드캐스트"""
        symbol = d.get('stk_cd') or d.get('mksc_shrn_iscd') or d.get('item', '')
        if not symbol:
            return

        price = self.clean_val(d.get('cur_prc') or d.get('stck_prpr') or d.get('price'))
        if price <= 0:
            return

        kst = timezone(timedelta(hours=9))
        now = datetime.now(kst)
        timestamp = d.get('cntr_tm') or d.get('stck_cntg_hour') or now.strftime('%H%M%S')

        tick_data = {
            'symbol': symbol,
            'price': int(price),
            'open': int(self.clean_val(d.get('open_pric') or d.get('stck_oprc') or d.get('open') or price)),
            'high': int(self.clean_val(d.get('high_pric') or d.get('stck_hgpr') or d.get('high') or price)),
            'low': int(self.clean_val(d.get('low_pric') or d.get('stck_lwpr') or d.get('low') or price)),
            'volume': int(self.clean_val(d.get('acc_trde_qty') or d.get('acml_vol') or d.get('volume') or 0)),
            'change_rate': float(d.get('fluc_rt') or d.get('prdy_ctrt') or 0),
            'timestamp': str(timestamp),
        }

        await multiplexer.handle_kiwoom_tick(tick_data)

kiwoom_client = KiwoomClient()
