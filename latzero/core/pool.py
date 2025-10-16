import time
from .registry import PoolRegistry
from .memory import SharedMemoryPoolData
from ..utils.serializer import serialize, deserialize
from ..utils.exceptions import PoolNotFound, AuthenticationError
from .encryption import encrypt_data, decrypt_data

class SharedMemoryPool:
    """Main API class for managing shared memory pools."""

    def __init__(self):
        self.registry = None

    def _get_registry(self):
        if self.registry is None:
            self.registry = PoolRegistry()
        return self.registry

    def create(self, name, auth=False, auth_key='', encryption=False):
        """Create a new shared memory pool."""
        registry = self._get_registry()
        registry.add_pool(name, auth, auth_key, encryption)
        registry.inc_clients(name)  # The creator is also a client

    def connect(self, name, auth_key=''):
        """Connect to an existing shared memory pool and return a client."""
        registry = self._get_registry()
        pool_info = registry.get_pool_info(name)

        if not pool_info:
            raise PoolNotFound(f"Pool '{name}' not found")

        # Authenticate if required
        if pool_info.get('auth', False) and pool_info.get('auth_key') != auth_key:
            raise AuthenticationError("Invalid authentication key")

        registry.inc_clients(name)
        return PoolClient(registry, name, pool_info.get('encryption', False), auth_key)

class PoolClient:
    """Client for interacting with a shared memory pool."""

    def __init__(self, registry, name, encryption, auth_key):
        self.registry = registry
        self.data_key_prefix = name + ':'
        self.encryption = encryption
        self.auth_key = auth_key
        self.lock = registry.get_lock(name)
        self.name = name
        self.disconnected = False  # Flag to prevent double cleanup

        # Initialize shared memory data access
        data_shm_name = registry.get_data_shm_name(name)
        if not data_shm_name:
            raise PoolNotFound(f"Pool '{name}' data not found")
        self.pool_data = SharedMemoryPoolData(data_shm_name, encryption, auth_key if encryption else '')

    def __del__(self):
        if not self.disconnected:  # Only cleanup if not manually disconnected
            self._cleanup()

    def disconnect(self):
        """Manually disconnect from the pool, cleaning up resources."""
        if not self.disconnected:
            self._cleanup()
            self.disconnected = True

    def _cleanup(self):
        try:
            self.registry.dec_clients(self.name)
            info = self.registry.get_pool_info(self.name)
            if info and info['clients'] <= 0:  # <= 0 to ensure cleanup
                self.registry.remove_pool(self.name)
        except:
            pass

    def set(self, key, value, auto_clean=None):
        if self.disconnected:
            raise RuntimeError("Cannot set on a disconnected client")
        if not isinstance(key, str):
            raise ValueError("Key must be a string")
        from ..utils.type_checker import is_pickleable
        if not is_pickleable(value):
            raise ValueError("Value is not pickleable")

        with self.lock:
            current_time = time.time()

            # Clean expired entries for this pool
            full_key = self.data_key_prefix + key
            self.pool_data.set(full_key, value, auto_clean)

    def get(self, key):
        if self.disconnected:
            raise RuntimeError("Cannot get on a disconnected client")
        with self.lock:
            full_key = self.data_key_prefix + key
            return self.pool_data.get(full_key)
