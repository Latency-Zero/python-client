"""
Benchmark implementations for latzero, HTTP, and Socket communication.

Windows-compatible version using threading instead of multiprocessing for servers.
"""

import time
import json
import socket
import threading
import statistics
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed


@dataclass
class BenchmarkResult:
    """Results from a single benchmark run."""
    name: str
    operation: str  # 'set', 'get', 'mixed'
    total_operations: int
    successful_operations: int
    failed_operations: int
    total_time_seconds: float
    latencies_ms: List[float] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    
    @property
    def throughput(self) -> float:
        """Operations per second."""
        if self.total_time_seconds == 0:
            return 0
        return self.successful_operations / self.total_time_seconds
    
    @property
    def success_rate(self) -> float:
        """Percentage of successful operations."""
        if self.total_operations == 0:
            return 0
        return (self.successful_operations / self.total_operations) * 100
    
    @property
    def latency_stats(self) -> Dict[str, float]:
        """Calculate latency statistics."""
        if not self.latencies_ms:
            return {'min': 0, 'max': 0, 'avg': 0, 'p50': 0, 'p95': 0, 'p99': 0, 'stdev': 0}
        
        sorted_latencies = sorted(self.latencies_ms)
        n = len(sorted_latencies)
        
        return {
            'min': min(sorted_latencies),
            'max': max(sorted_latencies),
            'avg': statistics.mean(sorted_latencies),
            'p50': sorted_latencies[int(n * 0.50)] if n > 0 else 0,
            'p95': sorted_latencies[int(n * 0.95)] if n > 1 else sorted_latencies[-1],
            'p99': sorted_latencies[int(n * 0.99)] if n > 1 else sorted_latencies[-1],
            'stdev': statistics.stdev(sorted_latencies) if n > 1 else 0,
        }
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            'name': self.name,
            'operation': self.operation,
            'total_operations': self.total_operations,
            'successful_operations': self.successful_operations,
            'failed_operations': self.failed_operations,
            'total_time_seconds': self.total_time_seconds,
            'throughput_ops_per_sec': self.throughput,
            'success_rate_percent': self.success_rate,
            'latency_ms': self.latency_stats,
            'error_count': len(self.errors),
            'sample_errors': self.errors[:5] if self.errors else [],
        }


class BaseBenchmark(ABC):
    """Base class for all benchmarks."""
    
    def __init__(self, name: str):
        self.name = name
    
    @abstractmethod
    def setup(self) -> None:
        """Setup before benchmark runs."""
        pass
    
    @abstractmethod
    def teardown(self) -> None:
        """Cleanup after benchmark runs."""
        pass
    
    @abstractmethod
    def set_operation(self, key: str, value: Any) -> Tuple[bool, Optional[str]]:
        """Perform a set operation. Returns (success, error_message)."""
        pass
    
    @abstractmethod
    def get_operation(self, key: str) -> Tuple[Any, bool, Optional[str]]:
        """Perform a get operation. Returns (value, success, error_message)."""
        pass
    
    def run_benchmark(
        self, 
        num_operations: int, 
        operation: str = 'mixed',
        payload_size: int = 100,
        num_threads: int = 1
    ) -> BenchmarkResult:
        """
        Run the benchmark.
        
        Args:
            num_operations: Total number of operations to perform
            operation: 'set', 'get', or 'mixed' (50/50)
            payload_size: Size of value in bytes
            num_threads: Number of concurrent threads
        """
        self.setup()
        
        latencies = []
        errors = []
        successful = 0
        failed = 0
        
        # Generate test data
        test_value = {"data": "x" * payload_size, "id": 0}
        
        # Pre-populate for get operations
        if operation == 'get':
            for i in range(min(1000, num_operations)):
                key = f"bench_key_{i}"
                self.set_operation(key, {**test_value, "id": i})
        
        def run_single_op(op_id: int) -> Tuple[float, bool, Optional[str]]:
            key = f"bench_key_{op_id % 1000}"  # Reuse keys
            value = {**test_value, "id": op_id}
            
            start = time.perf_counter()
            
            try:
                if operation == 'set':
                    success, error = self.set_operation(key, value)
                elif operation == 'get':
                    _, success, error = self.get_operation(key)
                else:  # mixed
                    if op_id % 2 == 0:
                        success, error = self.set_operation(key, value)
                    else:
                        _, success, error = self.get_operation(key)
                
                elapsed = (time.perf_counter() - start) * 1000  # ms
                return elapsed, success, error
            except Exception as e:
                elapsed = (time.perf_counter() - start) * 1000
                return elapsed, False, str(e)
        
        start_time = time.perf_counter()
        
        if num_threads == 1:
            # Single-threaded
            for i in range(num_operations):
                elapsed, success, error = run_single_op(i)
                latencies.append(elapsed)
                if success:
                    successful += 1
                else:
                    failed += 1
                    if error:
                        errors.append(error)
        else:
            # Multi-threaded
            with ThreadPoolExecutor(max_workers=num_threads) as executor:
                futures = [executor.submit(run_single_op, i) for i in range(num_operations)]
                for future in as_completed(futures):
                    elapsed, success, error = future.result()
                    latencies.append(elapsed)
                    if success:
                        successful += 1
                    else:
                        failed += 1
                        if error:
                            errors.append(error)
        
        total_time = time.perf_counter() - start_time
        
        self.teardown()
        
        return BenchmarkResult(
            name=self.name,
            operation=operation,
            total_operations=num_operations,
            successful_operations=successful,
            failed_operations=failed,
            total_time_seconds=total_time,
            latencies_ms=latencies,
            errors=errors,
        )


