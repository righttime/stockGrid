import asyncio
import time
from typing import Optional

class TokenBucket:
    """비동기 토큰 버킷 기반 Rate Limiter (초당 N회 제한)"""
    def __init__(self, rate_per_sec: float, capacity: int):
        self.rate = rate_per_sec
        self.capacity = capacity
        self.tokens = float(capacity)
        self.last_update = time.monotonic()
        self.lock = asyncio.Lock()

    async def consume(self, tokens: int = 1):
        """토큰을 소비할 때까지 대기합니다."""
        while True:
            async with self.lock:
                now = time.monotonic()
                # 경과 시간만큼 토큰 보충
                elapsed = now - self.last_update
                self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
                self.last_update = now

                if self.tokens >= tokens:
                    self.tokens -= tokens
                    return True
            
            # 토큰이 부족하면 짧게 대기 후 재시도
            await asyncio.sleep(0.1)

async def staggered_request(items, func, interval=0.2):
    """항목들을 순차적으로 처리하며 간격을 둠 (Staggering)"""
    results = []
    for item in items:
        res = await func(item)
        results.append(res)
        await asyncio.sleep(interval)
    return results

# 전역 API 제한기 (초당 5회 제한)
kiwoom_rate_limiter = TokenBucket(rate_per_sec=5.0, capacity=5)
