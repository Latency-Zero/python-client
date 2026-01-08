# latzero Evaluation Report

> Generated: 2026-01-08 16:12:24

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
| **Highest Throughput** | Socket | 10,040 ops/sec |
| **Lowest Latency** | Socket | 0.097 ms avg |
| **Best Reliability** | latzero | 100.00% success |

### Speed Advantage

latzero is: **0.1x faster** than Socket

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
| Ram Available Gb | 5.51 |

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
  "timestamp": "2026-01-08T16:10:48.186772"
}
```

---

## Results Overview

### Throughput Comparison (ops/sec)

| Method | SET | GET | Mixed |
|--------|-----|-----|-------|
| latzero | 189 | 459 | 519 |
| HTTP | 0 | 0 | 0 |
| Socket | 10,040 | 0 | 0 |

### Latency Comparison (ms)

| Method | Operation | Avg | P50 | P95 | P99 | Max |
|--------|-----------|-----|-----|-----|-----|-----|
| latzero | set | 5.274 | 4.935 | 7.823 | 10.466 | 52.788 |
| latzero | get | 2.173 | 1.664 | 4.396 | 9.351 | 30.515 |
| latzero | mixed | 1.921 | 1.737 | 3.552 | 4.960 | 29.383 |
| HTTP | set | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| HTTP | get | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| HTTP | mixed | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| Socket | set | 0.097 | 0.080 | 0.183 | 0.322 | 2.510 |
| Socket | get | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| Socket | mixed | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |

---

## Detailed Results

### latzero

#### SET Operations

- **Total Operations**: 10,000
- **Successful**: 10,000
- **Failed**: 0
- **Success Rate**: 100.00%
- **Total Time**: 52.82s
- **Throughput**: 189 ops/sec

**Latency Distribution:**

| Metric | Value (ms) |
|--------|------------|
| Min | 0.4232 |
| Avg | 5.2739 |
| P50 (Median) | 4.9349 |
| P95 | 7.8230 |
| P99 | 10.4660 |
| Max | 52.7880 |
| Std Dev | 2.1932 |

#### GET Operations

- **Total Operations**: 10,000
- **Successful**: 10,000
- **Failed**: 0
- **Success Rate**: 100.00%
- **Total Time**: 21.79s
- **Throughput**: 459 ops/sec

**Latency Distribution:**

| Metric | Value (ms) |
|--------|------------|
| Min | 0.4563 |
| Avg | 2.1731 |
| P50 (Median) | 1.6638 |
| P95 | 4.3959 |
| P99 | 9.3510 |
| Max | 30.5150 |
| Std Dev | 1.8963 |

#### MIXED Operations

- **Total Operations**: 10,000
- **Successful**: 10,000
- **Failed**: 0
- **Success Rate**: 100.00%
- **Total Time**: 19.27s
- **Throughput**: 519 ops/sec

**Latency Distribution:**

| Metric | Value (ms) |
|--------|------------|
| Min | 0.0362 |
| Avg | 1.9210 |
| P50 (Median) | 1.7370 |
| P95 | 3.5520 |
| P99 | 4.9603 |
| Max | 29.3829 |
| Std Dev | 1.8367 |

---

### HTTP

#### SET Operations

- **Total Operations**: 10,000
- **Successful**: 0
- **Failed**: 10,000
- **Success Rate**: 0.00%
- **Total Time**: 0.01s
- **Throughput**: 0 ops/sec

**Latency Distribution:**

| Metric | Value (ms) |
|--------|------------|
| Min | 0.0000 |
| Avg | 0.0000 |
| P50 (Median) | 0.0000 |
| P95 | 0.0000 |
| P99 | 0.0000 |
| Max | 0.0000 |
| Std Dev | 0.0000 |

**Sample Errors (1 total):**
```
  - cannot pickle 'module' object
```

#### GET Operations

- **Total Operations**: 10,000
- **Successful**: 0
- **Failed**: 10,000
- **Success Rate**: 0.00%
- **Total Time**: 0.01s
- **Throughput**: 0 ops/sec

**Latency Distribution:**

| Metric | Value (ms) |
|--------|------------|
| Min | 0.0000 |
| Avg | 0.0000 |
| P50 (Median) | 0.0000 |
| P95 | 0.0000 |
| P99 | 0.0000 |
| Max | 0.0000 |
| Std Dev | 0.0000 |

**Sample Errors (1 total):**
```
  - cannot pickle 'module' object
