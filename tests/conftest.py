"""
pytest fixtures for latzero tests.
"""

import pytest
import uuid
import time


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
