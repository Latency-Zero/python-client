"""
Report generation for evaluation results.

Creates a comprehensive Markdown report with:
- Executive summary
- Detailed benchmark results
- Comparison tables
- Resource usage analysis
- Recommendations
"""

import json
from datetime import datetime
from typing import List, Dict, Any
from pathlib import Path

from .benchmarks import BenchmarkResult
from .monitor import ResourceStats, get_system_info


def generate_report(
    results: Dict[str, List[BenchmarkResult]],
    resource_stats: Dict[str, ResourceStats],
    output_path: str = "evaluation/REPORT.md",
    config: dict = None
) -> str:
    """
    Generate a comprehensive evaluation report.
    
    Args:
        results: Dict of {method_name: [BenchmarkResult, ...]}
        resource_stats: Dict of {method_name: ResourceStats}
        output_path: Path to save the report
        config: Benchmark configuration used
    
    Returns:
        Path to generated report
    """
    config = config or {}
    report_lines = []
    
    def add(line: str = ""):
        report_lines.append(line)
    
    # === Header ===
    add("# latzero Evaluation Report")
    add()
    add(f"> Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    add()
    add("---")
    add()
    
    # === Table of Contents ===
    add("## Table of Contents")
    add()
    add("1. [Executive Summary](#executive-summary)")
    add("2. [System Information](#system-information)")
    add("3. [Benchmark Configuration](#benchmark-configuration)")
    add("4. [Results Overview](#results-overview)")
    add("5. [Detailed Results](#detailed-results)")
    add("6. [Latency Analysis](#latency-analysis)")
    add("7. [Resource Usage](#resource-usage)")
    add("8. [Reliability Analysis](#reliability-analysis)")
    add("9. [Comparison Charts](#comparison-charts)")
    add("10. [Conclusions](#conclusions)")
    add("11. [Raw Data](#raw-data)")
    add()
    add("---")
    add()
    
    # === Executive Summary ===
    add("## Executive Summary")
    add()
    
    # Find the best performer for key metrics
    all_results = []
    for method, method_results in results.items():
        for r in method_results:
            all_results.append((method, r))
    
    if all_results:
        # Best throughput
        best_throughput = max(all_results, key=lambda x: x[1].throughput)
        # Best latency (lowest avg)
        best_latency = min(all_results, key=lambda x: x[1].latency_stats['avg'] if x[1].latency_stats['avg'] > 0 else float('inf'))
        # Best reliability
        best_reliability = max(all_results, key=lambda x: x[1].success_rate)
        
        add("### Key Findings")
        add()
        add(f"| Metric | Winner | Value |")
        add(f"|--------|--------|-------|")
        add(f"| **Highest Throughput** | {best_throughput[0]} | {best_throughput[1].throughput:,.0f} ops/sec |")
        add(f"| **Lowest Latency** | {best_latency[0]} | {best_latency[1].latency_stats['avg']:.3f} ms avg |")
        add(f"| **Best Reliability** | {best_reliability[0]} | {best_reliability[1].success_rate:.2f}% success |")
        add()
        
        # Speed comparison
        if 'latzero' in results and len(results) > 1:
            latzero_throughput = max(r.throughput for r in results.get('latzero', [{'throughput': 0}]))
            comparisons = []
            for method, method_results in results.items():
                if method != 'latzero' and method_results:
                    other_throughput = max(r.throughput for r in method_results)
                    if other_throughput > 0:
                        speedup = latzero_throughput / other_throughput
                        comparisons.append(f"**{speedup:.1f}x faster** than {method}")
            
            if comparisons:
                add("### Speed Advantage")
                add()
                add(f"latzero is: {', '.join(comparisons)}")
                add()
    
    add("---")
    add()
    
    # === System Information ===
    add("## System Information")
    add()
    sys_info = get_system_info()
    add("| Property | Value |")
    add("|----------|-------|")
    for key, value in sys_info.items():
        add(f"| {key.replace('_', ' ').title()} | {value} |")
    add()
    add("---")
    add()
    
    # === Benchmark Configuration ===
    add("## Benchmark Configuration")
    add()
    add("```json")
    add(json.dumps(config, indent=2))
    add("```")
    add()
    add("---")
    add()
    
    # === Results Overview ===
    add("## Results Overview")
    add()
    add("### Throughput Comparison (ops/sec)")
    add()
    add("| Method | SET | GET | Mixed |")
    add("|--------|-----|-----|-------|")
    
    for method, method_results in results.items():
        set_tp = next((r.throughput for r in method_results if r.operation == 'set'), 0)
        get_tp = next((r.throughput for r in method_results if r.operation == 'get'), 0)
        mixed_tp = next((r.throughput for r in method_results if r.operation == 'mixed'), 0)
        add(f"| {method} | {set_tp:,.0f} | {get_tp:,.0f} | {mixed_tp:,.0f} |")
    add()
    
    add("### Latency Comparison (ms)")
    add()
    add("| Method | Operation | Avg | P50 | P95 | P99 | Max |")
    add("|--------|-----------|-----|-----|-----|-----|-----|")
    
    for method, method_results in results.items():
        for r in method_results:
            lat = r.latency_stats
            add(f"| {method} | {r.operation} | {lat['avg']:.3f} | {lat['p50']:.3f} | {lat['p95']:.3f} | {lat['p99']:.3f} | {lat['max']:.3f} |")
    add()
    add("---")
    add()
    
    # === Detailed Results ===
    add("## Detailed Results")
    add()
    
    for method, method_results in results.items():
        add(f"### {method}")
        add()
        
        for r in method_results:
            add(f"#### {r.operation.upper()} Operations")
            add()
            add(f"- **Total Operations**: {r.total_operations:,}")
            add(f"- **Successful**: {r.successful_operations:,}")
            add(f"- **Failed**: {r.failed_operations:,}")
            add(f"- **Success Rate**: {r.success_rate:.2f}%")
            add(f"- **Total Time**: {r.total_time_seconds:.2f}s")
            add(f"- **Throughput**: {r.throughput:,.0f} ops/sec")
            add()
            
            lat = r.latency_stats
            add("**Latency Distribution:**")
            add()
            add(f"| Metric | Value (ms) |")
            add(f"|--------|------------|")
            add(f"| Min | {lat['min']:.4f} |")
            add(f"| Avg | {lat['avg']:.4f} |")
            add(f"| P50 (Median) | {lat['p50']:.4f} |")
            add(f"| P95 | {lat['p95']:.4f} |")
            add(f"| P99 | {lat['p99']:.4f} |")
            add(f"| Max | {lat['max']:.4f} |")
            add(f"| Std Dev | {lat.get('stdev', 0):.4f} |")
            add()
            
            if r.errors:
                add(f"**Sample Errors ({len(r.errors)} total):**")
                add("```")
                for err in r.errors[:5]:
                    add(f"  - {err}")
                add("```")
                add()
        
        add("---")
        add()
    
    # === Latency Analysis ===
    add("## Latency Analysis")
    add()
    add("### Latency Distribution Visualization")
    add()
    add("```")
    add("Latency Percentiles (lower is better)")
    add("=" * 60)
    
    for method, method_results in results.items():
        for r in method_results:
            lat = r.latency_stats
            add(f"\n{method} - {r.operation}:")
            add(f"  Min  [{'█' * 1}] {lat['min']:.3f}ms")
            add(f"  P50  [{'█' * min(20, int(lat['p50'] * 10))}] {lat['p50']:.3f}ms")
            add(f"  P95  [{'█' * min(40, int(lat['p95'] * 10))}] {lat['p95']:.3f}ms")
            add(f"  P99  [{'█' * min(50, int(lat['p99'] * 10))}] {lat['p99']:.3f}ms")
            add(f"  Max  [{'█' * min(60, int(lat['max'] * 5))}] {lat['max']:.3f}ms")
    
    add("```")
    add()
    add("---")
    add()
    
    # === Resource Usage ===
    add("## Resource Usage")
    add()
    
    if resource_stats:
        add("### CPU and Memory by Method")
        add()
        add("| Method | CPU Avg (%) | CPU Max (%) | RAM Avg (MB) | RAM Max (MB) |")
        add("|--------|-------------|-------------|--------------|--------------|")
        
        for method, stats in resource_stats.items():
            data = stats.to_dict()
            cpu = data['cpu']
            mem = data['memory']
            add(f"| {method} | {cpu['avg_percent']:.1f} | {cpu['max_percent']:.1f} | {mem['avg_mb']:.1f} | {mem['max_mb']:.1f} |")
        add()
        
        # Efficiency calculation
        add("### Efficiency Score")
        add()
        add("*Efficiency = Throughput / (CPU% × RAM_MB)*")
        add()
        add("| Method | Throughput | CPU% | RAM (MB) | Efficiency |")
        add("|--------|------------|------|----------|------------|")
        
        for method, method_results in results.items():
            if method in resource_stats:
                stats = resource_stats[method].to_dict()
                total_throughput = sum(r.throughput for r in method_results)
                cpu = max(stats['cpu']['avg_percent'], 0.1)
                ram = max(stats['memory']['avg_mb'], 0.1)
                efficiency = total_throughput / (cpu * ram) * 100
                add(f"| {method} | {total_throughput:,.0f} | {cpu:.1f} | {ram:.1f} | {efficiency:,.0f} |")
        add()
    else:
        add("*Resource monitoring data not available*")
        add()
    
    add("---")
    add()
    
    # === Reliability Analysis ===
    add("## Reliability Analysis")
    add()
    add("| Method | Operation | Success Rate | Errors |")
    add("|--------|-----------|--------------|--------|")
    
    for method, method_results in results.items():
        for r in method_results:
            add(f"| {method} | {r.operation} | {r.success_rate:.2f}% | {r.failed_operations} |")
    add()
    
    # Reliability summary
    perfect = [m for m, rs in results.items() if all(r.success_rate == 100 for r in rs)]
    if perfect:
        add(f"✅ **100% reliability achieved by**: {', '.join(perfect)}")
    add()
    add("---")
    add()
    
    # === Comparison Charts ===
    add("## Comparison Charts")
    add()
    add("### Throughput Bar Chart")
    add()
    add("```")
    add("Operations per Second (higher is better)")
    add("=" * 60)
    
    max_tp = max(r.throughput for _, rs in results.items() for r in rs) if all_results else 1
    for method, method_results in results.items():
        avg_tp = sum(r.throughput for r in method_results) / len(method_results) if method_results else 0
        bar_len = int((avg_tp / max_tp) * 40)
        add(f"{method:12} [{'█' * bar_len}{'░' * (40-bar_len)}] {avg_tp:,.0f}")
    
    add("```")
    add()
    
    add("### Latency Comparison")
    add()
    add("```")
    add("Average Latency in ms (lower is better)")
    add("=" * 60)
    
    all_lats = [r.latency_stats['avg'] for _, rs in results.items() for r in rs if r.latency_stats['avg'] > 0]
    max_lat = max(all_lats) if all_lats else 1
    
    for method, method_results in results.items():
        avg_lat = sum(r.latency_stats['avg'] for r in method_results) / len(method_results) if method_results else 0
        bar_len = int((avg_lat / max_lat) * 40) if max_lat > 0 else 0
        add(f"{method:12} [{'█' * bar_len}{'░' * (40-bar_len)}] {avg_lat:.3f}ms")
    
    add("```")
    add()
    add("---")
    add()
    
    # === Conclusions ===
    add("## Conclusions")
    add()
    
    if 'latzero' in results:
        latzero_results = results['latzero']
        latzero_avg_tp = sum(r.throughput for r in latzero_results) / len(latzero_results)
        latzero_avg_lat = sum(r.latency_stats['avg'] for r in latzero_results) / len(latzero_results)
        
        add("### latzero Performance Summary")
        add()
        add(f"- **Average Throughput**: {latzero_avg_tp:,.0f} operations/second")
        add(f"- **Average Latency**: {latzero_avg_lat:.3f} ms")
        add()
        
        # Comparisons
        for method, method_results in results.items():
            if method != 'latzero' and method_results:
                other_avg_tp = sum(r.throughput for r in method_results) / len(method_results)
                other_avg_lat = sum(r.latency_stats['avg'] for r in method_results) / len(method_results)
                
                if other_avg_tp > 0:
                    tp_ratio = latzero_avg_tp / other_avg_tp
                    lat_ratio = other_avg_lat / latzero_avg_lat if latzero_avg_lat > 0 else 0
                    
                    add(f"**vs {method}:**")
                    add(f"- {tp_ratio:.1f}x faster throughput")
                    add(f"- {lat_ratio:.1f}x lower latency")
                    add()
    
    add("### Recommendations")
    add()
    add("1. **For maximum speed**: Use latzero for inter-process communication")
    add("2. **For cross-machine**: Use HTTP or Socket (latzero is same-machine only)")
    add("3. **For persistence**: Enable latzero snapshots for data durability")
    add()
    add("---")
    add()
    
    # === Raw Data ===
    add("## Raw Data")
    add()
    add("<details>")
    add("<summary>Click to expand JSON data</summary>")
    add()
    add("```json")
    
    raw_data = {
        'generated_at': datetime.now().isoformat(),
        'config': config,
        'system_info': sys_info,
        'results': {
            method: [r.to_dict() for r in rs]
            for method, rs in results.items()
        },
        'resource_stats': {
            method: stats.to_dict()
            for method, stats in resource_stats.items()
        }
    }
    add(json.dumps(raw_data, indent=2))
    add("```")
    add()
    add("</details>")
    add()
    add("---")
    add()
    add("*Report generated by latzero evaluation suite*")
    
    # Write report
    report_content = "\n".join(report_lines)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report_content, encoding='utf-8')
    
    # Also save raw JSON
    json_path = output_path.with_suffix('.json')
    json_path.write_text(json.dumps(raw_data, indent=2), encoding='utf-8')
    
    return str(output_path)
