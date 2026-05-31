"""
Server-backed LatZero client for the local TCP server mode.
"""

import json
import queue
import socket
import threading
import time
import uuid
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from .process_proxy import ProcessProxy
from .worker import (
    IncomingWorkerPool,
    WorkerKind,
    _default_send_result,
)
from .utils.exceptions import (
    AuthenticationError,
    PoolDisconnectedError,
    ServerConnectionError,
    ServerProtocolError,
    ServerTimeoutError,
)


def _ensure_jsonable(value: Any) -> None:
    """Raise when a server-mode value cannot be encoded as JSON."""
    try:
        json.dumps(value)
    except TypeError as exc:
        raise TypeError("Server mode only supports JSON-serializable values") from exc


class LatZero:
    """
    Server-backed LatZero client.

    Usage:
        client = LatZero("latzero://client-1", pool="alpha")
        client.set("key", {"value": 1}, persistent=True)
    """

    __slots__ = (
        "_client_id",
        "_pool_name",
        "_auth_token",
        "_host",
        "_port",
        "_sock",
        "_reader",
        "_send_lock",
        "_pending",
        "_receiver_thread",
        "_running",
        "_disconnected",
        "_dispatch_enabled",
        "_hooks",
        "_event_handlers",
        "_processes",
        "_replica_manager",
        "_metrics_push_thread",
        "process",
    )

    def __init__(
        self,
        dsn: str,
        pool: str,
        auth_token: Optional[str] = None,
        host: str = "127.0.0.1",
        port: int = 14130,
        timeout: float = 5.0,
    ):
        parsed = urlparse(dsn)
        if parsed.scheme != "latzero" or not parsed.netloc:
            raise ValueError("DSN must look like latzero://client-id")

        self._client_id = parsed.netloc
        self._pool_name = pool
        self._auth_token = auth_token
        self._host = host
        self._port = port
        self._sock = None
        self._reader = None
        self._send_lock = threading.Lock()
        self._pending: Dict[str, "queue.Queue[dict]"] = {}
        self._receiver_thread = None
        self._running = False
        self._disconnected = False
        self._dispatch_enabled = True
        self._hooks: Dict[str, List[Callable]] = {}
        self._event_handlers: Dict[str, List[Callable]] = {}
        self._processes: Dict[str, Callable] = {}
        self._replica_manager: Optional["ReplicaManager"] = None
        self._metrics_push_thread: Optional[threading.Thread] = None
        self.process = ProcessProxy(self)

        self._connect(timeout=timeout)
        self._emit("on_connect", self._pool_name)

    def _connect(self, timeout: float = 5.0) -> None:
        try:
            self._sock = socket.create_connection((self._host, self._port), timeout=timeout)
            self._reader = self._sock.makefile("rb")
        except OSError as exc:
            raise ServerConnectionError(
                f"Could not connect to latzero server at {self._host}:{self._port}"
            ) from exc

        self._running = True
        self._receiver_thread = threading.Thread(
            target=self._receiver_loop,
            daemon=True,
            name=f"latzero-server-client-{self._client_id}",
        )
        self._receiver_thread.start()

        self._request("hello", payload={"client_id": self._client_id}, pool=None, timeout=timeout)
        self._join_pool(self._pool_name, self._auth_token, timeout=timeout)

        # Clear socket timeout so the receiver loop can block indefinitely.
        # Request-level timeouts are handled by _wait_for_message via queue.get().
        self._sock.settimeout(None)

    def _start_metrics_push(self) -> None:
        """Start a background thread that periodically sends worker metrics
        to the server and runs local auto-scaling checks."""
        if self._metrics_push_thread is not None and self._metrics_push_thread.is_alive():
            return
        self._metrics_push_thread = threading.Thread(
            target=self._metrics_push_loop,
            daemon=True,
            name=f"latzero-metrics-push-{self._client_id}",
        )
        self._metrics_push_thread.start()

    def _metrics_push_loop(self) -> None:
        """
        Every ~1 second:
          1. Run local auto-scaling on each worker pool.
          2. Push aggregate metrics to the server (``worker_metrics``).
        """
        while self._running and not self._disconnected:
            time.sleep(1.0)
            try:
                # Local auto-scaling
                if self._replica_manager is not None:
                    self._replica_manager.check_local_autoscale()
                    metrics = self._replica_manager.get_all_metrics()
                    if metrics:
                        try:
                            self._request(
                                "worker_metrics",
                                payload={"metrics": metrics},
                                timeout=2.0,
                            )
                        except Exception:
                            pass
            except Exception:
                pass

    def _join_pool(self, pool: str, auth_token: Optional[str], timeout: float = 5.0) -> None:
        self._request(
            "join_pool",
            pool=pool,
            payload={
                "client_id": self._client_id,
                "pool": pool,
                "auth_token": auth_token,
            },
            timeout=timeout,
        )
        self._pool_name = pool
        self._auth_token = auth_token

    def __enter__(self) -> "LatZero":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        self.disconnect()
        return False

    def __del__(self):
        if not self._disconnected:
            try:
                self.disconnect()
            except Exception:
                pass

    @property
    def pool_name(self) -> str:
        return self._pool_name

    @property
    def client_id(self) -> str:
        return self._client_id

    def _check_connected(self) -> None:
        if self._disconnected or not self._running or self._sock is None:
            raise PoolDisconnectedError("Client is disconnected")

    def _next_request_id(self) -> str:
        return str(uuid.uuid4())

    def _send_message(self, message: dict) -> None:
        encoded = (json.dumps(message, separators=(",", ":"), ensure_ascii=True) + "\n").encode("utf-8")
        with self._send_lock:
            assert self._sock is not None
            self._sock.sendall(encoded)

    def _request(
        self,
        msg_type: str,
        payload: Optional[dict] = None,
        pool: Optional[str] = None,
        timeout: float = 5.0,
    ) -> dict:
        self._check_connected()
        request_id = self._next_request_id()
        pending: "queue.Queue[dict]" = queue.Queue()
        self._pending[request_id] = pending
        self._send_message(
            {
                "type": msg_type,
                "request_id": request_id,
                "client_id": self._client_id,
                "pool": pool if pool is not None else self._pool_name,
                "payload": payload or {},
            }
        )
        try:
            return self._wait_for_message(request_id, timeout, {"ack"})
        finally:
            self._pending.pop(request_id, None)

    def _wait_for_message(self, request_id: str, timeout: float, expected_types: set) -> dict:
        pending = self._pending.get(request_id)
        if pending is None:
            raise ServerProtocolError(f"Unknown pending request: {request_id}")

        deadline = time.time() + timeout
        buffered: List[dict] = []

        while True:
            remaining = deadline - time.time()
            if remaining <= 0:
                raise ServerTimeoutError(f"Timed out waiting for server response: {request_id}")
            try:
                reply = pending.get(timeout=remaining)
            except queue.Empty as exc:
                raise ServerTimeoutError(f"Timed out waiting for server response: {request_id}") from exc

            if reply.get("type") == "error":
                self._raise_server_error(reply)
            if reply.get("type") in expected_types:
                for item in buffered:
                    pending.put(item)
                return reply
            buffered.append(reply)

    def _raise_server_error(self, message: dict) -> None:
        payload = message.get("payload") or {}
        code = payload.get("code", "server_error")
        text = payload.get("message", "Unknown server error")
        if code == "auth_failed":
            raise AuthenticationError(text)
        if code in {"timeout", "connection_closed"}:
            raise ServerTimeoutError(text)
        raise ServerProtocolError(f"{code}: {text}")

    def _receiver_loop(self) -> None:
        try:
            while self._running and self._reader is not None:
                try:
                    raw = self._reader.readline()
                except (socket.timeout, TimeoutError):
                    continue
                except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError, OSError):
                    break
                if not raw:
                    break
                message = json.loads(raw.decode("utf-8").strip())
                request_id = message.get("request_id")
                mtype = message.get("type")
                pending_queue = self._pending.get(request_id) if request_id else None
                if pending_queue is not None and mtype in {"ack", "error", "app_result"}:
                    pending_queue.put(message)
                else:
                    self._dispatch_message(message)
        except Exception as exc:
            import traceback
            traceback.print_exc()
        finally:
            self._running = False
            for pending in list(self._pending.values()):
                pending.put(
                    {
                        "type": "error",
                        "payload": {
                            "code": "connection_closed",
                            "message": "Connection to latzero server was closed",
                        },
                    }
                )

    def _dispatch_message(self, message: dict) -> None:
        if not self._dispatch_enabled:
            return

        msg_type = message.get("type")
        payload = message.get("payload") or {}

        if msg_type == "presence_update":
            self._emit("on_presence", payload)
            return

        if msg_type == "buffer_update":
            operation = payload.get("operation")
            entry = payload.get("entry") or {}
            key = payload.get("key")
            if operation == "delete":
                self._emit("on_delete", key)
            else:
                self._emit("on_update", key, entry.get("value"))
            self._emit("on_buffer_update", payload)
            return

        if msg_type == "emit_event":
            self._invoke_event_handlers(payload.get("event", ""), payload.get("data", {}))
            return

        if msg_type == "call_app":
            self._handle_incoming_app_call(message, payload)
            return

        if msg_type == "app_result":
            self._emit("on_app_result", payload)
            return

        if msg_type == "process_scale":
            action = payload.get("action")
            process_name = payload.get("process_name")
            count = payload.get("count", 1)
            if self._replica_manager is None:
                self._replica_manager = ReplicaManager(self)
            if action == "up":
                self._replica_manager.scale_up(process_name, count)
            elif action == "down":
                self._replica_manager.scale_down(process_name, count)
            return

    def _handle_incoming_app_call(self, message: dict, payload: dict) -> None:
        """Route an incoming ``call_app`` to the appropriate worker pool."""
        event = payload.get("event", "")
        request_id = message.get("request_id")
        caller_client_id = message.get("client_id", "")
        data = payload.get("data", {})

        # Check if we have a worker pool for this event (compound key like "client-1:add")
        if self._replica_manager is not None:
            pool = self._replica_manager.get_pool(event)
            if pool is not None:
                pool.submit(request_id, caller_client_id, data)
                return

        # Fall back to non-scalable event handler (existing behavior)
        try:
            result = self._invoke_event_handlers(event, data, expect_result=True)
            response_payload = {"value": result, "error": None}
        except Exception as exc:
            response_payload = {
                "value": None,
                "error": {
                    "type": type(exc).__name__,
                    "message": str(exc),
                },
            }

        self._send_message(
            {
                "type": "app_result",
                "request_id": request_id,
                "client_id": self._client_id,
                "pool": self._pool_name,
                "payload": response_payload,
            }
        )

    def _invoke_event_handlers(self, event: str, data: dict, expect_result: bool = False):
        handlers = self._event_handlers.get(event, [])
        result = None
        for handler in handlers:
            result = handler(**data)
        if expect_result:
            return result
        return None

    def on(self, event: str, callback: Callable) -> None:
        self._hooks.setdefault(event, []).append(callback)

    def off(self, event: str, callback: Optional[Callable] = None) -> None:
        if event not in self._hooks:
            return
        if callback is None:
            del self._hooks[event]
        else:
            self._hooks[event] = [handler for handler in self._hooks[event] if handler != callback]

    def _emit(self, event: str, *args, **kwargs) -> None:
        for callback in self._hooks.get(event, []):
            try:
                callback(*args, **kwargs)
            except Exception:
                pass

    def switch_pool(self, pool: str, auth_token: Optional[str] = None, timeout: float = 5.0) -> None:
        self._request(
            "switch_pool",
            pool=pool,
            payload={
                "client_id": self._client_id,
                "pool": pool,
                "auth_token": auth_token,
            },
            timeout=timeout,
        )
        self._pool_name = pool
        self._auth_token = auth_token

    def disconnect(self) -> None:
        if self._disconnected:
            return
        try:
            if self._running:
                try:
                    self._request("leave_pool", payload={}, timeout=1.0)
                except Exception:
                    pass
        finally:
            self._running = False
            self._disconnected = True
            if self._replica_manager is not None:
                self._replica_manager.destroy_all()
            self._metrics_push_thread = None
            # Shutdown first so receiver thread's readline() unblocks on Windows
            try:
                if self._sock is not None:
                    self._sock.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            try:
                if self._reader is not None:
                    self._reader.close()
            except Exception:
                pass
            try:
                if self._sock is not None:
                    self._sock.close()
            except Exception:
                pass
            self._emit("on_disconnect", self._pool_name)

    def set(
        self,
        key: str,
        value: Any,
        auto_clean: Optional[int] = None,
        persistent: bool = False,
    ) -> None:
        _ensure_jsonable(value)
        self._request(
            "set_buffer",
            payload={
                "key": key,
                "value": value,
                "ttl": auto_clean,
                "persistent": persistent,
            },
        )

    def get(self, key: str, default: Any = None) -> Any:
        reply = self._request("get_buffer", payload={"key": key})
        payload = reply.get("payload") or {}
        if not payload.get("exists"):
            return default
        entry = payload.get("entry") or {}
        return entry.get("value", default)

    def delete(self, key: str) -> bool:
        reply = self._request("delete_buffer", payload={"key": key})
        return bool((reply.get("payload") or {}).get("deleted"))

    def exists(self, key: str) -> bool:
        reply = self._request("get_buffer", payload={"key": key})
        return bool((reply.get("payload") or {}).get("exists"))

    def keys(self, pattern: Optional[str] = None) -> List[str]:
        reply = self._request("list_buffers", payload={"pattern": pattern})
        return list((reply.get("payload") or {}).get("keys", []))

    def values(self, pattern: Optional[str] = None) -> List[Any]:
        return [self.get(key) for key in self.keys(pattern)]

    def items(self, pattern: Optional[str] = None) -> List[Tuple[str, Any]]:
        return [(key, self.get(key)) for key in self.keys(pattern)]

    def mset(self, data: dict, auto_clean: Optional[int] = None, persistent: bool = False) -> None:
        for key, value in data.items():
            self.set(key, value, auto_clean=auto_clean, persistent=persistent)

    def mget(self, keys: List[str]) -> Dict[str, Any]:
        return {key: self.get(key) for key in keys}

    def delete_many(self, keys: List[str]) -> int:
        deleted = 0
        for key in keys:
            if self.delete(key):
                deleted += 1
        return deleted

    def size(self) -> int:
        return len(self.keys())

    def stats(self) -> dict:
        return {
            "name": self._pool_name,
            "client_id": self._client_id,
            "server_mode": True,
            "key_count": self.size(),
        }

    def scan(self, cursor: int = 0, count: int = 100) -> Tuple[int, List[str]]:
        keys = self.keys()
        end = min(cursor + count, len(keys))
        next_cursor = end if end < len(keys) else 0
        return next_cursor, keys[cursor:end]

    def subscribe_buffer(self, key: str) -> None:
        self._request("subscribe_buffer", payload={"key": key})

    def unsubscribe_buffer(self, key: str) -> None:
        self._request("unsubscribe_buffer", payload={"key": key})

    def on_event(self, event: str, **options):
        def decorator(func: Callable) -> Callable:
            self._event_handlers.setdefault(event, []).append(func)
            return func

        return decorator

    def emit_event(
        self,
        event: str,
        target_client_id: Optional[str] = None,
        response_to: Optional[str] = None,
        **data,
    ) -> None:
        _ensure_jsonable(data)
        self._request(
            "emit_event",
            payload={
                "event": event,
                "data": data,
                "target_client_id": target_client_id,
                "response_to": response_to,
            },
        )

    def call_event(
        self,
        event: str,
        target_client_id: Optional[str] = None,
        _timeout: float = 5.0,
        response_to: Optional[str] = None,
        **data,
    ):
        if not target_client_id:
            raise ValueError("Server mode call_event requires target_client_id")
        return self.call_app(
            target_client_id=target_client_id,
            event=event,
            timeout=_timeout,
            response_to=response_to,
            **data,
        )

    def call_app(
        self,
        target_client_id: str,
        event: str,
        timeout: float = 5.0,
        response_to: Optional[str] = None,
        **data,
    ):
        _ensure_jsonable(data)
        request_id = self._next_request_id()
        pending: "queue.Queue[dict]" = queue.Queue()
        self._pending[request_id] = pending
        self._send_message(
            {
                "type": "call_app",
                "request_id": request_id,
                "client_id": self._client_id,
                "pool": self._pool_name,
                "payload": {
                    "target_client_id": target_client_id,
                    "event": event,
                    "data": data,
                    "response_to": response_to,
                    "timeout": timeout,
                },
            }
        )
        try:
            self._wait_for_message(request_id, timeout, {"ack"})
            if response_to and response_to != self._client_id:
                return request_id
            result = self._wait_for_message(request_id, timeout, {"app_result"})
        finally:
            self._pending.pop(request_id, None)
        payload = result.get("payload") or {}
        if payload.get("error"):
            raise ServerProtocolError(str(payload["error"]))
        return payload.get("value")

    def emit_app(
        self,
        target_client_id: str,
        event: str,
        response_to: Optional[str] = None,
        **data,
    ) -> None:
        self.emit_event(
            event=event,
            target_client_id=target_client_id,
            response_to=response_to,
            **data,
        )

    def listen(self) -> None:
        self._dispatch_enabled = True

    def stop_events(self) -> None:
        self._dispatch_enabled = False

    def event_emitter(self, namespace: str = "") -> "ServerEventEmitter":
        return ServerEventEmitter(self, namespace)

    def namespace(self, prefix: str) -> "ServerNamespacedClient":
        return ServerNamespacedClient(self, prefix)


