"""
latzero.core.registry - Global Pool Index Table with inter-process safety.

Tracks all active pools using a shared memory segment with proper locking.
"""

import multiprocessing.shared_memory as shm
import json
import struct
import time
from typing import Dict, Optional, Any

from .locking import get_registry_lock, FileLock


class PoolRegistry:
    """
    Global Pool Index Table for tracking active pools using shared memory.
    
    Thread-safe AND process-safe through FileLock-based synchronization.
    """

    REGISTRY_SIZE = 1024 * 1024  # 1MB for registry metadata
    REGISTRY_NAME = "latzero_registry"

    __slots__ = ('shm', 'is_creator', '_registry_data', '_lock')

    def __init__(self):
        self._lock = get_registry_lock()
        self._init_registry()
        self._registry_data: Dict[str, Any] = {}

    def _init_registry(self) -> None:
        """Initialize or connect to the global registry shared memory."""
        with self._lock:
            try:
                # Try to connect to existing registry
                self.shm = shm.SharedMemory(name=self.REGISTRY_NAME, create=False)
                self.is_creator = False
            except FileNotFoundError:
                # Create new registry
                try:
                    self.shm = shm.SharedMemory(
                        name=self.REGISTRY_NAME, 
                        create=True, 
                        size=self.REGISTRY_SIZE
                    )
                    self.is_creator = True
                    # Initialize with empty registry
                    data = {'pools': {}, 'pools_data_keys': {}}
                    self._write_registry_data_unsafe(json.dumps(data).encode('utf-8'))
                except FileExistsError:
                    # Race condition: another process created it
                    self.shm = shm.SharedMemory(name=self.REGISTRY_NAME, create=False)
                    self.is_creator = False
                except Exception as e:
                    raise RuntimeError(f"Could not create or connect to shared memory registry: {e}")

    def _write_registry_data_unsafe(self, data: bytes) -> None:
        """Write data to registry with length prefix. MUST hold lock."""
        if len(data) > self.REGISTRY_SIZE - 8:
            raise ValueError("Registry data too large")
        length = struct.pack('Q', len(data))  # 8-byte unsigned long
        self.shm.buf[:8] = length
        self.shm.buf[8:8+len(data)] = data

    def _read_registry_data_unsafe(self) -> dict:
        """Read data from registry. MUST hold lock."""
        length = struct.unpack('Q', bytes(self.shm.buf[:8]))[0]
        if length == 0:
            return {'pools': {}, 'pools_data_keys': {}}
        data = bytes(self.shm.buf[8:8+length]).decode('utf-8')
        return json.loads(data)

    def _load_registry(self) -> None:
        """Load registry state into memory (acquires lock)."""
        with self._lock:
            self._registry_data = self._read_registry_data_unsafe()

    def _save_registry(self) -> None:
        """Save registry state to shared memory (acquires lock)."""
        with self._lock:
            try:
                self._write_registry_data_unsafe(json.dumps(self._registry_data).encode('utf-8'))
            except Exception:
                # If save fails, reload to ensure consistency
                self._registry_data = self._read_registry_data_unsafe()
                raise

    def _atomic_update(self, update_fn) -> Any:
        """
        Atomically read, update, and write registry.
        
        Args:
            update_fn: Function that takes registry_data dict and returns result
        
        Returns:
            Result of update_fn
        """
        with self._lock:
            self._registry_data = self._read_registry_data_unsafe()
            result = update_fn(self._registry_data)
            self._write_registry_data_unsafe(json.dumps(self._registry_data).encode('utf-8'))
            return result

    def add_pool(
        self, 
        name: str, 
        auth: bool, 
        auth_key: str, 
        encryption: bool,
        ttl: Optional[int] = None
    ) -> bool:
        """
        Add a new pool to the registry.
        
        Args:
            name: Pool name
            auth: Whether authentication is required
            auth_key: Authentication key
            encryption: Whether encryption is enabled
            ttl: Optional time-to-live in seconds
        
        Returns:
            True if pool was created, False if it already exists
        """
        def update(data):
            if name in data['pools']:
                return False
            
            data['pools'][name] = {
                'auth': auth,
                'auth_key': auth_key,
                'encryption': encryption,
                'clients': 0,
                'created': time.time(),
                'last_activity': time.time(),
                'ttl': ttl
            }
            data['pools_data_keys'][name] = f"l0p_{name}"
            return True
        
        return self._atomic_update(update)

    def get_pool_info(self, name: str) -> Optional[dict]:
        """Get pool information by name."""
        self._load_registry()
        return self._registry_data['pools'].get(name)

    def inc_clients(self, name: str) -> int:
        """
        Increment client count for the pool.
        
        Returns:
            New client count, or -1 if pool doesn't exist
        """
        def update(data):
            if name not in data['pools']:
                return -1
            data['pools'][name]['clients'] += 1
            data['pools'][name]['last_activity'] = time.time()
            return data['pools'][name]['clients']
        
        return self._atomic_update(update)

    def dec_clients(self, name: str) -> int:
        """
        Decrement client count for the pool.
        
        Returns:
            New client count, or -1 if pool doesn't exist
        """
        def update(data):
            if name not in data['pools']:
                return -1
            data['pools'][name]['clients'] = max(0, data['pools'][name]['clients'] - 1)
            data['pools'][name]['last_activity'] = time.time()
            return data['pools'][name]['clients']
        
        return self._atomic_update(update)

    def remove_pool(self, name: str) -> bool:
        """
        Remove pool from registry and cleanup its shared memory.
        
        Returns:
            True if pool was removed, False if it didn't exist
        """
        def update(data):
            if name not in data['pools']:
                return None
            
            data_key = data['pools_data_keys'].get(name)
            del data['pools'][name]
            if name in data['pools_data_keys']:
                del data['pools_data_keys'][name]
            return data_key
        
        data_key = self._atomic_update(update)
        
        if data_key:
            # Try to clean up shared memory for this pool
            try:
                pool_shm = shm.SharedMemory(name=data_key)
                pool_shm.close()
                pool_shm.unlink()
            except Exception:
                pass
            return True
        return False

    def get_data_shm_name(self, pool_name: str) -> Optional[str]:
        """Get the shared memory name for pool data."""
        self._load_registry()
        return self._registry_data['pools_data_keys'].get(pool_name)

    def list_pools(self) -> Dict[str, dict]:
        """List all active pools with their info."""
        self._load_registry()
        return dict(self._registry_data['pools'])

    def get_stats(self) -> dict:
        """
        Get registry statistics.
        
        Returns:
            Dict with pool_count, total_clients, oldest_pool, etc.
        """
        self._load_registry()
        pools = self._registry_data['pools']
        
        if not pools:
            return {
                'pool_count': 0,
                'total_clients': 0,
                'oldest_pool': None,
                'newest_pool': None
            }
        
        total_clients = sum(p['clients'] for p in pools.values())
        oldest = min(pools.items(), key=lambda x: x[1]['created'])
        newest = max(pools.items(), key=lambda x: x[1]['created'])
        
        return {
            'pool_count': len(pools),
            'total_clients': total_clients,
            'oldest_pool': oldest[0],
            'newest_pool': newest[0],
            'pools': list(pools.keys())
        }

    def cleanup_expired_pools(self) -> list:
        """
        Remove pools that have exceeded their TTL.
        
        Returns:
            List of removed pool names
        """
        current_time = time.time()
        removed = []
        
        def update(data):
            to_remove = []
            for name, info in list(data['pools'].items()):
                ttl = info.get('ttl')
                if ttl is not None:
                    elapsed = current_time - info['last_activity']
                    if elapsed > ttl and info['clients'] <= 0:
                        to_remove.append(name)
            
            for name in to_remove:
                data_key = data['pools_data_keys'].get(name)
                del data['pools'][name]
                if name in data['pools_data_keys']:
                    del data['pools_data_keys'][name]
                removed.append((name, data_key))
            
            return to_remove
        
        self._atomic_update(update)
        
        # Cleanup shared memory outside the lock
        for name, data_key in removed:
            if data_key:
                try:
                    pool_shm = shm.SharedMemory(name=data_key)
                    pool_shm.close()
                    pool_shm.unlink()
                except Exception:
                    pass
        
        return [name for name, _ in removed]

    def touch_pool(self, name: str) -> bool:
        """
        Update last_activity timestamp for a pool.
        
        Returns:
            True if pool exists and was touched
        """
        def update(data):
            if name not in data['pools']:
                return False
            data['pools'][name]['last_activity'] = time.time()
            return True
        
        return self._atomic_update(update)

    def __del__(self):
        """Cleanup registry shared memory if we're the creator and no pools remain."""
        try:
            if hasattr(self, 'shm') and self.shm is not None:
                self.shm.close()
                # Only unlink if we're creator AND no pools exist
                if getattr(self, 'is_creator', False):
                    try:
                        with self._lock:
                            data = self._read_registry_data_unsafe()
                            if not data['pools']:
                                self.shm.unlink()
                    except Exception:
                        pass
        except Exception:
            pass
