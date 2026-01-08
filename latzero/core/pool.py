"""
latzero.core.pool - Main API for shared memory pools.

Provides:
- SharedMemoryPool: Create and connect to pools
- PoolClient: Interact with pool data
- NamespacedClient: Key prefixing for organization
"""

import time
import os
from typing import Optional, Any, Dict, List, Callable, Iterator, Tuple
from contextlib import contextmanager

from .registry import PoolRegistry
from .memory import SharedMemoryPoolData, get_serializer
from .locking import StripedLock
from .cleanup import start_cleanup_daemon
from ..utils.exceptions import (
    PoolNotFound, 
    AuthenticationError, 
    ReadOnlyError,
    PoolDisconnectedError
)


class SharedMemoryPool:
    """
    Main API class for managing shared memory pools.
    
    Usage:
        pool_manager = SharedMemoryPool()
        pool_manager.create("myPool", auth=True, auth_key="secret")
        
        with pool_manager.connect("myPool", auth_key="secret") as ipc:
            ipc.set("key", "value")
            print(ipc.get("key"))
    """

    __slots__ = ('_registry', '_auto_cleanup')

    def __init__(self, auto_cleanup: bool = True):
        """
        Initialize pool manager.
        
        Args:
            auto_cleanup: Start background cleanup daemon automatically
        """
        self._registry: Optional[PoolRegistry] = None
        self._auto_cleanup = auto_cleanup

    def _get_registry(self) -> PoolRegistry:
        if self._registry is None:
            self._registry = PoolRegistry()
            if self._auto_cleanup:
                start_cleanup_daemon()
        return self._registry

    def create(
        self, 
        name: str, 
        auth: bool = False, 
        auth_key: str = '', 
        encryption: bool = False,
        ttl: Optional[int] = None
    ) -> None:
        """
        Create a new shared memory pool.
        
        Args:
            name: Unique pool identifier
            auth: Require authentication key to connect
            auth_key: Authentication/encryption key
            encryption: Encrypt data with AES-256
            ttl: Optional pool TTL in seconds (auto-destroy after inactivity)
        """
        registry = self._get_registry()
        created = registry.add_pool(name, auth, auth_key, encryption, ttl)
        if created:
            registry.inc_clients(name)  # Creator is first client

    def connect(
        self, 
        name: str, 
        auth_key: str = '',
        readonly: bool = False
    ) -> "PoolClient":
        """
        Connect to an existing shared memory pool.
        
        Args:
            name: Pool name
            auth_key: Authentication key (if pool requires auth)
            readonly: If True, raises error on write operations
        
        Returns:
            PoolClient for interacting with the pool
        """
        registry = self._get_registry()
        pool_info = registry.get_pool_info(name)

        if not pool_info:
            raise PoolNotFound(f"Pool '{name}' not found")

        # Authenticate if required
        if pool_info.get('auth', False):
            if pool_info.get('auth_key') != auth_key:
                raise AuthenticationError("Invalid authentication key")

        registry.inc_clients(name)
        return PoolClient(
            registry, 
            name, 
            pool_info.get('encryption', False), 
            auth_key,
            readonly=readonly
        )

    def destroy(self, name: str) -> bool:
        """
        Force destroy a pool (removes all data).
        
        Returns:
            True if pool was destroyed
        """
        registry = self._get_registry()
        return registry.remove_pool(name)

    def exists(self, name: str) -> bool:
        """Check if a pool exists."""
        registry = self._get_registry()
        return registry.get_pool_info(name) is not None

    def list_pools(self) -> Dict[str, dict]:
        """List all active pools with their metadata."""
        registry = self._get_registry()
        return registry.list_pools()

    def stats(self) -> dict:
        """Get global registry statistics."""
        registry = self._get_registry()
        return registry.get_stats()


