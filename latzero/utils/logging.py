"""
latzero.utils.logging - Structured logging for latzero.
"""

import logging
import sys
import json
from datetime import datetime
from typing import Optional


class JsonFormatter(logging.Formatter):
    """JSON formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        log_obj = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
        }
        
        if record.exc_info:
            log_obj['exception'] = self.formatException(record.exc_info)
        
        if hasattr(record, 'pool_name'):
            log_obj['pool'] = record.pool_name
        
        if hasattr(record, 'operation'):
            log_obj['operation'] = record.operation
        
        return json.dumps(log_obj)


class SimpleFormatter(logging.Formatter):
    """Simple human-readable formatter."""
    
    def __init__(self):
        super().__init__(
            fmt='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )


# Global logger setup
_logger: Optional[logging.Logger] = None
_configured = False


def get_logger(name: str = 'latzero') -> logging.Logger:
    """
    Get a logger instance.
    
    Args:
        name: Logger name (default: 'latzero')
    
    Returns:
        Configured logger
    """
    return logging.getLogger(name)


def configure_logging(
    level: str = 'INFO',
    format: str = 'simple',
    stream=None
) -> logging.Logger:
    """
    Configure latzero logging.
    
    Args:
        level: Log level ('DEBUG', 'INFO', 'WARNING', 'ERROR')
        format: 'simple' for human readable, 'json' for structured
        stream: Output stream (default: stderr)
    
    Returns:
        Configured logger
    """
    global _configured
    
    logger = logging.getLogger('latzero')
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    
    # Remove existing handlers
    logger.handlers.clear()
    
    # Add handler
    handler = logging.StreamHandler(stream or sys.stderr)
    
    if format == 'json':
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(SimpleFormatter())
    
    logger.addHandler(handler)
    _configured = True
    
    return logger


def log_operation(
    logger: logging.Logger,
    operation: str,
    pool_name: str,
    key: Optional[str] = None,
    success: bool = True,
    duration_ms: Optional[float] = None,
    extra: Optional[dict] = None
) -> None:
    """
    Log an operation with structured context.
    
    Args:
        logger: Logger instance
        operation: Operation name (e.g., 'set', 'get', 'connect')
        pool_name: Pool name
        key: Key involved (if any)
        success: Whether operation succeeded
        duration_ms: Duration in milliseconds
        extra: Additional context
    """
    msg_parts = [f"op={operation}", f"pool={pool_name}"]
    
    if key:
        msg_parts.append(f"key={key}")
    
    msg_parts.append(f"success={success}")
    
    if duration_ms is not None:
        msg_parts.append(f"duration_ms={duration_ms:.2f}")
    
    if extra:
        for k, v in extra.items():
            msg_parts.append(f"{k}={v}")
    
    message = ' '.join(msg_parts)
    
    record = logger.makeRecord(
        logger.name,
        logging.INFO if success else logging.ERROR,
        '',
        0,
        message,
        (),
        None
    )
    record.pool_name = pool_name
    record.operation = operation
    
    logger.handle(record)
