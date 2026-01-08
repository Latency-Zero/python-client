"""
Tests for latzero.async_api module.
"""

import pytest
import asyncio


pytestmark = pytest.mark.asyncio


class TestAsyncSharedMemoryPool:
    """Tests for AsyncSharedMemoryPool class."""
    
    async def test_create_and_connect(self, unique_pool_name):
        """Test async pool creation and connection."""
        from latzero import AsyncSharedMemoryPool
        
        pool = AsyncSharedMemoryPool(auto_cleanup=False)
        await pool.create(unique_pool_name)
        
        assert await pool.exists(unique_pool_name)
        
        client = await pool.connect(unique_pool_name)
        assert client is not None
        
        await client.disconnect()
        await pool.destroy(unique_pool_name)
    
    async def test_async_set_get(self, unique_pool_name):
        """Test async set and get operations."""
        from latzero import AsyncSharedMemoryPool
        
        pool = AsyncSharedMemoryPool(auto_cleanup=False)
        await pool.create(unique_pool_name)
        
        async with await pool.connect(unique_pool_name) as client:
            await client.set("key", "value")
            result = await client.get("key")
            assert result == "value"
        
        await pool.destroy(unique_pool_name)
    
    async def test_async_batch_operations(self, unique_pool_name):
        """Test async batch operations."""
        from latzero import AsyncSharedMemoryPool
        
        pool = AsyncSharedMemoryPool(auto_cleanup=False)
        await pool.create(unique_pool_name)
        
        async with await pool.connect(unique_pool_name) as client:
            await client.mset({"a": 1, "b": 2, "c": 3})
            result = await client.mget(["a", "b", "c"])
            assert result == {"a": 1, "b": 2, "c": 3}
        
        await pool.destroy(unique_pool_name)
    
    async def test_async_atomic_operations(self, unique_pool_name):
        """Test async atomic operations."""
        from latzero import AsyncSharedMemoryPool
        
        pool = AsyncSharedMemoryPool(auto_cleanup=False)
        await pool.create(unique_pool_name)
        
        async with await pool.connect(unique_pool_name) as client:
            await client.set("counter", 0)
            result = await client.increment("counter", 5)
            assert result == 5
            
            result = await client.decrement("counter", 2)
            assert result == 3
        
        await pool.destroy(unique_pool_name)
    
    async def test_async_list_pools(self, unique_pool_name):
        """Test async list pools."""
        from latzero import AsyncSharedMemoryPool
        
        pool = AsyncSharedMemoryPool(auto_cleanup=False)
        await pool.create(unique_pool_name)
        
        pools = await pool.list_pools()
        assert unique_pool_name in pools
        
        await pool.destroy(unique_pool_name)
    
    async def test_concurrent_operations(self, unique_pool_name):
        """Test concurrent async operations."""
        from latzero import AsyncSharedMemoryPool
        
        pool = AsyncSharedMemoryPool(auto_cleanup=False)
        await pool.create(unique_pool_name)
        
        async with await pool.connect(unique_pool_name) as client:
            # Run multiple operations concurrently
            await asyncio.gather(
                client.set("key1", "value1"),
                client.set("key2", "value2"),
                client.set("key3", "value3"),
            )
            
            results = await asyncio.gather(
                client.get("key1"),
                client.get("key2"),
                client.get("key3"),
            )
            
            assert results == ["value1", "value2", "value3"]
        
        await pool.destroy(unique_pool_name)
