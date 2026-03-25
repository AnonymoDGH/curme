import time
import threading
import json
from contextlib import contextmanager
from collections import defaultdict, deque
from typing import Dict, Any

class MetricsCollector:
    """Recolector de métricas del agente"""

    def __init__(self):
        self._lock = threading.Lock()
        self.counters: Dict[str, int] = defaultdict(int)
        self.gauges: Dict[str, float] = {}
        self.timings: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=100)
        )
        self.start_time = time.time()

    def increment(self, name: str, value: int = 1):
        with self._lock:
            self.counters[name] += value

    def set_gauge(self, name: str, value: float):
        with self._lock:
            self.gauges[name] = value

    def record_timing(self, name: str, duration: float):
        with self._lock:
            self.timings[name].append(duration)

    @contextmanager
    def timer(self, name: str):
        start = time.time()
        try:
            yield
        finally:
            self.record_timing(name, time.time() - start)

    def get_summary(self) -> Dict[str, Any]:
        with self._lock:
            timing_stats = {}
            for name, values in self.timings.items():
                if values:
                    vals = list(values)
                    timing_stats[name] = {
                        'count': len(vals),
                        'avg': sum(vals) / len(vals),
                        'min': min(vals),
                        'max': max(vals),
                        'p95': sorted(vals)[int(len(vals) * 0.95)] if len(vals) >= 20 else max(vals)
                    }

            return {
                'uptime_seconds': time.time() - self.start_time,
                'counters': dict(self.counters),
                'gauges': dict(self.gauges),
                'timings': timing_stats
            }
