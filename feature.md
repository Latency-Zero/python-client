# latzero - Improvement & Feature Roadmap

A comprehensive list of improvements and features to enhance latzero.

---

## 🔴 Critical Fixes

### 1. Race Conditions in Registry
- `PoolRegistry` lacks proper inter-process locking
- Multiple processes reading/writing shared memory simultaneously can corrupt data
- **Fix**: Use file-based locks (`fcntl`/`msvcrt`) or `multiprocessing.Lock` with a manager

### 2. Memory Expansion Not Implemented
- `SharedMemoryPoolData` has `MAX_SIZE = 100MB` but no expansion logic
- Currently throws error if data exceeds initial 1MB allocation
- **Fix**: Implement dynamic resizing or chained memory segments

### 3. CleanupDaemon is Non-Functional
- `cleanup.py` is just a placeholder with empty `_run()` loop
- Expired entries and orphaned pools persist
- **Fix**: Implement actual cleanup logic using `psutil` for process detection

---

## 🟠 Reliability Improvements

### 4. Proper Shared Memory Cleanup
- On Windows, shared memory can leak if process crashes
- Add recovery mechanism to detect and clean orphaned segments
- Implement a heartbeat system for client liveness detection

### 5. Lock Per Key (Fine-Grained Locking)
- Currently one lock per pool blocks all operations
- High contention under concurrent writes
- **Fix**: Implement per-key or striped locking

### 6. Atomic Operations
- Add `increment()`, `decrement()`, `append()` for common atomic operations
- Prevents read-modify-write race conditions

### 7. Error Handling & Recovery
- Better exception messages with context
- Graceful handling of corrupted shared memory
- Auto-reconnect on transient failures

---

## 🟡 Performance Optimizations

### 8. Lazy Serialization
- Only serialize on `set()`, skip if value unchanged
- Cache deserialized values in `PoolClient` for repeated reads

### 9. Batch Operations
- Add `mset(dict)` and `mget(keys)` for bulk read/write
- Reduces lock acquisition overhead

### 10. Memory-Mapped Files Alternative
- Current `multiprocessing.shared_memory` has size limits on some OS
- Offer `mmap` backend as fallback

### 11. Compression Toggle
- zlib compression adds latency for small values
- Make compression optional or threshold-based (e.g., only compress > 1KB)

---

## 🟢 Feature Additions

### 12. Event Hooks (Already in PRD)
- `on_connect`, `on_disconnect`, `on_update` callbacks
- Enable reactive programming patterns

### 13. Key Expiration Notifications
- Callback when auto_clean triggers
- Allow renewal/extension of TTL

### 14. Namespace Support
- Logical grouping: `pool.namespace("users").set("123", data)`
- Simpler key management

### 15. Iterator/Scan Operations
- `keys()`, `values()`, `items()` with prefix filtering
- Pagination for large datasets

### 16. Pool Statistics
- `pool.stats()` → memory usage, key count, client count, uptime
- Useful for monitoring/debugging

### 17. Read-Only Clients
- `pool.connect(name, readonly=True)` for consumers
- Prevents accidental writes

### 18. Persistence Layer (Optional)
- Snapshot pool to disk on shutdown
- Restore on startup
- Useful for warm-start scenarios

### 19. TTL Per Pool (Not Just Per Key)
- Entire pool auto-destructs after N seconds of inactivity
- Useful for ephemeral workloads

### 20. WebSocket Bridge
- Expose pools to remote clients over WebSocket
- Enable cross-machine IPC (at cost of latency)

---

## 🔵 Developer Experience

### 21. CLI Tool
```bash
latzero list              # Show active pools
latzero inspect <pool>    # Show keys, metadata
latzero clear <pool>      # Force cleanup
```

### 22. Better Logging
- Structured logging with levels (DEBUG, INFO, WARNING)
- Optional verbose mode for debugging

### 23. Type Hints
- Add full type annotations to all modules
- Enables IDE autocompletion and static analysis

### 24. Async/Await Support
- `async def get()` / `async def set()` variants
- Integrate with `asyncio` event loops

### 25. Context Manager Protocol
```python
with pool.connect("myPool") as ipc:
    ipc.set("key", "value")
# Auto-disconnect on exit
```

### 26. Documentation
- Docstrings on all public methods
- Sphinx/MkDocs site with examples
- Benchmark results vs Redis, Memcached

---

## 📦 Packaging & CI

### 27. Unit Tests
- Test coverage for all modules
- Mock shared memory for isolation

### 28. CI Pipeline
- GitHub Actions for linting, testing, publishing
- Auto-versioning on release

### 29. Cross-Platform Testing
- Verify behavior on Windows, Linux, macOS
- Handle OS-specific shared memory quirks

---

## Priority Matrix

| Priority | Items |
|----------|-------|
| **P0** (Blocking) | #1, #2, #3 |
| **P1** (Important) | #4, #5, #6, #7, #25, #27 |
| **P2** (Nice to Have) | #8–#11, #21–#24, #26 |
| **P3** (Future) | #12–#20, #28, #29 |
