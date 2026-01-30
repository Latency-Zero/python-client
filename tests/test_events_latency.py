"""
latzero Events Latency & Throughput Benchmark

Tests:
1. Single-process round-trip latency
2. Ops/second throughput
3. emit (fire-and-forget) throughput
4. call (RPC) throughput with response

Run with: python tests/test_events_latency.py
"""

import time
import statistics
import threading
import multiprocessing
from latzero import SharedMemoryPool

# ============== Configuration ==============

POOL_NAME = "benchmark_pool"
WARMUP_ITERATIONS = 100
LATENCY_ITERATIONS = 10000
THROUGHPUT_ITERATIONS = 50000


def print_header(title: str):
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def format_latency(ns: float) -> str:
    """Format latency in human-readable units."""
    if ns < 1000:
        return f"{ns:.1f} ns"
    elif ns < 1_000_000:
        return f"{ns/1000:.2f} μs"
    else:
        return f"{ns/1_000_000:.2f} ms"


def format_rate(ops_per_sec: float) -> str:
    """Format rate in human-readable units."""
    if ops_per_sec >= 1_000_000:
        return f"{ops_per_sec/1_000_000:.2f}M ops/sec"
    elif ops_per_sec >= 1_000:
        return f"{ops_per_sec/1_000:.2f}K ops/sec"
    else:
        return f"{ops_per_sec:.1f} ops/sec"


# ============== Pool Manager ==============

# Global pool manager - reuse across tests to avoid resource leaks
_pool_manager = None

def get_pool_manager():
    """Get shared pool manager instance."""
    global _pool_manager
    if _pool_manager is None:
        _pool_manager = SharedMemoryPool()
    return _pool_manager


# ============== Single Process Tests ==============

def test_emit_latency():
    """Test fire-and-forget emit latency (no response)."""
    print_header("EMIT Latency Test (Fire-and-Forget)")
    
    pm = get_pool_manager()
    pm.create(POOL_NAME)
    
    try:
        with pm.connect(POOL_NAME) as ipc:
            received_count = [0]
            
            @ipc.on_event("bench:emit")
            def handle_emit(value: int):
                received_count[0] += 1
            
            ipc.listen()
            time.sleep(0.1)  # Let listener start
            
            # Warmup
            print(f"  Warming up ({WARMUP_ITERATIONS} iterations)...")
            for i in range(WARMUP_ITERATIONS):
                ipc.emit_event("bench:emit", value=i)
            time.sleep(0.2)  # Let events process
            
            # Benchmark
            print(f"  Running latency test ({LATENCY_ITERATIONS} iterations)...")
            latencies = []
            
            for i in range(LATENCY_ITERATIONS):
                start = time.perf_counter_ns()
                ipc.emit_event("bench:emit", value=i)
                end = time.perf_counter_ns()
                latencies.append(end - start)
            
            # Wait for processing
            time.sleep(0.5)
            
            # Results
            latencies.sort()
            print(f"\n  Results (emit dispatch time, not including handler):")
            print(f"    Min:     {format_latency(min(latencies))}")
            print(f"    Median:  {format_latency(latencies[len(latencies)//2])}")
            print(f"    Mean:    {format_latency(statistics.mean(latencies))}")
            print(f"    P95:     {format_latency(latencies[int(len(latencies)*0.95)])}")
            print(f"    P99:     {format_latency(latencies[int(len(latencies)*0.99)])}")
            print(f"    Max:     {format_latency(max(latencies))}")
            print(f"    Received: {received_count[0]} events")
            
            ipc.stop_events()
    finally:
        pm.destroy(POOL_NAME)


