## 🧠 **Product Requirements Document (PRD)**

### Product: `latzero`

**Tagline:** Zero-latency, zero-fuss shared memory for Python — dynamic, encrypted, and insanely fast.

---

### 🚀 1. Overview

**latzero** is a Python package designed to make **inter-process communication (IPC)** and **shared-memory data exchange** effortless.
Unlike traditional shared memory systems that require fixed buffer sizes and manual serialization, latzero enables developers to:

* Create **dynamic shared-memory pools** accessible by multiple processes or clients.
* Pass **any pickleable object** directly — no manual encoding/decoding.
* Enable **optional encryption + authentication** for secure multi-process collaboration.

latzero is ideal for AI workloads, distributed systems, and low-latency microservices that need real-time shared state management.

---

### 🧩 2. Core Features

| Feature                         | Description                                                                                                                      |
| ------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| **Dynamic Shared Memory Pools** | No predefined memory size. Pools expand and contract dynamically as new data arrives.                                            |
| **Multi-Client Access**         | Multiple processes/clients can connect to the same pool simultaneously and share data in real time.                              |
| **Auto Cleanup**                | Data can have optional timeouts (`auto_clean=5`), automatically clearing entries after specified seconds.                        |
| **Encryption & Authentication** | Pools can be protected with passwords. If `encryption=True`, the password becomes the encryption key.                            |
| **Data-Type Preservation**      | Stored data retains its type (`int`, `str`, `dict`, etc.) across clients.                                                        |
| **Self-Destructing Pools**      | Pools live only as long as one or more connected processes are active. When all disconnect, the pool is automatically destroyed. |
| **Pickle-Based Serialization**  | Any pickleable Python object can be stored and retrieved seamlessly.                                                             |
| **Event Sync** *(Future)*       | Hooks for client events like `on_connect`, `on_disconnect`, `on_update` for real-time sync logic.                                |

---

### ⚙️ 3. API Design

#### **Pool Creation**

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

* **name** *(str)*: Unique identifier for the pool.
* **auth** *(bool)*: Enables password-protected access.
* **auth_key** *(str)*: Password or encryption key.
* **encryption** *(bool)*: Encrypts data using AES-256 (if enabled).

---

#### **Connecting to a Pool**

```python
from latzero import SharedMemoryPool

pool_manager = SharedMemoryPool()
ipc_ = pool_manager.connect(
    name="myPool",
    auth_key="super_secret"
)
```

* Establishes connection to an existing pool.
* Handles automatic decryption (if applicable).

---

#### **Set and Get Operations**

```python
ipc_.set("key", value, auto_clean=5)
ipc_.get("key")
```

* **set(key, value, auto_clean=None)**: Stores `value` under `key`. Optional timeout auto-clears the entry.
* **get(key)**: Retrieves stored data. Returns correct type automatically.

---

#### **Type-Safe Example**

```python
ipc_.set("number", 42)
ipc_.set("text", "yo bro")
ipc_.set("data", {"a": 1, "b": 2})

print(ipc_.get("number"))  # 42 (int)
print(ipc_.get("text"))    # "yo bro" (str)
print(ipc_.get("data"))    # {"a": 1, "b": 2} (dict)
```

---

### 🛠️ 4. System Architecture

#### **Core Components**

1. **Memory Controller**

   * Manages shared memory segments dynamically.
   * Handles process reference counting (to destroy pool when unused).

2. **Pool Registry**

   * Tracks all active pools via a small shared index table (metadata).
   * Each pool’s metadata includes name, encryption state, clients connected, and last heartbeat.

3. **Encryption Layer**

   * AES-GCM encryption for secure reads/writes.
   * Uses pool `auth_key` as symmetric key.

4. **Data Layer (Pickle Serializer)**

   * Automatic pickle-based serialization and deserialization of objects.
   * Uses `zlib` compression for memory efficiency.

5. **IPC Protocol**

   * Processes communicate using `multiprocessing.shared_memory` + a small socket or pipe abstraction for signals and metadata exchange.

6. **Auto-Reclaim Daemon**

   * Background thread that monitors idle pools and clears them when no clients remain.

---

### 🔒 5. Security Model

| Concern             | Mechanism                                                             |
| ------------------- | --------------------------------------------------------------------- |
| Unauthorized access | Password-based authentication                                         |
| Data leakage        | AES-256 encryption when `encryption=True`                             |
| Data tampering      | Integrity checked using HMAC                                          |
| Memory persistence  | Pools are ephemeral; memory is released after last client disconnects |

---

### ⚡ 6. Performance Targets

| Metric                 | Target                             |
| ---------------------- | ---------------------------------- |
| Read latency           | < 1ms                              |
| Write latency          | < 2ms                              |
| Max concurrent clients | 128+                               |
| Memory scaling         | Dynamic up to available system RAM |
| Pool cleanup delay     | < 100ms post last disconnect       |

---

### 🧪 7. Testing Plan

* **Unit Tests:**

  * Serialization/deserialization validation
  * Encryption/decryption consistency
  * Auto-clean and pool lifecycle behavior
* **Load Tests:**

  * Multi-client concurrent reads/writes
  * Latency benchmarks under 10k ops/sec
* **Security Tests:**

  * Brute-force attempt resistance
  * Memory dump verification

---

### 🧰 8. Dependencies

* `multiprocessing.shared_memory`
* `cryptography` (for AES)
* `pickle`, `zlib`
* `threading`, `asyncio` (for pool watchers)
* `psutil` (for process detection / cleanup)

---

### 🧱 9. Directory Structure

```
latzero/
│
├── __init__.py
├── core/
│   ├── memory.py          # Core Shared Memory logic
│   ├── pool.py            # Pool Manager and client handling
│   ├── encryption.py      # AES utilities
│   ├── registry.py        # Global Pool Index Table
│   └── cleanup.py         # Auto-clean daemon
│
├── utils/
│   ├── serializer.py
│   ├── type_checker.py
│   └── exceptions.py
│
└── examples/
    ├── simple_pool.py
    ├── encrypted_pool.py
    └── multi_client_demo.py
```

---

### 🧭 10. Roadmap

| Phase       | Description                                        | ETA       |
| ----------- | -------------------------------------------------- | --------- |
| **Phase 1** | Core shared memory pools + pickle serialization    | Week 1–2  |
| **Phase 2** | Auth + encryption                                  | Week 3    |
| **Phase 3** | Dynamic memory expansion + auto-clean              | Week 4    |
| **Phase 4** | Performance optimization + release on PyPI         | Week 5    |
| **Phase 5** | Optional: real-time event hooks, WebSocket bridges | Post v1.0 |

---

### 🧃 11. Example Use Cases

* AI agents sharing memory (e.g., multiple worker models collaborating).
* Game servers syncing player states across processes.
* Local data caching layer between microservices.
* High-speed analytics engines (shared embeddings, configs, etc.).
* On-device multi-agent orchestration (e.g., BRAHMAI OS1 modules 😉).

---

### 🧠 TL;DR

`latzero` makes **shared-memory IPC as easy as Redis**, without the network overhead.
Fast, simple, encrypted, ephemeral — a *zero-latency* memory layer for Python devs who care about performance.