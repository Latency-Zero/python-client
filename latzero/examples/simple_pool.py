import multiprocessing as mp
from latzero import SharedMemoryPool
import time

# Example: Simple pool creation and basic operations

def producer(pool_name):
    """Process 1: Creates pool and sets data"""
    print("Producer: Creating pool...")
    pool_manager = SharedMemoryPool()
    pool_manager.create(name=pool_name)

    ipc = pool_manager.connect(name=pool_name)

    # Set data
    ipc.set("number", 42)
    ipc.set("text", "Hello from producer!")
    ipc.set("data", {"key": "value", "process": "producer"})
    print("Producer: Set data, waiting...")

    # Keep process alive
    time.sleep(5)
    print("Producer: Done")

def consumer(pool_name):
    """Process 2: Connects to existing pool and reads data"""
    time.sleep(1)  # Give producer time to create pool
    print("Consumer: Connecting to pool...")

    try:
        pool_manager = SharedMemoryPool()
        ipc = pool_manager.connect(name=pool_name)

        # Try to read data
        number = ipc.get("number")
        text = ipc.get("text")
        data = ipc.get("data")

        print(f"Consumer: Read number = {number}")
        print(f"Consumer: Read text = {text}")
        print(f"Consumer: Read data = {data}")

        if number == 42 and text == "Hello from producer!" and data["process"] == "producer":
            print("Consumer: SUCCESS - Cross-process communication works!")
        else:
            print("Consumer: ERROR - Data mismatch")
    except Exception as e:
        print(f"Consumer: ERROR - {e}")

def main():
    pool_name = "test_cross_process_pool"

    # Test within single process first
    print("=== Single Process Test ===")
    pool_manager = SharedMemoryPool()
    pool_manager.create(name=pool_name + "_single")
    ipc = pool_manager.connect(name=pool_name + "_single")
    ipc.set("single_test", "works")
    result = ipc.get("single_test")
    print(f"Single process test: {result}")

    # Test cross-process
    print("\n=== Cross-Process Test ===")
    p1 = mp.Process(target=producer, args=(pool_name,))
    p2 = mp.Process(target=consumer, args=(pool_name,))

    p1.start()
    p2.start()

    p1.join()
    p2.join()

    print("=== Test Complete ===")

if __name__ == "__main__":
    mp.set_start_method('spawn')  # Required for safe shared memory on Windows
    main()
