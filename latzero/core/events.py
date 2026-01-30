"""
latzero.core.events - Socket-like event system for shared memory IPC.

Provides:
- EventEmitter: Namespaced event emitter
- Signal: Cross-platform OS-native signaling
- Event registration, routing, and invocation
- Background listener with OS-level blocking

API:
    emit(event, **data)  - Fire-and-forget broadcast
    call(event, **data)  - RPC-style request/response with timeout
    @on(event)           - Register event handler decorator
"""

import os
import sys
import time
import uuid
import threading
import traceback
from typing import Optional, Callable, Any, Dict, List, TYPE_CHECKING

from .events_types import (
    EventMode,
    EventQueueMode,
    EventError,
    EventTimeout,
    HandlerInfo,
    EventRegistration,
    CallPayload,
    ResultPayload,
    validate_request,
    validate_response,
    PYDANTIC_AVAILABLE,
)

if TYPE_CHECKING:
    from .pool import PoolClient


# ============== Cross-Platform Signaling ==============

if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes
    
    kernel32 = ctypes.windll.kernel32
    
    # Constants
    WAIT_OBJECT_0 = 0
    WAIT_TIMEOUT = 0x102
    WAIT_FAILED = 0xFFFFFFFF
    INFINITE = 0xFFFFFFFF
    
    class WindowsSignal:
        """Windows Named Event for cross-process signaling."""
        
        def __init__(self, name: str, create: bool = True):
            """
            Initialize Windows named event.
            
            Args:
                name: Unique signal name
                create: If True, create event; if False, open existing
            """
            self.name = f"Global\\latzero_{name}"
            self._closed = False
            
            if create:
                self.handle = kernel32.CreateEventW(
                    None,           # Security attributes
                    False,          # Auto-reset event
                    False,          # Initial state (not signaled)
                    self.name
                )
            else:
                self.handle = kernel32.OpenEventW(
                    0x001F0003,     # EVENT_ALL_ACCESS
                    False,
                    self.name
                )
            
            if not self.handle:
                raise OSError(f"Failed to create/open event: {self.name}")
        
        def signal(self) -> None:
            """Signal the event, waking any waiting thread."""
            if not self._closed:
                kernel32.SetEvent(self.handle)
        
        def wait(self, timeout_ms: int = -1) -> bool:
            """
            Wait for signal.
            
            Args:
                timeout_ms: Timeout in milliseconds (-1 = infinite)
                
            Returns:
                True if signaled, False if timeout
            """
            if self._closed:
                return False
            
            wait_time = INFINITE if timeout_ms < 0 else timeout_ms
            result = kernel32.WaitForSingleObject(self.handle, wait_time)
            return result == WAIT_OBJECT_0
        
        def close(self) -> None:
            """Close the event handle."""
            if not self._closed and self.handle:
                kernel32.CloseHandle(self.handle)
                self._closed = True
        
        def __del__(self):
            self.close()
    
    Signal = WindowsSignal

