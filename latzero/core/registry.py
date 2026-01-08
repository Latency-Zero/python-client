import multiprocessing.shared_memory as shm
import json
import os
import struct
from multiprocessing import Lock
import tempfile
import time

class PoolRegistry:
    """Global Pool Index Table for tracking active pools using shared memory."""

    REGISTRY_SIZE = 1024 * 1024  # 1MB for registry metadata
    REGISTRY_NAME = "latzero_registry"

    def __init__(self):
        # Try to connect to existing registry, or create new one
        self._init_registry()
        self._load_registry()
        self._locks = {}  # name: Lock (locks are per-process)

    def _init_registry(self):
        """Initialize or connect to the global registry shared memory."""
        try:
            # Try to connect to existing registry
            self.shm = shm.SharedMemory(name=self.REGISTRY_NAME, create=False)
            self.is_creator = False
        except FileNotFoundError:
            # Create new registry
            try:
                self.shm = shm.SharedMemory(name=self.REGISTRY_NAME, create=True, size=self.REGISTRY_SIZE)
                self.is_creator = True
                # Initialize with empty registry
                data = {'pools': {}, 'pools_data_keys': {}}
                self._write_registry_data(json.dumps(data).encode('utf-8'))
            except Exception:
                # Fallback if creation fails
                raise RuntimeError("Could not create or connect to shared memory registry")

    def _write_registry_data(self, data: bytes):
        """Write data to registry with length prefix."""
        if len(data) > self.REGISTRY_SIZE - 8:
            raise ValueError("Registry data too large")
        length = struct.pack('Q', len(data))  # 8-byte unsigned long
        self.shm.buf[:8] = length
        self.shm.buf[8:8+len(data)] = data

    def _read_registry_data(self) -> dict:
        """Read data from registry."""
        length = struct.unpack('Q', bytes(self.shm.buf[:8]))[0]
        if length == 0:
            return {'pools': {}, 'pools_data_keys': {}}
        data = bytes(self.shm.buf[8:8+length]).decode('utf-8')
        return json.loads(data)

    def _load_registry(self):
        """Load registry state into memory for faster access."""
        self._registry_data = self._read_registry_data()

    def _save_registry(self):
        """Save registry state to shared memory."""
        try:
            self._write_registry_data(json.dumps(self._registry_data).encode('utf-8'))
        except Exception:
            # If save fails, try to reload to ensure consistency
            self._load_registry()

    def add_pool(self, name, auth, auth_key, encryption):
        """Add a new pool to the registry."""
        if name in self._registry_data['pools']:
            return

        self._registry_data['pools'][name] = {
            'auth': auth,
            'auth_key': auth_key,
            'encryption': encryption,
            'clients': 0,
            'created': time.time()
        }
        self._registry_data['pools_data_keys'][name] = f"l0p_{name}"
        self._save_registry()

    def get_pool_info(self, name):
        """Get pool information by name."""
        self._load_registry()  # Refresh from shared memory
        return self._registry_data['pools'].get(name)

    def inc_clients(self, name):
        """Increment client count for the pool."""
        self._load_registry()
        if name in self._registry_data['pools']:
            self._registry_data['pools'][name]['clients'] += 1
            self._save_registry()

    def dec_clients(self, name):
        """Decrement client count for the pool."""
        self._load_registry()
        if name in self._registry_data['pools']:
            self._registry_data['pools'][name]['clients'] -= 1
            self._save_registry()

    def get_lock(self, name):
        """Get the lock for the pool (locks are per-process)."""
        if name not in self._locks:
            self._locks[name] = Lock()
        return self._locks[name]

    def remove_pool(self, name):
        """Remove pool from registry."""
        if name in self._registry_data['pools']:
            data_key = self._registry_data['pools_data_keys'].get(name)
            del self._registry_data['pools'][name]
            if data_key in self._registry_data['pools_data_keys']:
                del self._registry_data['pools_data_keys'][name]
            self._save_registry()

            # Try to clean up shared memory for this pool
            try:
                pool_shm = shm.SharedMemory(name=data_key)
                pool_shm.close()
                pool_shm.unlink()
            except:
                pass

    def get_data_shm_name(self, pool_name):
        """Get the shared memory name for pool data."""
        self._load_registry()
        return self._registry_data['pools_data_keys'].get(pool_name)

    def __del__(self):
        """Cleanup registry shared memory if we're the creator."""
        try:
            if hasattr(self, 'shm') and self.shm is not None:
                self.shm.close()
                if getattr(self, 'is_creator', False):
                    self.shm.unlink()
        except:
            pass