class PoolClient:
    """
    Client for interacting with a shared memory pool.
    
    Supports context manager protocol for automatic cleanup:
        with pool.connect("myPool") as client:
            client.set("key", value)
    """

    __slots__ = (
        '_registry', '_name', '_data_key_prefix', '_encryption', '_auth_key',
        '_pool_data', '_readonly', '_disconnected', '_event_handlers'
    )

    def __init__(
        self, 
        registry: PoolRegistry, 
        name: str, 
        encryption: bool, 
        auth_key: str,
        readonly: bool = False
    ):
        self._registry = registry
        self._name = name
        self._data_key_prefix = name + ':'
        self._encryption = encryption
        self._auth_key = auth_key
        self._readonly = readonly
        self._disconnected = False
        self._event_handlers: Dict[str, List[Callable]] = {}

        # Get shared memory data access
        data_shm_name = registry.get_data_shm_name(name)
        if not data_shm_name:
            raise PoolNotFound(f"Pool '{name}' data not found")
        
        self._pool_data = SharedMemoryPoolData(
            data_shm_name, 
            encryption, 
            auth_key if encryption else ''
        )
        
        # Emit connect event
        self._emit('on_connect', self._name)

    def __enter__(self) -> "PoolClient":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        self.disconnect()
        return False

    def __del__(self):
        if not self._disconnected:
            try:
                self._cleanup()
            except Exception:
                pass

    def _check_connected(self) -> None:
        """Raise if disconnected."""
        if self._disconnected:
            raise PoolDisconnectedError("Client is disconnected")

    def _check_writable(self) -> None:
        """Raise if readonly."""
        if self._readonly:
            raise ReadOnlyError("Cannot write to readonly pool connection")

    def disconnect(self) -> None:
        """Manually disconnect from the pool."""
        if not self._disconnected:
            self._emit('on_disconnect', self._name)
            self._cleanup()
            self._disconnected = True

    def _cleanup(self) -> None:
        """Internal cleanup."""
        try:
            clients = self._registry.dec_clients(self._name)
            if clients <= 0:
                self._registry.remove_pool(self._name)
        except Exception:
            pass
        
        try:
            self._pool_data.close()
        except Exception:
            pass

    # =========== Event System ===========

    def on(self, event: str, callback: Callable) -> None:
        """
        Register an event handler.
        
        Events:
            - on_connect: Called when client connects
            - on_disconnect: Called when client disconnects
            - on_update: Called when a key is set (receives key, value)
            - on_delete: Called when a key is deleted (receives key)
        """
        if event not in self._event_handlers:
            self._event_handlers[event] = []
        self._event_handlers[event].append(callback)

    def off(self, event: str, callback: Optional[Callable] = None) -> None:
        """Remove event handler(s)."""
        if event in self._event_handlers:
            if callback:
                self._event_handlers[event] = [
                    h for h in self._event_handlers[event] if h != callback
                ]
            else:
                del self._event_handlers[event]

    def _emit(self, event: str, *args, **kwargs) -> None:
        """Emit an event to registered handlers."""
        for handler in self._event_handlers.get(event, []):
            try:
                handler(*args, **kwargs)
            except Exception:
                pass

    # =========== Core Operations ===========

    def set(self, key: str, value: Any, auto_clean: Optional[int] = None) -> None:
        """
        Set a value.
        
        Args:
            key: Key name
            value: Any pickleable/msgpack-able value
            auto_clean: Auto-expire after N seconds (None = never)
        """
        self._check_connected()
        self._check_writable()
        
        if not isinstance(key, str):
            raise ValueError("Key must be a string")

        full_key = self._data_key_prefix + key
        self._pool_data.set(full_key, value, auto_clean)
        self._emit('on_update', key, value)
        
        # Touch pool for TTL tracking
        self._registry.touch_pool(self._name)

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a value.
        
        Args:
            key: Key name
            default: Value to return if key doesn't exist
        
        Returns:
            The stored value, or default
        """
        self._check_connected()
        full_key = self._data_key_prefix + key
        result = self._pool_data.get(full_key)
        return result if result is not None else default

    def delete(self, key: str) -> bool:
        """
        Delete a key.
        
        Returns:
            True if key existed and was deleted
        """
        self._check_connected()
        self._check_writable()
        
        full_key = self._data_key_prefix + key
        deleted = self._pool_data.delete(full_key)
        if deleted:
            self._emit('on_delete', key)
        return deleted

    def exists(self, key: str) -> bool:
        """Check if a key exists."""
        self._check_connected()
        full_key = self._data_key_prefix + key
        return self._pool_data.exists(full_key)

    # =========== Atomic Operations ===========

    def increment(self, key: str, delta: int = 1) -> int:
        """
        Atomically increment a numeric value.
        
        Args:
            key: Key name
            delta: Amount to add (can be negative)
        
        Returns:
            New value after increment
        """
        self._check_connected()
        self._check_writable()
        
        current = self.get(key, 0)
        if not isinstance(current, (int, float)):
            raise TypeError(f"Cannot increment non-numeric value: {type(current)}")
        
        new_value = current + delta
        self.set(key, new_value)
        return new_value

    def decrement(self, key: str, delta: int = 1) -> int:
        """Atomically decrement a numeric value."""
        return self.increment(key, -delta)

    def append(self, key: str, value: Any) -> int:
        """
        Append to a list value.
        
        Returns:
            New list length
        """
        self._check_connected()
        self._check_writable()
        
        current = self.get(key, [])
        if not isinstance(current, list):
            raise TypeError(f"Cannot append to non-list value: {type(current)}")
        
        current.append(value)
        self.set(key, current)
        return len(current)

    def update(self, key: str, updates: dict) -> None:
        """
        Update a dict value.
        
        Args:
            key: Key name
            updates: Dict of updates to merge
        """
        self._check_connected()
        self._check_writable()
        
        current = self.get(key, {})
        if not isinstance(current, dict):
            raise TypeError(f"Cannot update non-dict value: {type(current)}")
        
        current.update(updates)
        self.set(key, current)

    # =========== Batch Operations ===========

    def mset(self, data: dict, auto_clean: Optional[int] = None) -> None:
        """
        Set multiple keys at once.
        
        Args:
            data: Dict of {key: value} pairs
            auto_clean: Auto-expire all keys after N seconds
        """
        self._check_connected()
        self._check_writable()
        
        for key, value in data.items():
            self.set(key, value, auto_clean)

    def mget(self, keys: List[str]) -> Dict[str, Any]:
        """
        Get multiple keys at once.
        
        Args:
            keys: List of keys
        
        Returns:
            Dict of {key: value} (missing keys have None)
        """
        self._check_connected()
        return {key: self.get(key) for key in keys}

    def delete_many(self, keys: List[str]) -> int:
        """
        Delete multiple keys.
        
        Returns:
            Number of keys actually deleted
        """
        self._check_connected()
        self._check_writable()
        
        count = 0
        for key in keys:
            if self.delete(key):
                count += 1
        return count

    # =========== Iterators ===========

    def keys(self, pattern: Optional[str] = None) -> List[str]:
        """
        Get all keys (optionally matching pattern prefix).
        
        Args:
            pattern: Optional prefix to filter keys
        """
        self._check_connected()
        all_keys = self._pool_data.keys_with_prefix(self._data_key_prefix)
        
        # Strip prefix
        stripped = [k[len(self._data_key_prefix):] for k in all_keys]
        
        if pattern:
            stripped = [k for k in stripped if k.startswith(pattern)]
        
        return stripped

    def values(self, pattern: Optional[str] = None) -> List[Any]:
        """Get all values (optionally for keys matching pattern)."""
        return [self.get(k) for k in self.keys(pattern)]

    def items(self, pattern: Optional[str] = None) -> List[Tuple[str, Any]]:
        """Get all (key, value) pairs."""
        return [(k, self.get(k)) for k in self.keys(pattern)]

    def scan(self, cursor: int = 0, count: int = 100) -> Tuple[int, List[str]]:
        """
        Paginated key scanning.
        
        Args:
            cursor: Starting position
            count: Max keys to return
        
        Returns:
            (next_cursor, keys) - cursor is 0 when complete
        """
        all_keys = self.keys()
        end = min(cursor + count, len(all_keys))
        next_cursor = end if end < len(all_keys) else 0
        return (next_cursor, all_keys[cursor:end])

    # =========== Pool Info ===========

    def size(self) -> int:
        """Get number of keys in this pool's namespace."""
        return len(self.keys())

    def stats(self) -> dict:
        """Get pool statistics."""
        self._check_connected()
        pool_info = self._registry.get_pool_info(self._name)
        memory_stats = self._pool_data.memory_usage()
        
        return {
            'name': self._name,
            'clients': pool_info.get('clients', 0) if pool_info else 0,
            'key_count': self.size(),
            'encryption': self._encryption,
            'readonly': self._readonly,
            **memory_stats
        }

    # =========== Namespace ===========

    def namespace(self, prefix: str) -> "NamespacedClient":
        """
        Create a namespaced view of this pool.
        
        Usage:
            users = client.namespace("users")
            users.set("123", {"name": "John"})  # Actually sets "users:123"
        """
        return NamespacedClient(self, prefix)

    @property
    def pool_name(self) -> str:
        """Get the pool name."""
        return self._name


