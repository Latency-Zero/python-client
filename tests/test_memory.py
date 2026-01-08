"""
Tests for latzero.core.memory module.
"""

import pytest


class TestSharedMemoryPoolData:
    """Tests for SharedMemoryPoolData class."""
    
    def test_create_pool_data(self, unique_pool_name):
        """Test creating pool data storage."""
        from latzero.core.memory import SharedMemoryPoolData
        
        shm_name = f"l0p_{unique_pool_name}"
        pool_data = SharedMemoryPoolData(shm_name)
        
        assert pool_data.shm_name == shm_name
        pool_data.close()
    
    def test_set_and_get(self, unique_pool_name):
        """Test basic set/get on pool data."""
        from latzero.core.memory import SharedMemoryPoolData
        
        shm_name = f"l0p_{unique_pool_name}"
        pool_data = SharedMemoryPoolData(shm_name)
        
        pool_data.set("test_key", "test_value")
        assert pool_data.get("test_key") == "test_value"
        
        pool_data.close()
    
    def test_delete(self, unique_pool_name):
        """Test delete on pool data."""
        from latzero.core.memory import SharedMemoryPoolData
        
        shm_name = f"l0p_{unique_pool_name}"
        pool_data = SharedMemoryPoolData(shm_name)
        
        pool_data.set("key", "value")
        assert pool_data.delete("key")
        assert pool_data.get("key") is None
        
        pool_data.close()
    
    def test_keys_with_prefix(self, unique_pool_name):
        """Test getting keys with prefix."""
        from latzero.core.memory import SharedMemoryPoolData
        
        shm_name = f"l0p_{unique_pool_name}"
        pool_data = SharedMemoryPoolData(shm_name)
        
        pool_data.set("prefix:one", 1)
        pool_data.set("prefix:two", 2)
        pool_data.set("other:key", 3)
        
        keys = pool_data.keys_with_prefix("prefix:")
        assert len(keys) == 2
        assert "prefix:one" in keys
        assert "prefix:two" in keys
        
        pool_data.close()
    
    def test_memory_usage(self, unique_pool_name):
        """Test memory usage stats."""
        from latzero.core.memory import SharedMemoryPoolData
        
        shm_name = f"l0p_{unique_pool_name}"
        pool_data = SharedMemoryPoolData(shm_name)
        
        pool_data.set("key", "x" * 1000)
        
        usage = pool_data.memory_usage()
        assert usage['used_bytes'] > 0
        assert usage['capacity_bytes'] >= usage['used_bytes']
        assert 0 < usage['utilization'] <= 1
        
        pool_data.close()
    
    def test_size(self, unique_pool_name):
        """Test size method."""
        from latzero.core.memory import SharedMemoryPoolData
        
        shm_name = f"l0p_{unique_pool_name}"
        pool_data = SharedMemoryPoolData(shm_name)
        
        pool_data.set("k1", "v1")
        pool_data.set("k2", "v2")
        pool_data.set("k3", "v3")
        
        assert pool_data.size() == 3
        
        pool_data.close()


class TestSerializer:
    """Tests for serialization."""
    
    def test_serialize_basic_types(self):
        """Test serializing basic types."""
        from latzero.core.memory import Serializer
        
        ser = Serializer()
        
        # String
        data = ser.serialize("hello")
        assert ser.deserialize(data) == "hello"
        
        # Int
        data = ser.serialize(42)
        assert ser.deserialize(data) == 42
        
        # Float
        data = ser.serialize(3.14)
        assert abs(ser.deserialize(data) - 3.14) < 0.001
        
        # Bool
        data = ser.serialize(True)
        assert ser.deserialize(data) == True
    
    def test_serialize_collections(self):
        """Test serializing collections."""
        from latzero.core.memory import Serializer
        
        ser = Serializer()
        
        # List
        data = ser.serialize([1, 2, 3])
        assert ser.deserialize(data) == [1, 2, 3]
        
        # Dict
        data = ser.serialize({"a": 1, "b": 2})
        assert ser.deserialize(data) == {"a": 1, "b": 2}
    
    def test_compression(self):
        """Test that large data is compressed."""
        from latzero.core.memory import Serializer
        
        ser = Serializer(compress_threshold=100)
        
        small_data = "x" * 50
        large_data = "x" * 1000
        
        small_serialized = ser.serialize(small_data)
        large_serialized = ser.serialize(large_data)
        
        # Large data should be compressed (smaller than raw)
        # Header byte + compressed data should be smaller than uncompressed
        assert len(large_serialized) < len(large_data)
        
        # Verify round-trip
        assert ser.deserialize(small_serialized) == small_data
        assert ser.deserialize(large_serialized) == large_data
