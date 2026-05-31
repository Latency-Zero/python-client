"""
Pluggable worker backends for executing registered process functions.

Provides:
    - WorkerKind enum (THREAD, PROCESS, ADAPTIVE)
    - WorkerBackend ABC
    - ThreadWorkerBackend  (concurrent.futures thread pool)
    - ProcessWorkerBackend (multiprocessing.Process pool)
    - AdaptiveWorkerBackend (auto-detect based on function type)
"""

import asyncio
import queue
import time
import uuid
from abc import ABC, abstractmethod
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from enum import Enum
from threading import Thread, Event as ThreadEvent
from typing import Any, Callable, Deque, Dict, List, Optional, Tuple


class WorkerKind(Enum):
    """Backend kind for process-function execution."""

    THREAD = "thread"
    """Thread-pool backend.  Fast spawn, shares parent address space.
    Best for I/O-bound or fast handlers.  GIL-limited for CPU work."""

    PROCESS = "process"
    """OS-process pool via ``multiprocessing``.  True parallelism.
    Best for CPU-bound or long-running handlers.  Higher spawn cost."""

    ADAPTIVE = "adaptive"
    """Auto-detect: if the registered function is a coroutine or
    explicitly annotated as I/O-heavy → THREAD; otherwise → PROCESS."""


class WorkerContext:
    """Immutable context shared across all workers in a backend."""

    __slots__ = ("client", "fn", "process_name", "pool_name")

    def __init__(
        self,
        client: Any,
        fn: Callable,
        process_name: str,
        pool_name: str,
    ) -> None:
        self.client = client
        self.fn = fn
        self.process_name = process_name
        self.pool_name = pool_name


def _default_send_result(client: Any, request_id: str, target_client_id: str,
                          pool_name: str, value: Any, error: Optional[dict]) -> None:
    """Helper to send an ``app_result`` message through the client's TCP connection."""
    client._send_message({
        "type": "app_result",
        "request_id": request_id,
        "client_id": client.client_id,
        "pool": pool_name,
        "payload": {"value": value, "error": error},
    })


class WorkerBackend(ABC):
    """
    Abstract base for a pool of workers that execute registered process
    functions and send results back through the parent ``LatZero`` connection.
    """

    @abstractmethod
    def start(self, ctx: WorkerContext, min_workers: int, max_workers: int,
              send_result: Callable = _default_send_result) -> None:
        ...

    @abstractmethod
    def submit(self, request_id: str, caller_client_id: str, data: dict) -> None:
        """Enqueue work.  Non-blocking from the caller's perspective."""

    @abstractmethod
    def scale_to(self, count: int) -> None:
        """Adjust the number of active workers (within [min, max])."""

    @abstractmethod
    def stop(self) -> None:
        """Shut down all workers and release resources."""

    @property
    @abstractmethod
    def active_count(self) -> int: ...

    @property
    @abstractmethod
    def queue_depth(self) -> int: ...

    @property
    @abstractmethod
    def completed_count(self) -> int: ...

    @property
    @abstractmethod
    def avg_latency(self) -> float: ...


# ---------------------------------------------------------------------------
# Thread backend
# ---------------------------------------------------------------------------

