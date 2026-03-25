import time
import threading
from typing import Optional
from enum import Enum
from collections import deque
from .logger import logger

# ============================================================================
# CIRCUIT BREAKER PATTERN
# ============================================================================

class CircuitState(Enum):
    CLOSED = "closed"        # Normal - requests pass through
    OPEN = "open"            # Failing - requests blocked
    HALF_OPEN = "half_open"  # Testing - limited requests


class CircuitBreaker:
    """Circuit breaker para proteger contra modelos/servicios caídos"""

    def __init__(
        self,
        failure_threshold: int = 3,
        recovery_timeout: float = 60.0,
        half_open_max_calls: int = 1
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: Optional[float] = None
        self._half_open_calls = 0
        self._lock = threading.Lock()

    @property
    def state(self) -> CircuitState:
        with self._lock:
            if self._state == CircuitState.OPEN:
                # Check if recovery timeout has passed
                if (self._last_failure_time and
                    time.time() - self._last_failure_time >= self.recovery_timeout):
                    self._state = CircuitState.HALF_OPEN
                    self._half_open_calls = 0
            return self._state

    def can_execute(self) -> bool:
        state = self.state
        if state == CircuitState.CLOSED:
            return True
        if state == CircuitState.HALF_OPEN:
            with self._lock:
                if self._half_open_calls < self.half_open_max_calls:
                    self._half_open_calls += 1
                    return True
            return False
        return False  # OPEN

    def record_success(self):
        with self._lock:
            self._failure_count = 0
            self._state = CircuitState.CLOSED

    def record_failure(self):
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()
            if self._failure_count >= self.failure_threshold:
                self._state = CircuitState.OPEN
                logger.warning(
                    f"Circuit breaker OPENED after {self._failure_count} failures"
                )


# ============================================================================
# RATE LIMITER
# ============================================================================

class RateLimiter:
    """Rate limiter con ventana deslizante"""

    def __init__(self, max_calls: int = 60, window_seconds: float = 60.0):
        self.max_calls = max_calls
        self.window_seconds = window_seconds
        self._calls: deque = deque()
        self._lock = threading.Lock()

    def acquire(self, timeout: float = 30.0) -> bool:
        """Intenta adquirir permiso. Bloquea si es necesario."""
        deadline = time.time() + timeout

        while time.time() < deadline:
            with self._lock:
                now = time.time()
                # Remove expired entries
                while self._calls and self._calls[0] <= now - self.window_seconds:
                    self._calls.popleft()

                if len(self._calls) < self.max_calls:
                    self._calls.append(now)
                    return True

            # Wait a bit before retrying
            time.sleep(0.1)

        return False

    @property
    def remaining(self) -> int:
        with self._lock:
            now = time.time()
            while self._calls and self._calls[0] <= now - self.window_seconds:
                self._calls.popleft()
            return max(0, self.max_calls - len(self._calls))
