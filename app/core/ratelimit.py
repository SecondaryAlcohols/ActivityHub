"""进程内滑动窗口限流。

单实例部署足够使用；多实例部署时应替换为 Redis 实现（保持同一接口即可）。
"""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque


class SlidingWindowLimiter:
    def __init__(self, limit: int, window_seconds: int) -> None:
        self.limit = limit
        self.window = window_seconds
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()
        self._last_cleanup = time.monotonic()

    async def hit(self, key: str) -> tuple[bool, int]:
        """记录一次请求，返回 (是否放行, 建议重试秒数)。"""
        now = time.monotonic()
        async with self._lock:
            bucket = self._events[key]
            cutoff = now - self.window
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()

            if len(bucket) >= self.limit:
                retry_after = max(1, int(self.window - (now - bucket[0])))
                return False, retry_after

            bucket.append(now)
            self._maybe_cleanup(now)
            return True, 0

    async def reset(self, key: str) -> None:
        async with self._lock:
            self._events.pop(key, None)

    def _maybe_cleanup(self, now: float) -> None:
        if now - self._last_cleanup < 300:
            return
        cutoff = now - self.window
        for key in [k for k, bucket in self._events.items() if not bucket or bucket[-1] <= cutoff]:
            self._events.pop(key, None)
        self._last_cleanup = now
