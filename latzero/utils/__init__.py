"""
latzero.utils - Utility functions and classes.
"""

from .exceptions import (
    LatzeroError,
    PoolNotFound,
    PoolExistsError,
    AuthenticationError,
    EncryptionError,
    SerializationError,
    MemoryFullError,
    ReadOnlyError,
    LockTimeoutError,
    OrphanedMemoryError,
    PoolDisconnectedError,
)
from .type_checker import is_pickleable, preserve_type
from .logging import get_logger, configure_logging, log_operation

__all__ = [
    # Exceptions
    'LatzeroError',
    'PoolNotFound',
    'PoolExistsError',
    'AuthenticationError',
    'EncryptionError',
    'SerializationError',
    'MemoryFullError',
    'ReadOnlyError',
    'LockTimeoutError',
    'OrphanedMemoryError',
    'PoolDisconnectedError',
    
    # Type checking
    'is_pickleable',
    'preserve_type',
    
    # Logging
    'get_logger',
    'configure_logging',
    'log_operation',
]
