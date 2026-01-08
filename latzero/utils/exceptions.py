"""
latzero.utils.exceptions - Exception types for latzero.
"""


class LatzeroError(Exception):
    """Base exception for all latzero errors."""
    pass


class PoolNotFound(LatzeroError):
    """Raised when trying to connect to a non-existent pool."""
    pass


class PoolExistsError(LatzeroError):
    """Raised when trying to create a pool that already exists."""
    pass


class AuthenticationError(LatzeroError):
    """Raised when authentication fails."""
    pass


class EncryptionError(LatzeroError):
    """Raised when encryption/decryption fails."""
    pass


class SerializationError(LatzeroError):
    """Raised when serialization/deserialization fails."""
    pass


class MemoryFullError(LatzeroError):
    """Raised when shared memory cannot be expanded further."""
    pass


class ReadOnlyError(LatzeroError):
    """Raised when attempting to write to a read-only pool connection."""
    pass


class LockTimeoutError(LatzeroError):
    """Raised when a lock cannot be acquired within the timeout."""
    pass


class OrphanedMemoryError(LatzeroError):
    """Raised when orphaned shared memory is detected."""
    pass


class PoolDisconnectedError(LatzeroError):
    """Raised when operations are attempted on a disconnected pool client."""
    pass
