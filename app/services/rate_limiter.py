"""Rate limiting with token bucket and sliding window algorithms.

Principle 8: Cooldown and Rate Limiting
Respect rate limits. Hammering APIs wastes resources and gets you blocked.

Two algorithms provided:
1. Sliding Window: Simple, counts requests in last N seconds
2. Token Bucket: Smooth, allows bursts while maintaining average rate

Usage:
    # Sliding window - simple and effective
    limiter = SlidingWindowRateLimiter(max_per_minute=60)
    await limiter.acquire()  # Blocks if at limit
    response = await api_call()

    # Token bucket - allows controlled bursts
    limiter = TokenBucketRateLimiter(
        rate=10,           # 10 tokens per second
        burst=20,          # Allow bursts up to 20
    )
    await limiter.acquire(tokens=1)

    # Decorator for automatic rate limiting
    @rate_limit(max_per_minute=30)
    async def make_api_call():
        return await client.get("/data")
"""

import asyncio
import time
import functools
from collections import deque
from dataclasses import dataclass
from typing import Deque, Optional, Dict, Callable, Awaitable, TypeVar
from threading import Lock
import structlog

logger = structlog.get_logger()

T = TypeVar("T")


@dataclass
class RateLimitStats:
    """Statistics for rate limiter."""

    current_usage: int
    max_allowed: int
    window_seconds: float
    time_until_available: float
    total_acquired: int
    total_waited: int


class SlidingWindowRateLimiter:
    """
    Sliding window rate limiter.

    Tracks request timestamps and allows only N requests per window.
    Simple and effective for most use cases.

    Attributes:
        max_requests: Maximum requests per window
        window_seconds: Size of sliding window in seconds
    """

    def __init__(
        self,
        max_per_minute: Optional[int] = None,
        max_per_second: Optional[int] = None,
        max_requests: Optional[int] = None,
        window_seconds: float = 60.0,
    ):
        """
        Initialize rate limiter.

        Specify rate as one of:
        - max_per_minute: Requests per minute
        - max_per_second: Requests per second
        - max_requests + window_seconds: Custom window

        Args:
            max_per_minute: Maximum requests per minute
            max_per_second: Maximum requests per second
            max_requests: Maximum requests per window
            window_seconds: Window size in seconds
        """
        if max_per_minute is not None:
            self.max_requests = max_per_minute
            self.window_seconds = 60.0
        elif max_per_second is not None:
            self.max_requests = max_per_second
            self.window_seconds = 1.0
        elif max_requests is not None:
            self.max_requests = max_requests
            self.window_seconds = window_seconds
        else:
            raise ValueError(
                "Must specify max_per_minute, max_per_second, or max_requests"
            )

        self._timestamps: Deque[float] = deque()
        self._lock = Lock()
        self._async_lock = asyncio.Lock()

        # Stats
        self._total_acquired = 0
        self._total_waited = 0

    def _cleanup_expired(self, now: float):
        """Remove timestamps outside the window."""
        cutoff = now - self.window_seconds
        while self._timestamps and self._timestamps[0] < cutoff:
            self._timestamps.popleft()

    def current_usage(self) -> int:
        """Get current number of requests in window."""
        with self._lock:
            self._cleanup_expired(time.time())
            return len(self._timestamps)

    def time_until_available(self) -> float:
        """Get seconds until a request slot is available."""
        with self._lock:
            now = time.time()
            self._cleanup_expired(now)

            if len(self._timestamps) < self.max_requests:
                return 0.0

            # Wait until oldest request expires
            oldest = self._timestamps[0]
            wait_time = (oldest + self.window_seconds) - now
            return max(0.0, wait_time)

    def try_acquire(self) -> bool:
        """
        Try to acquire a request slot without waiting.

        Returns:
            True if acquired, False if at limit
        """
        with self._lock:
            now = time.time()
            self._cleanup_expired(now)

            if len(self._timestamps) >= self.max_requests:
                return False

            self._timestamps.append(now)
            self._total_acquired += 1
            return True

    def acquire_sync(self, timeout: Optional[float] = None) -> bool:
        """
        Acquire a request slot, blocking if necessary.

        Args:
            timeout: Maximum seconds to wait (None = wait forever)

        Returns:
            True if acquired, False if timed out
        """
        start_time = time.time()

        while True:
            if self.try_acquire():
                return True

            wait_time = self.time_until_available()

            if timeout is not None:
                elapsed = time.time() - start_time
                if elapsed + wait_time > timeout:
                    return False
                wait_time = min(wait_time, timeout - elapsed)

            if wait_time > 0:
                self._total_waited += 1
                logger.debug(
                    "Rate limit reached, waiting",
                    wait_seconds=round(wait_time, 2),
                    current_usage=len(self._timestamps),
                    max_requests=self.max_requests,
                )
                time.sleep(wait_time + 0.01)  # Small buffer

    async def acquire(self, timeout: Optional[float] = None) -> bool:
        """
        Acquire a request slot asynchronously.

        Args:
            timeout: Maximum seconds to wait (None = wait forever)

        Returns:
            True if acquired, False if timed out
        """
        start_time = time.time()

        async with self._async_lock:
            while True:
                if self.try_acquire():
                    return True

                wait_time = self.time_until_available()

                if timeout is not None:
                    elapsed = time.time() - start_time
                    if elapsed + wait_time > timeout:
                        return False
                    wait_time = min(wait_time, timeout - elapsed)

                if wait_time > 0:
                    self._total_waited += 1
                    logger.debug(
                        "Rate limit reached, waiting",
                        wait_seconds=round(wait_time, 2),
                        current_usage=len(self._timestamps),
                        max_requests=self.max_requests,
                    )
                    await asyncio.sleep(wait_time + 0.01)

    def get_stats(self) -> RateLimitStats:
        """Get rate limiter statistics."""
        with self._lock:
            self._cleanup_expired(time.time())
            return RateLimitStats(
                current_usage=len(self._timestamps),
                max_allowed=self.max_requests,
                window_seconds=self.window_seconds,
                time_until_available=self.time_until_available(),
                total_acquired=self._total_acquired,
                total_waited=self._total_waited,
            )

    def reset(self):
        """Reset the rate limiter."""
        with self._lock:
            self._timestamps.clear()
            logger.debug("Rate limiter reset")


