"""app.security — Encryption and OS Keyring integration.

Provides functions to securely store API keys using AES-256-GCM,
leveraging the OS Keyring to store the encryption key with a local
machine-id fallback when headless or keyring is unavailable.
"""

import os
import secrets
import hashlib
import uuid
import keyring
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

SERVICE_NAME = "transcribe-assistant"
ACCOUNT_NAME = "cryptography_key"

# In-memory cached key to avoid querying keyring on every single decryption
_CACHED_KEY = None


def _get_system_fallback_key() -> bytes:
    """Derive a stable 256-bit key from local system identifiers.

    Used only as a fallback when the OS Keyring is unavailable.
    """
    identifiers = []
    # Linux machine-id
    try:
        if os.path.exists("/etc/machine-id"):
            with open("/etc/machine-id", "r") as f:
                identifiers.append(f.read().strip())
    except Exception:
        pass
    
    # Python system UUID identifier
    try:
        identifiers.append(str(uuid.getnode()))
    except Exception:
        pass
        
    raw_id = "-".join(identifiers).encode("utf-8")
    return hashlib.sha256(raw_id).digest()


def get_or_create_master_key() -> bytes:
    """Retrieve the master key from the OS Keyring, generating it if necessary.

    Returns:
        32 bytes key for AES-256-GCM.
    """
    global _CACHED_KEY
    if _CACHED_KEY is not None:
        return _CACHED_KEY

    try:
        key_hex = keyring.get_password(SERVICE_NAME, ACCOUNT_NAME)
        if not key_hex:
            # Generate a strong 256-bit encryption key
            key_bytes = secrets.token_bytes(32)
            key_hex = key_bytes.hex()
            try:
                keyring.set_password(SERVICE_NAME, ACCOUNT_NAME, key_hex)
            except Exception as e:
                # Keyring is unavailable (headless server, docker, etc.)
                print(
                    f"[SECURITY WARNING] OS Keyring is unavailable ({e}). "
                    f"Falling back to machine-derived key."
                )
                _CACHED_KEY = _get_system_fallback_key()
                return _CACHED_KEY
        
        _CACHED_KEY = bytes.fromhex(key_hex)
        return _CACHED_KEY
    except Exception as e:
        print(f"[SECURITY ERROR] Keyring exception: {e}. Using fallback key.")
        _CACHED_KEY = _get_system_fallback_key()
        return _CACHED_KEY


def encrypt_value(plain_text: str) -> str:
    """Encrypt a string using AES-256-GCM.

    Args:
        plain_text: Secret value to encrypt.

    Returns:
        Formatted string "nonce_hex:ciphertext_hex".
    """
    if not plain_text:
        return ""
        
    try:
        key = get_or_create_master_key()
        aesgcm = AESGCM(key)
        nonce = os.urandom(12)  # Standard 96-bit nonce for GCM
        encrypted_bytes = aesgcm.encrypt(nonce, plain_text.encode("utf-8"), None)
        return f"{nonce.hex()}:{encrypted_bytes.hex()}"
    except Exception as e:
        print(f"[SECURITY ERROR] Encryption failed: {e}")
        return ""


def decrypt_value(encrypted_text: str) -> str:
    """Decrypt an AES-256-GCM encrypted string.

    Also handles unencrypted fallback migration gracefully.

    Args:
        encrypted_text: Formatted string "nonce_hex:ciphertext_hex" or plain text.

    Returns:
        Decrypted plain text value.
    """
    if not encrypted_text:
        return ""

    # Safe fallback: if there is no ":" in the string, it could be plain text (e.g. legacy/development)
    if ":" not in encrypted_text:
        return encrypted_text

    try:
        parts = encrypted_text.split(":")
        if len(parts) != 2:
            return encrypted_text
            
        nonce = bytes.fromhex(parts[0])
        ciphertext = bytes.fromhex(parts[1])
        
        key = get_or_create_master_key()
        aesgcm = AESGCM(key)
        decrypted_bytes = aesgcm.decrypt(nonce, ciphertext, None)
        return decrypted_bytes.decode("utf-8")
    except Exception as e:
        # If decryption fails but looks like plain text (e.g., API key from before key changed),
        # return the raw input to prevent app crash if possible, but log the warning.
        print(f"[SECURITY WARNING] Decryption failed ({e}). Returning raw value.")
        return encrypted_text