```

#### MIXED Operations

- **Total Operations**: 10,000
- **Successful**: 0
- **Failed**: 10,000
- **Success Rate**: 0.00%
- **Total Time**: 0.01s
- **Throughput**: 0 ops/sec

**Latency Distribution:**

| Metric | Value (ms) |
|--------|------------|
| Min | 0.0000 |
| Avg | 0.0000 |
| P50 (Median) | 0.0000 |
| P95 | 0.0000 |
| P99 | 0.0000 |
| Max | 0.0000 |
| Std Dev | 0.0000 |

**Sample Errors (1 total):**
```
  - cannot pickle 'module' object
```

---

### Socket

#### SET Operations

- **Total Operations**: 10,000
- **Successful**: 10,000
- **Failed**: 0
- **Success Rate**: 100.00%
- **Total Time**: 1.00s
- **Throughput**: 10,040 ops/sec

**Latency Distribution:**

| Metric | Value (ms) |
|--------|------------|
| Min | 0.0616 |
| Avg | 0.0971 |
| P50 (Median) | 0.0801 |
| P95 | 0.1833 |
| P99 | 0.3216 |
| Max | 2.5105 |
| Std Dev | 0.0550 |

#### GET Operations

- **Total Operations**: 10,000
- **Successful**: 0
- **Failed**: 10,000
- **Success Rate**: 0.00%
- **Total Time**: 0.01s
- **Throughput**: 0 ops/sec

**Latency Distribution:**

| Metric | Value (ms) |
|--------|------------|
| Min | 0.0000 |
| Avg | 0.0000 |
| P50 (Median) | 0.0000 |
| P95 | 0.0000 |
| P99 | 0.0000 |
| Max | 0.0000 |
| Std Dev | 0.0000 |

**Sample Errors (1 total):**
```
  - [WinError 10038] An operation was attempted on something that is not a socket
```

#### MIXED Operations

- **Total Operations**: 10,000
- **Successful**: 0
- **Failed**: 10,000
- **Success Rate**: 0.00%
- **Total Time**: 0.01s
- **Throughput**: 0 ops/sec

**Latency Distribution:**

| Metric | Value (ms) |
|--------|------------|
| Min | 0.0000 |
| Avg | 0.0000 |
| P50 (Median) | 0.0000 |
| P95 | 0.0000 |
| P99 | 0.0000 |
| Max | 0.0000 |
| Std Dev | 0.0000 |

**Sample Errors (1 total):**
```
  - [WinError 10038] An operation was attempted on something that is not a socket
```

---

## Latency Analysis

### Latency Distribution Visualization

```
Latency Percentiles (lower is better)
============================================================

latzero - set:
  Min  [█] 0.423ms
  P50  [████████████████████] 4.935ms
  P95  [████████████████████████████████████████] 7.823ms
  P99  [██████████████████████████████████████████████████] 10.466ms
  Max  [████████████████████████████████████████████████████████████] 52.788ms

latzero - get:
  Min  [█] 0.456ms
  P50  [████████████████] 1.664ms
  P95  [████████████████████████████████████████] 4.396ms
  P99  [██████████████████████████████████████████████████] 9.351ms
  Max  [████████████████████████████████████████████████████████████] 30.515ms

latzero - mixed:
  Min  [█] 0.036ms
  P50  [█████████████████] 1.737ms
  P95  [███████████████████████████████████] 3.552ms
  P99  [█████████████████████████████████████████████████] 4.960ms
  Max  [████████████████████████████████████████████████████████████] 29.383ms

HTTP - set:
  Min  [█] 0.000ms
  P50  [] 0.000ms
  P95  [] 0.000ms
  P99  [] 0.000ms
  Max  [] 0.000ms

HTTP - get:
  Min  [█] 0.000ms
  P50  [] 0.000ms
  P95  [] 0.000ms
  P99  [] 0.000ms
  Max  [] 0.000ms

HTTP - mixed:
  Min  [█] 0.000ms
  P50  [] 0.000ms
  P95  [] 0.000ms
  P99  [] 0.000ms
  Max  [] 0.000ms

Socket - set:
  Min  [█] 0.062ms
  P50  [] 0.080ms
  P95  [█] 0.183ms
  P99  [███] 0.322ms
  Max  [████████████] 2.510ms

Socket - get:
  Min  [█] 0.000ms
  P50  [] 0.000ms
  P95  [] 0.000ms
  P99  [] 0.000ms
  Max  [] 0.000ms

