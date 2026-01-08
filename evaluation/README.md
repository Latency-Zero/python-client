# Evaluation Suite

Comprehensive benchmarking comparing latzero vs HTTP vs Socket communication.

## Quick Start

```bash
# Install dependencies
pip install flask requests psutil

# Run quick evaluation (10k ops)
python -m evaluation.runner --quick

# Run standard evaluation (50k ops)
python -m evaluation.runner

# Run stress test (100k ops)
python -m evaluation.runner --stress

# Run massive test (500k ops)
python -m evaluation.runner --massive
```

## CLI Options

```
usage: python -m evaluation.runner [-h] [-n NUM] [-p PAYLOAD] [-t THREADS] [-o OUTPUT]
                                   [--quick] [--stress] [--massive]
                                   [--latzero-only] [--skip-http] [--skip-socket]

Options:
  -n, --num-operations  Number of operations per test (default: 50000)
  -p, --payload-size    Payload size in bytes (default: 100)
  -t, --threads         Number of threads (default: 1)
  -o, --output          Output report path (default: evaluation/REPORT.md)
  --quick               Quick test (10k operations)
  --stress              Stress test (100k operations)
  --massive             Massive test (500k operations)
  --latzero-only        Only benchmark latzero
  --skip-http           Skip HTTP benchmark
  --skip-socket         Skip Socket benchmark
  -q, --quiet           Minimal output
```

## What's Measured

| Metric | Description |
|--------|-------------|
| Throughput | Operations per second |
| Latency | Min, Avg, P50, P95, P99, Max (ms) |
| Success Rate | Percentage of successful operations |
| CPU Usage | Average and peak CPU % |
| Memory Usage | Average and peak RAM (MB) |
| Efficiency | Throughput / (CPU × RAM) |

## Output

The evaluation generates:

1. **REPORT.md** - Comprehensive Markdown report with:
   - Executive summary
   - System information
   - Detailed results per method
   - Comparison tables and charts
   - Resource usage analysis
   - Conclusions and recommendations

2. **REPORT.json** - Raw benchmark data for further analysis

## Example Results

```
latzero Evaluation Suite
============================================================

Configuration:
  - Operations: 50,000
  - Payload: 100 bytes
  - Threads: 1
  - Methods: latzero, HTTP, Socket

────────────────────────────────────────
Benchmarking: latzero
────────────────────────────────────────
    SET: 50,000 ops, 100B payload, 1 threads... ✓ 45,000 ops/sec (1.11s)
    GET: 50,000 ops, 100B payload, 1 threads... ✓ 52,000 ops/sec (0.96s)
    MIXED: 50,000 ops, 100B payload, 1 threads... ✓ 48,000 ops/sec (1.04s)

────────────────────────────────────────
Benchmarking: HTTP
────────────────────────────────────────
    SET: 50,000 ops, 100B payload, 1 threads... ✓ 2,100 ops/sec (23.8s)
    GET: 50,000 ops, 100B payload, 1 threads... ✓ 2,300 ops/sec (21.7s)
    MIXED: 50,000 ops, 100B payload, 1 threads... ✓ 2,200 ops/sec (22.7s)

Quick Summary:
----------------------------------------
  latzero: 48,333 ops/sec, 0.021ms avg latency
  HTTP: 2,200 ops/sec, 0.455ms avg latency
  Socket: 8,500 ops/sec, 0.118ms avg latency

latzero is 22x faster than HTTP! 🚀
```
