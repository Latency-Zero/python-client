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


class ProcessProxy:
    """
    Attached as ``client.process``.  All process-pool operations live here.

    Usage::

        # Register — name inferred from function
        def add(x, y): return x + y
        client.process.register(add)                    # → "worker-1:add"
        client.process.register(add, name="sum")        # explicit override

        # Decorator forms
        @client.process.register
        def multiply(x, y): return x * y

        @client.process.register(name="mul")
        def multiply(x, y): return x * y

        # Call (blocking)
        result = client.process.call("worker-1:add", x=3, y=4)

        # Call with triangular routing (non-blocking)
        client.process.call("worker-1:add", response_to="client-3", x=3, y=4)

        # Broadcast
        targets = client.process.broadcast("add", x=3, y=4)

        # List
        procs = client.process.list()
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

    def register(self, fn: Optional[Callable] = None, *, name: Optional[str] = None):
        """
        Register a callable as a named process.

        Supports four call styles::

            client.process.register(fn)
            client.process.register(fn, name="override")
            @client.process.register
            @client.process.register(name="override")
        """
        # @client.process.register(name="override")  →  fn is None, return decorator
        if fn is None:
            def decorator(f: Callable) -> Callable:
                self._do_register(f, name or f.__name__)
                return f
            return decorator

        # client.process.register(fn)  or  @client.process.register  (bare)
        if callable(fn):
            self._do_register(fn, name or fn.__name__)
            return fn

        raise TypeError("register() expects a callable as the first argument")

    def _do_register(self, fn: Callable, process_name: str) -> None:
        if not process_name:
            raise ValueError(
                "Cannot infer process name from an anonymous/lambda function. "
                "Pass name= explicitly:  client.process.register(fn, name='my_proc')"
            )

        # Wrap async coroutines so they run synchronously in the receiver thread
        if asyncio.iscoroutinefunction(fn):
            _orig = fn

            def _sync_wrapper(**kwargs: Any) -> Any:
                loop = asyncio.new_event_loop()
                try:
                    return loop.run_until_complete(_orig(**kwargs))
                finally:
                    loop.close()

            wrapped: Callable = _sync_wrapper
        else:
            wrapped = fn

        client = self._client
        client._processes[process_name] = wrapped

        # Wire into _event_handlers under the compound key so that the
        # existing _handle_incoming_app_call dispatch picks it up automatically.
        compound_key = f"{client._client_id}:{process_name}"
        client._event_handlers[compound_key] = [wrapped]

        client._request("register_process", payload={"process_name": process_name})

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
        Call a registered process by its full ID (``client_id:process_name``).

        * ``response_to`` omitted  → blocks and returns the result.
        * ``response_to`` set      → returns ``None`` immediately; result is
          delivered to the specified client as an ``app_result`` push.
        """
        from .utils.exceptions import ServerProtocolError

        client = self._client
        _ensure_jsonable(data)

        if response_to is not None:
            # Non-blocking: only need the routing ack
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

        # Blocking: manually manage the pending queue so we can catch
        # both the ack (routing confirmed) and the app_result (actual result).
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

    def list(self, pattern: Optional[str] = None) -> Dict[str, str]:
        """
        List all registered processes in the pool.

        ``pattern`` filters by client_id prefix (e.g. ``"worker-1"``).
        Returns a dict mapping ``process_id → client_id``.
        """
        reply = self._client._request(
            "list_processes",
            payload={"pattern": pattern},
        )
        return dict((reply.get("payload") or {}).get("processes", {}))


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _ensure_jsonable(value: Any) -> None:
    import json
    try:
        json.dumps(value)
    except TypeError as exc:
        raise TypeError("Process data must be JSON-serializable") from exc