Socket - mixed:
  Min  [█] 0.000ms
  P50  [] 0.000ms
  P95  [] 0.000ms
  P99  [] 0.000ms
  Max  [] 0.000ms
```

---

## Resource Usage

### CPU and Memory by Method

| Method | CPU Avg (%) | CPU Max (%) | RAM Avg (MB) | RAM Max (MB) |
|--------|-------------|-------------|--------------|--------------|
| latzero | 100.1 | 169.8 | 50.0 | 50.8 |
| HTTP | 0.0 | 0.0 | 50.3 | 50.3 |
| Socket | 35.6 | 99.7 | 50.4 | 50.5 |

### Efficiency Score

*Efficiency = Throughput / (CPU% × RAM_MB)*

| Method | Throughput | CPU% | RAM (MB) | Efficiency |
|--------|------------|------|----------|------------|
| latzero | 1,167 | 100.1 | 50.0 | 23 |
| HTTP | 0 | 0.1 | 50.3 | 0 |
| Socket | 10,040 | 35.6 | 50.4 | 559 |

---

## Reliability Analysis

| Method | Operation | Success Rate | Errors |
|--------|-----------|--------------|--------|
| latzero | set | 100.00% | 0 |
| latzero | get | 100.00% | 0 |
| latzero | mixed | 100.00% | 0 |
| HTTP | set | 0.00% | 10000 |
| HTTP | get | 0.00% | 10000 |
| HTTP | mixed | 0.00% | 10000 |
| Socket | set | 100.00% | 0 |
| Socket | get | 0.00% | 10000 |
| Socket | mixed | 0.00% | 10000 |

✅ **100% reliability achieved by**: latzero

---

## Comparison Charts

### Throughput Bar Chart

```
Operations per Second (higher is better)
============================================================
latzero      [█░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░] 389
HTTP         [░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░] 0
Socket       [█████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░] 3,347
```

### Latency Comparison

```
Average Latency in ms (lower is better)
============================================================
latzero      [███████████████████████░░░░░░░░░░░░░░░░░] 3.123ms
HTTP         [░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░] 0.000ms
Socket       [░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░] 0.032ms
```

---

## Conclusions

### latzero Performance Summary

- **Average Throughput**: 389 operations/second
- **Average Latency**: 3.123 ms

**vs Socket:**
- 0.1x faster throughput
- 0.0x lower latency

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
  "generated_at": "2026-01-08T16:12:25.583885",
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
    "timestamp": "2026-01-08T16:10:48.186772"
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
    "ram_available_gb": 5.51
  },
  "results": {
    "latzero": [
      {
        "name": "latzero",
        "operation": "set",
        "total_operations": 10000,
        "successful_operations": 10000,
        "failed_operations": 0,
        "total_time_seconds": 52.8215875000169,
        "throughput_ops_per_sec": 189.31653653909586,
        "success_rate_percent": 100.0,
        "latency_ms": {
          "min": 0.42320002103224397,
          "max": 52.78800000087358,
          "avg": 5.273902440248639,
          "p50": 4.934900003718212,
          "p95": 7.822999992640689,
          "p99": 10.46600000699982,
          "stdev": 2.1932347466538613
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
        "total_time_seconds": 21.785484499996528,
        "throughput_ops_per_sec": 459.0212349879845,
        "success_rate_percent": 100.0,
        "latency_ms": {
          "min": 0.4563000111375004,
          "max": 30.51500002038665,
          "avg": 2.1731049200840062,
          "p50": 1.6638000088278204,
          "p95": 4.39590000314638,
          "p99": 9.350999986054376,
          "stdev": 1.896270690122663
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
        "total_time_seconds": 19.270898800023133,
        "throughput_ops_per_sec": 518.9171560585434,
        "success_rate_percent": 100.0,
        "latency_ms": {
          "min": 0.03619998460635543,
          "max": 29.38289998564869,
          "avg": 1.920997090174933,
          "p50": 1.7370000132359564,
          "p95": 3.552000009221956,
          "p99": 4.960299993399531,
          "stdev": 1.8367199126023233
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
        "successful_operations": 0,
        "failed_operations": 10000,
        "total_time_seconds": 0.014976263046264648,
        "throughput_ops_per_sec": 0.0,
        "success_rate_percent": 0.0,
        "latency_ms": {
          "min": 0,
          "max": 0,
          "avg": 0,
          "p50": 0,
          "p95": 0,
          "p99": 0
        },
        "error_count": 1,
        "sample_errors": [
          "cannot pickle 'module' object"
        ]
      },
      {
        "name": "HTTP",
        "operation": "get",
        "total_operations": 10000,
        "successful_operations": 0,
        "failed_operations": 10000,
        "total_time_seconds": 0.010441303253173828,
        "throughput_ops_per_sec": 0.0,
        "success_rate_percent": 0.0,
        "latency_ms": {
          "min": 0,
          "max": 0,
          "avg": 0,
          "p50": 0,
          "p95": 0,
          "p99": 0
        },
        "error_count": 1,
        "sample_errors": [
          "cannot pickle 'module' object"
        ]
      },
      {
        "name": "HTTP",
        "operation": "mixed",
        "total_operations": 10000,
        "successful_operations": 0,
        "failed_operations": 10000,
        "total_time_seconds": 0.011321306228637695,
        "throughput_ops_per_sec": 0.0,
        "success_rate_percent": 0.0,
        "latency_ms": {
          "min": 0,
          "max": 0,
          "avg": 0,
          "p50": 0,
          "p95": 0,
          "p99": 0
        },
        "error_count": 1,
        "sample_errors": [
          "cannot pickle 'module' object"
        ]
      }
    ],
    "Socket": [
      {
        "name": "Socket",
        "operation": "set",
        "total_operations": 10000,
        "successful_operations": 10000,
        "failed_operations": 0,
        "total_time_seconds": 0.9959987000038382,
        "throughput_ops_per_sec": 10040.173747176039,
        "success_rate_percent": 100.0,
        "latency_ms": {
          "min": 0.06160000339150429,
          "max": 2.5104999949689955,
          "avg": 0.09711330004502088,
          "p50": 0.08009999874047935,
          "p95": 0.1832999987527728,
          "p99": 0.32160000409930944,
          "stdev": 0.05503105369709212
        },
        "error_count": 0,
        "sample_errors": []
      },
      {
        "name": "Socket",
        "operation": "get",
        "total_operations": 10000,
        "successful_operations": 0,
        "failed_operations": 10000,
        "total_time_seconds": 0.00996088981628418,
        "throughput_ops_per_sec": 0.0,
        "success_rate_percent": 0.0,
        "latency_ms": {
          "min": 0,
          "max": 0,
          "avg": 0,
          "p50": 0,
          "p95": 0,
          "p99": 0
        },
        "error_count": 1,
        "sample_errors": [
          "[WinError 10038] An operation was attempted on something that is not a socket"
        ]
      },
      {
        "name": "Socket",
        "operation": "mixed",
        "total_operations": 10000,
        "successful_operations": 0,
        "failed_operations": 10000,
        "total_time_seconds": 0.00838923454284668,
        "throughput_ops_per_sec": 0.0,
        "success_rate_percent": 0.0,
        "latency_ms": {
          "min": 0,
          "max": 0,
          "avg": 0,
          "p50": 0,
          "p95": 0,
          "p99": 0
        },
        "error_count": 1,
        "sample_errors": [
          "[WinError 10038] An operation was attempted on something that is not a socket"
        ]
      }
    ]
  },
  "resource_stats": {
    "latzero": {
      "sample_count": 1814,
      "duration_seconds": 19.26,
      "cpu": {
        "avg_percent": 100.07,
        "min_percent": 0.0,
        "max_percent": 169.8
      },
      "memory": {
        "avg_mb": 50.01,
        "min_mb": 42.73,
        "max_mb": 50.8,
        "avg_percent": 0.21
      }
    },
    "HTTP": {
      "sample_count": 3,
      "duration_seconds": 0.0,
      "cpu": {
        "avg_percent": 0.0,
        "min_percent": 0.0,
        "max_percent": 0.0
      },
      "memory": {
        "avg_mb": 50.27,
        "min_mb": 50.21,
        "max_mb": 50.3,
        "avg_percent": 0.21
      }
    },
    "Socket": {
      "sample_count": 33,
      "duration_seconds": 0.0,
      "cpu": {
        "avg_percent": 35.64,
        "min_percent": 0.0,
        "max_percent": 99.7
      },
      "memory": {
        "avg_mb": 50.37,
        "min_mb": 50.3,
        "max_mb": 50.49,
        "avg_percent": 0.21
      }
    }
  }
}
```

</details>

---

*Report generated by latzero evaluation suite*