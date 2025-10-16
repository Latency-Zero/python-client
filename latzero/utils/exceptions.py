class PoolNotFound(Exception):
    """Raised when trying to connect to a non-existent pool."""
    pass

class AuthenticationError(Exception):
    """Raised when authentication fails."""
    pass

class EncryptionError(Exception):
    """Raised when encryption/decryption fails."""
    pass

class SerializationError(Exception):
    """Raised when serialization/deserialization fails."""
    pass
