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
]
