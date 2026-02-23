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
        # [Decision] REG 배치 처리: 개별 subscribe 요청을 모아서 한 번에 전송 (105110 초과 방지)
        self._batch_pending: Set[str] = set()
        self._batch_task: Optional[asyncio.Task] = None
        self._ws_task: Optional[asyncio.Task] = None  # WS task 중복 방지
        self._initialized = True

    async def get_http_client(self) -> httpx.AsyncClient:
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(timeout=15.0, verify=False)
        return self._http_client

    async def get_access_token(self, force: bool = False) -> bool:
        """Access Token 발급. force=True 이면 기존 토큰을 무시하고 재발급."""
        if self.access_token and not force: return True
        async with self._token_lock:
            if self.access_token and not force: return True
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
        """SOR(_AL) 대응 및 거래량 포함 데이터 반환"""
        if not self.access_token: await self.get_access_token()
        url = f"{self.host}/api/dostk/chart"
        kst = timezone(timedelta(hours=9))
        base_dt = datetime.now(kst).strftime('%Y%m%d')

        # [Decision] SOR(NXT 포함) 데이터 수신을 위해 종목코드에 _AL 접미사 추가
        sor_code = stock_code if stock_code.endswith('_AL') else f"{stock_code}_AL"
        logger.info(f"차트 요청 종목코드 (SOR): {sor_code}")
        payload = {'stk_cd': sor_code, 'upd_stkpc_tp': '1', 'base_dt': base_dt}
        if timeframe in ["1", "3", "5", "10", "15", "30", "45", "60"]:
            api_id = "ka10080"; payload['tic_scope'] = timeframe
        elif timeframe == "W": api_id = "ka10082"
        else: api_id = "ka10081"

        headers = {'Content-Type': 'application/json', 'authorization': f'Bearer {self.access_token}', 'api-id': api_id}
        client = await self.get_http_client()

        # [Fix] 429 Rate Limit 재시도: 최대 3회, 지수 백오프 (1s→2s→4s)
        for attempt in range(3):
            try:
                resp = await client.post(url, headers=headers, json=payload)

                if resp.status_code == 429:
                    wait = 2 ** attempt  # 1, 2, 4초
                    logger.warning(f"차트 API Rate Limit (429): {sor_code}, {wait}초 후 재시도 (attempt {attempt+1}/3)")
                    await asyncio.sleep(wait)
                    continue

                data = resp.json()
                raw_list = data.get("stk_min_pole_chart_qry") or data.get("stk_dt_pole_chart_qry") or data.get("stk_stk_pole_chart_qry", [])

                is_minute = timeframe in ["1", "3", "5", "10", "15", "30", "45", "60"]
                result = []
                for d in raw_list:
                    raw_dt = d.get("cntr_tm") or d.get("dt") or ""
                    # [Fix] 분봉: cntr_tm = HHMMSS(6자리) → 날짜 없는 시간만 옴
                    # base_dt를 앞에 붙여 YYYYMMDDHHMMSS(14자리)로 통일해야 프론트에서 파싱 가능
                    if is_minute and raw_dt and len(raw_dt) == 6:
                        raw_dt = base_dt + raw_dt
                    result.append({
                        "dt": raw_dt,
                        "open": self.clean_val(d.get("open_pric") or d.get("stck_oprc")),
                        "high": self.clean_val(d.get("high_pric") or d.get("stck_hgpr")),
                        "low": self.clean_val(d.get("low_pric") or d.get("stck_lwpr")),
                        "close": self.clean_val(d.get("cur_prc") or d.get("stck_prpr") or d.get("stck_clpr")),
                        "volume": self.clean_val(d.get("trde_qty") or d.get("acc_trde_qty"))
                    })
                return {"output": result}

            except Exception as e:
                logger.error(f"차트 API 요청 에러 ({sor_code}, attempt {attempt+1}): {e}")
                if attempt < 2:
                    await asyncio.sleep(2 ** attempt)

        logger.error(f"차트 API 최대 재시도 초과: {sor_code}")
        return {"output": []}

    # ──────────────────────────────────────────────────────────
    # [Decision] 키움 WebSocket 실시간 시세: LOGIN → REG → 수신 루프
    # 사용자 제공 프로토콜: trnm=LOGIN/REG/PING, type='00'(주식체결)
    # ──────────────────────────────────────────────────────────

    async def connect_websocket(self):
        """키움 실시간 WebSocket 연결 및 시세 수신 루프"""
        _token_fail_count = 0  # 연속 토큰 인증 실패 횟수
        while True:
            # 토큰이 없으면 새로 발급
            if not self.access_token:
                ok = await self.get_access_token()
                if not ok:
                    logger.error("Access Token 발급 실패. 10초 후 재시도...")
                    await asyncio.sleep(10)
                    continue
                await asyncio.sleep(1)
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
                        # [Debug] 키움 WS 수신 RAW 전체 로깅 (포맷 파악용)
                        logger.info(f"[WS RAW] {str(raw_msg)[:400]}")
                        try:
                            msg = json.loads(raw_msg)
                        except json.JSONDecodeError:
                            logger.warning(f"JSON 파싱 실패: {raw_msg[:200]}")
                            continue

                        trnm = msg.get('trnm', '')

                        # LOGIN 응답 처리
                        if trnm == 'LOGIN':
                            return_code = msg.get('return_code')
                            if return_code == 0:
                                self._ws_logged_in = True
                                _token_fail_count = 0  # 성공 시 실패 카운터 초기화
                                logger.info("키움 WebSocket LOGIN 성공")
                                # 대기 중인 종목 등록
                                await self._flush_pending_symbols()
                            else:
                                # [Fix] 토큰 만료(8005) 등 인증 실패 → 토큰 초기화 후 재발급 유도
                                _token_fail_count += 1
                                logger.error(
                                    f"키움 WebSocket LOGIN 실패: {msg.get('return_msg')} "
                                    f"[CODE={return_code}] → 토큰 초기화 후 재로그인 시도 (#{_token_fail_count})"
                                )
                                self.access_token = None  # 만료 토큰 폐기
                                break  # WebSocket 연결 종료 후 재연결 루프에서 신규 토큰 발급

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
                # 연속 토큰 실패가 많으면 대기 시간을 늘려 API 부하 방지
                wait_sec = min(5 * (1 + _token_fail_count // 3), 60)
                logger.info(f"키움 WebSocket 재연결 대기 ({wait_sec}초)...")
                await asyncio.sleep(wait_sec)

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
        # refresh='1': 기존 등록 유지하고 추가 등록 (공식 샘플 기준)
        # [Test] type에 "0B"(NXT체결), "01"(호가) 추가 시도 → 어떤 타입으로 데이터가 오는지 확인
        reg_msg = {
            'trnm': 'REG',
            'grp_no': '1',
            'refresh': '1',
            'data': [{
                'item': list(symbols),
                'type': ['00', '0B']  # [Test] "00"=KRX체결, "0B"=NXT체결 추정
            }]
        }
        try:
            await self.ws_connection.send(json.dumps(reg_msg))
            logger.info(f"실시간 REG 등록 전송: {list(symbols)}")
        except Exception as e:
            logger.error(f"REG 등록 전송 실패: {e}")
            self._pending_symbols.update(symbols)

    async def subscribe_symbol(self, symbol: str):
        """개별 종목 실시간 구독 등록 (_AL SOR 접미사 자동 적용, 배치 debounce 전송)"""
        # [Decision] SOR(NXT 포함) 실시간 시세를 수신하기 위해 _AL 접미사로 등록
        sor_symbol = symbol if symbol.endswith('_AL') else f"{symbol}_AL"
        self.subscribed_symbols.add(sor_symbol)
        if self._ws_logged_in and self.ws_connection:
            # [Decision] 즉시 REG 전송 대신 batch 큐에 적재 후 0.5초 debounce로 일괄 전송
            # → 여러 종목을 연속 구독할 때 REG 건수 초과(105110) 방지
            self._batch_pending.add(sor_symbol)
            await self._schedule_batch_reg()
        else:
            self._pending_symbols.add(sor_symbol)
            logger.info(f"종목 {sor_symbol} 대기열에 추가 (WebSocket 미연결)")

    async def _schedule_batch_reg(self):
        """0.5초 debounce: 배치로 모인 종목을 한 번에 REG 전송"""
        if self._batch_task and not self._batch_task.done():
            self._batch_task.cancel()
        self._batch_task = asyncio.get_event_loop().create_task(self._flush_batch_reg())

    async def _flush_batch_reg(self):
        """0.5초 대기 후 batch_pending 종목을 한 번에 REG 등록"""
        await asyncio.sleep(0.5)
        if self._batch_pending:
            symbols_to_reg = set(self._batch_pending)
            self._batch_pending.clear()
            await self._register_symbols(symbols_to_reg)

    async def _handle_realtime_data(self, msg: dict):
        """
        실시간 체결 데이터 파싱 및 브로드캐스트.
        키움 REST WebSocket 실제 포맷:
          { "data": [{ "item": "005930_AL", "values": { "10": "-73400", "11": "-600", "12": "-0.81",
                        "20": "090000", "13": "1234567", "16": "-73000", "17": "+75000", "18": "-73000" }}]}
        숫자 필드 코드:
          10=현재가, 11=전일대비, 12=등락률, 13=누적거래량
          16=시가, 17=고가, 18=저가, 20=체결시간
        """
        try:
            # [실제 키움 REST WS 포맷] data 배열 처리
            data_list = msg.get('data', [])
            if isinstance(data_list, list) and data_list:
                for entry in data_list:
                    # entry: { "item": "005930_AL", "values": { "10": ... } }
                    item_code = entry.get('item', '')
                    values = entry.get('values', {})
                    if item_code and values:
                        await self._parse_and_broadcast_numeric(item_code, values)
                return

            # fallback: 기존 문자열 키 포맷
            symbol = msg.get('stk_cd') or msg.get('mksc_shrn_iscd') or msg.get('item', '')
            if symbol:
                await self._parse_and_broadcast(msg)

        except Exception as e:
            logger.debug(f"실시간 데이터 처리 에러: {e} | msg={str(msg)[:300]}")

    async def _parse_and_broadcast_numeric(self, item_code: str, values: dict):
        """숫자 키 포맷(키움 REST WS 실제 응답)으로 파싱하고 브로드캐스트"""
        # [Decision] _AL 접미사 제거 → 프론트 매칭
        symbol = item_code[:-3] if item_code.endswith('_AL') else item_code

        price = self.clean_val(values.get('10', '0'))   # 10 = 현재가
        if price <= 0:
            logger.debug(f"tick 가격 없음: {symbol}")
            return

        kst = timezone(timedelta(hours=9))
        timestamp = values.get('20', datetime.now(kst).strftime('%H%M%S'))  # 20 = 체결시간

        tick_data = {
            'symbol': symbol,
            'price': int(price),
            'open': int(self.clean_val(values.get('16', '0') or str(price))),   # 16=시가
            'high': int(self.clean_val(values.get('17', '0') or str(price))),   # 17=고가
            'low': int(self.clean_val(values.get('18', '0') or str(price))),    # 18=저가
            'volume': int(self.clean_val(values.get('13', '0'))),               # 13=누적거래량
            'change_rate': float(self.clean_val(values.get('12', '0'))),        # 12=등락률
            'timestamp': str(timestamp),
        }

        logger.info(f"틱 브로드캐스트: {symbol} @ {int(price)}원 (vol={tick_data['volume']})")
        await multiplexer.handle_kiwoom_tick(tick_data)

    async def _parse_and_broadcast(self, d: dict):
        """기존 문자열 키 포맷 체결 데이터 파싱 (fallback)"""
        symbol = d.get('stk_cd') or d.get('mksc_shrn_iscd') or d.get('item', '')
        if not symbol:
            return

        if symbol.endswith('_AL'):
            symbol = symbol[:-3]

        price = self.clean_val(d.get('cur_prc') or d.get('stck_prpr') or d.get('price'))
        if price <= 0:
            logger.debug(f"tick 가격 없음, skip: symbol={symbol}")
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

        logger.info(f"통 브로드캐스트: {symbol} @ {int(price)}원")
        await multiplexer.handle_kiwoom_tick(tick_data)

kiwoom_client = KiwoomClient()
