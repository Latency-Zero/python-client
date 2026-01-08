"""
latzero.cli - Command-line interface for latzero.

Provides commands for inspecting and managing latzero pools.
"""

import argparse
import sys
import json
from typing import Optional


def get_pool_manager():
    """Lazy import to avoid startup overhead when CLI not used."""
    from ..core.pool import SharedMemoryPool
    return SharedMemoryPool(auto_cleanup=False)


def cmd_list(args) -> int:
    """List all active pools."""
    pool = get_pool_manager()
    pools = pool.list_pools()
    
    if not pools:
        print("No active pools")
        return 0
    
    if args.json:
        print(json.dumps(pools, indent=2, default=str))
    else:
        print(f"{'Pool Name':<30} {'Clients':<10} {'Encrypted':<10} {'Created'}")
        print("-" * 70)
        for name, info in pools.items():
            from datetime import datetime
            created = datetime.fromtimestamp(info['created']).strftime('%Y-%m-%d %H:%M')
            encrypted = 'Yes' if info.get('encryption') else 'No'
            print(f"{name:<30} {info['clients']:<10} {encrypted:<10} {created}")
    
    return 0


def cmd_inspect(args) -> int:
    """Inspect a specific pool."""
    pool = get_pool_manager()
    
    try:
        client = pool.connect(args.pool, auth_key=args.auth_key or '', readonly=True)
        
        stats = client.stats()
        keys = client.keys()
        
        if args.json:
            output = {
                'stats': stats,
                'keys': keys[:args.max_keys] if args.max_keys else keys,
                'total_keys': len(keys)
            }
            print(json.dumps(output, indent=2, default=str))
        else:
            print(f"Pool: {args.pool}")
            print(f"Clients: {stats.get('clients', 0)}")
            print(f"Keys: {stats.get('key_count', 0)}")
            print(f"Encrypted: {stats.get('encryption', False)}")
            print(f"Memory: {stats.get('used_bytes', 0):,} / {stats.get('capacity_bytes', 0):,} bytes")
            
            if keys:
                print(f"\nKeys (first {args.max_keys or len(keys)}):")
                for key in keys[:args.max_keys or len(keys)]:
                    print(f"  - {key}")
        
        client.disconnect()
        return 0
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_get(args) -> int:
    """Get a value from a pool."""
    pool = get_pool_manager()
    
    try:
        client = pool.connect(args.pool, auth_key=args.auth_key or '', readonly=True)
        value = client.get(args.key)
        
        if value is None:
            print(f"Key '{args.key}' not found", file=sys.stderr)
            client.disconnect()
            return 1
        
        if args.json:
            print(json.dumps({'key': args.key, 'value': value}, indent=2, default=str))
        else:
            print(value)
        
        client.disconnect()
        return 0
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_set(args) -> int:
    """Set a value in a pool."""
    pool = get_pool_manager()
    
    try:
        client = pool.connect(args.pool, auth_key=args.auth_key or '')
        
        # Try to parse value as JSON, otherwise use as string
        try:
            value = json.loads(args.value)
        except json.JSONDecodeError:
            value = args.value
        
        client.set(args.key, value, auto_clean=args.ttl)
        print(f"Set {args.key} = {value}")
        
        client.disconnect()
        return 0
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_delete(args) -> int:
    """Delete a key from a pool."""
    pool = get_pool_manager()
    
    try:
        client = pool.connect(args.pool, auth_key=args.auth_key or '')
        
        if client.delete(args.key):
            print(f"Deleted {args.key}")
        else:
            print(f"Key '{args.key}' not found", file=sys.stderr)
            client.disconnect()
            return 1
        
        client.disconnect()
        return 0
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_clear(args) -> int:
    """Clear all keys in a pool."""
    pool = get_pool_manager()
    
    try:
        client = pool.connect(args.pool, auth_key=args.auth_key or '')
        keys = client.keys()
        
        if not args.yes:
            confirm = input(f"Delete {len(keys)} keys from '{args.pool}'? [y/N]: ")
            if confirm.lower() != 'y':
                print("Aborted")
                client.disconnect()
                return 0
        
        count = client.delete_many(keys)
        print(f"Deleted {count} keys")
        
        client.disconnect()
        return 0
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_destroy(args) -> int:
    """Force destroy a pool."""
    pool = get_pool_manager()
    
    if not args.yes:
        confirm = input(f"Destroy pool '{args.pool}'? This cannot be undone. [y/N]: ")
        if confirm.lower() != 'y':
            print("Aborted")
            return 0
    
    if pool.destroy(args.pool):
        print(f"Destroyed pool '{args.pool}'")
        return 0
    else:
        print(f"Pool '{args.pool}' not found", file=sys.stderr)
        return 1


