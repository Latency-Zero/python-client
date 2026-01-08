"""
Resource monitoring for CPU and RAM usage during benchmarks.
"""

import time
import threading
from typing import List, Dict, Optional
from dataclasses import dataclass, field

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


@dataclass
class ResourceSample:
    """A single resource usage sample."""
    timestamp: float
    cpu_percent: float
    memory_mb: float
    memory_percent: float


@dataclass
class ResourceStats:
    """Aggregated resource statistics."""
    samples: List[ResourceSample] = field(default_factory=list)
    
    @property
    def cpu_avg(self) -> float:
        if not self.samples:
            return 0
        return sum(s.cpu_percent for s in self.samples) / len(self.samples)
    
    @property
    def cpu_max(self) -> float:
        if not self.samples:
            return 0
        return max(s.cpu_percent for s in self.samples)
    
    @property
    def cpu_min(self) -> float:
        if not self.samples:
            return 0
        return min(s.cpu_percent for s in self.samples)
    
    @property
    def memory_avg_mb(self) -> float:
        if not self.samples:
            return 0
        return sum(s.memory_mb for s in self.samples) / len(self.samples)
    
    @property
    def memory_max_mb(self) -> float:
        if not self.samples:
            return 0
        return max(s.memory_mb for s in self.samples)
    
    @property
    def memory_min_mb(self) -> float:
        if not self.samples:
            return 0
        return min(s.memory_mb for s in self.samples)
    
    @property
    def memory_avg_percent(self) -> float:
        if not self.samples:
            return 0
        return sum(s.memory_percent for s in self.samples) / len(self.samples)
    
    @property
    def duration_seconds(self) -> float:
        if len(self.samples) < 2:
            return 0
        return self.samples[-1].timestamp - self.samples[0].timestamp
    
    def to_dict(self) -> dict:
        return {
            'sample_count': len(self.samples),
            'duration_seconds': round(self.duration_seconds, 2),
            'cpu': {
                'avg_percent': round(self.cpu_avg, 2),
                'min_percent': round(self.cpu_min, 2),
                'max_percent': round(self.cpu_max, 2),
            },
            'memory': {
                'avg_mb': round(self.memory_avg_mb, 2),
                'min_mb': round(self.memory_min_mb, 2),
                'max_mb': round(self.memory_max_mb, 2),
                'avg_percent': round(self.memory_avg_percent, 2),
            }
        }


class ResourceMonitor:
    """
    Monitor CPU and RAM usage during benchmark execution.
    
    Usage:
        monitor = ResourceMonitor(interval=0.1)
        monitor.start()
        
        # ... run benchmark ...
        
        stats = monitor.stop()
        print(f"Avg CPU: {stats.cpu_avg}%")
    """
    
    def __init__(self, interval: float = 0.1):
        """
        Args:
            interval: Sampling interval in seconds
        """
        if not HAS_PSUTIL:
            raise ImportError("psutil is required for resource monitoring")
        
        self.interval = interval
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._samples: List[ResourceSample] = []
        self._process: Optional[psutil.Process] = None
        self._start_time: float = 0
    
    def start(self) -> None:
        """Start monitoring."""
        if self._running:
            return
        
        self._samples = []
        self._process = psutil.Process()
        self._running = True
        self._start_time = time.time()
        
        # Initial CPU call (first call returns 0)
        self._process.cpu_percent()
        
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
    
    def stop(self) -> ResourceStats:
        """Stop monitoring and return stats."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None
        
        return ResourceStats(samples=list(self._samples))
    
    def _monitor_loop(self) -> None:
        """Background monitoring loop."""
        while self._running:
            try:
                sample = ResourceSample(
                    timestamp=time.time() - self._start_time,
                    cpu_percent=self._process.cpu_percent(),
                    memory_mb=self._process.memory_info().rss / (1024 * 1024),
                    memory_percent=self._process.memory_percent(),
                )
                self._samples.append(sample)
            except Exception:
                pass
            
            time.sleep(self.interval)
    
    def get_current_sample(self) -> Optional[ResourceSample]:
        """Get the most recent sample."""
        if self._samples:
            return self._samples[-1]
        return None


class SystemResourceMonitor(ResourceMonitor):
    """
    Monitor system-wide CPU and RAM usage (not just this process).
    """
    
    def _monitor_loop(self) -> None:
        """Background monitoring loop for system resources."""
        while self._running:
            try:
                mem = psutil.virtual_memory()
                sample = ResourceSample(
                    timestamp=time.time() - self._start_time,
                    cpu_percent=psutil.cpu_percent(),
                    memory_mb=mem.used / (1024 * 1024),
                    memory_percent=mem.percent,
                )
                self._samples.append(sample)
            except Exception:
                pass
            
            time.sleep(self.interval)


def get_system_info() -> dict:
    """Get system information for the report."""
    if not HAS_PSUTIL:
        return {"error": "psutil not available"}
    
    import platform
    
    mem = psutil.virtual_memory()
    
    return {
        'platform': platform.system(),
        'platform_release': platform.release(),
        'platform_version': platform.version(),
        'architecture': platform.machine(),
        'processor': platform.processor(),
        'python_version': platform.python_version(),
        'cpu_count_physical': psutil.cpu_count(logical=False),
        'cpu_count_logical': psutil.cpu_count(logical=True),
        'ram_total_gb': round(mem.total / (1024 ** 3), 2),
        'ram_available_gb': round(mem.available / (1024 ** 3), 2),
    }
