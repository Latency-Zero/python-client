"""
latzero.core.memory - Dynamic shared memory data storage.

Manages data storage in shared memory segments with:
- Dynamic expansion when data grows
- Optimized serialization (msgpack default, pickle fallback)
- Lazy refresh for better performance
"""

import multiprocessing.shared_memory as shm
import struct
import time
import threading
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
    
    def __init__(self, prefer_msgpack: bool = True, compress_threshold: int = 10240):
        """
        Args:
            prefer_msgpack: Use msgpack when possible (faster)
            compress_threshold: Compress data larger than this (bytes). -1 = never
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
        
        # Compress if beneficial (only for large data)
        if self._compress_threshold >= 0 and len(data) > self._compress_threshold:
            compressed = zlib.compress(data, level=1)  # Level 1 = fast
            if len(compressed) < len(data) * 0.9:  # Only if 10%+ savings
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


def configure_serializer(prefer_msgpack: bool = True, compress_threshold: int = 10240) -> None:
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
    - Cached reads with dirty tracking for performance
    """

    INITIAL_SIZE = 1024 * 1024      # 1MB initial
    GROWTH_FACTOR = 2               # Double each expansion
    MAX_SIZE = 100 * 1024 * 1024    # 100MB max
    
    # Memory layout:
    # [8 bytes: data_length][8 bytes: version][data...]
    HEADER_SIZE = 16

    __slots__ = (
        'shm_name', 'encryption', 'auth_key', 'is_creator',
        'shm', '_data', '_lock', '_key_locks', '_serializer',
        '_current_size', '_version', '_last_read_version', '_dirty'
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
        self._lock = threading.RLock()
        self._key_locks = StripedLock(num_stripes=64)
        self._data: Dict[str, dict] = {}
        self._current_size = self.INITIAL_SIZE
        self._version = 0
        self._last_read_version = -1
        self._dirty = False

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
                self._write_data_raw({})
            except FileExistsError:
                # Race: another process created it
                self.shm = shm.SharedMemory(name=shm_name, create=False)
                self._current_size = len(self.shm.buf)
            except Exception as e:
                raise RuntimeError(f"Could not create shared memory for pool {shm_name}: {e}")

        self._sync_from_shm()

    def _write_data_raw(self, data: dict) -> None:
        """Write data dict to shared memory (low-level)."""
        serialized = self._serializer.serialize(data)
        total_needed = len(serialized) + self.HEADER_SIZE
        
        # Check if expansion needed
        if total_needed > self._current_size:
            self._expand_memory(total_needed)
        
        self._version += 1
        
        # Write: [length][version][data]
        length_bytes = struct.pack('Q', len(serialized))
        version_bytes = struct.pack('Q', self._version)
        
        self.shm.buf[:8] = length_bytes
        self.shm.buf[8:16] = version_bytes
        self.shm.buf[self.HEADER_SIZE:self.HEADER_SIZE + len(serialized)] = serialized

    def _read_data_raw(self) -> tuple:
        """Read data dict from shared memory (low-level). Returns (data, version)."""
        try:
            length = struct.unpack('Q', bytes(self.shm.buf[:8]))[0]
            version = struct.unpack('Q', bytes(self.shm.buf[8:16]))[0]
            
            if length == 0:
                return {}, version
            
            data_bytes = bytes(self.shm.buf[self.HEADER_SIZE:self.HEADER_SIZE + length])
            return self._serializer.deserialize(data_bytes), version
        except Exception:
            return {}, 0

    def _sync_from_shm(self) -> bool:
        """Sync local cache from shared memory if version changed. Returns True if synced."""
        data, version = self._read_data_raw()
        if version != self._last_read_version:
            self._data = data
            self._last_read_version = version
            self._version = version
            return True
        return False

    def _sync_to_shm(self) -> None:
        """Write local cache to shared memory."""
        self._write_data_raw(self._data)
        self._dirty = False
        self._last_read_version = self._version

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
        
        # Close old segment
        old_shm = self.shm
        
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

    def get(self, key: str) -> Any:
        """Get a value by key."""
        with self._lock:
            # Only sync if we haven't written recently
            if not self._dirty:
                self._sync_from_shm()
            
            entry = self._data.get(key)
            if not entry:
                return None

            # Check auto-clean
            if entry.get('auto_clean'):
                elapsed = time.time() - entry['timestamp']
                if elapsed > entry['auto_clean']:
                    del self._data[key]
                    self._sync_to_shm()
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
        with self._lock:
            # Sync first to get latest data
            self._sync_from_shm()
            
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
                'auto_clean': auto_clean,
            }
            
            self._dirty = True
            self._sync_to_shm()

    def delete(self, key: str) -> bool:
        """Delete a key. Returns True if key existed."""
        with self._lock:
            self._sync_from_shm()
            
            if key in self._data:
                del self._data[key]
                self._sync_to_shm()
                return True
            return False

    def exists(self, key: str) -> bool:
        """Check if key exists."""
        with self._lock:
            self._sync_from_shm()
            return key in self._data

    def keys(self) -> List[str]:
        """Get all keys."""
        with self._lock:
            self._sync_from_shm()
            return list(self._data.keys())

    def keys_with_prefix(self, prefix: str) -> List[str]:
        """Get keys matching prefix."""
        with self._lock:
            self._sync_from_shm()
            return [k for k in self._data.keys() if k.startswith(prefix)]

    def size(self) -> int:
        """Get number of keys."""
        with self._lock:
            self._sync_from_shm()
            return len(self._data)

    def items(self) -> List[tuple]:
        """Get all (key, value) pairs."""
        with self._lock:
            self._sync_from_shm()
            result = []
            for key, entry in self._data.items():
                value = entry['value']
                if self.encryption and isinstance(value, str) and value.startswith('enc:'):
                    from .encryption import decrypt_data
                    enc_bytes = bytes.fromhex(value[4:])
                    decrypted = decrypt_data(enc_bytes, self.auth_key)
                    value = self._serializer.deserialize(decrypted)
                result.append((key, value))
            return result

    def clear(self) -> None:
        """Clear all data."""
        with self._lock:
            self._data = {}
            self._sync_to_shm()

    def cleanup_expired(self) -> int:
        """Remove expired entries. Returns count removed."""
        with self._lock:
            self._sync_from_shm()
            
            now = time.time()
            to_remove = []
            
            for key, entry in self._data.items():
                if entry.get('auto_clean'):
                    elapsed = now - entry['timestamp']
                    if elapsed > entry['auto_clean']:
                        to_remove.append(key)
            
            for key in to_remove:
                del self._data[key]
            
            if to_remove:
                self._sync_to_shm()
            
            return len(to_remove)

    def memory_usage(self) -> dict:
        """Get memory usage statistics."""
        with self._lock:
            length = struct.unpack('Q', bytes(self.shm.buf[:8]))[0]
            return {
                'used_bytes': length + self.HEADER_SIZE,
                'capacity_bytes': self._current_size,
                'max_bytes': self.MAX_SIZE,
                'utilization': (length + self.HEADER_SIZE) / self._current_size,
            }

    def close(self) -> None:
        """Close the shared memory connection."""
        try:
            self.shm.close()
        except Exception:
            pass

    def destroy(self) -> None:
        """Destroy the shared memory segment."""
        try:
            self.shm.close()
            self.shm.unlink()
        except Exception:
            pass

    def refresh(self) -> None:
        """Force refresh from shared memory (for compatibility)."""
        with self._lock:
            self._sync_from_shm()

    def save(self) -> None:
        """Force save to shared memory (for compatibility)."""
        with self._lock:
            self._sync_to_shm()