def cmd_cleanup(args) -> int:
    """Cleanup orphaned shared memory segments."""
    from ..core.cleanup import cleanup_orphaned_memory
    
    cleaned = cleanup_orphaned_memory()
    
    if cleaned:
        print(f"Cleaned up {len(cleaned)} orphaned segments:")
        for name in cleaned:
            print(f"  - {name}")
    else:
        print("No orphaned segments found")
    
    return 0


def cmd_stats(args) -> int:
    """Show global latzero statistics."""
    pool = get_pool_manager()
    stats = pool.stats()
    
    if args.json:
        print(json.dumps(stats, indent=2, default=str))
    else:
        print(f"Total pools: {stats.get('pool_count', 0)}")
        print(f"Total clients: {stats.get('total_clients', 0)}")
        if stats.get('oldest_pool'):
            print(f"Oldest pool: {stats['oldest_pool']}")
        if stats.get('newest_pool'):
            print(f"Newest pool: {stats['newest_pool']}")
        if stats.get('pools'):
            print(f"Pools: {', '.join(stats['pools'])}")
    
    return 0


def main(argv: Optional[list] = None) -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog='latzero',
        description='Zero-latency shared memory pool management'
    )
    parser.add_argument(
        '--version', 
        action='version', 
        version='latzero 0.2.0'
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # list
    list_parser = subparsers.add_parser('list', help='List all active pools')
    list_parser.add_argument('--json', action='store_true', help='Output as JSON')
    list_parser.set_defaults(func=cmd_list)
    
    # inspect
    inspect_parser = subparsers.add_parser('inspect', help='Inspect a pool')
    inspect_parser.add_argument('pool', help='Pool name')
    inspect_parser.add_argument('--auth-key', help='Authentication key')
    inspect_parser.add_argument('--max-keys', type=int, default=50, help='Max keys to show')
    inspect_parser.add_argument('--json', action='store_true', help='Output as JSON')
    inspect_parser.set_defaults(func=cmd_inspect)
    
    # get
    get_parser = subparsers.add_parser('get', help='Get a value')
    get_parser.add_argument('pool', help='Pool name')
    get_parser.add_argument('key', help='Key name')
    get_parser.add_argument('--auth-key', help='Authentication key')
    get_parser.add_argument('--json', action='store_true', help='Output as JSON')
    get_parser.set_defaults(func=cmd_get)
    
    # set
    set_parser = subparsers.add_parser('set', help='Set a value')
    set_parser.add_argument('pool', help='Pool name')
    set_parser.add_argument('key', help='Key name')
    set_parser.add_argument('value', help='Value (JSON string)')
    set_parser.add_argument('--auth-key', help='Authentication key')
    set_parser.add_argument('--ttl', type=int, help='Time-to-live in seconds')
    set_parser.set_defaults(func=cmd_set)
    
    # delete
    delete_parser = subparsers.add_parser('delete', help='Delete a key')
    delete_parser.add_argument('pool', help='Pool name')
    delete_parser.add_argument('key', help='Key name')
    delete_parser.add_argument('--auth-key', help='Authentication key')
    delete_parser.set_defaults(func=cmd_delete)
    
    # clear
    clear_parser = subparsers.add_parser('clear', help='Clear all keys in a pool')
    clear_parser.add_argument('pool', help='Pool name')
    clear_parser.add_argument('--auth-key', help='Authentication key')
    clear_parser.add_argument('-y', '--yes', action='store_true', help='Skip confirmation')
    clear_parser.set_defaults(func=cmd_clear)
    
    # destroy
    destroy_parser = subparsers.add_parser('destroy', help='Destroy a pool')
    destroy_parser.add_argument('pool', help='Pool name')
    destroy_parser.add_argument('-y', '--yes', action='store_true', help='Skip confirmation')
    destroy_parser.set_defaults(func=cmd_destroy)
    
    # cleanup
    cleanup_parser = subparsers.add_parser('cleanup', help='Cleanup orphaned memory')
    cleanup_parser.set_defaults(func=cmd_cleanup)
    
    # stats
    stats_parser = subparsers.add_parser('stats', help='Show global statistics')
    stats_parser.add_argument('--json', action='store_true', help='Output as JSON')
    stats_parser.set_defaults(func=cmd_stats)
    
    args = parser.parse_args(argv)
    
    if not args.command:
        parser.print_help()
        return 0
    
    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())
