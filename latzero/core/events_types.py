"""
latzero.core.events_types - Type definitions for the events system.

Provides:
- EventError, EventTimeout exceptions
- EventMode enum
- Pydantic integration helpers
"""

from enum import Enum
from typing import Optional, Type, TypeVar, Any
from dataclasses import dataclass

# Try to import pydantic for optional type-safe payloads
try:
    from pydantic import BaseModel
    PYDANTIC_AVAILABLE = True
except ImportError:
    BaseModel = None
    PYDANTIC_AVAILABLE = False


class EventMode(Enum):
    """Event delivery modes."""
    FIRST = "first"           # First available handler takes the event (default)
    ROUND_ROBIN = "round_robin"  # Handlers take turns
    BROADCAST = "broadcast"   # All handlers receive the event


class EventQueueMode(Enum):
    """Event queueing behavior modes."""
    IMMEDIATE = "immediate"   # Process immediately (default)
    DEBOUNCE = "debounce"     # Only process last event in time window
    QUEUE = "queue"           # Queue events for ordered processing
    COALESCE = "coalesce"     # Merge multiple events into one


class EventError(Exception):
    """Exception raised when an event handler fails."""
    
    def __init__(
        self, 
        message: str,
        error_type: str = "EventError",
        traceback_str: Optional[str] = None,
        handler_pid: Optional[int] = None,
        retryable: bool = False
    ):
        super().__init__(message)
        self.message = message
        self.error_type = error_type
        self.traceback_str = traceback_str
        self.handler_pid = handler_pid
        self.retryable = retryable
    
    def to_dict(self) -> dict:
        """Serialize to dictionary for shared memory storage."""
        return {
            "type": self.error_type,
            "message": self.message,
            "traceback": self.traceback_str,
            "handler_pid": self.handler_pid,
            "retryable": self.retryable,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "EventError":
        """Deserialize from dictionary."""
        return cls(
            message=data.get("message", "Unknown error"),
            error_type=data.get("type", "EventError"),
            traceback_str=data.get("traceback"),
            handler_pid=data.get("handler_pid"),
            retryable=data.get("retryable", False),
        )


class EventTimeout(Exception):
    """Exception raised when an event call times out."""
    
    def __init__(self, event: str, timeout: float):
        super().__init__(f"Event '{event}' timed out after {timeout}s")
        self.event = event
        self.timeout = timeout


@dataclass
class HandlerInfo:
    """Information about a registered event handler."""
    pid: int
    signal_name: str
    registered_at: float
    
    def to_dict(self) -> dict:
        return {
            "pid": self.pid,
            "signal": self.signal_name,
            "registered_at": self.registered_at,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "HandlerInfo":
        return cls(
            pid=data["pid"],
            signal_name=data["signal"],
            registered_at=data["registered_at"],
        )


@dataclass
class EventRegistration:
    """Registration data for an event type."""
    handlers: list  # List of HandlerInfo dicts
    mode: EventMode
    
    def to_dict(self) -> dict:
        return {
            "handlers": self.handlers,
            "mode": self.mode.value,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "EventRegistration":
        return cls(
            handlers=data.get("handlers", []),
            mode=EventMode(data.get("mode", "first")),
        )


@dataclass
class CallPayload:
    """Payload for an event call."""
    event: str
    args: dict
    caller_pid: int
    caller_signal: str
    created_at: float
    
    def to_dict(self) -> dict:
        return {
            "event": self.event,
            "args": self.args,
            "caller_pid": self.caller_pid,
            "caller_signal": self.caller_signal,
            "created_at": self.created_at,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "CallPayload":
        return cls(
            event=data["event"],
            args=data["args"],
            caller_pid=data["caller_pid"],
            caller_signal=data["caller_signal"],
            created_at=data["created_at"],
        )


@dataclass
class ResultPayload:
    """Payload for an event result."""
    value: Any
    error: Optional[dict]  # EventError.to_dict() or None
    completed_at: float
    
    def to_dict(self) -> dict:
        return {
            "value": self.value,
            "error": self.error,
            "completed_at": self.completed_at,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "ResultPayload":
        return cls(
            value=data.get("value"),
            error=data.get("error"),
            completed_at=data.get("completed_at", 0),
        )


# Type variable for generic response types
T = TypeVar('T')


def validate_request(data: dict, model: Type[T]) -> T:
    """
    Validate request data against a Pydantic model.
    
    Args:
        data: Dictionary of request data
        model: Pydantic model class to validate against
        
    Returns:
        Validated model instance
    """
    if not PYDANTIC_AVAILABLE:
        raise RuntimeError("Pydantic is required for type-safe payloads")
    
    if not issubclass(model, BaseModel):
        raise TypeError(f"Model must be a Pydantic BaseModel, got {type(model)}")
    
    return model(**data)


def validate_response(value: Any, model: Optional[Type[T]]) -> Any:
    """
    Validate response value against a Pydantic model if provided.
    
    Args:
        value: Response value
        model: Optional Pydantic model class
        
    Returns:
        Validated value (or original if no model)
    """
    if model is None:
        return value
    
    if not PYDANTIC_AVAILABLE:
        raise RuntimeError("Pydantic is required for type-safe payloads")
    
    if isinstance(value, dict):
        return model(**value)
    elif isinstance(value, model):
        return value
    else:
        raise TypeError(f"Expected {model.__name__}, got {type(value).__name__}")