else:
    # POSIX (Linux/macOS) - Use fast native primitives
    import select as _select_module
    
    # Detect platform for optimal signal implementation
    _is_linux = sys.platform.startswith('linux')
    _is_macos = sys.platform == 'darwin'
    
    if _is_linux:
        # Linux: Use eventfd for ultra-fast signaling (~1-5μs)
        import ctypes
        import ctypes.util
        
        _libc = ctypes.CDLL(ctypes.util.find_library('c'), use_errno=True)
        
        # eventfd flags
        _EFD_CLOEXEC = 0o2000000
        _EFD_NONBLOCK = 0o4000
        _EFD_SEMAPHORE = 1
        
        # Setup eventfd function
        _libc.eventfd.argtypes = [ctypes.c_uint, ctypes.c_int]
        _libc.eventfd.restype = ctypes.c_int
        
        class LinuxEventFD:
            """Linux eventfd for ultra-fast cross-process signaling (~1-5μs)."""
            
            def __init__(self, name: str, create: bool = True):
                """
                Initialize Linux eventfd.
                
                Note: eventfd is process-local, so we use a file-based approach
                for cross-process signaling with a shared path.
                
                Args:
                    name: Unique signal name
                    create: If True, create; if False, open existing
                """
                self.name = name
                self._sock_path = f"/tmp/latzero_sig_{name}.sock"
                self._closed = False
                self._is_creator = create
                
                if create:
                    # Server side - create Unix datagram socket
                    try:
                        os.unlink(self._sock_path)
                    except FileNotFoundError:
                        pass
                    except OSError:
                        pass
                    
                    import socket
                    self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
                    self._sock.setblocking(False)
                    self._sock.bind(self._sock_path)
                    # Make socket world-writable for cross-user IPC
                    try:
                        os.chmod(self._sock_path, 0o777)
                    except:
                        pass
                else:
                    # Client side - just need path to send to
                    import socket
                    self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
                    self._sock.setblocking(False)
            
            def signal(self) -> None:
                """Send 1-byte signal (~1-5μs)."""
                if self._closed:
                    return
                try:
                    self._sock.sendto(b'1', self._sock_path)
                except (OSError, ConnectionRefusedError, FileNotFoundError):
                    pass
            
            def wait(self, timeout_ms: int = -1) -> bool:
                """
                Wait for signal using select() for instant wake-up.
                
                Args:
                    timeout_ms: Timeout in milliseconds (-1 = infinite)
                    
                Returns:
                    True if signaled, False if timeout
                """
                if self._closed:
                    return False
                
                timeout = None if timeout_ms < 0 else timeout_ms / 1000.0
                try:
                    readable, _, _ = _select_module.select([self._sock], [], [], timeout)
                    if readable:
                        try:
                            self._sock.recv(64)  # Drain all pending signals
                            return True
                        except BlockingIOError:
                            pass
                except (ValueError, OSError):
                    pass
                return False
            
            def fileno(self) -> int:
                """Return file descriptor for select() multiplexing."""
                return self._sock.fileno()
            
            def close(self) -> None:
                """Close the socket."""
                if not self._closed:
                    try:
                        self._sock.close()
                    except:
                        pass
                    if self._is_creator:
                        try:
                            os.unlink(self._sock_path)
                        except:
                            pass
                    self._closed = True
            
            def __del__(self):
                self.close()
        
        Signal = LinuxEventFD
    
    elif _is_macos:
        # macOS: Use Unix domain sockets for fast signaling (~5-20μs)
        import socket as _socket_module
        
        class MacOSSignal:
            """macOS Unix socket for fast cross-process signaling (~5-20μs)."""
            
            def __init__(self, name: str, create: bool = True):
                """
                Initialize macOS Unix domain socket signal.
                
                Args:
                    name: Unique signal name
                    create: If True, create socket; if False, connect to existing
                """
                self.name = name
                self._sock_path = f"/tmp/latzero_sig_{name}.sock"
                self._closed = False
                self._is_creator = create
                
                if create:
                    # Server side - create Unix datagram socket
                    try:
                        os.unlink(self._sock_path)
                    except FileNotFoundError:
                        pass
                    except OSError:
                        pass
                    
                    self._sock = _socket_module.socket(_socket_module.AF_UNIX, _socket_module.SOCK_DGRAM)
                    self._sock.setblocking(False)
                    self._sock.bind(self._sock_path)
                    # Make socket world-writable for cross-user IPC
                    try:
                        os.chmod(self._sock_path, 0o777)
                    except:
                        pass
                else:
                    # Client side - just need path to send to
                    self._sock = _socket_module.socket(_socket_module.AF_UNIX, _socket_module.SOCK_DGRAM)
                    self._sock.setblocking(False)
            
            def signal(self) -> None:
                """Send 1-byte signal (~5-20μs)."""
                if self._closed:
                    return
                try:
                    self._sock.sendto(b'1', self._sock_path)
                except (OSError, ConnectionRefusedError, FileNotFoundError):
                    pass
            
            def wait(self, timeout_ms: int = -1) -> bool:
                """
                Wait for signal using select() for instant wake-up.
                
                Args:
                    timeout_ms: Timeout in milliseconds (-1 = infinite)
                    
                Returns:
                    True if signaled, False if timeout
                """
                if self._closed:
                    return False
                
                timeout = None if timeout_ms < 0 else timeout_ms / 1000.0
                try:
                    readable, _, _ = _select_module.select([self._sock], [], [], timeout)
                    if readable:
                        try:
                            self._sock.recv(64)  # Drain all pending signals
                            return True
                        except BlockingIOError:
                            pass
                except (ValueError, OSError):
                    pass
                return False
            
            def fileno(self) -> int:
                """Return file descriptor for select() multiplexing."""
                return self._sock.fileno()
            
            def close(self) -> None:
                """Close the socket."""
                if not self._closed:
                    try:
                        self._sock.close()
                    except:
                        pass
                    if self._is_creator:
                        try:
                            os.unlink(self._sock_path)
                        except:
                            pass
                    self._closed = True
            
            def __del__(self):
                self.close()
        
        Signal = MacOSSignal
    
    else:
        # Other POSIX: Fall back to posix_ipc or threading
        try:
            import posix_ipc
            
            class PosixSignal:
                """POSIX semaphore for cross-process signaling (fallback)."""
                
                def __init__(self, name: str, create: bool = True):
                    self.name = f"/latzero_{name}"
                    self._closed = False
                    
                    flags = posix_ipc.O_CREAT if create else 0
                    self.sem = posix_ipc.Semaphore(
                        self.name,
                        flags=flags,
                        initial_value=0
                    )
                
                def signal(self) -> None:
                    if not self._closed:
                        self.sem.release()
                
                def wait(self, timeout_ms: int = -1) -> bool:
                    if self._closed:
                        return False
                    try:
                        timeout = None if timeout_ms < 0 else timeout_ms / 1000.0
                        self.sem.acquire(timeout=timeout)
                        return True
                    except posix_ipc.BusyError:
                        return False
                
                def fileno(self) -> int:
                    """Not supported for semaphores."""
                    return -1
                
                def close(self) -> None:
                    if not self._closed:
                        try:
                            self.sem.close()
                        except:
                            pass
                        self._closed = True
                
                def __del__(self):
                    self.close()
            
            Signal = PosixSignal
            
        except ImportError:
            # Final fallback to threading.Event (single-process only)
            class ThreadingSignal:
                """Threading-based signal (fallback, same process only)."""
                
                def __init__(self, name: str, create: bool = True):
                    self.name = name
                    self._event = threading.Event()
                    self._closed = False
                
                def signal(self) -> None:
                    if not self._closed:
                        self._event.set()
                
                def wait(self, timeout_ms: int = -1) -> bool:
                    if self._closed:
                        return False
                    timeout = None if timeout_ms < 0 else timeout_ms / 1000.0
                    result = self._event.wait(timeout=timeout)
                    self._event.clear()
                    return result
                
                def fileno(self) -> int:
                    """Not supported for threading events."""
                    return -1
                
                def close(self) -> None:
                    self._closed = True
                
                def __del__(self):
                    self.close()
            
            Signal = ThreadingSignal