class LatzeroBenchmark(BaseBenchmark):
    """Benchmark for latzero shared memory IPC."""
    
    def __init__(self):
        super().__init__("latzero")
        self.pool = None
        self.client = None
        self.pool_name = "eval_benchmark_pool"
    
    def setup(self) -> None:
        from latzero import SharedMemoryPool
        self.pool = SharedMemoryPool(auto_cleanup=False)
        
        # Destroy any existing pool
        try:
            self.pool.destroy(self.pool_name)
        except:
            pass
        
        self.pool.create(self.pool_name)
        self.client = self.pool.connect(self.pool_name)
    
    def teardown(self) -> None:
        if self.client:
            try:
                self.client.disconnect()
            except:
                pass
        if self.pool:
            try:
                self.pool.destroy(self.pool_name)
            except:
                pass
    
    def set_operation(self, key: str, value: Any) -> Tuple[bool, Optional[str]]:
        try:
            self.client.set(key, value)
            return True, None
        except Exception as e:
            return False, str(e)
    
    def get_operation(self, key: str) -> Tuple[Any, bool, Optional[str]]:
        try:
            value = self.client.get(key)
            return value, True, None
        except Exception as e:
            return None, False, str(e)


class HTTPBenchmark(BaseBenchmark):
    """Benchmark for HTTP communication using Flask (threaded server)."""
    
    def __init__(self, host: str = "127.0.0.1", port: int = 5999):
        super().__init__("HTTP")
        self.host = host
        self.port = port
        self.server_thread = None
        self.data_store = {}
        self._shutdown = False
    
    def setup(self) -> None:
        self._shutdown = False
        
        # Start Flask server in thread
        self.server_thread = threading.Thread(target=self._run_server, daemon=True)
        self.server_thread.start()
        
        # Wait for server to start
        import requests
        for _ in range(20):
            try:
                resp = requests.get(f"http://{self.host}:{self.port}/health", timeout=1)
                if resp.status_code == 200:
                    break
            except:
                time.sleep(0.2)
    
    def _run_server(self) -> None:
        """Run Flask server in thread."""
        from flask import Flask, request, jsonify
        import logging
        
        # Suppress Flask logging
        log = logging.getLogger('werkzeug')
        log.setLevel(logging.ERROR)
        
        app = Flask(__name__)
        data_store = {}
        
        @app.route('/health')
        def health():
            return jsonify({"status": "ok"})
        
        @app.route('/set', methods=['POST'])
        def set_value():
            data = request.json
            data_store[data['key']] = data['value']
            return jsonify({"success": True})
        
        @app.route('/get/<key>')
        def get_value(key):
            value = data_store.get(key)
            return jsonify({"value": value, "found": value is not None})
        
        # Use werkzeug directly to avoid Flask dev server warnings
        from werkzeug.serving import make_server
        server = make_server(self.host, self.port, app, threaded=True)
        server.timeout = 1
        
        while not self._shutdown:
            server.handle_request()
    
    def teardown(self) -> None:
        self._shutdown = True
        # Send a dummy request to unblock the server
        try:
            import requests
            requests.get(f"http://{self.host}:{self.port}/health", timeout=0.5)
        except:
            pass
        if self.server_thread:
            self.server_thread.join(timeout=2)
    
    def set_operation(self, key: str, value: Any) -> Tuple[bool, Optional[str]]:
        try:
            import requests
            resp = requests.post(
                f"http://{self.host}:{self.port}/set",
                json={"key": key, "value": value},
                timeout=5
            )
            return resp.status_code == 200, None
        except Exception as e:
            return False, str(e)
    
    def get_operation(self, key: str) -> Tuple[Any, bool, Optional[str]]:
        try:
            import requests
            resp = requests.get(
                f"http://{self.host}:{self.port}/get/{key}",
                timeout=5
            )
            if resp.status_code == 200:
                data = resp.json()
                return data.get('value'), True, None
            return None, False, f"HTTP {resp.status_code}"
        except Exception as e:
            return None, False, str(e)


