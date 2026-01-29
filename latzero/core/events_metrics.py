"""
latzero.core.events_metrics - Observability for the events system.

Provides:
- EventMetrics: Statistics and metrics collection
- Prometheus exporter
- Health check utilities
"""

import time
import os
from typing import Dict, List, Any, Optional, TYPE_CHECKING
from dataclasses import dataclass, field
from collections import defaultdict

if TYPE_CHECKING:
    from .pool import PoolClient

from .events import EventKeys


@dataclass
class EventStats:
    """Statistics for a single event type."""
    emit_count: int = 0
    call_count: int = 0
    total_latency_us: float = 0.0
    latencies: List[float] = field(default_factory=list)
    error_count: int = 0
    last_emit: float = 0.0
    last_call: float = 0.0
    
    @property
    def avg_latency_us(self) -> float:
        """Average latency in microseconds."""
        if not self.latencies:
            return 0.0
        return sum(self.latencies) / len(self.latencies)
    
    @property
    def p99_latency_us(self) -> float:
        """P99 latency in microseconds."""
        if not self.latencies:
            return 0.0
        sorted_latencies = sorted(self.latencies)
        idx = int(len(sorted_latencies) * 0.99)
        return sorted_latencies[idx] if idx < len(sorted_latencies) else sorted_latencies[-1]
    
    @property
    def error_rate(self) -> float:
        """Error rate as fraction of total calls."""
        total = self.emit_count + self.call_count
        if total == 0:
            return 0.0
        return self.error_count / total
    
    def record_latency(self, latency_us: float) -> None:
        """Record a latency measurement."""
        self.latencies.append(latency_us)
        self.total_latency_us += latency_us
        # Keep only last 1000 measurements to bound memory
        if len(self.latencies) > 1000:
            self.latencies = self.latencies[-1000:]
    
    def to_dict(self) -> dict:
        """Convert to dictionary representation."""
        return {
            "emit_count": self.emit_count,
            "call_count": self.call_count,
            "avg_latency_us": self.avg_latency_us,
            "p99_latency_us": self.p99_latency_us,
            "error_count": self.error_count,
            "error_rate": self.error_rate,
            "last_emit": self.last_emit,
            "last_call": self.last_call,
        }