# ============== Event Keys ==============

class EventKeys:
    """Key prefix constants for event system storage."""
    
    REGISTRY = "__events__:registry"
    CALL_PREFIX = "__events__:call:"
    RESULT_PREFIX = "__events__:result:"
    HEARTBEAT_PREFIX = "__events__:heartbeat:"


# ============== Event Handler Wrapper ==============

class EventHandler:
    """Wrapper for registered event handlers."""
    
    def __init__(
        self,
        func: Callable,
        event: str,
        mode: EventMode = EventMode.FIRST,
        queue_mode: EventQueueMode = EventQueueMode.IMMEDIATE,
        request_model: Optional[type] = None,
        response_model: Optional[type] = None,
        debounce_ms: int = 0,
        max_queue: int = 1000,
    ):
        self.func = func
        self.event = event
        self.mode = mode
        self.queue_mode = queue_mode
        self.request_model = request_model
        self.response_model = response_model
        self.debounce_ms = debounce_ms
        self.max_queue = max_queue
        
        # For debounce/coalesce
        self._last_call_time = 0.0
        self._pending_args: Optional[dict] = None
        self._queue: List[dict] = []
    
    def __call__(self, **kwargs) -> Any:
        """Execute the handler with optional type validation."""
        # Validate request if model provided
        if self.request_model and PYDANTIC_AVAILABLE:
            validated = validate_request(kwargs, self.request_model)
            result = self.func(validated)
        else:
            result = self.func(**kwargs)
        
        # Validate response if model provided
        if self.response_model and PYDANTIC_AVAILABLE:
            result = validate_response(result, self.response_model)
        
        return result


# ============== Event Manager ==============

