import time
from dataclasses import dataclass
from threading import Lock

# 进程内限流，适用于当前单 worker 部署；多 worker / 多实例时应替换为 Redis
_attempts: dict[str, "_Attempt"] = {}
_lock = Lock()


@dataclass
class _Attempt:
    failures: int = 0
    window_started_at: float = 0.0
    locked_until: float = 0.0


def _prune(now: float, window_seconds: int) -> None:
    expired = [
        key
        for key, state in _attempts.items()
        if (state.locked_until and state.locked_until <= now)
        or (not state.locked_until and now - state.window_started_at > window_seconds)
    ]
    for key in expired:
        _attempts.pop(key, None)


def seconds_until_allowed(key: str, window_seconds: int) -> int:
    now = time.monotonic()
    with _lock:
        state = _attempts.get(key)
        if state is None:
            return 0
        if state.locked_until:
            if state.locked_until > now:
                return int(state.locked_until - now) + 1
            _attempts.pop(key, None)
            return 0
        if now - state.window_started_at > window_seconds:
            _attempts.pop(key, None)
        return 0


def record_failure(
    key: str,
    max_attempts: int,
    window_seconds: int,
    lock_seconds: int,
) -> None:
    now = time.monotonic()
    with _lock:
        if len(_attempts) > 1000:
            _prune(now, window_seconds)
        state = _attempts.get(key)
        if state is None or now - state.window_started_at > window_seconds:
            state = _Attempt(window_started_at=now)
            _attempts[key] = state
        state.failures += 1
        if state.failures >= max_attempts:
            state.locked_until = now + lock_seconds


def reset_attempts(key: str) -> None:
    with _lock:
        _attempts.pop(key, None)


def reset_all_attempts() -> None:
    with _lock:
        _attempts.clear()
