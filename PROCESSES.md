# LatZero Python Client — Process Pool

The **Process Pool** lets any client publish named functions and have other
clients call them by name, without needing to know connection details in
advance.

---

## Quick Start

```python
from latzero import LatZero

client = LatZero("latzero://worker-1", pool="my-pool", host="127.0.0.1", port=14130)
```

The process pool API lives entirely under **`client.process`**.

---

## Registering a Process

### As a decorator (recommended)

```python
@client.process.register
def add(x, y):
    return x + y
# Registered as "worker-1:add"
```

### With an explicit name override

```python
@client.process.register(name="sum_two")
def add(x, y):
    return x + y
# Registered as "worker-1:sum_two"
```

### Direct call (pre-defined function)

```python
def multiply(x, y):
    return x * y

client.process.register(multiply)             # name inferred: "multiply"
client.process.register(multiply, name="mul") # explicit override
```

### Async functions

```python
@client.process.register
async def slow_task(prompt):
    await asyncio.sleep(1)
    return f"done: {prompt}"
# Async functions are automatically wrapped and run safely in the receiver thread.
```

> **Name inference rule** — the function's `__name__` is used automatically.
> Anonymous lambdas must always receive an explicit `name=` argument.

---

## Calling a Process

Process IDs are always **`client_id:process_name`**.

```python
# On a *different* client (or the same one)
caller = LatZero("latzero://caller-1", pool="my-pool")

result = caller.process.call("worker-1:add", x=3, y=4)
print(result)  # 7
```

Keyword arguments after the process ID are forwarded to the function as `**data`.

### Timeout

```python
result = caller.process.call("worker-1:slow_task", _timeout=10.0, prompt="hello")
```

### Triangular routing — send the result to a third client

```python
# caller-1 triggers the work; the result arrives at logger-1 instead
caller.process.call(
    "worker-1:add",
    response_to="logger-1",   # result is delivered here, not to the caller
    x=3, y=4,
)
# Returns None immediately; "logger-1" receives an app_result push.
```

---

## Broadcasting

Call **every** registered instance of a short process name across the pool at once.

```python
# worker-1 and worker-2 both registered "add"
targets = caller.process.broadcast("add", x=3, y=4)
print(targets)  # ["worker-1:add", "worker-2:add"]
```

With result redirect:

```python
caller.process.broadcast("add", response_to="logger-1", x=3, y=4)
```

Broadcast is fire-and-forget at the aggregation level — individual results are
delivered to `response_to` (or the caller) independently.

---

## Listing Processes

```python
# All registered processes in the pool
procs = caller.process.list()
# {"worker-1:add": "worker-1", "worker-2:multiply": "worker-2"}

# Filter by owner
procs = caller.process.list("worker-1")
# {"worker-1:add": "worker-1"}
```

---

## Unregistering a Process

```python
client.process.unregister("add")
# Removes "worker-1:add" from the pool immediately.
```

> **Auto-cleanup** — all processes owned by a client are automatically
> unregistered when the client disconnects.

---

## Full Example

```python
# ── worker.py ──────────────────────────────────────────────────────────────
from latzero import LatZero
import time

worker = LatZero("latzero://worker-1", pool="demo")

@worker.process.register
def add(x, y):
    return x + y

@worker.process.register
def greet(name):
    return f"Hello, {name}!"

print("Worker ready. Registered processes:")
print(worker.process.list("worker-1"))

# Keep alive
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    worker.disconnect()
```

```python
# ── caller.py ──────────────────────────────────────────────────────────────
from latzero import LatZero

caller = LatZero("latzero://caller-1", pool="demo")

# Simple blocking call
result = caller.process.call("worker-1:add", x=10, y=32)
print(result)   # 42

msg = caller.process.call("worker-1:greet", name="World")
print(msg)      # Hello, World!

# Discover what's available
print(caller.process.list())

caller.disconnect()
```

---

## Error Handling

```python
from latzero.utils.exceptions import ServerProtocolError

try:
    result = caller.process.call("worker-1:add", x=1, y=2)
except ServerProtocolError as e:
    print(f"Handler raised an error: {e}")
except TimeoutError:
    print("Process did not respond in time.")
```

| Server error code       | Meaning                                            |
|-------------------------|----------------------------------------------------|
| `process_not_found`     | No process with that ID is registered in the pool  |
| `process_owner_offline` | The owning client disconnected before responding   |

---

## API Reference

| Method | Description |
|---|---|
| `client.process.register(fn, *, name=None)` | Register a function. Works as decorator or direct call. |
| `client.process.unregister(name)` | Remove a process registration. |
| `client.process.call(process_id, response_to=None, _timeout=5.0, **data)` | Call one process. Blocking unless `response_to` is set. |
| `client.process.broadcast(process_name, response_to=None, **data)` | Call all processes with matching short name. |
| `client.process.list(pattern=None)` | List registered processes, optionally filtered by owner prefix. |
