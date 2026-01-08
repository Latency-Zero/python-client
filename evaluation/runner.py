"""
Main evaluation runner.

Orchestrates all benchmarks, monitors resources, and generates reports.
"""

import sys
import time
import argparse
from typing import Dict, List, Optional
from datetime import datetime

from .benchmarks import (
    BaseBenchmark,
    BenchmarkResult,
    LatzeroBenchmark,
    HTTPBenchmark,
    SocketBenchmark,
)
from .monitor import ResourceMonitor, ResourceStats, get_system_info
from .report import generate_report


# Default configuration
DEFAULT_CONFIG = {
    'operations': {
        'small': 10000,      # Quick test
        'medium': 50000,     # Standard test
        'large': 100000,     # Stress test
        'massive': 500000,   # Ultimate stress test
    },
    'payload_sizes': [100, 1000, 10000],  # bytes
    'threads': [1, 4, 8],
    'operations_types': ['set', 'get', 'mixed'],
    'methods': ['latzero', 'HTTP', 'Socket'],
}


def run_single_benchmark(
    benchmark: BaseBenchmark,
    num_operations: int,
    operation: str,
    payload_size: int,
    threads: int,
    monitor: Optional[ResourceMonitor] = None
) -> tuple:
    """Run a single benchmark with optional resource monitoring."""
    
    print(f"    {operation.upper()}: {num_operations:,} ops, {payload_size}B payload, {threads} threads...", end=" ", flush=True)
    
    # Start monitoring
    if monitor:
        monitor.start()
    
    start = time.time()
    
    try:
        result = benchmark.run_benchmark(
            num_operations=num_operations,
            operation=operation,
            payload_size=payload_size,
            num_threads=threads
        )
        
        elapsed = time.time() - start
        print(f"✓ {result.throughput:,.0f} ops/sec ({elapsed:.2f}s)")
        
    except Exception as e:
        elapsed = time.time() - start
        print(f"✗ Error: {e}")
        result = BenchmarkResult(
            name=benchmark.name,
            operation=operation,
            total_operations=num_operations,
            successful_operations=0,
            failed_operations=num_operations,
            total_time_seconds=elapsed,
            errors=[str(e)]
        )
    
    # Stop monitoring
    resource_stats = None
    if monitor:
        resource_stats = monitor.stop()
    
    return result, resource_stats


