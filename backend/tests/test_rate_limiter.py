import pytest
import asyncio
import time
from app.core.rate_limiter import TokenBucket

@pytest.mark.asyncio
async def test_token_bucket_limit():
    # 초당 2회 제한으로 설정
    limiter = TokenBucket(rate_per_sec=2.0, capacity=2)
    
    start_time = time.monotonic()
    
    # 처음 2개는 즉시 소모
    await limiter.consume()
    await limiter.consume()
    
    # 3번째는 토큰 보충을 위해 대기 필요 (약 0.5초)
    await limiter.consume()
    
    duration = time.monotonic() - start_time
    assert duration >= 0.4 # 약 0.5초 정도 걸려야 함

@pytest.mark.asyncio
async def test_staggered_execution():
    async def mock_task(x): return x * 2
    
    start_time = time.monotonic()
    items = [1, 2, 3]
    from app.core.rate_limiter import staggered_request
    
    results = await staggered_request(items, mock_task, interval=0.1)
    
    duration = time.monotonic() - start_time
    assert results == [2, 4, 6]
    assert duration >= 0.2 # 0.1s * 2 intervals
