import multiprocessing as mp
from latzero import SharedMemoryPool

# Shared pool_manager instance for processes
pool_manager = SharedMemoryPool()

def client_worker(pool_name, auth_key, client_id, use_encryption):
    try:
        # Connect to the pool
        auth_key_param = auth_key if use_encryption else None
        ipc = pool_manager.connect(name=pool_name, auth_key=auth_key_param)

        # Set a unique value
        key = f"key_{client_id}"
        value = f"value_{client_id}"
        ipc.set(key, value, auto_clean=10)  # Auto-clean after 10 seconds
        print(f"Client {client_id} set {key} = {value}")

        # Attempt to get another client's value
        other_client_id = (client_id + 1) % 3
        other_key = f"key_{other_client_id}"
        other_value = ipc.get(other_key)
        print(f"Client {client_id} read {other_key} = {other_value}")

    except Exception as e:
        print(f"Client {client_id} error: {e}")

def main():
    pool_name = "multiPool"
    use_encryption = False  # Change to True for encrypted version
    auth_key = "secret" if use_encryption else None

    # Create the pool
    pool_manager.create(name=pool_name, auth=use_encryption, auth_key=auth_key, encryption=use_encryption)

    # Launch multiple client processes
    processes = []
    for client_id in range(3):
        p = mp.Process(target=client_worker, args=(pool_name, auth_key, client_id, use_encryption))
        processes.append(p)
        p.start()

    # Wait for all processes to finish
    for p in processes:
        p.join()

    print("Multi-client demo complete.")

if __name__ == "__main__":
    mp.set_start_method('spawn')  # Required for safe shared memory on Windows
    main()