def run_evaluation(
    num_operations: int = 50000,
    payload_size: int = 100,
    threads: int = 1,
    methods: Optional[List[str]] = None,
    operations: Optional[List[str]] = None,
    output_path: str = "evaluation/REPORT.md",
    skip_http: bool = False,
    skip_socket: bool = False,
    verbose: bool = True
) -> str:
    """
    Run the full evaluation suite.
    
    Args:
        num_operations: Number of operations per test
        payload_size: Size of test payload in bytes
        threads: Number of concurrent threads
        methods: List of methods to test ('latzero', 'HTTP', 'Socket')
        operations: List of operations to test ('set', 'get', 'mixed')
        output_path: Path for the report
        skip_http: Skip HTTP benchmark (requires Flask)
        skip_socket: Skip Socket benchmark
        verbose: Print progress
    
    Returns:
        Path to generated report
    """
    if methods is None:
        methods = ['latzero']
        if not skip_http:
            methods.append('HTTP')
        if not skip_socket:
            methods.append('Socket')
    
    if operations is None:
        operations = ['set', 'get', 'mixed']
    
    config = {
        'num_operations': num_operations,
        'payload_size': payload_size,
        'threads': threads,
        'methods': methods,
        'operations': operations,
        'timestamp': datetime.now().isoformat(),
    }
    
    if verbose:
        print("=" * 60)
        print("latzero Evaluation Suite")
        print("=" * 60)
        print()
        print(f"Configuration:")
        print(f"  - Operations: {num_operations:,}")
        print(f"  - Payload: {payload_size} bytes")
        print(f"  - Threads: {threads}")
        print(f"  - Methods: {', '.join(methods)}")
        print(f"  - Operations: {', '.join(operations)}")
        print()
        print("System Info:")
        sys_info = get_system_info()
        print(f"  - Platform: {sys_info.get('platform', 'Unknown')}")
        print(f"  - CPUs: {sys_info.get('cpu_count_logical', 'Unknown')}")
        print(f"  - RAM: {sys_info.get('ram_total_gb', 'Unknown')} GB")
        print()
    
    # Initialize benchmarks
    benchmarks: Dict[str, BaseBenchmark] = {}
    
    if 'latzero' in methods:
        benchmarks['latzero'] = LatzeroBenchmark()
    
    if 'HTTP' in methods:
        try:
            import flask
            import requests
            benchmarks['HTTP'] = HTTPBenchmark()
        except ImportError:
            if verbose:
                print("⚠ Flask/requests not installed, skipping HTTP benchmark")
    
    if 'Socket' in methods:
        benchmarks['Socket'] = SocketBenchmark()
    
    # Run benchmarks
    results: Dict[str, List[BenchmarkResult]] = {name: [] for name in benchmarks}
    resource_stats: Dict[str, ResourceStats] = {}
    
    for method_name, benchmark in benchmarks.items():
        if verbose:
            print(f"\n{'─' * 40}")
            print(f"Benchmarking: {method_name}")
            print(f"{'─' * 40}")
        
        method_resource_samples = []
        
        for operation in operations:
            monitor = ResourceMonitor(interval=0.05)
            
            result, stats = run_single_benchmark(
                benchmark=benchmark,
                num_operations=num_operations,
                operation=operation,
                payload_size=payload_size,
                threads=threads,
                monitor=monitor
            )
            
            results[method_name].append(result)
            
            if stats and stats.samples:
                method_resource_samples.extend(stats.samples)
        
        # Aggregate resource stats for this method
        if method_resource_samples:
            resource_stats[method_name] = ResourceStats(samples=method_resource_samples)
    
    # Generate report
    if verbose:
        print()
        print("=" * 60)
        print("Generating Report...")
        print("=" * 60)
    
    report_path = generate_report(
        results=results,
        resource_stats=resource_stats,
        output_path=output_path,
        config=config
    )
    
    if verbose:
        print(f"\n✓ Report saved to: {report_path}")
        print(f"✓ JSON data saved to: {report_path.replace('.md', '.json')}")
        print()
        
        # Quick summary
        print("Quick Summary:")
        print("-" * 40)
        for method, method_results in results.items():
            avg_tp = sum(r.throughput for r in method_results) / len(method_results) if method_results else 0
            avg_lat = sum(r.latency_stats['avg'] for r in method_results) / len(method_results) if method_results else 0
            print(f"  {method}: {avg_tp:,.0f} ops/sec, {avg_lat:.3f}ms avg latency")
    
    return report_path


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description='latzero Evaluation Suite - Compare IPC performance',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Quick test (10k operations)
  python -m evaluation.runner --quick

  # Standard test (50k operations)
  python -m evaluation.runner

  # Stress test (100k operations)
  python -m evaluation.runner --stress

  # Massive test (500k operations)
  python -m evaluation.runner --massive

  # Custom configuration
  python -m evaluation.runner -n 100000 -p 1000 -t 4

  # Only test latzero
  python -m evaluation.runner --latzero-only
        """
    )
    
    parser.add_argument(
        '-n', '--num-operations',
        type=int,
        default=50000,
        help='Number of operations per test (default: 50000)'
    )
    parser.add_argument(
        '-p', '--payload-size',
        type=int,
        default=100,
        help='Payload size in bytes (default: 100)'
    )
    parser.add_argument(
        '-t', '--threads',
        type=int,
        default=1,
        help='Number of threads (default: 1)'
    )
    parser.add_argument(
        '-o', '--output',
        default='evaluation/REPORT.md',
        help='Output report path (default: evaluation/REPORT.md)'
    )
    parser.add_argument(
        '--quick',
        action='store_true',
        help='Quick test (10k operations)'
    )
    parser.add_argument(
        '--stress',
        action='store_true',
        help='Stress test (100k operations)'
    )
    parser.add_argument(
        '--massive',
        action='store_true',
        help='Massive test (500k operations)'
    )
    parser.add_argument(
        '--latzero-only',
        action='store_true',
        help='Only benchmark latzero'
    )
    parser.add_argument(
        '--skip-http',
        action='store_true',
        help='Skip HTTP benchmark'
    )
    parser.add_argument(
        '--skip-socket',
        action='store_true',
        help='Skip Socket benchmark'
    )
    parser.add_argument(
        '-q', '--quiet',
        action='store_true',
        help='Minimal output'
    )
    
    args = parser.parse_args()
    
    # Adjust operations based on flags
    num_ops = args.num_operations
    if args.quick:
        num_ops = 10000
    elif args.stress:
        num_ops = 100000
    elif args.massive:
        num_ops = 500000
    
    # Determine methods
    methods = None
    if args.latzero_only:
        methods = ['latzero']
    
    try:
        run_evaluation(
            num_operations=num_ops,
            payload_size=args.payload_size,
            threads=args.threads,
            methods=methods,
            output_path=args.output,
            skip_http=args.skip_http or args.latzero_only,
            skip_socket=args.skip_socket or args.latzero_only,
            verbose=not args.quiet
        )
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
