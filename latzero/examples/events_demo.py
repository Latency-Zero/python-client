"""
latzero Events Example - Socket-like IPC

Demonstrates the socket.io-style event system for inter-process communication.
Events use OS-native signaling (Windows Named Events / POSIX Semaphores) for
instant wake-up with zero polling overhead.

Run this file to see events in action.
"""

from latzero import SharedMemoryPool

POOL_NAME = "events_demo"


def main():
    pm = SharedMemoryPool()
    pm.create(POOL_NAME)
    
    print("=" * 50)
    print("  latzero Events Demo")
    print("=" * 50)
    
    with pm.connect(POOL_NAME) as ipc:
        
        # ─────────────────────────────────────────────
        # 1. Register event handlers using decorator
        # ─────────────────────────────────────────────
        
        @ipc.on_event("compute:multiply")
        def multiply(x: int, y: int) -> int:
            """RPC handler - returns a value to caller."""
            result = x * y
            print(f"  [Handler] compute:multiply({x}, {y}) = {result}")
            return result
        
        @ipc.on_event("user:login")
        def handle_login(username: str, session_id: str):
            """Fire-and-forget handler - no return needed."""
            print(f"  [Handler] user:login: {username} (session: {session_id})")
        
        @ipc.on_event("ping")
        def pong():
            """Simple ping-pong handler."""
            return "pong"
        
        # Start background listener (non-blocking)
        ipc.listen()
        print("\n✓ Event handlers registered and listening\n")
        
        # ─────────────────────────────────────────────
        # 2. Fire-and-forget emit (no response)
        # ─────────────────────────────────────────────
        
        print("Testing emit (fire-and-forget)...")
        ipc.emit_event("user:login", username="alice", session_id="abc123")
        
        import time
        time.sleep(0.1)  # Let handler process
        
        # ─────────────────────────────────────────────
        # 3. RPC-style call (waits for response)
        # ─────────────────────────────────────────────
        
        print("\nTesting call (RPC with response)...")
        
        result = ipc.call_event("compute:multiply", x=7, y=6, _timeout=1.0)
        print(f"  Result: {result}")
        assert result == 42, "Math is broken!"
        
        result = ipc.call_event("ping", _timeout=1.0)
        print(f"  Ping response: {result}")
        assert result == "pong"
        
        # ─────────────────────────────────────────────
        # 4. Namespaced emitters
        # ─────────────────────────────────────────────
        
        print("\nTesting namespaced emitters...")
        
        compute = ipc.event_emitter("compute")
        
        @compute.on("add")
        def add(a: int, b: int) -> int:
            return a + b
        
        compute.listen()
        
        result = compute.call("add", a=10, b=5, _timeout=1.0)
        print(f"  compute:add(10, 5) = {result}")
        assert result == 15
        
        # ─────────────────────────────────────────────
        # 5. Cleanup
        # ─────────────────────────────────────────────
        
        ipc.stop_events()
        print("\n✓ Events stopped and cleaned up")
    
    pm.destroy(POOL_NAME)
    
    print("\n" + "=" * 50)
    print("  Demo Complete!")
    print("=" * 50)


if __name__ == "__main__":
    main()