class SocketBenchmark(BaseBenchmark):
    """Benchmark for raw TCP socket communication (threaded server)."""
    
    def __init__(self, host: str = "127.0.0.1", port: int = 5998):
        super().__init__("Socket")
        self.host = host
        self.port = port
        self.server_thread = None
        self.server_socket = None
        self.client_socket = None
        self._shutdown = False
    
    def setup(self) -> None:
        self._shutdown = False
        
        # Start socket server in thread
        self.server_thread = threading.Thread(target=self._run_server, daemon=True)
        self.server_thread.start()
        
        # Wait for server to start
        time.sleep(0.3)
        
        # Connect client
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client_socket.connect((self.host, self.port))
        self.client_socket.settimeout(5)
    
    def _run_server(self) -> None:
        """Run socket server in thread."""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.settimeout(1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)
        
        data_store = {}
        
        def handle_client(conn):
            try:
                while not self._shutdown:
                    try:
                        conn.settimeout(1)
                        data = conn.recv(65536)
                        if not data:
                            break
                        
                        msg = json.loads(data.decode())
                        
                        if msg['op'] == 'set':
                            data_store[msg['key']] = msg['value']
                            response = {"success": True}
                        elif msg['op'] == 'get':
                            value = data_store.get(msg['key'])
                            response = {"value": value, "found": value is not None}
                        else:
                            response = {"error": "Unknown operation"}
                        
                        conn.sendall(json.dumps(response).encode())
                    except socket.timeout:
                        continue
                    except Exception as e:
                        try:
                            conn.sendall(json.dumps({"error": str(e)}).encode())
                        except:
                            break
            except:
                pass
            finally:
                try:
                    conn.close()
                except:
                    pass
        
        while not self._shutdown:
            try:
                conn, addr = self.server_socket.accept()
                thread = threading.Thread(target=handle_client, args=(conn,), daemon=True)
                thread.start()
            except socket.timeout:
                continue
            except:
                break
    
    def teardown(self) -> None:
        self._shutdown = True
        if self.client_socket:
            try:
                self.client_socket.close()
            except:
                pass
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
        if self.server_thread:
            self.server_thread.join(timeout=2)
    
    def set_operation(self, key: str, value: Any) -> Tuple[bool, Optional[str]]:
        try:
            msg = json.dumps({"op": "set", "key": key, "value": value})
            self.client_socket.sendall(msg.encode())
            response = self.client_socket.recv(65536)
            data = json.loads(response.decode())
            return data.get('success', False), data.get('error')
        except Exception as e:
            return False, str(e)
    
    def get_operation(self, key: str) -> Tuple[Any, bool, Optional[str]]:
        try:
            msg = json.dumps({"op": "get", "key": key})
            self.client_socket.sendall(msg.encode())
            response = self.client_socket.recv(65536)
            data = json.loads(response.decode())
            return data.get('value'), data.get('found', False), data.get('error')
        except Exception as e:
            return None, False, str(e)
