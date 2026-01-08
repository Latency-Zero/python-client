"""
latzero Evaluation Suite

Comprehensive benchmarking comparing:
- latzero (shared memory IPC)
- HTTP (Flask/requests)
- Socket (raw TCP)

Metrics:
- Throughput (ops/sec)
- Latency (min, avg, max, p50, p95, p99)
- Reliability (success rate, errors)
- Resource usage (CPU, RAM)
"""

from .runner import run_evaluation
from .benchmarks import LatzeroBenchmark, HTTPBenchmark, SocketBenchmark
from .monitor import ResourceMonitor
from .report import generate_report

__all__ = [
    'run_evaluation',
    'LatzeroBenchmark',
    'HTTPBenchmark', 
    'SocketBenchmark',
    'ResourceMonitor',
    'generate_report',
]
