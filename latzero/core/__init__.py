"""
latzero.core - Core components for shared memory pool management.
"""

from .pool import SharedMemoryPool, PoolClient, NamespacedClient
from .memory import SharedMemoryPoolData, configure_serializer, get_serializer
from .registry import PoolRegistry
from .locking import FileLock, StripedLock, ReadWriteLock, get_registry_lock
from .cleanup import (
    CleanupDaemon, 
    start_cleanup_daemon, 
    stop_cleanup_daemon,
    cleanup_orphaned_memory
)
from .events import EventEmitter, EventManager
from .events_types import EventError, EventTimeout, EventMode
from .events_metrics import EventMetrics, get_pool_event_health

__all__ = [
    # Main API
    'SharedMemoryPool',
    'PoolClient',
    'NamespacedClient',
    
    # Memory
    'SharedMemoryPoolData',
    'configure_serializer',
    'get_serializer',
    
    # Registry
    'PoolRegistry',
    
    # Locking
    'FileLock',
    'StripedLock',
    'ReadWriteLock',
    'get_registry_lock',
    
    # Cleanup
    'CleanupDaemon',
    'start_cleanup_daemon',
    'stop_cleanup_daemon',
    'cleanup_orphaned_memory',
    
    # Events
    'EventEmitter',
    'EventManager',
    'EventError',
    'EventTimeout',
    'EventMode',
    'EventMetrics',
    'get_pool_event_health',
]