class ThreadWorkerBackend(WorkerBackend):
    """
    Thread-pool backend using ``concurrent.futures.ThreadPoolExecutor``.
    Workers share the parent's address space and TCP connection directly.
    """

    __slots__ = (
        "_ctx", "_send_result", "_executor", "_work_queue",
        "_stop_event", "_dispatcher", "_active", "_completed",
        "_latencies", "_min", "_max",
    )

    def __init__(self) -> None:
        self._ctx: Optional[WorkerContext] = None
        self._send_result: Optional[Callable] = None
        self._executor: Optional[ThreadPoolExecutor] = None
        self._work_queue: queue.Queue = queue.Queue()
        self._stop_event = ThreadEvent()
        self._dispatcher: Optional[Thread] = None
        self._active: int = 0
        self._completed: int = 0
        self._latencies: Deque[float] = deque(maxlen=200)
        self._min: int = 1
        self._max: int = 10

    def start(self, ctx: WorkerContext, min_workers: int = 1,
              max_workers: int = 10,
              send_result: Callable = _default_send_result) -> None:
        self._ctx = ctx
        self._send_result = send_result
        self._min = min_workers
        self._max = max_workers
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._active = min_workers
        self._dispatcher = Thread(target=self._dispatch_loop, daemon=True,
                                  name=f"latzero-worker-dispatch-{ctx.process_name}")
        self._dispatcher.start()

    def _dispatch_loop(self) -> None:
        """Pull work items from the queue and submit to the thread pool."""
        while not self._stop_event.is_set():
            try:
                request_id, caller_client_id, data = self._work_queue.get(timeout=0.5)
            except queue.Empty:
                continue
            if self._executor is None:
                continue
            future = self._executor.submit(
                self._execute, request_id, caller_client_id, data
            )
            future.add_done_callback(lambda f: self._work_queue.task_done())

    def _execute(self, request_id: str, caller_client_id: str, data: dict) -> None:
        start = time.time()
        error: Optional[dict] = None
        value: Any = None
        try:
            result = self._ctx.fn(**data)
            # Handle async coroutines from sync context
            if asyncio.iscoroutine(result):
                loop = asyncio.new_event_loop()
                try:
                    result = loop.run_until_complete(result)
                finally:
                    loop.close()
            value = result
        except Exception as exc:
            error = {"type": type(exc).__name__, "message": str(exc)}
        latency = time.time() - start
        self._latencies.append(latency)
        self._completed += 1
        self._send_result(
            self._ctx.client, request_id, caller_client_id,
            self._ctx.pool_name, value, error,
        )

    def submit(self, request_id: str, caller_client_id: str, data: dict) -> None:
        self._work_queue.put((request_id, caller_client_id, data))

    def scale_to(self, count: int) -> None:
        count = max(self._min, min(count, self._max))
        if count > self._active:
            self._active = count
            if self._executor is not None:
                self._executor._max_workers = count
        elif count < self._active:
            self._active = count
            # Workers finish naturally; no need to kill threads.

    def stop(self) -> None:
        self._stop_event.set()
        if self._executor is not None:
            self._executor.shutdown(wait=False)
            self._executor = None

    @property
    def active_count(self) -> int:
        return self._active

    @property
    def queue_depth(self) -> int:
        return self._work_queue.qsize()

    @property
    def completed_count(self) -> int:
        return self._completed

    @property
    def avg_latency(self) -> float:
        if not self._latencies:
            return 0.0
        return sum(self._latencies) / len(self._latencies)


# ---------------------------------------------------------------------------
# Process backend
# ---------------------------------------------------------------------------

class _ProcessWorker(Thread):
    """Worker running in a thread that feeds a child process via mp.Queue."""

    def __init__(self, ctx: WorkerContext, task_queue: Any, result_queue: Any,
                 stop_event: ThreadEvent, idx: int) -> None:
        super().__init__(daemon=True)
        self._ctx = ctx
        self._task_queue = task_queue
        self._result_queue = result_queue
        self._stop_event = stop_event
        self._idx = idx
        self._completed: int = 0
        self._latencies: Deque[float] = deque(maxlen=100)

    def run(self) -> None:
        while not self._stop_event.is_set():
            try:
                request_id, caller_client_id, data = self._task_queue.get(timeout=0.5)
            except queue.Empty:
                continue
            start = time.time()
            error: Optional[dict] = None
            value: Any = None
            try:
                result = self._ctx.fn(**data)
                if asyncio.iscoroutine(result):
                    loop = asyncio.new_event_loop()
                    try:
                        result = loop.run_until_complete(result)
                    finally:
                        loop.close()
                value = result
            except Exception as exc:
                error = {"type": type(exc).__name__, "message": str(exc)}
            latency = time.time() - start
            self._latencies.append(latency)
            self._completed += 1
            self._result_queue.put({
                "request_id": request_id,
                "caller_client_id": caller_client_id,
                "value": value,
                "error": error,
                "latency": latency,
            })

    @property
    def completed(self) -> int:
        return self._completed

    @property
    def latencies(self) -> Deque[float]:
        return self._latencies