class ServerNamespacedClient:
    """Namespaced wrapper around the server-backed LatZero client."""

    __slots__ = ("_client", "_prefix")

    def __init__(self, client: LatZero, prefix: str):
        self._client = client
        self._prefix = prefix + ":"

    def _key(self, key: str) -> str:
        return self._prefix + key

    def set(
        self,
        key: str,
        value: Any,
        auto_clean: Optional[int] = None,
        persistent: bool = False,
    ) -> None:
        self._client.set(self._key(key), value, auto_clean=auto_clean, persistent=persistent)

    def get(self, key: str, default: Any = None) -> Any:
        return self._client.get(self._key(key), default)

    def delete(self, key: str) -> bool:
        return self._client.delete(self._key(key))

    def exists(self, key: str) -> bool:
        return self._client.exists(self._key(key))

    def keys(self, pattern: Optional[str] = None) -> List[str]:
        prefix = self._prefix + (pattern or "")
        keys = self._client.keys(prefix)
        return [key[len(self._prefix):] for key in keys if key.startswith(self._prefix)]

    def mset(self, data: dict, auto_clean: Optional[int] = None, persistent: bool = False) -> None:
        for key, value in data.items():
            self.set(key, value, auto_clean=auto_clean, persistent=persistent)

    def mget(self, keys: List[str]) -> Dict[str, Any]:
        return {key: self.get(key) for key in keys}

    def increment(self, key: str, delta: int = 1) -> int:
        current = self.get(key, 0)
        if not isinstance(current, (int, float)):
            raise TypeError(f"Cannot increment non-numeric value: {type(current)}")
        updated = current + delta
        self.set(key, updated)
        return updated

    def decrement(self, key: str, delta: int = 1) -> int:
        return self.increment(key, -delta)