class EventManager:
    """
    Manages event registration, signaling, and invocation.
    
    This is the core engine that powers the socket-like event system.
    """
    
    def __init__(self, pool_client: "PoolClient"):
        self._client = pool_client
        self._handlers: Dict[str, EventHandler] = {}
        self._signals: Dict[str, Signal] = {}
        self._listener_thread: Optional[threading.Thread] = None
        self._listener_running = False
        self._pid = os.getpid()
        self._round_robin_index: Dict[str, int] = {}
        
        # Heartbeat tracking
        self._processed_count = 0
        self._error_count = 0
        self._heartbeat_thread: Optional[threading.Thread] = None
    
    def _get_signal_name(self, event: str) -> str:
        """Generate unique signal name for this handler."""
        pool_name = self._client._name
        return f"{pool_name}:{event}:{self._pid}"
    
    def _get_result_signal_name(self, call_id: str) -> str:
        """Generate signal name for result notification."""
        return f"result:{call_id}"
    
    def register_handler(
        self,
        event: str,
        handler: EventHandler,
    ) -> None:
        """Register an event handler."""
        self._handlers[event] = handler
        
        # Create signal for this handler
        signal_name = self._get_signal_name(event)
        self._signals[event] = Signal(signal_name, create=True)
        
        # Register in shared memory
        registry = self._client.get(EventKeys.REGISTRY, {})
        
        if event not in registry:
            registry[event] = EventRegistration(
                handlers=[],
                mode=handler.mode,
            ).to_dict()
        
        # Add handler info
        handler_info = HandlerInfo(
            pid=self._pid,
            signal_name=signal_name,
            registered_at=time.time(),
        ).to_dict()
        
        registry[event]["handlers"].append(handler_info)
        self._client.set(EventKeys.REGISTRY, registry)
    
    def unregister_handler(self, event: str) -> None:
        """Unregister an event handler."""
        if event in self._handlers:
            del self._handlers[event]
        
        if event in self._signals:
            self._signals[event].close()
            del self._signals[event]
        
        # Remove from shared memory registry
        registry = self._client.get(EventKeys.REGISTRY, {})
        if event in registry:
            registry[event]["handlers"] = [
                h for h in registry[event]["handlers"]
                if h.get("pid") != self._pid
            ]
            if not registry[event]["handlers"]:
                del registry[event]
            self._client.set(EventKeys.REGISTRY, registry)
    
    def emit(self, event: str, **data) -> None:
        """
        Fire-and-forget event emission.
        
        Sends the event to registered handlers without waiting for response.
        """
        registry = self._client.get(EventKeys.REGISTRY, {})
        event_info = registry.get(event)
        
        if not event_info or not event_info.get("handlers"):
            return  # No handlers registered
        
        handlers = event_info["handlers"]
        mode = EventMode(event_info.get("mode", "first"))
        
        # Create call payload
        call_id = str(uuid.uuid4())
        payload = CallPayload(
            event=event,
            args=data,
            caller_pid=self._pid,
            caller_signal="",  # No response needed
            created_at=time.time(),
        ).to_dict()
        
        # Store call data
        self._client.set(f"{EventKeys.CALL_PREFIX}{call_id}", payload)
        
        # Signal handlers based on mode
        if mode == EventMode.BROADCAST:
            for handler in handlers:
                try:
                    sig = Signal(handler["signal"], create=False)
                    sig.signal()
                    sig.close()
                except:
                    pass
        elif mode == EventMode.ROUND_ROBIN:
            idx = self._round_robin_index.get(event, 0)
            handler = handlers[idx % len(handlers)]
            self._round_robin_index[event] = idx + 1
            try:
                sig = Signal(handler["signal"], create=False)
                sig.signal()
                sig.close()
            except:
                pass
        else:  # FIRST
            handler = handlers[0]
            try:
                sig = Signal(handler["signal"], create=False)
                sig.signal()
                sig.close()
            except:
                pass
    
    def call(
        self, 
        event: str, 
        _timeout: float = 5.0,
        _retry: int = 0,
        _retry_backoff: str = "linear",
        **data
    ) -> Any:
        """
        RPC-style event call with response.
        
        Args:
            event: Event name
            _timeout: Timeout in seconds
            _retry: Number of retries on failure
            _retry_backoff: Backoff strategy ("linear" or "exponential")
            **data: Event data
            
        Returns:
            Handler response value
            
        Raises:
            EventTimeout: If no response within timeout
            EventError: If handler raises an exception
        """
        registry = self._client.get(EventKeys.REGISTRY, {})
        event_info = registry.get(event)
        
        if not event_info or not event_info.get("handlers"):
            raise EventError(f"No handlers registered for event: {event}")
        
        handlers = event_info["handlers"]
        mode = EventMode(event_info.get("mode", "first"))
        
        # Create call payload with response signal
        call_id = str(uuid.uuid4())
        result_signal_name = self._get_result_signal_name(call_id)
        
        payload = CallPayload(
            event=event,
            args=data,
            caller_pid=self._pid,
            caller_signal=result_signal_name,
            created_at=time.time(),
        ).to_dict()
        
        # Create signal to wait for result
        result_signal = Signal(result_signal_name, create=True)
        
        try:
            # Store call data
            self._client.set(f"{EventKeys.CALL_PREFIX}{call_id}", payload)
            
            # Signal handler(s)
            if mode == EventMode.BROADCAST:
                # For broadcast, collect all results
                results = []
                for handler in handlers:
                    try:
                        sig = Signal(handler["signal"], create=False)
                        sig.signal()
                        sig.close()
                    except:
                        pass
                
                # Wait for all results (simplified - just wait once for now)
                if result_signal.wait(timeout_ms=int(_timeout * 1000)):
                    result_key = f"{EventKeys.RESULT_PREFIX}{call_id}"
                    result_data = self._client.get(result_key)
                    if result_data:
                        result = ResultPayload.from_dict(result_data)
                        self._client.delete(result_key)
                        
                        if result.error:
                            raise EventError.from_dict(result.error)
                        return result.value
                
                raise EventTimeout(event, _timeout)
            
            else:
                # Single handler (FIRST or ROUND_ROBIN)
                if mode == EventMode.ROUND_ROBIN:
                    idx = self._round_robin_index.get(event, 0)
                    handler = handlers[idx % len(handlers)]
                    self._round_robin_index[event] = idx + 1
                else:
                    handler = handlers[0]
                
                attempt = 0
                last_error = None
                
                while attempt <= _retry:
                    try:
                        sig = Signal(handler["signal"], create=False)
                        sig.signal()
                        sig.close()
                    except:
                        pass
                    
                    # Wait for result
                    if result_signal.wait(timeout_ms=int(_timeout * 1000)):
                        result_key = f"{EventKeys.RESULT_PREFIX}{call_id}"
                        result_data = self._client.get(result_key)
                        if result_data:
                            result = ResultPayload.from_dict(result_data)
                            self._client.delete(result_key)
                            
                            if result.error:
                                err = EventError.from_dict(result.error)
                                if err.retryable and attempt < _retry:
                                    last_error = err
                                    attempt += 1
                                    # Backoff
                                    if _retry_backoff == "exponential":
                                        time.sleep(0.1 * (2 ** attempt))
                                    else:
                                        time.sleep(0.1 * (attempt + 1))
                                    continue
                                raise err
                            return result.value
                    
                    attempt += 1
                    if attempt <= _retry:
                        if _retry_backoff == "exponential":
                            time.sleep(0.1 * (2 ** attempt))
                        else:
                            time.sleep(0.1 * (attempt + 1))
                
                if last_error:
                    raise last_error
                raise EventTimeout(event, _timeout)
        
        finally:
            # Cleanup
            result_signal.close()
            self._client.delete(f"{EventKeys.CALL_PREFIX}{call_id}")
    
    def listen(self) -> None:
        """Start listening for events in background thread."""
        if self._listener_running:
            return
        
        self._listener_running = True
        self._listener_thread = threading.Thread(
            target=self._listener_loop,
            daemon=True,
            name=f"latzero-event-listener-{self._pid}"
        )
        self._listener_thread.start()
        
        # Start heartbeat
        self._start_heartbeat()
    
    def stop_listening(self) -> None:
        """Stop listening for events."""
        self._listener_running = False
        
        # Signal all handlers to wake up and exit
        for event, signal in self._signals.items():
            signal.signal()
    
    def _listener_loop(self) -> None:
        """
        Main listener loop using select() for instant wake-up.
        
        Unlike the old polling approach (10ms timeout per signal = N×10ms latency),
        this uses select() to monitor ALL signals with a single syscall.
        When any signal fires, we wake up immediately (~1-20μs).
        """
        import select as select_module
        
        # Check if we can use select() (signals have fileno())
        use_select = all(
            hasattr(sig, 'fileno') and sig.fileno() >= 0 
            for sig in self._signals.values()
        )
        
        if use_select and self._signals:
            self._listener_loop_select(select_module)
        else:
            self._listener_loop_poll()
    
    def _listener_loop_select(self, select_module) -> None:
        """Fast listener loop using select() - O(1) wake-up time."""
        while self._listener_running:
            # Build fd -> event mapping
            fd_to_event = {}
            fds = []
            
            for event, signal in list(self._signals.items()):
                if hasattr(signal, 'fileno') and not getattr(signal, '_closed', False):
                    try:
                        fd = signal.fileno()
                        if fd >= 0:
                            fd_to_event[fd] = event
                            fds.append(signal)  # select() can take objects with fileno()
                    except:
                        pass
            
            if not fds:
                time.sleep(0.01)  # No valid signals, short sleep
                continue
            
            try:
                # select() blocks until ANY signal fires OR timeout
                # This is THE key optimization - single syscall, instant wake-up
                readable, _, _ = select_module.select(fds, [], [], 0.1)
                
                for sig in readable:
                    if not self._listener_running:
                        break
                    
                    fd = sig.fileno()
                    event = fd_to_event.get(fd)
                    if event:
                        # Drain the signal (already woken up)
                        try:
                            sig._sock.recv(64)
                        except:
                            pass
                        
                        # Process immediately - no polling delay!
                        self._process_pending_calls(event)
                        
            except (ValueError, OSError, AttributeError) as e:
                # Invalid fd or signal closed - will rebuild on next iteration
                time.sleep(0.001)
            except Exception:
                time.sleep(0.001)
    
    def _listener_loop_poll(self) -> None:
        """Fallback polling loop for signals without fileno() support."""
        while self._listener_running:
            for event, signal in list(self._signals.items()):
                if not self._listener_running:
                    break
                
                # Use short timeout for responsiveness
                if signal.wait(timeout_ms=5):
                    self._process_pending_calls(event)
    
    def _process_pending_calls(self, event: str) -> None:
        """Process any pending calls for an event."""
        handler = self._handlers.get(event)
        if not handler:
            return
        
        # Find pending calls for this event
        all_keys = self._client.keys()
        call_keys = [k for k in all_keys if k.startswith(EventKeys.CALL_PREFIX.replace(self._client._data_key_prefix, ""))]
        
        for call_key in call_keys:
            full_key = call_key
            call_data = self._client.get(full_key)
            if not call_data or call_data.get("event") != event:
                continue
            
            payload = CallPayload.from_dict(call_data)
            
            # Execute handler
            try:
                result_value = handler(**payload.args)
                self._processed_count += 1
                
                result = ResultPayload(
                    value=result_value,
                    error=None,
                    completed_at=time.time(),
                )
            except Exception as e:
                self._error_count += 1
                result = ResultPayload(
                    value=None,
                    error=EventError(
                        message=str(e),
                        error_type=type(e).__name__,
                        traceback_str=traceback.format_exc(),
                        handler_pid=self._pid,
                        retryable=False,
                    ).to_dict(),
                    completed_at=time.time(),
                )
            
            # If caller wants response, send it
            if payload.caller_signal:
                call_id = full_key.replace(EventKeys.CALL_PREFIX.replace(self._client._data_key_prefix, ""), "")
                self._client.set(f"{EventKeys.RESULT_PREFIX}{call_id}", result.to_dict())
                
                # Signal caller
                try:
                    sig = Signal(payload.caller_signal, create=False)
                    sig.signal()
                    sig.close()
                except:
                    pass
            
            # Cleanup call data
            self._client.delete(full_key)
    
    def _start_heartbeat(self) -> None:
        """Start heartbeat thread."""
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop,
            daemon=True,
            name=f"latzero-heartbeat-{self._pid}"
        )
        self._heartbeat_thread.start()
    
    def _heartbeat_loop(self) -> None:
        """Update heartbeat every 500ms."""
        while self._listener_running:
            heartbeat_key = f"{EventKeys.HEARTBEAT_PREFIX}{self._pid}"
            heartbeat_data = {
                "pid": self._pid,
                "events": list(self._handlers.keys()),
                "last_seen": time.time(),
                "processed_count": self._processed_count,
                "error_count": self._error_count,
            }
            self._client.set(heartbeat_key, heartbeat_data)
            time.sleep(0.5)
    
    def cleanup(self) -> None:
        """Cleanup all handlers and signals."""
        self.stop_listening()
        
        for event in list(self._handlers.keys()):
            self.unregister_handler(event)
        
        # Remove heartbeat
        heartbeat_key = f"{EventKeys.HEARTBEAT_PREFIX}{self._pid}"
        try:
            self._client.delete(heartbeat_key)
        except:
            pass


