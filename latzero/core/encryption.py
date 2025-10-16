import os
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend

def derive_key(auth_key):
    """Derive a 256-bit key from the auth_key string."""
    digest = hashes.Hash(hashes.SHA256(), backend=default_backend())
    digest.update(auth_key.encode())
    return digest.finalize()

def encrypt_data(data, auth_key):
    """Encrypt data using AES-GCM."""
    try:
        key = derive_key(auth_key)
        iv = os.urandom(12)
        cipher = Cipher(algorithms.AES(key), modes.GCM(iv), backend=default_backend())
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(data) + encryptor.finalize()
        return iv + encryptor.tag + ciphertext
    except Exception as e:
        from ..utils.exceptions import EncryptionError
        raise EncryptionError(f"Encryption failed: {e}")

def decrypt_data(encrypted_data, auth_key):
    """Decrypt data using AES-GCM."""
    try:
        key = derive_key(auth_key)
        if len(encrypted_data) < 28:
            raise ValueError("Encrypted data too short")
        iv, tag, ciphertext = encrypted_data[:12], encrypted_data[12:28], encrypted_data[28:]
        cipher = Cipher(algorithms.AES(key), modes.GCM(iv, tag), backend=default_backend())
        decryptor = cipher.decryptor()
        return decryptor.update(ciphertext) + decryptor.finalize()
    except Exception as e:
        from ..utils.exceptions import EncryptionError
        raise EncryptionError(f"Decryption failed: {e}")