class ProcessWorkerBackend(WorkerBackend):
    """
    Multi-process backend.  Workers run in subprocesses and communicate
    results via a ``multiprocessing.Queue``.  A dedicated drain thread
    reads the result queue and sends ``app_result`` messages.
    """

    __slots__ = (
        "_ctx", "_send_result", "_workers", "_task_queue",
        "_result_queue", "_drain_thread", "_stop_event",
        "_completed", "_latencies", "_min", "_max",
    )

    def __init__(self) -> None:
        self._ctx: Optional[WorkerContext] = None
        self._send_result: Optional[Callable] = None
        self._workers: List[_ProcessWorker] = []
        self._task_queue: Any = None
        self._result_queue: Any = None
        self._drain_thread: Optional[Thread] = None
        self._stop_event = ThreadEvent()
        self._completed: int = 0
        self._latencies: Deque[float] = deque(maxlen=200)
        self._min: int = 1
        self._max: int = 10

    def start(self, ctx: WorkerContext, min_workers: int = 1,
              max_workers: int = 10,
              send_result: Callable = _default_send_result) -> None:
        self._ctx = ctx
        self._send_result = send_result
        self._min = min_workers
        self._max = max_workers
        import multiprocessing as mp
        self._task_queue = mp.Queue()
        self._result_queue = mp.Queue()

        # Start result drain thread
        self._drain_thread = Thread(target=self._drain_loop, daemon=True,
                                     name=f"latzero-process-drain-{ctx.process_name}")
        self._drain_thread.start()

        # Start workers
        for i in range(min_workers):
            self._spawn_worker(i)

    def _spawn_worker(self, idx: int) -> None:
        w = _ProcessWorker(
            self._ctx, self._task_queue, self._result_queue,
            self._stop_event, idx,
        )
        w.start()
        self._workers.append(w)

    def _drain_loop(self) -> None:
        """Read results from the multiprocessing result queue and send over TCP."""
        while not self._stop_event.is_set():
            try:
                result = self._result_queue.get(timeout=0.5)
            except queue.Empty:
                continue
            self._latencies.append(result["latency"])
            self._completed += 1
            self._send_result(
                self._ctx.client,
                result["request_id"],
                result["caller_client_id"],
                self._ctx.pool_name,
                result["value"],
                result["error"],
            )

    def submit(self, request_id: str, caller_client_id: str, data: dict) -> None:
        self._task_queue.put((request_id, caller_client_id, data))

    def scale_to(self, count: int) -> None:
        count = max(self._min, min(count, self._max))
        while len(self._workers) < count:
            self._spawn_worker(len(self._workers))
        while len(self._workers) > count:
            w = self._workers.pop()
            w.join(timeout=2.0)

    def stop(self) -> None:
        self._stop_event.set()
        for w in self._workers:
            w.join(timeout=2.0)
        self._workers.clear()

    @property
    def active_count(self) -> int:
        return len(self._workers)

    @property
    def queue_depth(self) -> int:
        if self._task_queue is None:
            return 0
        try:
            return self._task_queue.qsize()
        except NotImplementedError:
            return 0

    @property
    def completed_count(self) -> int:
        return self._completed

    @property
    def avg_latency(self) -> float:
        if not self._latencies:
            return 0.0
        return sum(self._latencies) / len(self._latencies)


# ---------------------------------------------------------------------------
# Adaptive backend
# ---------------------------------------------------------------------------

def _is_async_fn(fn: Callable) -> bool:
    """Best-effort detection of async/coroutine functions."""
    if asyncio.iscoroutinefunction(fn):
        return True
    import inspect
    try:
        sig = inspect.signature(fn)
        # Check if return annotation suggests a coroutine
        ret = sig.return_annotation
        if ret is not inspect.Parameter.empty:
            ret_str = str(ret)
            if "coroutine" in ret_str.lower() or "awaitable" in ret_str.lower():
                return True
    except (ValueError, TypeError):
        pass
    return False


class AdaptiveWorkerBackend(WorkerBackend):
    """
    Auto-detects the optimal backend based on the registered function.

    - Async/coroutine functions → Thread backend (needs event loop)
    - Sync CPU-heavy functions  → Process backend (true parallelism)
    - Fast sync I/O functions   → Thread backend (lower overhead)
    """

    __slots__ = ("_backend",)

    def __init__(self) -> None:
        self._backend: Optional[WorkerBackend] = None

    def _select_backend(self, fn: Callable) -> WorkerBackend:
        if _is_async_fn(fn):
            return ThreadWorkerBackend()
        return ProcessWorkerBackend()

    def start(self, ctx: WorkerContext, min_workers: int = 1,
              max_workers: int = 10,
              send_result: Callable = _default_send_result) -> None:
        self._backend = self._select_backend(ctx.fn)
        self._backend.start(ctx, min_workers, max_workers, send_result)

    def submit(self, request_id: str, caller_client_id: str, data: dict) -> None:
        self._backend.submit(request_id, caller_client_id, data)

    def scale_to(self, count: int) -> None:
        self._backend.scale_to(count)

    def stop(self) -> None:
        if self._backend is not None:
            self._backend.stop()

    @property
    def active_count(self) -> int:
        return self._backend.active_count if self._backend else 0

    @property
    def queue_depth(self) -> int:
        return self._backend.queue_depth if self._backend else 0

    @property
    def completed_count(self) -> int:
        return self._backend.completed_count if self._backend else 0

    @property
    def avg_latency(self) -> float:
        return self._backend.avg_latency if self._backend else 0.0


