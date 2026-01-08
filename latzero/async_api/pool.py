"""
latzero.async_api - Async/await API for shared memory pools.

Provides asyncio-compatible wrappers around the synchronous API.
Uses asyncio.to_thread() for non-blocking operations.
"""

import asyncio
from typing import Optional, Any, Dict, List, Tuple, Callable
from functools import wraps

from ..core.pool import SharedMemoryPool, PoolClient, NamespacedClient


def _async_wrapper(sync_method):
    """Decorator to wrap sync methods in asyncio.to_thread."""
    @wraps(sync_method)
    async def wrapper(*args, **kwargs):
        return await asyncio.to_thread(sync_method, *args, **kwargs)
    return wrapper


class AsyncPoolClient:
    """
    Async wrapper around PoolClient.
    
    All operations are non-blocking using asyncio.to_thread().
    
    Usage:
        async with pool.connect("myPool") as client:
            await client.set("key", "value")
            value = await client.get("key")
    """

    __slots__ = ('_client',)

    def __init__(self, client: PoolClient):
        self._client = client

    async def __aenter__(self) -> "AsyncPoolClient":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        await self.disconnect()
        return False

    # =========== Event System ===========

    def on(self, event: str, callback: Callable) -> None:
        """Register an event handler (sync callback)."""
        self._client.on(event, callback)

    def off(self, event: str, callback: Optional[Callable] = None) -> None:
        """Remove event handler(s)."""
        self._client.off(event, callback)

    # =========== Core Operations ===========

    async def set(self, key: str, value: Any, auto_clean: Optional[int] = None) -> None:
        """Set a value (non-blocking)."""
        await asyncio.to_thread(self._client.set, key, value, auto_clean)

    async def get(self, key: str, default: Any = None) -> Any:
        """Get a value (non-blocking)."""
        return await asyncio.to_thread(self._client.get, key, default)

    async def delete(self, key: str) -> bool:
        """Delete a key (non-blocking)."""
        return await asyncio.to_thread(self._client.delete, key)

    async def exists(self, key: str) -> bool:
        """Check if key exists (non-blocking)."""
        return await asyncio.to_thread(self._client.exists, key)

    async def disconnect(self) -> None:
        """Disconnect from pool (non-blocking)."""
        await asyncio.to_thread(self._client.disconnect)

    # =========== Atomic Operations ===========

    async def increment(self, key: str, delta: int = 1) -> int:
        """Atomically increment a numeric value."""
        return await asyncio.to_thread(self._client.increment, key, delta)

    async def decrement(self, key: str, delta: int = 1) -> int:
        """Atomically decrement a numeric value."""
        return await asyncio.to_thread(self._client.decrement, key, delta)

    async def append(self, key: str, value: Any) -> int:
        """Append to a list value."""
        return await asyncio.to_thread(self._client.append, key, value)

    async def update(self, key: str, updates: dict) -> None:
        """Update a dict value."""
        await asyncio.to_thread(self._client.update, key, updates)

    # =========== Batch Operations ===========

    async def mset(self, data: dict, auto_clean: Optional[int] = None) -> None:
        """Set multiple keys at once."""
        await asyncio.to_thread(self._client.mset, data, auto_clean)

    async def mget(self, keys: List[str]) -> Dict[str, Any]:
        """Get multiple keys at once."""
        return await asyncio.to_thread(self._client.mget, keys)

    async def delete_many(self, keys: List[str]) -> int:
        """Delete multiple keys."""
        return await asyncio.to_thread(self._client.delete_many, keys)

    # =========== Iterators ===========

    async def keys(self, pattern: Optional[str] = None) -> List[str]:
        """Get all keys."""
        return await asyncio.to_thread(self._client.keys, pattern)

    async def values(self, pattern: Optional[str] = None) -> List[Any]:
        """Get all values."""
        return await asyncio.to_thread(self._client.values, pattern)

    async def items(self, pattern: Optional[str] = None) -> List[Tuple[str, Any]]:
        """Get all (key, value) pairs."""
        return await asyncio.to_thread(self._client.items, pattern)

    async def scan(self, cursor: int = 0, count: int = 100) -> Tuple[int, List[str]]:
        """Paginated key scanning."""
        return await asyncio.to_thread(self._client.scan, cursor, count)

    # =========== Info ===========

    async def size(self) -> int:
        """Get number of keys."""
        return await asyncio.to_thread(self._client.size)

    async def stats(self) -> dict:
        """Get pool statistics."""
        return await asyncio.to_thread(self._client.stats)

    def namespace(self, prefix: str) -> "AsyncNamespacedClient":
        """Create a namespaced view."""
        return AsyncNamespacedClient(self._client.namespace(prefix))

    @property
    def pool_name(self) -> str:
        """Get the pool name."""
        return self._client.pool_name


