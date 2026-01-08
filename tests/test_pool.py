"""
Tests for latzero.core.pool module.
"""

import pytest
import time


class TestSharedMemoryPool:
    """Tests for SharedMemoryPool class."""
    
    def test_create_pool(self, pool_manager, unique_pool_name):
        """Test basic pool creation."""
        pool_manager.create(unique_pool_name)
        assert pool_manager.exists(unique_pool_name)
        pool_manager.destroy(unique_pool_name)
    
    def test_create_encrypted_pool(self, pool_manager, unique_pool_name):
        """Test encrypted pool creation."""
        pool_manager.create(
            unique_pool_name, 
            auth=True, 
            auth_key="secret", 
            encryption=True
        )
        assert pool_manager.exists(unique_pool_name)
        pool_manager.destroy(unique_pool_name)
    
    def test_connect_to_pool(self, pool_manager, unique_pool_name):
        """Test connecting to a pool."""
        pool_manager.create(unique_pool_name)
        client = pool_manager.connect(unique_pool_name)
        assert client is not None
        assert client.pool_name == unique_pool_name
        client.disconnect()
        pool_manager.destroy(unique_pool_name)
    
    def test_connect_with_wrong_auth(self, pool_manager, unique_pool_name):
        """Test that wrong auth key raises error."""
        from latzero import AuthenticationError
        
        pool_manager.create(unique_pool_name, auth=True, auth_key="correct")
        
        with pytest.raises(AuthenticationError):
            pool_manager.connect(unique_pool_name, auth_key="wrong")
        
        pool_manager.destroy(unique_pool_name)
    
    def test_connect_nonexistent_pool(self, pool_manager):
        """Test connecting to non-existent pool raises error."""
        from latzero import PoolNotFound
        
        with pytest.raises(PoolNotFound):
            pool_manager.connect("nonexistent_pool_xyz_123")
    
    def test_list_pools(self, pool_manager, unique_pool_name):
        """Test listing pools."""
        pool_manager.create(unique_pool_name)
        pools = pool_manager.list_pools()
        assert unique_pool_name in pools
        pool_manager.destroy(unique_pool_name)
    
    def test_destroy_pool(self, pool_manager, unique_pool_name):
        """Test destroying a pool."""
        pool_manager.create(unique_pool_name)
        assert pool_manager.exists(unique_pool_name)
        pool_manager.destroy(unique_pool_name)
        assert not pool_manager.exists(unique_pool_name)
    
    def test_stats(self, pool_manager, unique_pool_name):
        """Test getting global stats."""
        pool_manager.create(unique_pool_name)
        stats = pool_manager.stats()
        assert 'pool_count' in stats
        assert stats['pool_count'] >= 1
        pool_manager.destroy(unique_pool_name)


