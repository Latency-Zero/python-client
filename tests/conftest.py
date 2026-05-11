"""
pytest fixtures for latzero tests.
"""

import asyncio
import socket
import sys
import threading
import uuid
from pathlib import Path

import pytest


@pytest.fixture
def unique_pool_name():
    """Generate a unique pool name for each test."""
    return f"test_pool_{uuid.uuid4().hex[:8]}"


@pytest.fixture
def pool_manager():
    """Create a SharedMemoryPool instance."""
    from latzero import SharedMemoryPool
    return SharedMemoryPool(auto_cleanup=False)


@pytest.fixture
def pool_with_data(pool_manager, unique_pool_name):
    """Create a pool with some test data."""
    pool_manager.create(unique_pool_name)
    client = pool_manager.connect(unique_pool_name)
    
    # Add test data
    client.set("string_key", "test_value")
    client.set("int_key", 42)
    client.set("float_key", 3.14)
    client.set("list_key", [1, 2, 3])
    client.set("dict_key", {"a": 1, "b": 2})
    
    yield {
        "pool_manager": pool_manager,
        "pool_name": unique_pool_name,
        "client": client,
    }
    
    # Cleanup
    try:
        client.disconnect()
    except Exception:
        pass
    
    try:
        pool_manager.destroy(unique_pool_name)
    except Exception:
        pass


@pytest.fixture
def encrypted_pool(pool_manager, unique_pool_name):
    """Create an encrypted pool."""
    auth_key = "test_secret_key_123"
    pool_name = f"{unique_pool_name}_encrypted"
    
    pool_manager.create(pool_name, auth=True, auth_key=auth_key, encryption=True)
    client = pool_manager.connect(pool_name, auth_key=auth_key)
    
    yield {
        "pool_manager": pool_manager,
        "pool_name": pool_name,
        "client": client,
        "auth_key": auth_key,
    }
    
    try:
        client.disconnect()
    except Exception:
        pass
    
    try:
        pool_manager.destroy(pool_name)
    except Exception:
        pass


def cleanup_test_pools():
    """Cleanup any leftover test pools."""
    from latzero import SharedMemoryPool
    pool = SharedMemoryPool(auto_cleanup=False)
    pools = pool.list_pools()
    
    for name in pools:
        if name.startswith("test_pool_"):
            try:
                pool.destroy(name)
            except Exception:
                pass


def _free_port():
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


@pytest.fixture(scope="session")
def latzero_server():
    """Run a local latzero-server instance for integration tests."""
    server_root = Path(__file__).resolve().parents[2] / "latzero-server"
    if str(server_root) not in sys.path:
        sys.path.insert(0, str(server_root))

    from latzero_server import LatZeroServer, ServerConfig

    port = _free_port()
    data_dir = Path(__file__).resolve().parents[1] / "_server_test_state"
    data_dir.mkdir(parents=True, exist_ok=True)
    config = ServerConfig(host="127.0.0.1", port=port, data_dir=data_dir)
    server = LatZeroServer(config=config)
    loop = asyncio.new_event_loop()
    ready = threading.Event()

    async def runner():
        await server.start()
        ready.set()
        while True:
            await asyncio.sleep(3600)

    def run():
        asyncio.set_event_loop(loop)
        task = loop.create_task(runner())
        try:
            loop.run_forever()
        finally:
            task.cancel()
            loop.run_until_complete(server.stop())
            loop.run_until_complete(asyncio.sleep(0))
            loop.close()

    thread = threading.Thread(target=run, daemon=True, name="latzero-server-test")
    thread.start()
    ready.wait(timeout=5)

    yield {
        "host": config.host,
        "port": config.port,
        "data_dir": data_dir,
    }

    loop.call_soon_threadsafe(loop.stop)
    thread.join(timeout=5)
