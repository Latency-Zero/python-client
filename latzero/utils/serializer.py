import pickle
import zlib

def serialize(obj):
    """Serialize an object using pickle and compress with zlib."""
    try:
        return zlib.compress(pickle.dumps(obj))
    except Exception as e:
        from .exceptions import SerializationError
        raise SerializationError(f"Serialization failed: {e}")

def deserialize(data):
    """Deserialize compressed pickled data."""
    try:
        return pickle.loads(zlib.decompress(data))
    except Exception as e:
        from .exceptions import SerializationError
        raise SerializationError(f"Deserialization failed: {e}")