class EventMetrics:
    """
    Metrics and observability for the event system.
    
    Usage:
        metrics = EventMetrics(ipc)
        
        # Get stats for specific event
        stats = metrics.get_stats("compute:multiply")
        
        # Expose Prometheus metrics
        metrics.expose_prometheus(port=9090)
    """
    
    def __init__(self, pool_client: "PoolClient"):
        self._client = pool_client
        self._stats: Dict[str, EventStats] = defaultdict(EventStats)
        self._prometheus_server = None
    
    def record_emit(self, event: str) -> None:
        """Record an emit event."""
        self._stats[event].emit_count += 1
        self._stats[event].last_emit = time.time()
    
    def record_call(self, event: str, latency_us: float, error: bool = False) -> None:
        """Record a call event with latency."""
        stats = self._stats[event]
        stats.call_count += 1
        stats.record_latency(latency_us)
        stats.last_call = time.time()
        if error:
            stats.error_count += 1
    
    def get_stats(self, event: str) -> dict:
        """
        Get statistics for a specific event.
        
        Returns:
            Dict with emit_count, call_count, avg_latency_us, p99_latency_us,
            error_count, error_rate, active_handlers
        """
        stats = self._stats[event].to_dict()
        
        # Get handler count from registry
        registry = self._client.get(EventKeys.REGISTRY, {})
        event_info = registry.get(event, {})
        stats["active_handlers"] = len(event_info.get("handlers", []))
        
        return stats
    
    def get_all_stats(self) -> Dict[str, dict]:
        """Get statistics for all events."""
        return {event: self.get_stats(event) for event in self._stats}
    
    def get_handler_health(self) -> List[dict]:
        """
        Get health status of all registered handlers.
        
        Returns:
            List of handler health info dicts
        """
        handlers = []
        all_keys = self._client.keys()
        
        for key in all_keys:
            if key.startswith(EventKeys.HEARTBEAT_PREFIX.replace(self._client._data_key_prefix, "")):
                heartbeat = self._client.get(key)
                if heartbeat:
                    # Check if handler is alive (last seen within 2s)
                    is_alive = (time.time() - heartbeat.get("last_seen", 0)) < 2.0
                    handlers.append({
                        **heartbeat,
                        "alive": is_alive,
                    })
        
        return handlers
    
    def cleanup_dead_handlers(self) -> int:
        """
        Remove handlers that haven't sent heartbeat in 2s.
        
        Returns:
            Number of handlers removed
        """
        removed = 0
        registry = self._client.get(EventKeys.REGISTRY, {})
        
        # Get all live PIDs
        live_pids = set()
        handlers = self.get_handler_health()
        for h in handlers:
            if h.get("alive"):
                live_pids.add(h.get("pid"))
        
        # Remove dead handlers from registry
        for event, info in list(registry.items()):
            original_count = len(info.get("handlers", []))
            info["handlers"] = [
                h for h in info.get("handlers", [])
                if h.get("pid") in live_pids
            ]
            removed += original_count - len(info["handlers"])
            
            if not info["handlers"]:
                del registry[event]
        
        if removed > 0:
            self._client.set(EventKeys.REGISTRY, registry)
        
        return removed
    
    def expose_prometheus(self, port: int = 9090) -> None:
        """
        Expose metrics in Prometheus format on HTTP server.
        
        Args:
            port: Port to serve metrics on
        """
        try:
            from http.server import HTTPServer, BaseHTTPRequestHandler
            import threading
        except ImportError:
            raise RuntimeError("HTTP server not available")
        
        metrics = self
        
        class MetricsHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == "/metrics":
                    self.send_response(200)
                    self.send_header("Content-Type", "text/plain")
                    self.end_headers()
                    
                    output = []
                    
                    # Event metrics
                    for event, stats in metrics.get_all_stats().items():
                        safe_event = event.replace(":", "_").replace("-", "_")
                        output.append(f'latzero_event_emit_total{{event="{event}"}} {stats["emit_count"]}')
                        output.append(f'latzero_event_call_total{{event="{event}"}} {stats["call_count"]}')
                        output.append(f'latzero_event_latency_avg_us{{event="{event}"}} {stats["avg_latency_us"]:.2f}')
                        output.append(f'latzero_event_latency_p99_us{{event="{event}"}} {stats["p99_latency_us"]:.2f}')
                        output.append(f'latzero_event_errors_total{{event="{event}"}} {stats["error_count"]}')
                        output.append(f'latzero_event_handlers{{event="{event}"}} {stats["active_handlers"]}')
                    
                    # Handler health
                    handlers = metrics.get_handler_health()
                    alive_count = sum(1 for h in handlers if h.get("alive"))
                    output.append(f'latzero_handlers_alive {alive_count}')
                    output.append(f'latzero_handlers_total {len(handlers)}')
                    
                    self.wfile.write("\n".join(output).encode())
                else:
                    self.send_response(404)
                    self.end_headers()
            
            def log_message(self, format, *args):
                pass  # Suppress logging
        
        self._prometheus_server = HTTPServer(("", port), MetricsHandler)
        
        thread = threading.Thread(
            target=self._prometheus_server.serve_forever,
            daemon=True,
            name="latzero-prometheus"
        )
        thread.start()
    
    def stop_prometheus(self) -> None:
        """Stop Prometheus metrics server."""
        if self._prometheus_server:
            self._prometheus_server.shutdown()
            self._prometheus_server = None


def get_pool_event_health(pool_client: "PoolClient") -> dict:
    """
    Get overall health status of the event system for a pool.
    
    Args:
        pool_client: Connected pool client
        
    Returns:
        Dict with health status
    """
    metrics = EventMetrics(pool_client)
    handlers = metrics.get_handler_health()
    
    alive_handlers = [h for h in handlers if h.get("alive")]
    dead_handlers = [h for h in handlers if not h.get("alive")]
    
    # Get registered events
    registry = pool_client.get(EventKeys.REGISTRY, {})
    
    return {
        "status": "healthy" if len(dead_handlers) == 0 else "degraded",
        "registered_events": list(registry.keys()),
        "total_handlers": len(handlers),
        "alive_handlers": len(alive_handlers),
        "dead_handlers": len(dead_handlers),
        "handlers": handlers,
    }