def test_call_latency():
    """Test RPC call round-trip latency."""
    print_header("CALL Latency Test (RPC Round-trip)")
    
    pm = get_pool_manager()
    pm.create(POOL_NAME)
    
    try:
        with pm.connect(POOL_NAME) as ipc:
            
            @ipc.on_event("bench:call")
            def handle_call(x: int, y: int) -> int:
                return x + y
            
            ipc.listen()
            time.sleep(0.1)  # Let listener start
            
            # Warmup
            print(f"  Warming up ({WARMUP_ITERATIONS} iterations)...")
            for i in range(WARMUP_ITERATIONS):
                try:
                    ipc.call_event("bench:call", x=i, y=1, _timeout=1.0)
                except:
                    pass
            
            # Benchmark
            iterations = min(LATENCY_ITERATIONS, 1000)  # RPC is slower, use fewer iterations
            print(f"  Running latency test ({iterations} iterations)...")
            latencies = []
            errors = 0
            
            for i in range(iterations):
                start = time.perf_counter_ns()
                try:
                    result = ipc.call_event("bench:call", x=i, y=1, _timeout=2.0)
                    end = time.perf_counter_ns()
                    latencies.append(end - start)
                except Exception as e:
                    errors += 1
            
            if latencies:
                latencies.sort()
                print(f"\n  Results (full round-trip including handler execution):")
                print(f"    Min:     {format_latency(min(latencies))}")
                print(f"    Median:  {format_latency(latencies[len(latencies)//2])}")
                print(f"    Mean:    {format_latency(statistics.mean(latencies))}")
                print(f"    P95:     {format_latency(latencies[int(len(latencies)*0.95)])}")
                print(f"    P99:     {format_latency(latencies[int(len(latencies)*0.99)])}")
                print(f"    Max:     {format_latency(max(latencies))}")
                print(f"    Successful: {len(latencies)}, Errors: {errors}")
            else:
                print(f"  No successful calls. Errors: {errors}")
            
            ipc.stop_events()
    finally:
        pm.destroy(POOL_NAME)


def test_emit_throughput():
    """Test emit throughput (ops/second)."""
    print_header("EMIT Throughput Test")
    
    pm = get_pool_manager()
    pm.create(POOL_NAME)
    
    try:
        with pm.connect(POOL_NAME) as ipc:
            received_count = [0]
            
            @ipc.on_event("bench:throughput")
            def handle_throughput(value: int):
                received_count[0] += 1
            
            ipc.listen()
            time.sleep(0.1)
            
            print(f"  Running throughput test ({THROUGHPUT_ITERATIONS:,} emits)...")
            
            start = time.perf_counter()
            for i in range(THROUGHPUT_ITERATIONS):
                ipc.emit_event("bench:throughput", value=i)
            elapsed = time.perf_counter() - start
            
            emit_rate = THROUGHPUT_ITERATIONS / elapsed
            print(f"\n  Results (emit dispatch rate):")
            print(f"    Total emits:   {THROUGHPUT_ITERATIONS:,}")
            print(f"    Time elapsed:  {elapsed:.3f}s")
            print(f"    Emit rate:     {format_rate(emit_rate)}")
            
            # Wait and check receive rate
            time.sleep(1.0)
            print(f"    Received:      {received_count[0]:,} events")
            
            ipc.stop_events()
    finally:
        pm.destroy(POOL_NAME)


def test_baseline_set_get():
    """Test baseline set/get performance for comparison."""
    print_header("BASELINE: set/get Performance")
    
    pm = get_pool_manager()
    pm.create(POOL_NAME)
    
    try:
        with pm.connect(POOL_NAME) as ipc:
            iterations = THROUGHPUT_ITERATIONS
            
            # SET throughput
            print(f"  Testing SET throughput ({iterations:,} operations)...")
            start = time.perf_counter()
            for i in range(iterations):
                ipc.set(f"key_{i % 1000}", {"value": i, "data": "test"})
            elapsed = time.perf_counter() - start
            set_rate = iterations / elapsed
            print(f"    SET rate: {format_rate(set_rate)}")
            
            # GET throughput
            print(f"  Testing GET throughput ({iterations:,} operations)...")
            start = time.perf_counter()
            for i in range(iterations):
                ipc.get(f"key_{i % 1000}")
            elapsed = time.perf_counter() - start
            get_rate = iterations / elapsed
            print(f"    GET rate: {format_rate(get_rate)}")
            
    finally:
        pm.destroy(POOL_NAME)


# ============== Main ==============


def main():
    print("\n" + "=" * 60)
    print("       latzero Events System Benchmark")
    print("=" * 60)
    print(f"\n  Configuration:")
    print(f"    Warmup iterations:     {WARMUP_ITERATIONS:,}")
    print(f"    Latency iterations:    {LATENCY_ITERATIONS:,}")
    print(f"    Throughput iterations: {THROUGHPUT_ITERATIONS:,}")
    
    try:
        # Run baseline first
        test_baseline_set_get()
        
        # Run emit tests
        test_emit_latency()
        test_emit_throughput()
        
        # Run call tests
        test_call_latency()
        
        print("\n" + "=" * 60)
        print("  Benchmark Complete!")
        print("=" * 60 + "\n")
    finally:
        # Cleanup pool manager to prevent resource leak warnings
        global _pool_manager
        if _pool_manager is not None:
            _pool_manager.close(force=True)
            _pool_manager = None


if __name__ == "__main__":
    main()
