"""
latzero.core.locking - Cross-platform inter-process locking for shared memory.

Provides:
- FileLock: OS-level file locking for inter-process synchronization
- StripedLock: Hash-based lock striping for fine-grained key locking
- ReadWriteLock: Allows concurrent reads, exclusive writes
"""

import os
import sys
import threading
import hashlib
from pathlib import Path
from typing import Optional
from contextlib import contextmanager

# Platform-specific imports
if sys.platform == 'win32':
    import msvcrt
else:
    import fcntl


class FileLock:
    """
    Cross-platform file-based lock for inter-process synchronization.
    
    Uses msvcrt.locking on Windows, fcntl.flock on Unix.
    This is THE FASTEST inter-process lock available on each platform.
    """
    
    __slots__ = ('_lock_path', '_lock_file', '_thread_lock', '_acquired')
    
    def __init__(self, name: str, lock_dir: Optional[str] = None):
        """
        Initialize a file lock.
        
        Args:
            name: Unique name for the lock (will be sanitized)
            lock_dir: Directory for lock files (default: temp directory)
        """
        if lock_dir is None:
            lock_dir = os.path.join(os.environ.get('TEMP', '/tmp'), 'latzero_locks')
        
        Path(lock_dir).mkdir(parents=True, exist_ok=True)
        
        # Sanitize name for filesystem
        safe_name = ''.join(c if c.isalnum() or c in '-_' else '_' for c in name)
        self._lock_path = os.path.join(lock_dir, f'{safe_name}.lock')
        self._lock_file: Optional[int] = None
        self._thread_lock = threading.Lock()  # For thread-safety within process
        self._acquired = False
    
    def acquire(self, blocking: bool = True, timeout: float = -1) -> bool:
        """
        Acquire the lock.
        
        Args:
            blocking: If True, wait for lock. If False, return immediately.
            timeout: Max seconds to wait (-1 = infinite, 0 = non-blocking)
        
        Returns:
            True if lock acquired, False otherwise.
        """
        # First acquire thread lock (fast path for same-process)
        if not self._thread_lock.acquire(blocking=blocking, timeout=timeout if timeout > 0 else -1):
            return False
        
        try:
            # Open lock file (create if needed)
            self._lock_file = os.open(self._lock_path, os.O_CREAT | os.O_RDWR)
            
            if sys.platform == 'win32':
                # Windows: msvcrt.locking
                mode = msvcrt.LK_NBLCK if not blocking else msvcrt.LK_LOCK
                try:
                    msvcrt.locking(self._lock_file, mode, 1)
                    self._acquired = True
                    return True
                except OSError:
                    if not blocking:
                        os.close(self._lock_file)
                        self._lock_file = None
                        self._thread_lock.release()
                        return False
                    raise
            else:
                # Unix: fcntl.flock
                mode = fcntl.LOCK_EX | (fcntl.LOCK_NB if not blocking else 0)
                try:
                    fcntl.flock(self._lock_file, mode)
                    self._acquired = True
                    return True
                except BlockingIOError:
                    if not blocking:
                        os.close(self._lock_file)
                        self._lock_file = None
                        self._thread_lock.release()
                        return False
                    raise
        except Exception:
            if self._lock_file is not None:
                os.close(self._lock_file)
                self._lock_file = None
            self._thread_lock.release()
            raise
    
    def release(self) -> None:
        """Release the lock."""
        if not self._acquired:
            return
        
        try:
            if self._lock_file is not None:
                if sys.platform == 'win32':
                    try:
                        msvcrt.locking(self._lock_file, msvcrt.LK_UNLCK, 1)
                    except OSError:
                        pass
                else:
                    try:
                        fcntl.flock(self._lock_file, fcntl.LOCK_UN)
                    except OSError:
                        pass
                
                os.close(self._lock_file)
                self._lock_file = None
        finally:
            self._acquired = False
            self._thread_lock.release()
    
    def __enter__(self):
        self.acquire()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
        return False
    
    def __del__(self):
        if self._acquired:
            try:
                self.release()
            except Exception:
                pass


class StripedLock:
    """
    Hash-based lock striping for fine-grained key locking.
    
    Instead of one lock per key (memory-expensive), we hash keys
    to a fixed number of lock stripes. This provides good concurrency
    while keeping memory usage bounded.
    
    Default: 64 stripes = up to 64 concurrent operations on different keys.
    """
    
    __slots__ = ('_stripes', '_num_stripes')
    
    def __init__(self, num_stripes: int = 64):
        """
        Initialize striped lock.
        
        Args:
            num_stripes: Number of lock stripes (power of 2 recommended)
        """
        self._num_stripes = num_stripes
        self._stripes = [threading.RLock() for _ in range(num_stripes)]
    
    def _get_stripe(self, key: str) -> int:
        """Hash key to stripe index. Uses fast FNV-1a variant."""
        # FNV-1a hash (faster than SHA for short strings)
        h = 2166136261
        for char in key.encode():
            h ^= char
            h = (h * 16777619) & 0xFFFFFFFF
        return h % self._num_stripes
    
    @contextmanager
    def acquire(self, key: str):
        """
        Acquire lock for a specific key.
        
        Usage:
            with striped_lock.acquire("my_key"):
                # critical section
        """
        stripe_idx = self._get_stripe(key)
        lock = self._stripes[stripe_idx]
        lock.acquire()
        try:
            yield
        finally:
            lock.release()
    
    def acquire_many(self, keys: list):
        """
        Acquire locks for multiple keys (in consistent order to prevent deadlock).
        
        Args:
            keys: List of keys to lock
        
        Returns:
            Context manager that releases all locks on exit
        """
        # Get unique stripes in sorted order (prevents deadlock)
        stripes = sorted(set(self._get_stripe(k) for k in keys))
        
        @contextmanager
        def multi_lock():
            acquired = []
            try:
                for idx in stripes:
                    self._stripes[idx].acquire()
                    acquired.append(idx)
                yield
            finally:
                for idx in reversed(acquired):
                    self._stripes[idx].release()
        
        return multi_lock()


class ReadWriteLock:
    """
    Read-write lock allowing concurrent reads, exclusive writes.
    
    Optimized for read-heavy workloads (which IPC typically is).
    Uses a readers count + writer flag approach.
    """
    
    __slots__ = ('_lock', '_read_ready', '_readers')
    
    def __init__(self):
        self._lock = threading.Lock()
        self._read_ready = threading.Condition(self._lock)
        self._readers = 0
    
    @contextmanager
    def read(self):
        """Acquire read lock (shared)."""
        with self._lock:
            self._readers += 1
        try:
            yield
        finally:
            with self._lock:
                self._readers -= 1
                if self._readers == 0:
                    self._read_ready.notify_all()
    
    @contextmanager
    def write(self):
        """Acquire write lock (exclusive)."""
        with self._lock:
            while self._readers > 0:
                self._read_ready.wait()
            yield


# Global registry lock (singleton for inter-process safety)
_registry_lock: Optional[FileLock] = None


def get_registry_lock() -> FileLock:
    """Get the global registry lock (creates if needed)."""
    global _registry_lock
    if _registry_lock is None:
        _registry_lock = FileLock('latzero_registry')
    return _registry_lock
