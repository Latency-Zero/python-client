"""
ProcessProxy — the ``client.process`` namespace for LatZero server-mode clients.

Exposes register, unregister, call, broadcast, and list under a clean sub-object
so that process-pool operations are distinct from buffer/event operations.
"""

import asyncio
import queue as _queue
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

if TYPE_CHECKING:
    from .server_client import LatZero

from .worker import WorkerKind


class ProcessProxy:
    """
    Attached as ``client.process``.  All process-pool operations live here.

    Usage::

        # Register — name inferred from function
        def add(x, y): return x + y
        client.process.register(add)                    # → "worker-1:add"
        client.process.register(add, name="sum")        # explicit override

        # With worker backend configuration
        @client.process.register(worker_kind=WorkerKind.THREAD, min_workers=2, max_workers=20)
        def multiply(x, y): return x * y

        # Call by full ID or short name (server picks client)
        result = client.process.call("worker-1:add", x=3, y=4)
        result = client.process.call("add", x=3, y=4)   # short-name → server RR

        # Broadcast
        targets = client.process.broadcast("add", x=3, y=4)

        # List
        procs = client.process.list("worker-1")

        # Unregister
        client.process.unregister("add")
    """

    __slots__ = ("_client",)

    def __init__(self, client: "LatZero") -> None:
        self._client = client

    # ------------------------------------------------------------------
    # register
    # ------------------------------------------------------------------

    def register(
        self,
        fn: Optional[Callable] = None,
        *,
        name: Optional[str] = None,
        scale: bool = False,
        max_replicas: int = 10,
        group_id: Optional[str] = None,
        worker_kind: WorkerKind = WorkerKind.THREAD,
        min_workers: int = 1,
        max_workers: int = 10,
    ):
        """
        Register a callable as a named process.

        Supports::

            client.process.register(fn)
            client.process.register(fn, name="override", scale=True, max_replicas=5)
            client.process.register(fn, worker_kind=WorkerKind.PROCESS, min_workers=2)
            @client.process.register
            @client.process.register(name="override", worker_kind=WorkerKind.ADAPTIVE)
        """
        if fn is None:
            def decorator(f: Callable) -> Callable:
                self._do_register(
                    f, name or f.__name__,
                    scale=scale, max_replicas=max_replicas, group_id=group_id,
                    worker_kind=worker_kind, min_workers=min_workers, max_workers=max_workers,
                )
                return f
            return decorator

        if callable(fn):
            self._do_register(
                fn, name or fn.__name__,
                scale=scale, max_replicas=max_replicas, group_id=group_id,
                worker_kind=worker_kind, min_workers=min_workers, max_workers=max_workers,
            )
            return fn

        raise TypeError("register() expects a callable as the first argument")

    def _do_register(
        self,
        fn: Callable,
        process_name: str,
        scale: bool = False,
        max_replicas: int = 10,
        group_id: Optional[str] = None,
        worker_kind: WorkerKind = WorkerKind.THREAD,
        min_workers: int = 1,
        max_workers: int = 10,
    ) -> None:
        if not process_name:
            raise ValueError(
                "Cannot infer process name from an anonymous/lambda function. "
                "Pass name= explicitly:  client.process.register(fn, name='my_proc')"
            )

        # Store the raw function (backends handle async coroutines internally)
        client = self._client
        client._processes[process_name] = fn

        # Wire into _event_handlers as fallback for non-scalable paths
        compound_key = f"{client._client_id}:{process_name}"
        client._event_handlers[compound_key] = [fn]

        # Build payload
        payload: dict = {
            "process_name": process_name,
            "worker_kind": worker_kind.value,
            "min_workers": min_workers,
            "max_workers": max_workers,
        }
        if scale:
            payload["scale"] = True
            payload["max_replicas"] = max_replicas
        if group_id:
            payload["group_id"] = group_id

        # Register on server
        reply = client._request("register_process", payload=payload)
        ack_payload = reply.get("payload") or {}

        # Set up local worker pool via ReplicaManager
        rm = client._replica_manager
        if rm is None:
            from .server_client import ReplicaManager
            rm = ReplicaManager(client)
            client._replica_manager = rm

        rm.setup_pool(
            process_name=process_name,
            fn=fn,
            worker_kind=worker_kind,
            min_workers=min_workers,
            max_workers=max_workers,
        )

        # Start metrics push if not already running
        if client._metrics_push_thread is None:
            client._start_metrics_push()

    # ------------------------------------------------------------------
    # unregister
    # ------------------------------------------------------------------

    def unregister(self, name: str) -> None:
        """Unregister a process by its short (unqualified) name."""
        client = self._client
        client._processes.pop(name, None)
        compound_key = f"{client._client_id}:{name}"
        client._event_handlers.pop(compound_key, None)
        client._request("unregister_process", payload={"process_name": name})
        # Destroy local worker pool
        if client._replica_manager is not None:
            client._replica_manager.destroy_pool(name)

    # ------------------------------------------------------------------
    # call
    # ------------------------------------------------------------------

    def call(
        self,
        process_id: str,
        response_to: Optional[str] = None,
        _timeout: float = 5.0,
        **data: Any,
    ) -> Any:
        """
        Call a registered process.

        * ``process_id`` contains ``:`` → direct targeting (full ID).
        * ``process_id`` has no ``:``   → short-name; server picks a client
          via round-robin and routes to it.

        * ``response_to`` omitted  → blocks and returns the result.
        * ``response_to`` set      → returns ``None`` immediately; result is
          delivered to the specified client as an ``app_result`` push.
        """
        from .utils.exceptions import ServerProtocolError

        client = self._client
        _ensure_jsonable(data)

        client._check_connected()

        if response_to is not None:
            client._request(
                "call_process",
                payload={
                    "process_id": process_id,
                    "data": data,
                    "response_to": response_to,
                    "timeout": _timeout,
                },
                timeout=_timeout,
            )
            return None

        request_id = client._next_request_id()
        pending: "_queue.Queue[dict]" = _queue.Queue()
        client._pending[request_id] = pending
        client._send_message(
            {
                "type": "call_process",
                "request_id": request_id,
                "client_id": client._client_id,
                "pool": client._pool_name,
                "payload": {
                    "process_id": process_id,
                    "data": data,
                    "response_to": None,
                    "timeout": _timeout,
                },
            }
        )
        try:
            client._wait_for_message(request_id, _timeout, {"ack"})
            result = client._wait_for_message(request_id, _timeout, {"app_result"})
        finally:
            client._pending.pop(request_id, None)

        payload = result.get("payload") or {}
        if payload.get("error"):
            raise ServerProtocolError(str(payload["error"]))
        return payload.get("value")

    # ------------------------------------------------------------------
    # broadcast
    # ------------------------------------------------------------------

    def broadcast(
        self,
        process_name: str,
        response_to: Optional[str] = None,
        **data: Any,
    ) -> List[str]:
        """
        Broadcast to every process registered under the given short name.

        Returns the list of ``process_id`` strings that were invoked.
        """
        _ensure_jsonable(data)
        reply = self._client._request(
            "broadcast_process",
            payload={
                "process_name": process_name,
                "data": data,
                "response_to": response_to,
            },
        )
        return list((reply.get("payload") or {}).get("targets", []))

    # ------------------------------------------------------------------
    # list
    # ------------------------------------------------------------------

    def list(self, pattern: Optional[str] = None) -> Dict[str, Any]:
        """
        List all registered processes in the pool.

        Returns a dict mapping ``process_id → { client_id, worker_kind,
        worker_count, queue_depth, ... }``.
        """
        reply = self._client._request(
            "list_processes",
            payload={"pattern": pattern},
        )
        return dict((reply.get("payload") or {}).get("processes", {}))


def _ensure_jsonable(value: Any) -> None:
    import json
    try:
        json.dumps(value)
    except TypeError as exc:
        raise TypeError("Process data must be JSON-serializable") from exc
