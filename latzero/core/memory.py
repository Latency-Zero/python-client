"""
latzero.core.memory - Dynamic shared memory data storage.

Manages data storage in shared memory segments with:
- Dynamic expansion when data grows
- Chained segments for large data
- Optimized serialization (msgpack default, pickle fallback)
"""

import multiprocessing.shared_memory as shm
import struct
import time
from typing import Optional, Any, Dict, List

from .locking import StripedLock, ReadWriteLock


# Try msgpack for speed, fallback to pickle
try:
    import msgpack
    HAS_MSGPACK = True
except ImportError:
    HAS_MSGPACK = False

import pickle
import zlib


class Serializer:
    """
    Fast serializer with msgpack default, pickle fallback.
    
    msgpack is ~3-5x faster than pickle for common types.
    Falls back to pickle for complex Python objects.
    """
    
    __slots__ = ('_use_msgpack', '_compress_threshold')
    
    # Header byte to indicate serialization format
    MSGPACK_HEADER = b'\x01'
    PICKLE_HEADER = b'\x02'
    COMPRESSED_FLAG = 0x80  # High bit set = compressed
    
    def __init__(self, prefer_msgpack: bool = True, compress_threshold: int = 1024):
        """
        Args:
            prefer_msgpack: Use msgpack when possible (faster)
            compress_threshold: Compress data larger than this (bytes). 0 = never, -1 = always
        """
        self._use_msgpack = prefer_msgpack and HAS_MSGPACK
        self._compress_threshold = compress_threshold
    
    def serialize(self, obj: Any) -> bytes:
        """Serialize object to bytes."""
        data: bytes
        header: int
        
        if self._use_msgpack:
            try:
                data = msgpack.packb(obj, use_bin_type=True)
                header = self.MSGPACK_HEADER[0]
            except (TypeError, ValueError):
                # msgpack can't handle this type, fall back to pickle
                data = pickle.dumps(obj, protocol=pickle.HIGHEST_PROTOCOL)
                header = self.PICKLE_HEADER[0]
        else:
            data = pickle.dumps(obj, protocol=pickle.HIGHEST_PROTOCOL)
            header = self.PICKLE_HEADER[0]
        
        # Compress if beneficial
        if self._compress_threshold >= 0 and len(data) > self._compress_threshold:
            compressed = zlib.compress(data, level=1)  # Level 1 = fast
            if len(compressed) < len(data):
                data = compressed
                header |= self.COMPRESSED_FLAG
        
        return bytes([header]) + data
    
    def deserialize(self, data: bytes) -> Any:
        """Deserialize bytes to object."""
        if not data:
            return None
        
        header = data[0]
        payload = data[1:]
        
        # Check compression
        if header & self.COMPRESSED_FLAG:
            payload = zlib.decompress(payload)
            header &= ~self.COMPRESSED_FLAG
        
        if header == self.MSGPACK_HEADER[0]:
            return msgpack.unpackb(payload, raw=False)
        else:
            return pickle.loads(payload)


# Global serializer instance (can be reconfigured)
_serializer = Serializer()


def get_serializer() -> Serializer:
    """Get the global serializer."""
    return _serializer


def configure_serializer(prefer_msgpack: bool = True, compress_threshold: int = 1024) -> None:
    """Configure the global serializer."""
    global _serializer
    _serializer = Serializer(prefer_msgpack, compress_threshold)