class NamespacedClient:
    """
    A namespaced wrapper around PoolClient.
    
    All keys are automatically prefixed with the namespace.
    """

    __slots__ = ('_client', '_prefix')

    def __init__(self, client: PoolClient, prefix: str):
        self._client = client
        self._prefix = prefix + ':'

    def _prefixed(self, key: str) -> str:
        return self._prefix + key

    def set(self, key: str, value: Any, auto_clean: Optional[int] = None) -> None:
        self._client.set(self._prefixed(key), value, auto_clean)

    def get(self, key: str, default: Any = None) -> Any:
        return self._client.get(self._prefixed(key), default)

    def delete(self, key: str) -> bool:
        return self._client.delete(self._prefixed(key))

    def exists(self, key: str) -> bool:
        return self._client.exists(self._prefixed(key))

    def keys(self, pattern: Optional[str] = None) -> List[str]:
        full_pattern = self._prefix + (pattern or '')
        all_keys = self._client.keys(full_pattern)
        return [k[len(self._prefix):] for k in all_keys if k.startswith(self._prefix)]

    def increment(self, key: str, delta: int = 1) -> int:
        return self._client.increment(self._prefixed(key), delta)

    def decrement(self, key: str, delta: int = 1) -> int:
        return self._client.decrement(self._prefixed(key), delta)

    def mset(self, data: dict, auto_clean: Optional[int] = None) -> None:
        prefixed = {self._prefixed(k): v for k, v in data.items()}
        self._client.mset(prefixed, auto_clean)

    def mget(self, keys: List[str]) -> Dict[str, Any]:
        prefixed_keys = [self._prefixed(k) for k in keys]
        result = self._client.mget(prefixed_keys)
        return {k: result.get(self._prefixed(k)) for k in keys}
