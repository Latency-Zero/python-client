# latzero

**Zero-latency, zero-fuss shared memory for Python — dynamic, encrypted, and insanely fast.**

🚀 **170,000+ ops/sec** | ⚡ **0.006ms latency** | 🔒 **AES-256 encryption**

## Overview

**latzero** is a Python package designed to make inter-process communication (IPC) and shared-memory data exchange effortless. Unlike traditional shared memory systems that require fixed buffer sizes and manual serialization, latzero enables developers to:

- Create dynamic shared-memory pools accessible by multiple processes or clients
- Pass any pickleable object directly — no manual encoding/decoding
- Enable optional encryption and authentication for secure multi-process collaboration

latzero is ideal for AI workloads, distributed systems, and low-latency microservices that need real-time shared state management.

## Core Features

**Dynamic Shared Memory Pools**  
No predefined memory size. Pools expand and contract dynamically as new data arrives.

**Multi-Client Access**  
Multiple processes/clients can connect to the same pool simultaneously and share data in real time.

**Auto Cleanup**  
Data can have optional timeouts (`auto_clean=5`), automatically clearing entries after specified seconds.

**Encryption & Authentication**  
Pools can be protected with passwords. If `encryption=True`, the password becomes the encryption key.

**Data-Type Preservation**  
Stored data retains its type (`int`, `str`, `dict`, etc.) across clients.

**High-Performance Batched Writes**  
Use `set_fast()` + `flush()` for 77,000+ writes/sec. Standard `set()` syncs immediately.

**Self-Destructing Pools**  
Pools live only as long as one or more connected processes are active. When all disconnect, the pool is automatically destroyed.

**Pickle + msgpack Serialization**  
Any pickleable Python object can be stored. Use msgpack for 3-5x faster serialization.

**Event Hooks**  
Hooks for client events: `on_connect`, `on_disconnect`, `on_update`, `on_delete`.

**Socket-like Events API**  
RPC-style `emit()` and `call()` for inter-process communication with OS-native signaling (~50μs latency).

**Async Support**  
Full async/await API with `AsyncSharedMemoryPool`.

**CLI Tool**  
Manage pools from command line: `latzero list`, `latzero inspect`, etc.

## Installation

```bash
pip install latzero
```

## Quick Start

### Creating a Pool

```python
from latzero import SharedMemoryPool

pool_manager = SharedMemoryPool()
pool_manager.create(
    name="myPool",
    auth=True,
    auth_key="super_secret",
    encryption=True
)
```

### Connecting to a Pool

```python
ipc = pool_manager.connect(
    name="myPool",
    auth_key="super_secret"
)
```

### Basic Operations

```python
# Set values with optional auto-cleanup
ipc.set("key", value, auto_clean=5)

# Retrieve values
result = ipc.get("key")
```

### Type-Safe Example

```python
ipc.set("number", 42)
ipc.set("text", "yo bro")
ipc.set("data", {"a": 1, "b": 2})

print(ipc.get("number"))  # 42 (int)
print(ipc.get("text"))    # "yo bro" (str)
print(ipc.get("data"))    # {"a": 1, "b": 2} (dict)
```

### High-Performance Batched Writes

```python
with pool_manager.connect("myPool", auth_key="super_secret") as client:
    # Use set_fast() for batched writes (100x faster)
    for i in range(1000):
        client.set_fast(f"key_{i}", {"value": i})

    # Flush to persist all writes
    client.flush()

    # Reads are always instant
    print(client.get("key_0"))  # {'value': 0}
```

### Events API (Socket-like IPC)

latzero provides a socket.io-style events API for RPC and fire-and-forget messaging:

```python
from latzero import SharedMemoryPool

pm = SharedMemoryPool()
pm.create("my_pool")

with pm.connect("my_pool") as ipc:
    # Register event handler
    @ipc.on_event("compute:multiply")
    def multiply(x: int, y: int) -> int:
        return x * y

    # Start background listener
    ipc.listen()

    # Fire-and-forget emit
    ipc.emit_event("user:login", username="alice")

    # RPC call with response (~50μs latency)
    result = ipc.call_event("compute:multiply", x=7, y=6, _timeout=1.0)
    print(result)  # 42

    # Namespaced emitters
    compute = ipc.event_emitter("compute")

    @compute.on("add")
    def add(a: int, b: int) -> int:
        return a + b

    compute.listen()
    result = compute.call("add", a=10, b=5)  # 15
```

## System Architecture

### Core Components

**Memory Controller**  
Manages shared memory segments dynamically.

**Pool Registry**  
Tracks all active pools via metadata.

**Encryption Layer**  
AES-GCM encryption for secure reads/writes.

**Data Layer (Pickle Serializer)**  
Automatic serialization with zlib compression.

**IPC Protocol**  
Uses `multiprocessing.shared_memory` for communication.

**Auto-Reclaim Daemon**  
Monitors idle pools and clears them when unused.

## Security Model

| Concern             | Mechanism                                                             |
| ------------------- | --------------------------------------------------------------------- |
| Unauthorized access | Password-based authentication                                         |
| Data leakage        | AES-256 encryption when `encryption=True`                             |
| Data tampering      | Integrity checked using HMAC                                          |
| Memory persistence  | Pools are ephemeral; memory is released after last client disconnects |

## Performance

| Operation                | Throughput           | Latency  |
| ------------------------ | -------------------- | -------- |
| `set_fast()` (batched)   | **77,000+ ops/sec**  | ~0.01ms  |
| `get()`                  | **287,000+ ops/sec** | ~0.003ms |
| `set()` (immediate sync) | 600 ops/sec          | ~1.6ms   |
| Mixed workload           | **146,000+ ops/sec** | ~0.007ms |

### vs Other Methods

| Method       | Throughput          | Speedup       |
| ------------ | ------------------- | ------------- |
| **latzero**  | **170,000 ops/sec** | —             |
| Raw Socket   | 5,277 ops/sec       | 32x faster    |
| HTTP (Flask) | 133 ops/sec         | 1,280x faster |

## Examples

Check the `examples/` directory for usage demos:

- `simple_pool.py` - Basic pool operations
- `encrypted_pool.py` - Secure pool with encryption
- `multi_client_demo.py` - Concurrent multi-client access
- `events_demo.py` - Socket-like events API demo

## Dependencies

- `multiprocessing.shared_memory`
- `cryptography` (for AES)
- `pickle`, `zlib`
- `threading`, `multiprocessing`
- `psutil` (for process detection)

## Roadmap

**Phase 1:** Core shared memory pools + pickle serialization  
**Phase 2:** Auth + encryption  
**Phase 3:** Dynamic memory expansion + auto-clean  
**Phase 4:** Performance optimization + PyPI release  
**Phase 5:** Real-time event hooks, WebSocket bridges

## Use Cases

- AI agents sharing memory
- Game servers syncing states
- Local caching for microservices
- High-speed analytics pipelines
- Multi-agent orchestration systems

## About

latzero makes shared-memory IPC as easy as Redis, without the network overhead. Fast, simple, encrypted, ephemeral — a zero-latency memory layer for Python developers.

**Created by BRAHMAI**  
https://brahmai.in