# ---------------------------------------------------------------------------
# Backend factory
# ---------------------------------------------------------------------------

_BACKEND_MAP: Dict[WorkerKind, type] = {
    WorkerKind.THREAD: ThreadWorkerBackend,
    WorkerKind.PROCESS: ProcessWorkerBackend,
    WorkerKind.ADAPTIVE: AdaptiveWorkerBackend,
}


def create_backend(kind: WorkerKind) -> WorkerBackend:
    """Create a new ``WorkerBackend`` instance for the given ``WorkerKind``."""
    cls = _BACKEND_MAP.get(kind)
    if cls is None:
        raise ValueError(f"Unknown WorkerKind: {kind}")
    return cls()


# ---------------------------------------------------------------------------
# IncomingWorkerPool — wraps a backend with lifecycle & local auto-scaling
# ---------------------------------------------------------------------------


class IncomingWorkerPool:
    """
    Manages a ``WorkerBackend`` for a single registered process function.

    Responsibilities:
        - Start / stop the worker backend.
        - Forward incoming ``call_app`` messages to ``submit()``.
        - Local auto-scaling: if the internal queue depth exceeds
          ``_local_scale_up_threshold`` (default 10) for more than 1 s,
          provision an additional worker (capped at ``max_workers``).
        - If queue stays empty and active count > min_workers for 10+ s,
          drain one worker.
        - Expose metrics (active count, queue depth, latency) for the
          periodic push to the server.
    """

    __slots__ = (
        "_backend", "_ctx", "_send_result",
        "_min", "_max", "_local_up_threshold",
        "_last_scale_event",
    )

    def __init__(
        self,
        client: Any,
        fn: Callable,
        process_name: str,
        pool_name: str,
        *,
        worker_kind: WorkerKind = WorkerKind.THREAD,
        min_workers: int = 1,
        max_workers: int = 10,
        local_scale_up_threshold: int = 10,
        send_result: Callable = _default_send_result,
    ) -> None:
        self._backend = create_backend(worker_kind)
        self._ctx = WorkerContext(client, fn, process_name, pool_name)
        self._send_result = send_result
        self._min = min_workers
        self._max = max_workers
        self._local_up_threshold = local_scale_up_threshold
        self._last_scale_event = time.monotonic()
        self._backend.start(self._ctx, min_workers, max_workers, send_result)

    def submit(self, request_id: str, caller_client_id: str, data: dict) -> None:
        self._backend.submit(request_id, caller_client_id, data)

    def scale_up(self, count: int = 1) -> None:
        """Add workers (called by server ``process_scale up``)."""
        target = min(self._backend.active_count + count, self._max)
        self._backend.scale_to(target)
        self._last_scale_event = time.monotonic()

    def scale_down(self, count: int = 1) -> None:
        """Remove workers (called by server ``process_scale down``)."""
        target = max(self._backend.active_count - count, self._min)
        self._backend.scale_to(target)
        self._last_scale_event = time.monotonic()

    def check_local_autoscale(self) -> None:
        """
        Called periodically (e.g. every second) to evaluate local queue
        depth and adjust workers within [min, max].

        Hybrid model: the server drives the primary scaling signals, but
        the client can autonomously add one extra worker if the local
        queue is backing up beyond the threshold.
        """
        qd = self._backend.queue_depth
        now = time.monotonic()
        if qd > self._local_up_threshold and self._backend.active_count < self._max:
            self._backend.scale_to(min(self._backend.active_count + 1, self._max))
            self._last_scale_event = now
        elif (qd == 0 and self._backend.active_count > self._min
              and (now - self._last_scale_event) > 10.0):
            self._backend.scale_to(max(self._backend.active_count - 1, self._min))
            self._last_scale_event = now

    def stop(self) -> None:
        self._backend.stop()

    def get_metrics(self) -> dict:
        return {
            "process_name": self._ctx.process_name,
            "active_workers": self._backend.active_count,
            "queue_depth": self._backend.queue_depth,
            "avg_latency": self._backend.avg_latency,
            "completed_count": self._backend.completed_count,
        }

    @property
    def active_count(self) -> int:
        return self._backend.active_count

    @property
    def queue_depth(self) -> int:
        return self._backend.queue_depth

    @property
    def avg_latency(self) -> float:
        return self._backend.avg_latency

    @property
    def completed_count(self) -> int:
        return self._backend.completed_count