class TestPoolClient:
    """Tests for PoolClient class."""
    
    def test_set_and_get_string(self, pool_with_data):
        """Test set/get with string value."""
        client = pool_with_data["client"]
        assert client.get("string_key") == "test_value"
    
    def test_set_and_get_int(self, pool_with_data):
        """Test set/get with integer value."""
        client = pool_with_data["client"]
        assert client.get("int_key") == 42
    
    def test_set_and_get_float(self, pool_with_data):
        """Test set/get with float value."""
        client = pool_with_data["client"]
        assert abs(client.get("float_key") - 3.14) < 0.001
    
    def test_set_and_get_list(self, pool_with_data):
        """Test set/get with list value."""
        client = pool_with_data["client"]
        assert client.get("list_key") == [1, 2, 3]
    
    def test_set_and_get_dict(self, pool_with_data):
        """Test set/get with dict value."""
        client = pool_with_data["client"]
        assert client.get("dict_key") == {"a": 1, "b": 2}
    
    def test_get_nonexistent_key(self, pool_with_data):
        """Test get with nonexistent key returns None."""
        client = pool_with_data["client"]
        assert client.get("nonexistent_key") is None
    
    def test_get_with_default(self, pool_with_data):
        """Test get with default value."""
        client = pool_with_data["client"]
        assert client.get("nonexistent_key", "default") == "default"
    
    def test_delete_key(self, pool_with_data):
        """Test deleting a key."""
        client = pool_with_data["client"]
        client.set("to_delete", "value")
        assert client.delete("to_delete")
        assert client.get("to_delete") is None
    
    def test_exists(self, pool_with_data):
        """Test exists method."""
        client = pool_with_data["client"]
        assert client.exists("string_key")
        assert not client.exists("nonexistent_key")
    
    def test_keys(self, pool_with_data):
        """Test getting all keys."""
        client = pool_with_data["client"]
        keys = client.keys()
        assert "string_key" in keys
        assert "int_key" in keys
        assert len(keys) >= 5
    
    def test_keys_with_pattern(self, pool_with_data):
        """Test keys with pattern filter."""
        client = pool_with_data["client"]
        client.set("prefix_one", 1)
        client.set("prefix_two", 2)
        
        keys = client.keys("prefix_")
        assert "prefix_one" in keys
        assert "prefix_two" in keys
        assert "string_key" not in keys
    
    def test_size(self, pool_with_data):
        """Test size method."""
        client = pool_with_data["client"]
        assert client.size() >= 5
    
    def test_stats(self, pool_with_data):
        """Test pool stats."""
        client = pool_with_data["client"]
        stats = client.stats()
        assert stats['name'] == pool_with_data["pool_name"]
        assert stats['key_count'] >= 5
    
    def test_context_manager(self, pool_manager, unique_pool_name):
        """Test context manager protocol."""
        pool_manager.create(unique_pool_name)
        
        with pool_manager.connect(unique_pool_name) as client:
            client.set("ctx_key", "ctx_value")
            assert client.get("ctx_key") == "ctx_value"
        
        # Client should be disconnected now
        pool_manager.destroy(unique_pool_name)


class TestAtomicOperations:
    """Tests for atomic operations."""
    
    def test_increment(self, pool_with_data):
        """Test increment operation."""
        client = pool_with_data["client"]
        client.set("counter", 10)
        
        result = client.increment("counter")
        assert result == 11
        assert client.get("counter") == 11
    
    def test_increment_with_delta(self, pool_with_data):
        """Test increment with custom delta."""
        client = pool_with_data["client"]
        client.set("counter", 10)
        
        result = client.increment("counter", 5)
        assert result == 15
    
    def test_decrement(self, pool_with_data):
        """Test decrement operation."""
        client = pool_with_data["client"]
        client.set("counter", 10)
        
        result = client.decrement("counter")
        assert result == 9
    
    def test_increment_nonexistent_key(self, pool_with_data):
        """Test increment on nonexistent key starts from 0."""
        client = pool_with_data["client"]
        result = client.increment("new_counter")
        assert result == 1
    
    def test_append(self, pool_with_data):
        """Test append to list."""
        client = pool_with_data["client"]
        client.set("my_list", [1, 2])
        
        length = client.append("my_list", 3)
        assert length == 3
        assert client.get("my_list") == [1, 2, 3]
    
    def test_update_dict(self, pool_with_data):
        """Test update dict operation."""
        client = pool_with_data["client"]
        client.set("my_dict", {"a": 1})
        
        client.update("my_dict", {"b": 2, "c": 3})
        result = client.get("my_dict")
        assert result == {"a": 1, "b": 2, "c": 3}


