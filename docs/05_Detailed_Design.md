# 05_Detailed_Design: Trading WebApp Implementation Spec

## 1. 시스템 개요
- **목표**: 키움 REST API의 초당 제한을 우회하며 16개 차트에 실시간 시세를 공급하는 고성능 백엔드 및 Vue.js 프론트엔드 구현.
- **핵심 전략**: Python `asyncio` 기반의 토큰 버킷 제한기 및 Vue 3 `shallowRef`를 활용한 메모리 최적화 차트 렌더링.

---

## 2. 모듈 상세 설계

### 2.1 Backend: Kiwoom Manager (Python)
```python
class KiwoomAPIManager:
    """키움 API 요청 및 제한 관리 모듈"""
    def __init__(self, api_key: str, secret: str):
        self.rate_limiter = TokenBucket(rate=5, capacity=5)
        
    async def get_market_data(self, stock_code: str) -> dict:
        async with self.rate_limiter:
            # API 요청 로직
            pass

class StockBroadcaster:
    """WebSocket 클라이언트에게 실시간 데이터를 브로드캐스트"""
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def broadcast(self, data: StockTickModel):
        for connection in self.active_connections:
            await connection.send_json(data.dict())
```

### 2.2 Frontend: Chart Grid System (Vue.js)
```javascript
/** @type {import('vue').Component} */
const ChartCell = {
  props: {
    symbol: String,
    interval: String
  },
  setup(props) {
    const chartContainer = ref(null);
    /** @type {import('lightweight-charts').IChartApi} */
    let chart = null;

    onMounted(() => {
      chart = createChart(chartContainer.value, chartOptions);
      // vtk.js 메모리 관리 원칙 계승: 언마운트 시 명시적 제거
    });

    onUnmounted(() => {
      if (chart) {
        chart.remove(); // 메모리 해제
        chart = null;
      }
    });
  }
};
```

---

## 3. 데이터 설계

### 3.1 Pydantic Models (Backend)
```python
from pydantic import BaseModel

class StockTickModel(BaseModel):
    symbol: str
    price: float
    change_rate: float
    volume: int
    timestamp: str

class APIResponse(BaseModel):
    success: bool
    data: Optional[Any]
    error: Optional[dict] = None # {code: int, message: str}
```

### 3.2 Secure Storage (Local SQLite)
- **Table**: `user_config`
  - `key_name`: TEXT (Primary Key)
  - `encrypted_value`: BLOB (AES-256 encrypted AppKey, Secret)
  - `updated_at`: DATETIME

---

## 4. API 명세 (Normalized API)

### GET /api/v1/stocks/{code}/candles
- **Request**: `interval=1m&count=100`
- **Response (Success)**:
```json
{
  "success": true,
  "data": [
    {"time": "2026-02-16 10:00", "open": 50000, "high": 50500, "low": 49900, "close": 50200},
    ...
  ],
  "error": null
}
```

---

## 5. 핵심 알고리즘: Rate Limiting (Token Bucket)
```python
import asyncio
import time

class TokenBucket:
    def __init__(self, rate, capacity):
        self._rate = rate
        self._capacity = capacity
        self._tokens = capacity
        self._last_update = time.monotonic()
        self._lock = asyncio.Lock()

    async def __aenter__(self):
        while True:
            async with self._lock:
                now = time.monotonic()
                self._tokens = min(self._capacity, self._tokens + (now - self._last_update) * self._rate)
                self._last_update = now
                if self._tokens >= 1:
                    self._tokens -= 1
                    return self
            await asyncio.sleep(0.1)

    async def __aexit__(self, exc_type, exc, tb):
        pass
```

---

## 6. 보안 및 성능 전략
- **Input Sanitization**: Pydantic을 활용하여 모든 API 입력(종목 코드 등)의 형식 검증.
- **Memory Management**: Vue 차트 컴포넌트 파괴 시 반드시 `chart.remove()`를 호출하여 브라우저 메모리 누수 방지.
- **Binary Transport**: (향후 확장 시) 대용량 호가 잔량 데이터 전송 시 JSON 대신 MessagePack 또는 Protobuf 도입 검토.

---

## 7. Verification
- **아키텍처 원칙 준수**: `Normalized API`, `Explicit Typing`, `Memory Management` 조항이 모두 코드 수준 설계에 반영됨.
- **생성 확인**: `ls -l docs/05_Detailed_Design.md` 실행 대기 중.