class TokenBucketRateLimiter:
    """
    Token bucket rate limiter.

    Allows bursts while maintaining average rate.
    Tokens are added at a constant rate up to a maximum (bucket size).
    Each request consumes tokens.

    Attributes:
        rate: Tokens added per second
        burst: Maximum tokens (bucket size)
    """

    def __init__(
        self,
        rate: float = 10.0,
        burst: int = 10,
    ):
        """
        Initialize token bucket.

        Args:
            rate: Tokens added per second
            burst: Maximum tokens (bucket capacity)
        """
        self.rate = rate
        self.burst = burst
        self._tokens = float(burst)
        self._last_update = time.time()
        self._lock = Lock()
        self._async_lock = asyncio.Lock()

        # Stats
        self._total_acquired = 0
        self._total_waited = 0

    def _add_tokens(self):
        """Add tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self._last_update
        self._tokens = min(self.burst, self._tokens + elapsed * self.rate)
        self._last_update = now

    def current_tokens(self) -> float:
        """Get current number of tokens."""
        with self._lock:
            self._add_tokens()
            return self._tokens

    def time_until_tokens(self, tokens: int = 1) -> float:
        """Get seconds until N tokens are available."""
        with self._lock:
            self._add_tokens()
            if self._tokens >= tokens:
                return 0.0
            needed = tokens - self._tokens
            return needed / self.rate

    def try_acquire(self, tokens: int = 1) -> bool:
        """
        Try to acquire tokens without waiting.

        Args:
            tokens: Number of tokens to acquire

        Returns:
            True if acquired, False if insufficient tokens
        """
        with self._lock:
            self._add_tokens()
            if self._tokens >= tokens:
                self._tokens -= tokens
                self._total_acquired += tokens
                return True
            return False

    def acquire_sync(
        self,
        tokens: int = 1,
        timeout: Optional[float] = None,
    ) -> bool:
        """
        Acquire tokens, blocking if necessary.

        Args:
            tokens: Number of tokens to acquire
            timeout: Maximum seconds to wait

        Returns:
            True if acquired, False if timed out
        """
        start_time = time.time()

        while True:
            if self.try_acquire(tokens):
                return True

            wait_time = self.time_until_tokens(tokens)

            if timeout is not None:
                elapsed = time.time() - start_time
                if elapsed + wait_time > timeout:
                    return False
                wait_time = min(wait_time, timeout - elapsed)

            if wait_time > 0:
                self._total_waited += 1
                logger.debug(
                    "Insufficient tokens, waiting",
                    wait_seconds=round(wait_time, 2),
                    current_tokens=round(self._tokens, 2),
                    needed=tokens,
                )
                time.sleep(wait_time + 0.001)

    async def acquire(
        self,
        tokens: int = 1,
        timeout: Optional[float] = None,
    ) -> bool:
        """
        Acquire tokens asynchronously.

        Args:
            tokens: Number of tokens to acquire
            timeout: Maximum seconds to wait

        Returns:
            True if acquired, False if timed out
        """
        start_time = time.time()

        async with self._async_lock:
            while True:
                if self.try_acquire(tokens):
                    return True

                wait_time = self.time_until_tokens(tokens)

                if timeout is not None:
                    elapsed = time.time() - start_time
                    if elapsed + wait_time > timeout:
                        return False
                    wait_time = min(wait_time, timeout - elapsed)

                if wait_time > 0:
                    self._total_waited += 1
                    logger.debug(
                        "Insufficient tokens, waiting",
                        wait_seconds=round(wait_time, 2),
                        current_tokens=round(self._tokens, 2),
                        needed=tokens,
                    )
                    await asyncio.sleep(wait_time + 0.001)

    def get_stats(self) -> dict:
        """Get rate limiter statistics."""
        with self._lock:
            self._add_tokens()
            return {
                "current_tokens": round(self._tokens, 2),
                "max_tokens": self.burst,
                "rate_per_second": self.rate,
                "total_acquired": self._total_acquired,
                "total_waited": self._total_waited,
            }


class MultiRateLimiter:
    """
    Composite rate limiter for multiple limits.

    Useful when you need to respect multiple rate limits simultaneously,
    e.g., 10 requests per second AND 100 requests per minute.

    Usage:
        limiter = MultiRateLimiter([
            SlidingWindowRateLimiter(max_per_second=10),
            SlidingWindowRateLimiter(max_per_minute=100),
        ])
        await limiter.acquire()
    """

    def __init__(self, limiters: list):
        """
        Initialize with multiple limiters.

        Args:
            limiters: List of rate limiters to check
        """
        self.limiters = limiters

    async def acquire(self, timeout: Optional[float] = None) -> bool:
        """
        Acquire from all limiters.

        Must pass all limiters to proceed.

        Args:
            timeout: Maximum total seconds to wait

        Returns:
            True if acquired from all, False if timed out
        """
        start_time = time.time()

        for limiter in self.limiters:
            remaining_timeout = None
            if timeout is not None:
                elapsed = time.time() - start_time
                remaining_timeout = max(0, timeout - elapsed)
                if remaining_timeout <= 0:
                    return False

            if not await limiter.acquire(timeout=remaining_timeout):
                return False

        return True

    def current_usage(self) -> Dict[int, int]:
        """Get usage from all limiters."""
        return {i: limiter.current_usage() for i, limiter in enumerate(self.limiters)}


class RateLimitExceeded(Exception):
    """Raised when rate limit is exceeded and timeout occurs."""

    def __init__(self, message: str, wait_time: float):
        super().__init__(message)
        self.wait_time = wait_time


def rate_limit(
    max_per_minute: Optional[int] = None,
    max_per_second: Optional[int] = None,
    timeout: float = 60.0,
):
    """
    Decorator to rate limit async functions.

    Usage:
        @rate_limit(max_per_minute=30)
        async def call_api():
            return await client.get("/data")

    Args:
        max_per_minute: Maximum calls per minute
        max_per_second: Maximum calls per second
        timeout: Maximum seconds to wait for rate limit

    Returns:
        Decorated function
    """
    limiter = SlidingWindowRateLimiter(
        max_per_minute=max_per_minute,
        max_per_second=max_per_second,
    )

    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            if not await limiter.acquire(timeout=timeout):
                raise RateLimitExceeded(
                    f"Rate limit exceeded for {func.__name__}",
                    wait_time=limiter.time_until_available(),
                )
            return await func(*args, **kwargs)

        # Attach limiter for inspection
        wrapper.rate_limiter = limiter
        return wrapper

    return decorator


def rate_limit_sync(
    max_per_minute: Optional[int] = None,
    max_per_second: Optional[int] = None,
    timeout: float = 60.0,
):
    """
    Decorator to rate limit sync functions.

    Usage:
        @rate_limit_sync(max_per_minute=30)
        def call_api():
            return requests.get("/data")
    """
    limiter = SlidingWindowRateLimiter(
        max_per_minute=max_per_minute,
        max_per_second=max_per_second,
    )

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            if not limiter.acquire_sync(timeout=timeout):
                raise RateLimitExceeded(
                    f"Rate limit exceeded for {func.__name__}",
                    wait_time=limiter.time_until_available(),
                )
            return func(*args, **kwargs)

        wrapper.rate_limiter = limiter
        return wrapper

    return decorator


# Pre-configured rate limiters for common APIs
# Fal.ai: 10 requests per second, 600 per minute
fal_rate_limiter = SlidingWindowRateLimiter(max_per_second=10)

# OpenAI: Depends on tier, conservative default
openai_rate_limiter = SlidingWindowRateLimiter(max_per_minute=60)

# General API rate limiter
api_rate_limiter = SlidingWindowRateLimiter(max_per_minute=120)
