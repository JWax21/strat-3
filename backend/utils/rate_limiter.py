"""Rate limiting utilities for API calls."""
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Optional
from collections import deque
import logging

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Token bucket rate limiter for API requests.
    
    Implements a sliding window rate limiter that tracks request timestamps
    and ensures we don't exceed the configured rate limit.
    """
    
    def __init__(self, requests_per_minute: int, name: str = "default"):
        """
        Initialize the rate limiter.
        
        Args:
            requests_per_minute: Maximum number of requests allowed per minute
            name: Name identifier for logging purposes
        """
        self.requests_per_minute = requests_per_minute
        self.name = name
        self.request_timestamps: deque = deque()
        self._lock = asyncio.Lock()
        
    async def acquire(self) -> None:
        """
        Acquire permission to make a request.
        
        This method will block if the rate limit has been reached,
        waiting until a slot becomes available.
        """
        async with self._lock:
            now = datetime.now()
            window_start = now - timedelta(minutes=1)
            
            # Remove timestamps outside the sliding window
            while self.request_timestamps and self.request_timestamps[0] < window_start:
                self.request_timestamps.popleft()
            
            # If we're at the limit, wait for the oldest request to expire
            if len(self.request_timestamps) >= self.requests_per_minute:
                oldest = self.request_timestamps[0]
                wait_time = (oldest + timedelta(minutes=1) - now).total_seconds()
                
                if wait_time > 0:
                    logger.info(
                        f"[{self.name}] Rate limit reached. "
                        f"Waiting {wait_time:.2f}s before next request."
                    )
                    await asyncio.sleep(wait_time)
                    
                    # Re-clean the window after sleeping
                    now = datetime.now()
                    window_start = now - timedelta(minutes=1)
                    while self.request_timestamps and self.request_timestamps[0] < window_start:
                        self.request_timestamps.popleft()
            
            # Record this request
            self.request_timestamps.append(datetime.now())
    
    @property
    def available_requests(self) -> int:
        """Get the number of requests available in the current window."""
        now = datetime.now()
        window_start = now - timedelta(minutes=1)
        
        # Count requests in current window
        current_count = sum(
            1 for ts in self.request_timestamps if ts >= window_start
        )
        
        return max(0, self.requests_per_minute - current_count)
    
    def __repr__(self) -> str:
        return f"RateLimiter(name={self.name}, rpm={self.requests_per_minute})"


class RateLimiterManager:
    """Manages multiple rate limiters for different API endpoints."""
    
    _limiters: Dict[str, RateLimiter] = {}
    
    @classmethod
    def get_limiter(cls, name: str, requests_per_minute: int) -> RateLimiter:
        """
        Get or create a rate limiter with the given name.
        
        Args:
            name: Unique identifier for the rate limiter
            requests_per_minute: Rate limit configuration
            
        Returns:
            RateLimiter instance
        """
        if name not in cls._limiters:
            cls._limiters[name] = RateLimiter(requests_per_minute, name)
        return cls._limiters[name]
    
    @classmethod
    def get_status(cls) -> Dict[str, int]:
        """Get the status of all rate limiters."""
        return {
            name: limiter.available_requests 
            for name, limiter in cls._limiters.items()
        }