class TestBatchOperations:
    """Tests for batch operations."""
    
    def test_mset(self, pool_with_data):
        """Test batch set."""
        client = pool_with_data["client"]
        
        client.mset({
            "batch_1": "value1",
            "batch_2": "value2",
            "batch_3": "value3",
        })
        
        assert client.get("batch_1") == "value1"
        assert client.get("batch_2") == "value2"
        assert client.get("batch_3") == "value3"
    
    def test_mget(self, pool_with_data):
        """Test batch get."""
        client = pool_with_data["client"]
        
        result = client.mget(["string_key", "int_key", "nonexistent"])
        assert result["string_key"] == "test_value"
        assert result["int_key"] == 42
        assert result["nonexistent"] is None
    
    def test_delete_many(self, pool_with_data):
        """Test batch delete."""
        client = pool_with_data["client"]
        client.mset({"del_1": 1, "del_2": 2, "del_3": 3})
        
        count = client.delete_many(["del_1", "del_2", "nonexistent"])
        assert count == 2
        assert not client.exists("del_1")
        assert client.exists("del_3")


class TestNamespace:
    """Tests for namespace support."""
    
    def test_namespace_set_get(self, pool_with_data):
        """Test namespaced set/get."""
        client = pool_with_data["client"]
        users = client.namespace("users")
        
        users.set("123", {"name": "John"})
        assert users.get("123") == {"name": "John"}
    
    def test_namespace_keys(self, pool_with_data):
        """Test namespaced keys."""
        client = pool_with_data["client"]
        users = client.namespace("users")
        
        users.set("1", "a")
        users.set("2", "b")
        users.set("3", "c")
        
        keys = users.keys()
        assert "1" in keys
        assert "2" in keys
        assert "3" in keys
    
    def test_namespace_isolation(self, pool_with_data):
        """Test that namespaces are isolated."""
        client = pool_with_data["client"]
        users = client.namespace("users")
        posts = client.namespace("posts")
        
        users.set("id", "user_value")
        posts.set("id", "post_value")
        
        assert users.get("id") == "user_value"
        assert posts.get("id") == "post_value"


class TestReadOnlyClient:
    """Tests for read-only client mode."""
    
    def test_readonly_get(self, pool_manager, unique_pool_name):
        """Test read-only client can read."""
        pool_manager.create(unique_pool_name)
        
        # Setup with writable client
        writer = pool_manager.connect(unique_pool_name)
        writer.set("key", "value")
        writer.disconnect()
        
        # Read with readonly client
        reader = pool_manager.connect(unique_pool_name, readonly=True)
        assert reader.get("key") == "value"
        reader.disconnect()
        
        pool_manager.destroy(unique_pool_name)
    
    def test_readonly_cannot_write(self, pool_manager, unique_pool_name):
        """Test read-only client cannot write."""
        from latzero import ReadOnlyError
        
        pool_manager.create(unique_pool_name)
        reader = pool_manager.connect(unique_pool_name, readonly=True)
        
        with pytest.raises(ReadOnlyError):
            reader.set("key", "value")
        
        reader.disconnect()
        pool_manager.destroy(unique_pool_name)


class TestAutoClean:
    """Tests for auto-clean functionality."""
    
    def test_auto_clean_expires_key(self, pool_manager, unique_pool_name):
        """Test that auto_clean expires keys."""
        pool_manager.create(unique_pool_name)
        client = pool_manager.connect(unique_pool_name)
        
        client.set("expire_key", "value", auto_clean=1)
        assert client.get("expire_key") == "value"
        
        time.sleep(1.5)
        assert client.get("expire_key") is None
        
        client.disconnect()
        pool_manager.destroy(unique_pool_name)


class TestEncryptedPool:
    """Tests for encrypted pool operations."""
    
    def test_encrypted_set_get(self, encrypted_pool):
        """Test set/get with encryption."""
        client = encrypted_pool["client"]
        
        client.set("secret_data", {"password": "hunter2"})
        result = client.get("secret_data")
        assert result == {"password": "hunter2"}
    
    def test_encrypted_complex_data(self, encrypted_pool):
        """Test complex data with encryption."""
        client = encrypted_pool["client"]
        
        data = {
            "users": [
                {"id": 1, "name": "Alice"},
                {"id": 2, "name": "Bob"},
            ],
            "config": {
                "nested": {"deep": True}
            }
        }
        
        client.set("complex", data)
        assert client.get("complex") == data
