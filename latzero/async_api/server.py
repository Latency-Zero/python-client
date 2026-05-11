"""
Async wrappers for the server-backed LatZero client.
"""

import asyncio
from typing import Any, Dict, List, Optional, Tuple

from ..server_client import LatZero, ServerNamespacedClient


class AsyncLatZero:
    """Async wrapper around the server-backed LatZero client."""

    __slots__ = ("_client",)

    def __init__(
        self,
        dsn: str,
        pool: str,
        auth_token: Optional[str] = None,
        host: str = "127.0.0.1",
        port: int = 14130,
        timeout: float = 5.0,
    ):
        self._client = LatZero(
            dsn=dsn,
            pool=pool,
            auth_token=auth_token,
            host=host,
            port=port,
            timeout=timeout,
        )

    async def __aenter__(self) -> "AsyncLatZero":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        await self.disconnect()
        return False

    async def switch_pool(self, pool: str, auth_token: Optional[str] = None, timeout: float = 5.0) -> None:
        await asyncio.to_thread(self._client.switch_pool, pool, auth_token, timeout)

    async def disconnect(self) -> None:
        await asyncio.to_thread(self._client.disconnect)

    async def set(
        self,
        key: str,
        value: Any,
        auto_clean: Optional[int] = None,
        persistent: bool = False,
    ) -> None:
        await asyncio.to_thread(self._client.set, key, value, auto_clean, persistent)

    async def get(self, key: str, default: Any = None) -> Any:
        return await asyncio.to_thread(self._client.get, key, default)

    async def delete(self, key: str) -> bool:
        return await asyncio.to_thread(self._client.delete, key)

    async def exists(self, key: str) -> bool:
        return await asyncio.to_thread(self._client.exists, key)

    async def keys(self, pattern: Optional[str] = None) -> List[str]:
        return await asyncio.to_thread(self._client.keys, pattern)

    async def mset(self, data: dict, auto_clean: Optional[int] = None, persistent: bool = False) -> None:
        await asyncio.to_thread(self._client.mset, data, auto_clean, persistent)

    async def mget(self, keys: List[str]) -> Dict[str, Any]:
        return await asyncio.to_thread(self._client.mget, keys)

    async def delete_many(self, keys: List[str]) -> int:
        return await asyncio.to_thread(self._client.delete_many, keys)

    async def scan(self, cursor: int = 0, count: int = 100) -> Tuple[int, List[str]]:
        return await asyncio.to_thread(self._client.scan, cursor, count)

    async def subscribe_buffer(self, key: str) -> None:
        await asyncio.to_thread(self._client.subscribe_buffer, key)

    async def unsubscribe_buffer(self, key: str) -> None:
        await asyncio.to_thread(self._client.unsubscribe_buffer, key)

    async def call_app(
        self,
        target_client_id: str,
        event: str,
        timeout: float = 5.0,
        response_to: Optional[str] = None,
        **data,
    ):
        return await asyncio.to_thread(
            self._client.call_app,
            target_client_id,
            event,
            timeout,
            response_to,
            **data,
        )

    async def emit_app(self, target_client_id: str, event: str, response_to: Optional[str] = None, **data) -> None:
        await asyncio.to_thread(self._client.emit_app, target_client_id, event, response_to, **data)

    def on(self, event: str, callback) -> None:
        self._client.on(event, callback)

    def off(self, event: str, callback=None) -> None:
        self._client.off(event, callback)

    def on_event(self, event: str, **options):
        return self._client.on_event(event, **options)

    def listen(self) -> None:
        self._client.listen()

    def stop_events(self) -> None:
        self._client.stop_events()

    def namespace(self, prefix: str) -> "AsyncServerNamespacedClient":
        return AsyncServerNamespacedClient(self._client.namespace(prefix))


class AsyncServerNamespacedClient:
    """Async wrapper around ServerNamespacedClient."""

    __slots__ = ("_client",)

    def __init__(self, client: ServerNamespacedClient):
        self._client = client

    async def set(
        self,
        key: str,
        value: Any,
        auto_clean: Optional[int] = None,
        persistent: bool = False,
    ) -> None:
        await asyncio.to_thread(self._client.set, key, value, auto_clean, persistent)

    async def get(self, key: str, default: Any = None) -> Any:
        return await asyncio.to_thread(self._client.get, key, default)

    async def delete(self, key: str) -> bool:
        return await asyncio.to_thread(self._client.delete, key)

    async def exists(self, key: str) -> bool:
        return await asyncio.to_thread(self._client.exists, key)

    async def keys(self, pattern: Optional[str] = None) -> List[str]:
        return await asyncio.to_thread(self._client.keys, pattern)
