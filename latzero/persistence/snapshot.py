"""
latzero.persistence - Snapshot persistence for pools.

Save and restore pool data to/from disk.
"""

import os
import json
import time
import threading
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime


class PoolSnapshot:
    """
    Snapshot manager for persisting pool data to disk.
    
    Stores pool state as compressed JSON files.
    """
    
    __slots__ = ('_pool_name', '_snapshot_dir', '_auto_thread', '_auto_interval', '_running')
    
    def __init__(
        self, 
        pool_name: str, 
        snapshot_dir: Optional[str] = None
    ):
        """
        Initialize snapshot manager.
        
        Args:
            pool_name: Name of the pool to snapshot
            snapshot_dir: Directory for snapshots (default: ~/.latzero/snapshots)
        """
        self._pool_name = pool_name
        
        if snapshot_dir is None:
            home = Path.home()
            snapshot_dir = str(home / '.latzero' / 'snapshots')
        
        self._snapshot_dir = snapshot_dir
        Path(self._snapshot_dir).mkdir(parents=True, exist_ok=True)
        
        self._auto_thread: Optional[threading.Thread] = None
        self._auto_interval: int = 0
        self._running = False
    
    def _get_snapshot_path(self, name: Optional[str] = None) -> str:
        """Get path for a snapshot file."""
        if name:
            filename = f"{self._pool_name}_{name}.json"
        else:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{self._pool_name}_{timestamp}.json"
        
        return os.path.join(self._snapshot_dir, filename)
    
    def save(self, path: Optional[str] = None) -> str:
        """
        Save pool data to a snapshot file.
        
        Args:
            path: Optional custom path (default: auto-generated with timestamp)
        
        Returns:
            Path to saved snapshot
        """
        from ..core.pool import SharedMemoryPool
        
        pool = SharedMemoryPool(auto_cleanup=False)
        
        try:
            client = pool.connect(self._pool_name)
        except Exception as e:
            raise RuntimeError(f"Cannot connect to pool '{self._pool_name}': {e}")
        
        # Collect all data
        keys = client.keys()
        data = {}
        
        for key in keys:
            try:
                value = client.get(key)
                data[key] = value
            except Exception:
                # Skip keys that can't be serialized to JSON
                pass
        
        # Get metadata
        stats = client.stats()
        client.disconnect()
        
        snapshot = {
            'pool_name': self._pool_name,
            'created': datetime.utcnow().isoformat() + 'Z',
            'key_count': len(data),
            'data': data,
            'metadata': {
                'encryption': stats.get('encryption', False),
            }
        }
        
        # Save
        save_path = path or self._get_snapshot_path()
        
        with open(save_path, 'w', encoding='utf-8') as f:
            json.dump(snapshot, f, indent=2, default=str)
        
        return save_path
    
    def load(self, path: str, create_if_not_exists: bool = True) -> int:
        """
        Load pool data from a snapshot file.
        
        Args:
            path: Path to snapshot file
            create_if_not_exists: Create pool if it doesn't exist
        
        Returns:
            Number of keys loaded
        """
        from ..core.pool import SharedMemoryPool
        
        if not os.path.exists(path):
            raise FileNotFoundError(f"Snapshot not found: {path}")
        
        with open(path, 'r', encoding='utf-8') as f:
            snapshot = json.load(f)
        
        pool = SharedMemoryPool(auto_cleanup=False)
        
        # Create pool if needed
        if create_if_not_exists and not pool.exists(self._pool_name):
            encryption = snapshot.get('metadata', {}).get('encryption', False)
            pool.create(
                self._pool_name, 
                encryption=encryption
            )
        
        try:
            client = pool.connect(self._pool_name)
        except Exception as e:
            raise RuntimeError(f"Cannot connect to pool '{self._pool_name}': {e}")
        
        # Load data
        data = snapshot.get('data', {})
        count = 0
        
        for key, value in data.items():
            try:
                client.set(key, value)
                count += 1
            except Exception:
                pass
        
        client.disconnect()
        return count
    
    def list_snapshots(self) -> List[Dict[str, Any]]:
        """
        List available snapshots for this pool.
        
        Returns:
            List of snapshot info dicts
        """
        snapshots = []
        pattern = f"{self._pool_name}_"
        
        for filename in os.listdir(self._snapshot_dir):
            if filename.startswith(pattern) and filename.endswith('.json'):
                path = os.path.join(self._snapshot_dir, filename)
                stat = os.stat(path)
                
                try:
                    with open(path, 'r') as f:
                        header = json.load(f)
                        key_count = header.get('key_count', 0)
                except Exception:
                    key_count = 0
                
                snapshots.append({
                    'filename': filename,
                    'path': path,
                    'size_bytes': stat.st_size,
                    'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    'key_count': key_count
                })
        
        return sorted(snapshots, key=lambda x: x['modified'], reverse=True)
    
    def enable_auto_snapshot(self, interval: int = 300) -> None:
        """
        Enable automatic periodic snapshots.
        
        Args:
            interval: Seconds between snapshots (default: 5 minutes)
        """
        if self._running:
            return
        
        self._auto_interval = interval
        self._running = True
        self._auto_thread = threading.Thread(target=self._auto_loop, daemon=True)
        self._auto_thread.start()
    
    def disable_auto_snapshot(self) -> None:
        """Disable automatic snapshots."""
        self._running = False
        if self._auto_thread:
            self._auto_thread.join(timeout=5)
            self._auto_thread = None
    
    def _auto_loop(self) -> None:
        """Background auto-snapshot loop."""
        while self._running:
            try:
                self.save()
            except Exception:
                pass
            
            # Sleep in increments for responsive shutdown
            for _ in range(self._auto_interval):
                if not self._running:
                    break
                time.sleep(1)
    
    def cleanup_old_snapshots(self, keep: int = 10) -> int:
        """
        Remove old snapshots, keeping the most recent N.
        
        Args:
            keep: Number of snapshots to keep
        
        Returns:
            Number of snapshots deleted
        """
        snapshots = self.list_snapshots()
        
        if len(snapshots) <= keep:
            return 0
        
        to_delete = snapshots[keep:]
        count = 0
        
        for snap in to_delete:
            try:
                os.remove(snap['path'])
                count += 1
            except Exception:
                pass
        
        return count


def save_pool_snapshot(pool_name: str, path: Optional[str] = None) -> str:
    """
    Convenience function to save a pool snapshot.
    
    Args:
        pool_name: Pool to snapshot
        path: Optional custom path
    
    Returns:
        Path to saved snapshot
    """
    return PoolSnapshot(pool_name).save(path)


def load_pool_snapshot(pool_name: str, path: str) -> int:
    """
    Convenience function to load a pool snapshot.
    
    Args:
        pool_name: Pool to load into
        path: Snapshot file path
    
    Returns:
        Number of keys loaded
    """
    return PoolSnapshot(pool_name).load(path)
