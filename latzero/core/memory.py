import multiprocessing.shared_memory as shm
import json
import struct
import time
from ..utils.serializer import serialize, deserialize
from .encryption import encrypt_data, decrypt_data

class SharedMemoryPoolData:
    """Manages data storage in shared memory for a single pool."""

    INITIAL_SIZE = 1024 * 1024  # 1MB initial size per pool
    MAX_SIZE = 100 * 1024 * 1024  # 100MB max size per pool

    def __init__(self, shm_name: str, encryption=False, auth_key=''):
        self.shm_name = shm_name
        self.encryption = encryption
        self.auth_key = auth_key
        self.is_creator = False

        try:
            # Try to connect to existing shared memory
            self.shm = shm.SharedMemory(name=shm_name, create=False)
        except FileNotFoundError:
            # Create new shared memory for this pool
            try:
                self.shm = shm.SharedMemory(name=shm_name, create=True, size=self.INITIAL_SIZE)
                self.is_creator = True
                # Initialize with empty data
                self._write_data({})
            except Exception:
                raise RuntimeError(f"Could not create shared memory for pool {shm_name}")

        self._data = self._read_data()

    def _write_data(self, data: dict):
        """Write data to shared memory with length prefix."""
        json_data = json.dumps(data).encode('utf-8')
        if len(json_data) > len(self.shm.buf) - 8:
            raise ValueError("Data too large for shared memory segment")

        length = struct.pack('Q', len(json_data))
        self.shm.buf[:8] = length
        self.shm.buf[8:8+len(json_data)] = json_data

    def _read_data(self) -> dict:
        """Read data from shared memory."""
        length = struct.unpack('Q', bytes(self.shm.buf[:8]))[0]
        if length == 0:
            return {}
        json_data = bytes(self.shm.buf[8:8+length]).decode('utf-8')
        return json.loads(json_data)

    def refresh(self):
        """Refresh data from shared memory."""
        self._data = self._read_data()

    def save(self):
        """Save data to shared memory."""
        try:
            self._write_data(self._data)
        except ValueError:
            # If data is too large, we'll need to implement expansion later
            # For now, just refresh to ensure consistency
            self.refresh()

    def get(self, key: str):
        """Get a value by key."""
        self.refresh()
        entry = self._data.get(key)
        if not entry:
            return None

        # Check auto-clean
        if entry.get('auto_clean') and time.time() - entry['timestamp'] > entry['auto_clean']:
            del self._data[key]
            self.save()
            return None

        value = entry['value']
        if self.encryption and isinstance(value, str) and value.startswith('encrypted:'):
            enc = bytes.fromhex(value[10:])
            ser = decrypt_data(enc, self.auth_key)
            value = deserialize(ser)

        return value

    def set(self, key: str, value, auto_clean=None):
        """Set a value by key."""
        self.refresh()

        current_time = time.time()

        if self.encryption:
            ser = serialize(value)
            enc = encrypt_data(ser, self.auth_key)
            stored_value = 'encrypted:' + enc.hex()
        else:
            stored_value = value

        self._data[key] = {
            'value': stored_value,
            'timestamp': current_time,
            'auto_clean': auto_clean
        }

        self.save()

    def keys_with_prefix(self, prefix: str):
        """Get all keys with a given prefix."""
        self.refresh()
        return [k for k in self._data.keys() if k.startswith(prefix)]

    def cleanup_expired(self):
        """Remove expired entries."""
        current_time = time.time()
        to_remove = []
        for key, entry in self._data.items():
            if entry.get('auto_clean') and current_time - entry['timestamp'] > entry['auto_clean']:
                to_remove.append(key)

        for key in to_remove:
            del self._data[key]

        if to_remove:
            self.save()

    def close(self):
        """Close shared memory access."""
        if hasattr(self, 'shm'):
            self.shm.close()
            if self.is_creator:
                self.shm.unlink()

    def __del__(self):
        self.close()