class SharedMemoryPoolData:
    """
    Manages data storage in shared memory for a single pool.
    
    Features:
    - Dynamic expansion: starts at 1MB, grows up to 100MB
    - Efficient binary format with length prefixes
    - Per-key locking via StripedLock
    - Lazy cleanup of expired entries
    """

    INITIAL_SIZE = 1024 * 1024      # 1MB initial
    GROWTH_FACTOR = 2               # Double each expansion
    MAX_SIZE = 100 * 1024 * 1024    # 100MB max
    
    # Memory layout:
    # [8 bytes: data_length][8 bytes: current_capacity][data...]
    HEADER_SIZE = 16

    __slots__ = (
        'shm_name', 'encryption', 'auth_key', 'is_creator',
        'shm', '_data', '_lock', '_key_locks', '_serializer',
        '_current_size'
    )

    def __init__(
        self, 
        shm_name: str, 
        encryption: bool = False, 
        auth_key: str = '',
        serializer: Optional[Serializer] = None
    ):
        self.shm_name = shm_name
        self.encryption = encryption
        self.auth_key = auth_key
        self.is_creator = False
        self._serializer = serializer or get_serializer()
        self._lock = ReadWriteLock()
        self._key_locks = StripedLock(num_stripes=64)
        self._data: Dict[str, dict] = {}
        self._current_size = self.INITIAL_SIZE

        try:
            # Try to connect to existing shared memory
            self.shm = shm.SharedMemory(name=shm_name, create=False)
            self._current_size = len(self.shm.buf)
        except FileNotFoundError:
            # Create new shared memory for this pool
            try:
                self.shm = shm.SharedMemory(
                    name=shm_name, 
                    create=True, 
                    size=self.INITIAL_SIZE
                )
                self.is_creator = True
                self._current_size = self.INITIAL_SIZE
                # Initialize with empty data
                self._write_data({})
            except FileExistsError:
                # Race: another process created it
                self.shm = shm.SharedMemory(name=shm_name, create=False)
                self._current_size = len(self.shm.buf)
            except Exception as e:
                raise RuntimeError(f"Could not create shared memory for pool {shm_name}: {e}")

        self._data = self._read_data()

    def _write_data(self, data: dict) -> None:
        """Write data dict to shared memory."""
        serialized = self._serializer.serialize(data)
        total_needed = len(serialized) + self.HEADER_SIZE
        
        # Check if expansion needed
        if total_needed > self._current_size:
            self._expand_memory(total_needed)
        
        # Write: [length][capacity][data]
        length_bytes = struct.pack('Q', len(serialized))
        capacity_bytes = struct.pack('Q', self._current_size)
        
        self.shm.buf[:8] = length_bytes
        self.shm.buf[8:16] = capacity_bytes
        self.shm.buf[self.HEADER_SIZE:self.HEADER_SIZE + len(serialized)] = serialized

    def _read_data(self) -> dict:
        """Read data dict from shared memory."""
        try:
            length = struct.unpack('Q', bytes(self.shm.buf[:8]))[0]
            if length == 0:
                return {}
            
            data_bytes = bytes(self.shm.buf[self.HEADER_SIZE:self.HEADER_SIZE + length])
            return self._serializer.deserialize(data_bytes)
        except Exception:
            return {}

    def _expand_memory(self, needed_size: int) -> None:
        """
        Expand shared memory to accommodate more data.
        
        Strategy: Create new segment, copy data, switch over.
        """
        new_size = self._current_size
        while new_size < needed_size and new_size < self.MAX_SIZE:
            new_size = min(new_size * self.GROWTH_FACTOR, self.MAX_SIZE)
        
        if new_size >= self.MAX_SIZE and needed_size > new_size:
            from ..utils.exceptions import MemoryFullError
            raise MemoryFullError(f"Cannot expand beyond {self.MAX_SIZE} bytes")
        
        # Create new segment with larger size
        new_name = f"{self.shm_name}_exp_{int(time.time() * 1000)}"
        new_shm = shm.SharedMemory(name=new_name, create=True, size=new_size)
        
        # Copy existing data
        old_length = struct.unpack('Q', bytes(self.shm.buf[:8]))[0]
        if old_length > 0:
            new_shm.buf[:self.HEADER_SIZE + old_length] = self.shm.buf[:self.HEADER_SIZE + old_length]
        
        # Update capacity in new segment
        new_shm.buf[8:16] = struct.pack('Q', new_size)
        
        # Close old segment
        old_shm = self.shm
        old_name = self.shm_name
        
        # Switch to new segment
        self.shm = new_shm
        self.shm_name = new_name
        self._current_size = new_size
        
        # Cleanup old
        try:
            old_shm.close()
            if self.is_creator:
                old_shm.unlink()
        except Exception:
            pass

    def refresh(self) -> None:
        """Refresh data from shared memory."""
        with self._lock.read():
            self._data = self._read_data()

    def save(self) -> None:
        """Save data to shared memory."""
        with self._lock.write():
            self._write_data(self._data)

    def get(self, key: str) -> Any:
        """Get a value by key."""
        with self._key_locks.acquire(key):
            self.refresh()
            entry = self._data.get(key)
            if not entry:
                return None

            # Check auto-clean
            if entry.get('auto_clean'):
                elapsed = time.time() - entry['timestamp']
                if elapsed > entry['auto_clean']:
                    del self._data[key]
                    self.save()
                    return None

            value = entry['value']
            
            # Handle encryption
            if self.encryption and isinstance(value, str) and value.startswith('enc:'):
                from .encryption import decrypt_data
                enc_bytes = bytes.fromhex(value[4:])
                decrypted = decrypt_data(enc_bytes, self.auth_key)
                value = self._serializer.deserialize(decrypted)

            return value

    def set(self, key: str, value: Any, auto_clean: Optional[int] = None) -> None:
        """Set a value by key."""
        with self._key_locks.acquire(key):
            self.refresh()
            
            stored_value = value
            
            # Handle encryption
            if self.encryption:
                from .encryption import encrypt_data
                serialized = self._serializer.serialize(value)
                encrypted = encrypt_data(serialized, self.auth_key)
                stored_value = 'enc:' + encrypted.hex()

            self._data[key] = {
                'value': stored_value,
                'timestamp': time.time(),
                'auto_clean': auto_clean
            }

            self.save()

    def delete(self, key: str) -> bool:
        """Delete a key. Returns True if key existed."""
        with self._key_locks.acquire(key):
            self.refresh()
            if key in self._data:
                del self._data[key]
                self.save()
                return True
            return False

    def exists(self, key: str) -> bool:
        """Check if key exists (respects auto_clean)."""
        return self.get(key) is not None

    def keys_with_prefix(self, prefix: str) -> List[str]:
        """Get all keys with a given prefix."""
        self.refresh()
        return [k for k in self._data.keys() if k.startswith(prefix)]

    def all_keys(self) -> List[str]:
        """Get all keys in the pool."""
        self.refresh()
        return list(self._data.keys())

    def cleanup_expired(self) -> int:
        """
        Remove expired entries.
        
        Returns:
            Number of entries removed
        """
        current_time = time.time()
        
        with self._lock.write():
            self._data = self._read_data()
            to_remove = []
            
            for key, entry in self._data.items():
                if entry.get('auto_clean'):
                    if current_time - entry['timestamp'] > entry['auto_clean']:
                        to_remove.append(key)

            for key in to_remove:
                del self._data[key]

            if to_remove:
                self._write_data(self._data)
            
            return len(to_remove)

    def size(self) -> int:
        """Get number of keys."""
        self.refresh()
        return len(self._data)

    def memory_usage(self) -> dict:
        """Get memory usage stats."""
        length = struct.unpack('Q', bytes(self.shm.buf[:8]))[0]
        return {
            'used_bytes': length,
            'capacity_bytes': self._current_size,
            'utilization': length / self._current_size if self._current_size > 0 else 0,
            'max_bytes': self.MAX_SIZE
        }

    def close(self) -> None:
        """Close shared memory access."""
        if hasattr(self, 'shm') and self.shm is not None:
            try:
                self.shm.close()
                if self.is_creator:
                    self.shm.unlink()
            except Exception:
                pass

    def __del__(self):
        self.close()