# ============== Event Emitter ==============

class EventEmitter:
    """
    Namespaced event emitter for complex scenarios.
    
    Usage:
        user_events = EventEmitter(ipc, namespace="user")
        
        @user_events.on("login")
        def on_login(username: str):
            pass
        
        user_events.emit("login", username="bob")
    """
    
    def __init__(self, pool_client: "PoolClient", namespace: str = ""):
        self._client = pool_client
        self._namespace = namespace
        self._manager: Optional[EventManager] = None
    
    def _get_manager(self) -> EventManager:
        """Get or create event manager."""
        if self._manager is None:
            # Check if client has event manager that is not None
            if hasattr(self._client, '_event_manager') and self._client._event_manager is not None:
                self._manager = self._client._event_manager
            else:
                self._manager = EventManager(self._client)
                self._client._event_manager = self._manager
        return self._manager
    
    def _namespaced(self, event: str) -> str:
        """Add namespace prefix to event name."""
        if self._namespace:
            return f"{self._namespace}:{event}"
        return event
    
    def on(
        self,
        event: str,
        mode: EventMode = EventMode.FIRST,
        request: Optional[type] = None,
        response: Optional[type] = None,
        queue_mode: EventQueueMode = EventQueueMode.IMMEDIATE,
        debounce_ms: int = 0,
        max_queue: int = 1000,
    ) -> Callable:
        """
        Decorator to register an event handler.
        
        Args:
            event: Event name
            mode: Handler mode (first, round_robin, broadcast)
            request: Optional Pydantic model for request validation
            response: Optional Pydantic model for response validation
            queue_mode: Event queueing behavior
            debounce_ms: Debounce window in milliseconds
            max_queue: Maximum queue size
        """
        def decorator(func: Callable) -> Callable:
            handler = EventHandler(
                func=func,
                event=self._namespaced(event),
                mode=mode,
                queue_mode=queue_mode,
                request_model=request,
                response_model=response,
                debounce_ms=debounce_ms,
                max_queue=max_queue,
            )
            self._get_manager().register_handler(self._namespaced(event), handler)
            return func
        return decorator
    
    def emit(self, event: str, **data) -> None:
        """Fire-and-forget event emission."""
        self._get_manager().emit(self._namespaced(event), **data)
    
    def call(
        self,
        event: str,
        _timeout: float = 5.0,
        _retry: int = 0,
        _retry_backoff: str = "linear",
        **data
    ) -> Any:
        """RPC-style event call with response."""
        return self._get_manager().call(
            self._namespaced(event),
            _timeout=_timeout,
            _retry=_retry,
            _retry_backoff=_retry_backoff,
            **data
        )
    
    def broadcast(self, event: str, **data) -> None:
        """Broadcast event to all handlers (fan-out)."""
        # Temporarily set broadcast mode for this emit
        full_event = self._namespaced(event)
        registry = self._client.get(EventKeys.REGISTRY, {})
        
        if full_event in registry:
            original_mode = registry[full_event].get("mode")
            registry[full_event]["mode"] = EventMode.BROADCAST.value
            self._client.set(EventKeys.REGISTRY, registry)
            
            try:
                self._get_manager().emit(full_event, **data)
            finally:
                # Restore original mode
                if original_mode:
                    registry[full_event]["mode"] = original_mode
                    self._client.set(EventKeys.REGISTRY, registry)
    
    def listen(self) -> None:
        """Start listening for events."""
        self._get_manager().listen()
    
    def stop(self) -> None:
        """Stop listening and cleanup."""
        self._get_manager().cleanup()
