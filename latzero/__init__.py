"""
latzero - Zero-latency, zero-fuss shared memory for Python.

Dynamic, encrypted, and insanely fast inter-process communication.

Usage:
    from latzero import SharedMemoryPool
    
    pool = SharedMemoryPool()
    pool.create("myPool")
    
    with pool.connect("myPool") as client:
        client.set("key", "value")
        print(client.get("key"))
"""

__version__ = '0.2.0'
__author__ = 'BRAHMAI'

# Core API
from .core.pool import SharedMemoryPool, PoolClient, NamespacedClient
from .core.memory import configure_serializer, get_serializer
from .core.cleanup import start_cleanup_daemon, stop_cleanup_daemon, cleanup_orphaned_memory

# Events API
from .core.events import EventEmitter
from .core.events_types import EventError, EventTimeout, EventMode
from .core.events_metrics import EventMetrics

# Async API
from .async_api import AsyncSharedMemoryPool, AsyncPoolClient

# Persistence
from .persistence import PoolSnapshot, save_pool_snapshot, load_pool_snapshot

# Utilities
from .utils import configure_logging, get_logger
from .utils.exceptions import (
    LatzeroError,
    PoolNotFound,
    PoolExistsError,
    AuthenticationError,
    EncryptionError,
    MemoryFullError,
    ReadOnlyError,
    PoolDisconnectedError,
)

__all__ = [
    # Version
    '__version__',
    '__author__',
    
    # Core API
    'SharedMemoryPool',
    'PoolClient',
    'NamespacedClient',
    'configure_serializer',
    'get_serializer',
    
    # Cleanup
    'start_cleanup_daemon',
    'stop_cleanup_daemon',
    'cleanup_orphaned_memory',
    
    # Events API
    'EventEmitter',
    'EventError',
    'EventTimeout',
    'EventMode',
    'EventMetrics',
    
    # Async API
    'AsyncSharedMemoryPool',
    'AsyncPoolClient',
    
    # Persistence
    'PoolSnapshot',
    'save_pool_snapshot',
    'load_pool_snapshot',
    
    # Logging
    'configure_logging',
    'get_logger',
    
    # Exceptions
    'LatzeroError',
    'PoolNotFound',
    'PoolExistsError',
    'AuthenticationError',
    'EncryptionError',
    'MemoryFullError',
    'ReadOnlyError',
    'PoolDisconnectedError',
]
