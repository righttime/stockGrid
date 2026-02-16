import httpx
import logging
import asyncio
from typing import List, Dict

logger = logging.getLogger(__name__)

# [Decision] ka10099 실패 시 사용할 fallback 종목 (주요 대형주)
STOCK_MASTER_FALLBACK = [
    {"code": "005930", "name": "삼성전자"},
    {"code": "000660", "name": "SK하이닉스"},
    {"code": "035420", "name": "NAVER"},
    {"code": "035720", "name": "카카오"},
    {"code": "005380", "name": "현대차"},
    {"code": "005490", "name": "POSCO홀딩스"},
    {"code": "051910", "name": "LG화학"},
    {"code": "000270", "name": "기아"},
    {"code": "006400", "name": "삼성SDI"},
    {"code": "068270", "name": "셀트리온"},
    {"code": "105560", "name": "KB금융"},
    {"code": "055550", "name": "신한지주"},
    {"code": "000810", "name": "삼성화재"},
    {"code": "034220", "name": "LG디스플레이"},
    {"code": "017670", "name": "SK텔레콤"},
    {"code": "018260", "name": "삼성에스디에스"},
    {"code": "032830", "name": "삼성생명"},
    {"code": "003550", "name": "LG"},
    {"code": "015760", "name": "한국전력"},
    {"code": "034730", "name": "SK"},
    {"code": "012330", "name": "현대모비스"},
    {"code": "066570", "name": "LG전자"},
]

# 전체 종목 캐시
_stock_cache: List[Dict[str, str]] = []
_cache_loaded = False


async def _fetch_market(client: httpx.AsyncClient, token: str, host: str, mrkt_tp: str) -> List[Dict[str, str]]:
    """특정 시장(mrkt_tp)의 전체 종목을 연속조회로 가져오기"""
    stocks = []
    cont_yn = "N"
    next_key = ""

    while True:
        headers = {
            "Content-Type": "application/json;charset=UTF-8",
            "authorization": f"Bearer {token}",
            "api-id": "ka10099",
            "cont-yn": cont_yn,
            "next-key": next_key,
        }
        body = {"mrkt_tp": mrkt_tp}

        try:
            resp = await client.post(f"{host}/api/dostk/stkinfo", headers=headers, json=body)
            if resp.status_code != 200:
                logger.warning(f"ka10099 mrkt_tp={mrkt_tp} 응답 오류: {resp.status_code}")
                break

            data = resp.json()

            # 응답 바디에서 리스트 데이터 추출 (키 이름 동적 탐색)
            stock_list = None
            for key in data:
                if isinstance(data[key], list) and len(data[key]) > 0:
                    stock_list = data[key]
                    logger.info(f"ka10099 mrkt_tp={mrkt_tp} 응답 키: '{key}', 건수: {len(data[key])}")
                    # 첫 항목 로깅 (필드명 확인용)
                    if stocks == []:
                        logger.info(f"ka10099 샘플 데이터: {data[key][0]}")
                    break

            if not stock_list:
                logger.warning(f"ka10099 mrkt_tp={mrkt_tp} 리스트 데이터 없음. keys={list(data.keys())}")
                break

            for item in stock_list:
                # 가능한 필드명 후보 탐색
                code = (item.get("code") or item.get("stk_cd") or
                        item.get("shrt_cd") or item.get("mksc_shrn_iscd") or "")
                name = (item.get("name") or item.get("stk_nm") or
                        item.get("hts_kor_isnm") or item.get("prdt_abrv_name") or "")
                if code and name:
                    stocks.append({"code": code.strip(), "name": name.strip()})

            # 연속조회 확인: 응답 헤더에서 cont-yn, next-key 확인
            resp_cont = resp.headers.get("cont-yn", "N")
            resp_next = resp.headers.get("next-key", "")
            if resp_cont == "Y" and resp_next:
                cont_yn = "Y"
                next_key = resp_next
                await asyncio.sleep(0.3)  # API rate limit 방지
            else:
                break

        except Exception as e:
            logger.error(f"ka10099 mrkt_tp={mrkt_tp} 오류: {e}")
            break

    return stocks


async def load_all_stocks_from_api(access_token: str, host: str = "https://api.kiwoom.com"):
    """
    [Decision] ka10099 API로 코스피(0) + 코스닥(10) 전체 종목 로딩
    앱 시작 시 1회 호출하여 캐시
    """
    global _stock_cache, _cache_loaded
    all_stocks = []

    async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
        # 코스피(0) + 코스닥(10) 순차 조회
        for mrkt_tp in ["0", "10"]:
            market_name = "코스피" if mrkt_tp == "0" else "코스닥"
            logger.info(f"📡 ka10099: {market_name} 종목 로딩 중...")
            stocks = await _fetch_market(client, access_token, host, mrkt_tp)
            logger.info(f"✅ {market_name}: {len(stocks)}개 종목 로딩")
            all_stocks.extend(stocks)
            await asyncio.sleep(0.5)  # 시장 간 간격

    if all_stocks:
        # 중복 제거 (코드 기준)
        seen = set()
        unique = []
        for s in all_stocks:
            if s["code"] not in seen:
                seen.add(s["code"])
                unique.append(s)
        _stock_cache = unique
        _cache_loaded = True
        logger.info(f"🎯 전체 종목 마스터 로딩 완료: {len(unique)}개")
    else:
        _stock_cache = STOCK_MASTER_FALLBACK
        _cache_loaded = True
        logger.warning(f"⚠️ ka10099 실패, fallback 종목 {len(STOCK_MASTER_FALLBACK)}개 사용")


def get_stock_master() -> List[Dict[str, str]]:
    """현재 캐시된 종목 마스터 반환"""
    return _stock_cache if _cache_loaded else STOCK_MASTER_FALLBACK


def get_all_stock_names() -> Dict[str, str]:
    """전체 종목 코드→이름 매핑 반환"""
    return {s["code"]: s["name"] for s in get_stock_master()}


def search_stocks(query: str) -> List[Dict[str, str]]:
    """코드 또는 이름으로 종목 검색 (최대 30개)"""
    q = query.lower()
    results = [s for s in get_stock_master() if q in s["code"] or q in s["name"].lower()]
    return results[:30]