class AsyncNamespacedClient:
    """Async wrapper around NamespacedClient."""

    __slots__ = ('_ns_client',)

    def __init__(self, ns_client: NamespacedClient):
        self._ns_client = ns_client

    async def set(self, key: str, value: Any, auto_clean: Optional[int] = None) -> None:
        await asyncio.to_thread(self._ns_client.set, key, value, auto_clean)

    async def get(self, key: str, default: Any = None) -> Any:
        return await asyncio.to_thread(self._ns_client.get, key, default)

    async def delete(self, key: str) -> bool:
        return await asyncio.to_thread(self._ns_client.delete, key)

    async def exists(self, key: str) -> bool:
        return await asyncio.to_thread(self._ns_client.exists, key)

    async def keys(self, pattern: Optional[str] = None) -> List[str]:
        return await asyncio.to_thread(self._ns_client.keys, pattern)

    async def increment(self, key: str, delta: int = 1) -> int:
        return await asyncio.to_thread(self._ns_client.increment, key, delta)

    async def decrement(self, key: str, delta: int = 1) -> int:
        return await asyncio.to_thread(self._ns_client.decrement, key, delta)

    async def mset(self, data: dict, auto_clean: Optional[int] = None) -> None:
        await asyncio.to_thread(self._ns_client.mset, data, auto_clean)

    async def mget(self, keys: List[str]) -> Dict[str, Any]:
        return await asyncio.to_thread(self._ns_client.mget, keys)


class AsyncSharedMemoryPool:
    """
    Async-compatible SharedMemoryPool.
    
    Usage:
        pool = AsyncSharedMemoryPool()
        await pool.create("myPool")
        async with await pool.connect("myPool") as client:
            await client.set("key", "value")
    """

    __slots__ = ('_pool',)

    def __init__(self, auto_cleanup: bool = True):
        self._pool = SharedMemoryPool(auto_cleanup=auto_cleanup)

    async def create(
        self, 
        name: str, 
        auth: bool = False, 
        auth_key: str = '', 
        encryption: bool = False,
        ttl: Optional[int] = None
    ) -> None:
        """Create a new pool."""
        await asyncio.to_thread(
            self._pool.create, name, auth, auth_key, encryption, ttl
        )

    async def connect(
        self, 
        name: str, 
        auth_key: str = '',
        readonly: bool = False
    ) -> AsyncPoolClient:
        """Connect to a pool and return an async client."""
        client = await asyncio.to_thread(
            self._pool.connect, name, auth_key, readonly
        )
        return AsyncPoolClient(client)

    async def destroy(self, name: str) -> bool:
        """Destroy a pool."""
        return await asyncio.to_thread(self._pool.destroy, name)

    async def exists(self, name: str) -> bool:
        """Check if pool exists."""
        return await asyncio.to_thread(self._pool.exists, name)

    async def list_pools(self) -> Dict[str, dict]:
        """List all pools."""
        return await asyncio.to_thread(self._pool.list_pools)

    async def stats(self) -> dict:
        """Get global stats."""
        return await asyncio.to_thread(self._pool.stats)
