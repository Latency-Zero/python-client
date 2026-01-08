"""
latzero.core.cleanup - Auto-cleanup daemon for pools and entries.

Monitors pools for:
- Expired entries (auto_clean)
- Dead client processes
- Orphaned shared memory segments
- TTL-based pool expiration
"""

import threading
import time
import os
import sys
from typing import Optional, Set, Callable, List

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


class CleanupDaemon:
    """
    Background daemon for automatic cleanup of:
    - Expired entries in pools (auto_clean)
    - Pools with TTL exceeded
    - Orphaned shared memory (dead processes)
    
    Runs as a daemon thread - stops when main process exits.
    """
    
    __slots__ = (
        '_running', '_thread', '_interval', '_registry',
        '_on_cleanup', '_known_pids'
    )
    
    def __init__(
        self, 
        interval: float = 10.0,
        on_cleanup: Optional[Callable[[str, str], None]] = None
    ):
        """
        Initialize cleanup daemon.
        
        Args:
            interval: Seconds between cleanup cycles
            on_cleanup: Callback(pool_name, reason) when cleanup happens
        """
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._interval = interval
        self._registry = None  # Lazy import to avoid circular
        self._on_cleanup = on_cleanup
        self._known_pids: Set[int] = set()
    
    @property
    def is_running(self) -> bool:
        return self._running
    
    def start(self) -> None:
        """Start the cleanup daemon."""
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
    
    def stop(self, timeout: float = 5.0) -> None:
        """Stop the cleanup daemon."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)
            self._thread = None
    
    def _get_registry(self):
        """Lazy import registry to avoid circular imports."""
        if self._registry is None:
            from .registry import PoolRegistry
            self._registry = PoolRegistry()
        return self._registry
    
    def _run(self) -> None:
        """Main cleanup loop."""
        while self._running:
            try:
                self._cleanup_cycle()
            except Exception as e:
                # Log but don't crash daemon
                pass
            
            # Sleep in small increments for responsive shutdown
            for _ in range(int(self._interval * 10)):
                if not self._running:
                    break
                time.sleep(0.1)
    
    def _cleanup_cycle(self) -> None:
        """Run one cleanup cycle."""
        registry = self._get_registry()
        
        # 1. Cleanup expired TTL pools
        expired_pools = registry.cleanup_expired_pools()
        for pool_name in expired_pools:
            self._notify_cleanup(pool_name, 'ttl_expired')
        
        # 2. Cleanup expired entries in active pools
        self._cleanup_expired_entries(registry)
        
        # 3. Detect dead processes and cleanup orphaned pools
        if HAS_PSUTIL:
            self._cleanup_orphaned_pools(registry)
    
    def _cleanup_expired_entries(self, registry) -> None:
        """Cleanup auto_clean entries in all pools."""
        from .memory import SharedMemoryPoolData
        
        pools = registry.list_pools()
        for pool_name, info in pools.items():
            try:
                data_shm_name = registry.get_data_shm_name(pool_name)
                if data_shm_name:
                    pool_data = SharedMemoryPoolData(
                        data_shm_name,
                        encryption=info.get('encryption', False),
                        auth_key=info.get('auth_key', '')
                    )
                    removed = pool_data.cleanup_expired()
                    if removed > 0:
                        self._notify_cleanup(pool_name, f'entries_expired:{removed}')
                    pool_data.close()
            except Exception:
                pass
    
    def _cleanup_orphaned_pools(self, registry) -> None:
        """
        Detect pools with dead client processes and clean them up.
        
        Uses psutil to check if PIDs are still alive.
        """
        if not HAS_PSUTIL:
            return
        
        pools = registry.list_pools()
        current_pids = set(p.pid for p in psutil.process_iter(['pid']))
        
        for pool_name, info in pools.items():
            # If pool has clients but no activity for too long, check if processes are alive
            if info['clients'] > 0:
                last_activity = info.get('last_activity', info['created'])
                idle_time = time.time() - last_activity
                
                # If idle for more than 60 seconds with clients, suspicious
                if idle_time > 60:
                    # Force cleanup if clients count seems stale
                    # This handles cases where a process crashed without cleanup
                    registry.remove_pool(pool_name)
                    self._notify_cleanup(pool_name, 'orphaned_clients')
    
    def _notify_cleanup(self, pool_name: str, reason: str) -> None:
        """Notify about cleanup via callback."""
        if self._on_cleanup:
            try:
                self._on_cleanup(pool_name, reason)
            except Exception:
                pass


# Global daemon instance (singleton)
_daemon: Optional[CleanupDaemon] = None
_daemon_lock = threading.Lock()


def get_cleanup_daemon() -> CleanupDaemon:
    """Get or create the global cleanup daemon."""
    global _daemon
    with _daemon_lock:
        if _daemon is None:
            _daemon = CleanupDaemon()
        return _daemon


def start_cleanup_daemon(
    interval: float = 10.0,
    on_cleanup: Optional[Callable[[str, str], None]] = None
) -> CleanupDaemon:
    """
    Start the global cleanup daemon.
    
    Args:
        interval: Seconds between cleanup cycles
        on_cleanup: Callback(pool_name, reason) when cleanup happens
    
    Returns:
        The daemon instance
    """
    global _daemon
    with _daemon_lock:
        if _daemon is None:
            _daemon = CleanupDaemon(interval=interval, on_cleanup=on_cleanup)
        _daemon.start()
        return _daemon


def stop_cleanup_daemon() -> None:
    """Stop the global cleanup daemon."""
    global _daemon
    with _daemon_lock:
        if _daemon:
            _daemon.stop()


def cleanup_orphaned_memory() -> List[str]:
    """
    Find and cleanup orphaned shared memory segments.
    
    This is a more aggressive cleanup that looks for any latzero
    shared memory segments that aren't in the registry.
    
    Returns:
        List of cleaned segment names
    """
    import multiprocessing.shared_memory as shm
    from .registry import PoolRegistry
    
    cleaned = []
    registry = PoolRegistry()
    known_segments = set()
    
    # Get all known segment names from registry
    known_segments.add(registry.REGISTRY_NAME)
    for pool_name, info in registry.list_pools().items():
        data_key = registry.get_data_shm_name(pool_name)
        if data_key:
            known_segments.add(data_key)
    
    # On Windows, we can't easily enumerate shared memory segments
    # On Linux, we can look in /dev/shm
    if sys.platform != 'win32':
        import os
        shm_dir = '/dev/shm'
        if os.path.exists(shm_dir):
            for name in os.listdir(shm_dir):
                if name.startswith('l0p_') or name.startswith('latzero'):
                    if name not in known_segments:
                        try:
                            orphan = shm.SharedMemory(name=name)
                            orphan.close()
                            orphan.unlink()
                            cleaned.append(name)
                        except Exception:
                            pass
    
    return cleaned
