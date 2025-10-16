from latzero import SharedMemoryPool

# Example: Encrypted pool with authentication

def main():
    # Create an encrypted and authenticated pool
    pool_manager = SharedMemoryPool()
    pool_manager.create(name="securePool", auth=True, auth_key="super_secret", encryption=True)

    # Connect to the secure pool
    ipc = pool_manager.connect(name="securePool", auth_key="super_secret")

    # Set and get data (encrypted in shared memory)
    ipc.set("secret_number", 1337)
    ipc.set("secret_text", "Top secret!")
    ipc.set("secret_data", ["array", 42, True])

    # Retrieve and print
    print("Secret Number:", ipc.get("secret_number"))  # 1337 (int)
    print("Secret Text:", ipc.get("secret_text"))      # "Top secret!" (str)
    print("Secret Data:", ipc.get("secret_data"))      # ["array", 42, True] (list)

if __name__ == "__main__":
    main()
