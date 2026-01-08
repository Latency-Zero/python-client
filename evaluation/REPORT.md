# latzero Evaluation Report

> Generated: 2026-01-08 16:34:35

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [System Information](#system-information)
3. [Benchmark Configuration](#benchmark-configuration)
4. [Results Overview](#results-overview)
5. [Detailed Results](#detailed-results)
6. [Latency Analysis](#latency-analysis)
7. [Resource Usage](#resource-usage)
8. [Reliability Analysis](#reliability-analysis)
9. [Comparison Charts](#comparison-charts)
10. [Conclusions](#conclusions)
11. [Raw Data](#raw-data)

---

## Executive Summary

### Key Findings

| Metric | Winner | Value |
|--------|--------|-------|
| **Highest Throughput** | latzero | 359,479 ops/sec |
| **Lowest Latency** | latzero | 0.002 ms avg |
| **Best Reliability** | latzero | 100.00% success |

### Speed Advantage

latzero is: **2515.9x faster** than HTTP, **45.4x faster** than Socket

---

## System Information

| Property | Value |
|----------|-------|
| Platform | Windows |
| Platform Release | 11 |
| Platform Version | 10.0.26200 |
| Architecture | AMD64 |
| Processor | AMD64 Family 26 Model 36 Stepping 0, AuthenticAMD |
| Python Version | 3.12.7 |
| Cpu Count Physical | 10 |
| Cpu Count Logical | 20 |
| Ram Total Gb | 23.12 |
| Ram Available Gb | 5.76 |

---

## Benchmark Configuration

```json
{
  "num_operations": 10000,
  "payload_size": 100,
  "threads": 1,
  "methods": [
    "latzero",
    "HTTP",
    "Socket"
  ],
  "operations": [
    "set",
    "get",
    "mixed"
  ],
  "timestamp": "2026-01-08T16:30:34.139366"
}
```

---

## Results Overview

### Throughput Comparison (ops/sec)

| Method | SET | GET | Mixed |
|--------|-----|-----|-------|
| latzero | 80,213 | 359,479 | 184,827 |
| HTTP | 143 | 132 | 124 |
| Socket | 7,351 | 7,921 | 3,932 |

### Latency Comparison (ms)

| Method | Operation | Avg | P50 | P95 | P99 | Max |
|--------|-----------|-----|-----|-----|-----|-----|
| latzero | set | 0.011 | 0.002 | 0.004 | 0.316 | 1.549 |
| latzero | get | 0.002 | 0.001 | 0.002 | 0.003 | 0.238 |
| latzero | mixed | 0.004 | 0.002 | 0.003 | 0.011 | 0.779 |
| HTTP | set | 6.989 | 5.461 | 21.461 | 29.505 | 45.734 |
| HTTP | get | 7.478 | 5.762 | 22.746 | 30.514 | 44.529 |
| HTTP | mixed | 8.065 | 6.032 | 25.230 | 31.673 | 80.959 |
| Socket | set | 0.132 | 0.106 | 0.257 | 0.390 | 52.170 |
| Socket | get | 0.123 | 0.104 | 0.254 | 0.382 | 3.915 |
| Socket | mixed | 0.124 | 0.104 | 0.239 | 0.379 | 1.958 |

---

## Detailed Results

### latzero

#### SET Operations

- **Total Operations**: 10,000
- **Successful**: 10,000
- **Failed**: 0
- **Success Rate**: 100.00%
- **Total Time**: 0.12s
- **Throughput**: 80,213 ops/sec

**Latency Distribution:**

| Metric | Value (ms) |
|--------|------------|
| Min | 0.0019 |
| Avg | 0.0113 |
| P50 (Median) | 0.0021 |
| P95 | 0.0038 |
| P99 | 0.3157 |
| Max | 1.5492 |
| Std Dev | 0.0893 |

#### GET Operations

- **Total Operations**: 10,000
- **Successful**: 10,000
- **Failed**: 0
- **Success Rate**: 100.00%
- **Total Time**: 0.03s
- **Throughput**: 359,479 ops/sec

**Latency Distribution:**

| Metric | Value (ms) |
|--------|------------|
| Min | 0.0011 |
| Avg | 0.0016 |
| P50 (Median) | 0.0013 |
| P95 | 0.0023 |
| P99 | 0.0030 |
| Max | 0.2379 |
| Std Dev | 0.0035 |

#### MIXED Operations

- **Total Operations**: 10,000
- **Successful**: 10,000
- **Failed**: 0
- **Success Rate**: 100.00%
- **Total Time**: 0.05s
- **Throughput**: 184,827 ops/sec

**Latency Distribution:**

| Metric | Value (ms) |
|--------|------------|
| Min | 0.0011 |
| Avg | 0.0043 |
| P50 (Median) | 0.0021 |
| P95 | 0.0035 |
| P99 | 0.0110 |
| Max | 0.7793 |
| Std Dev | 0.0326 |

---

### HTTP

#### SET Operations

- **Total Operations**: 10,000
- **Successful**: 10,000
- **Failed**: 0
- **Success Rate**: 100.00%
- **Total Time**: 69.99s
- **Throughput**: 143 ops/sec

**Latency Distribution:**

| Metric | Value (ms) |
|--------|------------|
| Min | 3.4860 |
| Avg | 6.9886 |
| P50 (Median) | 5.4611 |
| P95 | 21.4611 |
| P99 | 29.5054 |
| Max | 45.7344 |
| Std Dev | 5.1424 |

#### GET Operations

- **Total Operations**: 10,000
- **Successful**: 9,854
- **Failed**: 146
- **Success Rate**: 98.54%
- **Total Time**: 74.89s
- **Throughput**: 132 ops/sec

**Latency Distribution:**

| Metric | Value (ms) |
|--------|------------|
| Min | 3.5023 |
| Avg | 7.4780 |
| P50 (Median) | 5.7618 |
| P95 | 22.7464 |
| P99 | 30.5137 |
| Max | 44.5288 |
| Std Dev | 5.4020 |

**Sample Errors (146 total):**
```
  - HTTPConnectionPool(host='127.0.0.1', port=5999): Max retries exceeded with url: /get/bench_key_233 (Caused by NewConnectionError('<urllib3.connection.HTTPConnection object at 0x0000021BE41C3170>: Failed to establish a new connection: [WinError 10048] Only one usage of each socket address (protocol/network address/port) is normally permitted'))
  - HTTPConnectionPool(host='127.0.0.1', port=5999): Max retries exceeded with url: /get/bench_key_234 (Caused by NewConnectionError('<urllib3.connection.HTTPConnection object at 0x0000021BE3D60D40>: Failed to establish a new connection: [WinError 10048] Only one usage of each socket address (protocol/network address/port) is normally permitted'))
  - HTTPConnectionPool(host='127.0.0.1', port=5999): Max retries exceeded with url: /get/bench_key_235 (Caused by NewConnectionError('<urllib3.connection.HTTPConnection object at 0x0000021BE41D2C30>: Failed to establish a new connection: [WinError 10048] Only one usage of each socket address (protocol/network address/port) is normally permitted'))
  - HTTPConnectionPool(host='127.0.0.1', port=5999): Max retries exceeded with url: /get/bench_key_236 (Caused by NewConnectionError('<urllib3.connection.HTTPConnection object at 0x0000021BE41D2660>: Failed to establish a new connection: [WinError 10048] Only one usage of each socket address (protocol/network address/port) is normally permitted'))
  - HTTPConnectionPool(host='127.0.0.1', port=5999): Max retries exceeded with url: /get/bench_key_237 (Caused by NewConnectionError('<urllib3.connection.HTTPConnection object at 0x0000021BE3D63D40>: Failed to establish a new connection: [WinError 10048] Only one usage of each socket address (protocol/network address/port) is normally permitted'))
```

#### MIXED Operations

- **Total Operations**: 10,000
- **Successful**: 10,000
- **Failed**: 0
- **Success Rate**: 100.00%
- **Total Time**: 80.76s
- **Throughput**: 124 ops/sec

**Latency Distribution:**

| Metric | Value (ms) |
|--------|------------|
| Min | 3.5689 |
| Avg | 8.0653 |
| P50 (Median) | 6.0321 |
| P95 | 25.2303 |
| P99 | 31.6734 |
| Max | 80.9586 |
| Std Dev | 6.6661 |

---

### Socket

#### SET Operations

- **Total Operations**: 10,000
- **Successful**: 10,000
- **Failed**: 0
- **Success Rate**: 100.00%
- **Total Time**: 1.36s
- **Throughput**: 7,351 ops/sec

**Latency Distribution:**

| Metric | Value (ms) |
|--------|------------|
| Min | 0.0682 |
| Avg | 0.1325 |
| P50 (Median) | 0.1064 |
| P95 | 0.2568 |
| P99 | 0.3898 |
| Max | 52.1702 |
| Std Dev | 0.5252 |

#### GET Operations

- **Total Operations**: 10,000
- **Successful**: 10,000
- **Failed**: 0
- **Success Rate**: 100.00%
- **Total Time**: 1.26s
- **Throughput**: 7,921 ops/sec

**Latency Distribution:**

| Metric | Value (ms) |
|--------|------------|
| Min | 0.0676 |
| Avg | 0.1232 |
| P50 (Median) | 0.1042 |
| P95 | 0.2540 |
| P99 | 0.3821 |
| Max | 3.9150 |
| Std Dev | 0.0814 |

#### MIXED Operations

- **Total Operations**: 10,000
- **Successful**: 5,000
- **Failed**: 5,000
- **Success Rate**: 50.00%
- **Total Time**: 1.27s
- **Throughput**: 3,932 ops/sec

**Latency Distribution:**

| Metric | Value (ms) |
|--------|------------|
| Min | 0.0707 |
| Avg | 0.1238 |
| P50 (Median) | 0.1038 |
| P95 | 0.2388 |
| P99 | 0.3792 |
| Max | 1.9584 |
| Std Dev | 0.0615 |

---

## Latency Analysis

### Latency Distribution Visualization

```
Latency Percentiles (lower is better)
============================================================

latzero - set:
  Min  [█] 0.002ms
  P50  [] 0.002ms
  P95  [] 0.004ms
  P99  [███] 0.316ms
  Max  [███████] 1.549ms

latzero - get:
  Min  [█] 0.001ms
  P50  [] 0.001ms
  P95  [] 0.002ms
  P99  [] 0.003ms
  Max  [█] 0.238ms

latzero - mixed:
  Min  [█] 0.001ms
  P50  [] 0.002ms
  P95  [] 0.003ms
  P99  [] 0.011ms
  Max  [███] 0.779ms

HTTP - set:
  Min  [█] 3.486ms
  P50  [████████████████████] 5.461ms
  P95  [████████████████████████████████████████] 21.461ms
  P99  [██████████████████████████████████████████████████] 29.505ms
  Max  [████████████████████████████████████████████████████████████] 45.734ms

HTTP - get:
  Min  [█] 3.502ms
  P50  [████████████████████] 5.762ms
  P95  [████████████████████████████████████████] 22.746ms
  P99  [██████████████████████████████████████████████████] 30.514ms
  Max  [████████████████████████████████████████████████████████████] 44.529ms

HTTP - mixed:
  Min  [█] 3.569ms
  P50  [████████████████████] 6.032ms
  P95  [████████████████████████████████████████] 25.230ms
  P99  [██████████████████████████████████████████████████] 31.673ms
  Max  [████████████████████████████████████████████████████████████] 80.959ms

Socket - set:
  Min  [█] 0.068ms
  P50  [█] 0.106ms
  P95  [██] 0.257ms
  P99  [███] 0.390ms
  Max  [████████████████████████████████████████████████████████████] 52.170ms

Socket - get:
  Min  [█] 0.068ms
  P50  [█] 0.104ms
  P95  [██] 0.254ms
  P99  [███] 0.382ms
  Max  [███████████████████] 3.915ms

Socket - mixed:
  Min  [█] 0.071ms
  P50  [█] 0.104ms
  P95  [██] 0.239ms
  P99  [███] 0.379ms
  Max  [█████████] 1.958ms
```

---

## Resource Usage

### CPU and Memory by Method

| Method | CPU Avg (%) | CPU Max (%) | RAM Avg (MB) | RAM Max (MB) |
|--------|-------------|-------------|--------------|--------------|
| latzero | 52.1 | 99.7 | 45.3 | 46.8 |
| HTTP | 99.7 | 266.0 | 51.0 | 65.0 |
| Socket | 87.6 | 199.5 | 52.0 | 52.7 |

### Efficiency Score

*Efficiency = Throughput / (CPU% × RAM_MB)*

| Method | Throughput | CPU% | RAM (MB) | Efficiency |
|--------|------------|------|----------|------------|
| latzero | 624,519 | 52.1 | 45.3 | 26,423 |
| HTTP | 398 | 99.7 | 51.0 | 8 |
| Socket | 19,204 | 87.6 | 52.0 | 421 |

---

## Reliability Analysis

| Method | Operation | Success Rate | Errors |
|--------|-----------|--------------|--------|
| latzero | set | 100.00% | 0 |
| latzero | get | 100.00% | 0 |
| latzero | mixed | 100.00% | 0 |
| HTTP | set | 100.00% | 0 |
| HTTP | get | 98.54% | 146 |
| HTTP | mixed | 100.00% | 0 |
| Socket | set | 100.00% | 0 |
| Socket | get | 100.00% | 0 |
| Socket | mixed | 50.00% | 5000 |

✅ **100% reliability achieved by**: latzero

---

## Comparison Charts

### Throughput Bar Chart

```
Operations per Second (higher is better)
============================================================
latzero      [███████████████████████░░░░░░░░░░░░░░░░░] 208,173
HTTP         [░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░] 133
Socket       [░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░] 6,401
```

### Latency Comparison

```
Average Latency in ms (lower is better)
============================================================
latzero      [░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░] 0.006ms
HTTP         [█████████████████████████████████████░░░] 7.511ms
Socket       [░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░] 0.126ms
```

---

## Conclusions

### latzero Performance Summary

- **Average Throughput**: 208,173 operations/second
- **Average Latency**: 0.006 ms

**vs HTTP:**
- 1568.0x faster throughput
- 1317.1x lower latency

**vs Socket:**
- 32.5x faster throughput
- 22.2x lower latency

### Recommendations

1. **For maximum speed**: Use latzero for inter-process communication
2. **For cross-machine**: Use HTTP or Socket (latzero is same-machine only)
3. **For persistence**: Enable latzero snapshots for data durability

---

## Raw Data

<details>
<summary>Click to expand JSON data</summary>

```json
{
  "generated_at": "2026-01-08T16:34:36.939040",
  "config": {
    "num_operations": 10000,
    "payload_size": 100,
    "threads": 1,
    "methods": [
      "latzero",
      "HTTP",
      "Socket"
    ],
    "operations": [
      "set",
      "get",
      "mixed"
    ],
    "timestamp": "2026-01-08T16:30:34.139366"
  },
  "system_info": {
    "platform": "Windows",
    "platform_release": "11",
    "platform_version": "10.0.26200",
    "architecture": "AMD64",
    "processor": "AMD64 Family 26 Model 36 Stepping 0, AuthenticAMD",
    "python_version": "3.12.7",
    "cpu_count_physical": 10,
    "cpu_count_logical": 20,
    "ram_total_gb": 23.12,
    "ram_available_gb": 5.76
  },
  "results": {
    "latzero": [
      {
        "name": "latzero",
        "operation": "set",
        "total_operations": 10000,
        "successful_operations": 10000,
        "failed_operations": 0,
        "total_time_seconds": 0.12466819997644052,
        "throughput_ops_per_sec": 80212.91718248739,
        "success_rate_percent": 100.0,
        "latency_ms": {
          "min": 0.0018999853637069464,
          "max": 1.549200009321794,
          "avg": 0.011259700066875666,
          "p50": 0.002100015990436077,
          "p95": 0.0037999998312443495,
          "p99": 0.3157000173814595,
          "stdev": 0.08930062856977974
        },
        "error_count": 0,
        "sample_errors": []
      },
      {
        "name": "latzero",
        "operation": "get",
        "total_operations": 10000,
        "successful_operations": 10000,
        "failed_operations": 0,
        "total_time_seconds": 0.027818000002298504,
        "throughput_ops_per_sec": 359479.47369234794,
        "success_rate_percent": 100.0,
        "latency_ms": {
          "min": 0.0010999792721122503,
          "max": 0.23790000705048442,
          "avg": 0.0015899299702141433,
          "p50": 0.0012999807950109243,
          "p95": 0.0022999884095042944,
          "p99": 0.0029999937396496534,
          "stdev": 0.003522139176851881
        },
        "error_count": 0,
        "sample_errors": []
      },
      {
        "name": "latzero",
        "operation": "mixed",
        "total_operations": 10000,
        "successful_operations": 10000,
        "failed_operations": 0,
        "total_time_seconds": 0.054104700015159324,
        "throughput_ops_per_sec": 184826.82645312054,
        "success_rate_percent": 100.0,
        "latency_ms": {
          "min": 0.0010999792721122503,
          "max": 0.7792999967932701,
          "avg": 0.004257730030803941,
          "p50": 0.002100015990436077,
          "p95": 0.0034999975468963385,
          "p99": 0.011000025551766157,
          "stdev": 0.03263486493893644
        },
        "error_count": 0,
        "sample_errors": []
      }
    ],
    "HTTP": [
      {
        "name": "HTTP",
        "operation": "set",
        "total_operations": 10000,
        "successful_operations": 10000,
        "failed_operations": 0,
        "total_time_seconds": 69.98811090001254,
        "throughput_ops_per_sec": 142.88141044821668,
        "success_rate_percent": 100.0,
        "latency_ms": {
          "min": 3.4860000014305115,
          "max": 45.73440001695417,
          "avg": 6.988624759990489,
          "p50": 5.4610999941360205,
          "p95": 21.46109999739565,
          "p99": 29.505399987101555,
          "stdev": 5.1424143004421605
        },
        "error_count": 0,
        "sample_errors": []
      },
      {
        "name": "HTTP",
        "operation": "get",
        "total_operations": 10000,
        "successful_operations": 9854,
        "failed_operations": 146,
        "total_time_seconds": 74.88615189999109,
        "throughput_ops_per_sec": 131.5864115058257,
        "success_rate_percent": 98.54,
        "latency_ms": {
          "min": 3.5023000091314316,
          "max": 44.528800004627556,
          "avg": 7.4779660801315915,
          "p50": 5.761799984611571,
          "p95": 22.746400005416945,
          "p99": 30.51370001048781,
          "stdev": 5.40195630301949
        },
        "error_count": 146,
        "sample_errors": [
          "HTTPConnectionPool(host='127.0.0.1', port=5999): Max retries exceeded with url: /get/bench_key_233 (Caused by NewConnectionError('<urllib3.connection.HTTPConnection object at 0x0000021BE41C3170>: Failed to establish a new connection: [WinError 10048] Only one usage of each socket address (protocol/network address/port) is normally permitted'))",
          "HTTPConnectionPool(host='127.0.0.1', port=5999): Max retries exceeded with url: /get/bench_key_234 (Caused by NewConnectionError('<urllib3.connection.HTTPConnection object at 0x0000021BE3D60D40>: Failed to establish a new connection: [WinError 10048] Only one usage of each socket address (protocol/network address/port) is normally permitted'))",
          "HTTPConnectionPool(host='127.0.0.1', port=5999): Max retries exceeded with url: /get/bench_key_235 (Caused by NewConnectionError('<urllib3.connection.HTTPConnection object at 0x0000021BE41D2C30>: Failed to establish a new connection: [WinError 10048] Only one usage of each socket address (protocol/network address/port) is normally permitted'))",
          "HTTPConnectionPool(host='127.0.0.1', port=5999): Max retries exceeded with url: /get/bench_key_236 (Caused by NewConnectionError('<urllib3.connection.HTTPConnection object at 0x0000021BE41D2660>: Failed to establish a new connection: [WinError 10048] Only one usage of each socket address (protocol/network address/port) is normally permitted'))",
          "HTTPConnectionPool(host='127.0.0.1', port=5999): Max retries exceeded with url: /get/bench_key_237 (Caused by NewConnectionError('<urllib3.connection.HTTPConnection object at 0x0000021BE3D63D40>: Failed to establish a new connection: [WinError 10048] Only one usage of each socket address (protocol/network address/port) is normally permitted'))"
        ]
      },
      {
        "name": "HTTP",
        "operation": "mixed",
        "total_operations": 10000,
        "successful_operations": 10000,
        "failed_operations": 0,
        "total_time_seconds": 80.75584709999384,
        "throughput_ops_per_sec": 123.8300427660397,
        "success_rate_percent": 100.0,
        "latency_ms": {
          "min": 3.568899992387742,
          "max": 80.95859998138621,
          "avg": 8.06529005978955,
          "p50": 6.032100005540997,
          "p95": 25.23030000156723,
          "p99": 31.673400022555143,
          "stdev": 6.666147144497959
        },
        "error_count": 0,
        "sample_errors": []
      }
    ],
    "Socket": [
      {
        "name": "Socket",
        "operation": "set",
        "total_operations": 10000,
        "successful_operations": 10000,
        "failed_operations": 0,
        "total_time_seconds": 1.360309200012125,
        "throughput_ops_per_sec": 7351.269843584727,
        "success_rate_percent": 100.0,
        "latency_ms": {
          "min": 0.06819999543949962,
          "max": 52.17020001146011,
          "avg": 0.13245156994962598,
          "p50": 0.10639999527484179,
          "p95": 0.25680000544525683,
          "p99": 0.38979999953880906,
          "stdev": 0.5251896732345432
        },
        "error_count": 0,
        "sample_errors": []
      },
      {
        "name": "Socket",
        "operation": "get",
        "total_operations": 10000,
        "successful_operations": 10000,
        "failed_operations": 0,
        "total_time_seconds": 1.2625393000198528,
        "throughput_ops_per_sec": 7920.54552269601,
        "success_rate_percent": 100.0,
        "latency_ms": {
          "min": 0.0675999908708036,
          "max": 3.915000008419156,
          "avg": 0.12322689022694248,
          "p50": 0.10420000762678683,
          "p95": 0.2539999841246754,
          "p99": 0.382099999114871,
          "stdev": 0.08141400812146195
        },
        "error_count": 0,
        "sample_errors": []
      },
      {
        "name": "Socket",
        "operation": "mixed",
        "total_operations": 10000,
        "successful_operations": 5000,
        "failed_operations": 5000,
        "total_time_seconds": 1.2715204000123776,
        "throughput_ops_per_sec": 3932.300260342915,
        "success_rate_percent": 50.0,
        "latency_ms": {
          "min": 0.07070001447573304,
          "max": 1.9583999819587916,
          "avg": 0.12376208995701746,
          "p50": 0.10380000458098948,
          "p95": 0.238799984799698,
          "p99": 0.3792000061366707,
          "stdev": 0.061542163430139046
        },
        "error_count": 0,
        "sample_errors": []
      }
    ]
  },
  "resource_stats": {
    "latzero": {
      "sample_count": 8,
      "duration_seconds": 0.05,
      "cpu": {
        "avg_percent": 52.14,
        "min_percent": 0.0,
        "max_percent": 99.7
      },
      "memory": {
        "avg_mb": 45.33,
        "min_mb": 42.24,
        "max_mb": 46.84,
        "avg_percent": 0.19
      }
    },
    "HTTP": {
      "sample_count": 4606,
      "duration_seconds": 81.25,
      "cpu": {
        "avg_percent": 99.66,
        "min_percent": 0.0,
        "max_percent": 266.0
      },
      "memory": {
        "avg_mb": 50.99,
        "min_mb": 46.89,
        "max_mb": 64.99,
        "avg_percent": 0.22
      }
    },
    "Socket": {
      "sample_count": 99,
      "duration_seconds": 1.57,
      "cpu": {
        "avg_percent": 87.62,
        "min_percent": 0.0,
        "max_percent": 199.5
      },
      "memory": {
        "avg_mb": 52.01,
        "min_mb": 50.96,
        "max_mb": 52.69,
        "avg_percent": 0.22
      }
    }
  }
}
```

</details>

---

*Report generated by latzero evaluation suite*