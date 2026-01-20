"""
Rate Limiter for Claude API calls.
Implements token bucket algorithm with configurable limits.
"""
import time
import threading
from dataclasses import dataclass
from typing import Optional


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""
    requests_per_minute: int = 50
    requests_per_hour: int = 1000
    tokens_per_minute: int = 100000
    cooldown_seconds: float = 60.0


class RateLimiter:
    """
    Thread-safe rate limiter for API calls.

    Tracks requests per minute and per hour to stay within API limits.
    """

    def __init__(self, config: Optional[RateLimitConfig] = None):
        """
        Initialize rate limiter.

        Args:
            config: Rate limit configuration. Uses defaults if not provided.
        """
        self.config = config or RateLimitConfig()
        self._minute_calls: list = []
        self._hour_calls: list = []
        self._lock = threading.Lock()

    def can_call(self) -> bool:
        """
        Check if we can make a call without blocking.

        Returns:
            True if a call can be made immediately, False otherwise.
        """
        self._cleanup_old_calls()
        with self._lock:
            return (
                len(self._minute_calls) < self.config.requests_per_minute and
                len(self._hour_calls) < self.config.requests_per_hour
            )

    def wait_if_needed(self) -> float:
        """
        Block until a call can be made.

        Returns:
            The number of seconds waited (0 if no wait was needed).
        """
        self._cleanup_old_calls()
        wait_time = 0.0

        with self._lock:
            # Check minute limit
            if len(self._minute_calls) >= self.config.requests_per_minute:
                oldest = self._minute_calls[0]
                wait_time = max(0, 60 - (time.time() - oldest))

            # Check hour limit
            if len(self._hour_calls) >= self.config.requests_per_hour:
                oldest = self._hour_calls[0]
                hour_wait = max(0, 3600 - (time.time() - oldest))
                wait_time = max(wait_time, hour_wait)

        if wait_time > 0:
            time.sleep(wait_time)

        return wait_time

    def record_call(self):
        """Record a successful API call."""
        now = time.time()
        with self._lock:
            self._minute_calls.append(now)
            self._hour_calls.append(now)

    def _cleanup_old_calls(self):
        """Remove calls older than their respective windows."""
        now = time.time()
        with self._lock:
            self._minute_calls = [t for t in self._minute_calls if now - t < 60]
            self._hour_calls = [t for t in self._hour_calls if now - t < 3600]

    def get_status(self) -> dict:
        """
        Get current rate limit status.

        Returns:
            Dictionary with current call counts and limits.
        """
        self._cleanup_old_calls()
        with self._lock:
            return {
                'minute_calls': len(self._minute_calls),
                'minute_limit': self.config.requests_per_minute,
                'minute_remaining': self.config.requests_per_minute - len(self._minute_calls),
                'hour_calls': len(self._hour_calls),
                'hour_limit': self.config.requests_per_hour,
                'hour_remaining': self.config.requests_per_hour - len(self._hour_calls),
                'can_call': self.can_call()
            }

    def reset(self):
        """Reset all rate limit counters."""
        with self._lock:
            self._minute_calls = []
            self._hour_calls = []