class ServerEventEmitter:
    """Namespaced event emitter for the server-backed client."""

    __slots__ = ("_client", "_namespace")

    def __init__(self, client: LatZero, namespace: str = ""):
        self._client = client
        self._namespace = namespace

    def _event(self, event: str) -> str:
        if not self._namespace:
            return event
        return f"{self._namespace}:{event}"

    def on(self, event: str, **options):
        return self._client.on_event(self._event(event), **options)

    def emit(self, event: str, **data) -> None:
        self._client.emit_event(self._event(event), **data)

    def call(self, event: str, target_client_id: Optional[str] = None, _timeout: float = 5.0, **data):
        return self._client.call_event(
            self._event(event),
            target_client_id=target_client_id,
            _timeout=_timeout,
            **data,
        )


# ---------------------------------------------------------------------------
# ReplicaManager — local worker pools
# ---------------------------------------------------------------------------


class ReplicaManager:
    """
    Manages local ``IncomingWorkerPool`` instances for scalable registered
    processes.  Workers are threads or OS processes inside the current
    client — no separate TCP connections.

    The server sends ``process_scale`` commands; this class translates
    them into ``IncomingWorkerPool.scale_up() / scale_down()`` calls.

    Pool lookups use the compound key ``"client_id:process_name"``
    (e.g. ``"worker-1:add"``) so that incoming ``call_app`` messages
    can be routed to the correct local worker pool.
    """

    __slots__ = ("_client", "_pools", "_lock")

    def __init__(self, client: "LatZero") -> None:
        self._client = client
        self._pools: Dict[str, "IncomingWorkerPool"] = {}
        self._lock = threading.Lock()

    def setup_pool(self, process_name: str, fn: Callable,
                   worker_kind: WorkerKind = WorkerKind.THREAD,
                   min_workers: int = 1,
                   max_workers: int = 10) -> None:
        """
        Create an ``IncomingWorkerPool`` for the given process name and
        register it so incoming ``call_app`` messages are routed here.
        """
        compound_key = f"{self._client._client_id}:{process_name}"
        with self._lock:
            if compound_key in self._pools:
                return  # already set up

        pool = IncomingWorkerPool(
            client=self._client,
            fn=fn,
            process_name=compound_key,
            pool_name=self._client._pool_name,
            worker_kind=worker_kind,
            min_workers=min_workers,
            max_workers=max_workers,
        )
        with self._lock:
            self._pools[compound_key] = pool

    def get_pool(self, compound_key: str) -> Optional["IncomingWorkerPool"]:
        """Look up a pool by its compound key (``client_id:process_name``)."""
        return self._pools.get(compound_key)

    def scale_up(self, process_name: str, count: int = 1) -> None:
        """Add workers to the pool for the given short process name."""
        compound_key = f"{self._client._client_id}:{process_name}"
        with self._lock:
            pool = self._pools.get(compound_key)
        if pool is not None:
            pool.scale_up(count)

    def scale_down(self, process_name: str, count: int = 1) -> None:
        """Remove workers from the pool for the given short process name."""
        compound_key = f"{self._client._client_id}:{process_name}"
        with self._lock:
            pool = self._pools.get(compound_key)
        if pool is not None:
            pool.scale_down(count)

    def destroy_pool(self, process_name: str) -> None:
        """Stop and remove a pool by its short process name."""
        compound_key = f"{self._client._client_id}:{process_name}"
        with self._lock:
            pool = self._pools.pop(compound_key, None)
        if pool is not None:
            pool.stop()

    def destroy_all(self) -> None:
        """Stop every pool (called during parent disconnect)."""
        with self._lock:
            pools = dict(self._pools)
            self._pools.clear()
        for pool in pools.values():
            try:
                pool.stop()
            except Exception:
                pass

    def get_all_metrics(self) -> List[dict]:
        """Aggregate metrics from every pool for the server push."""
        with self._lock:
            pools = list(self._pools.values())
        return [p.get_metrics() for p in pools]

    def check_local_autoscale(self) -> None:
        """Trigger local auto-scaling on every pool."""
        with self._lock:
            pools = list(self._pools.values())
        for p in pools:
            try:
                p.check_local_autoscale()
            except Exception:
                pass
