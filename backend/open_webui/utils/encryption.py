import os
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import logging

log = logging.getLogger(__name__)

# Get encryption key from environment or generate one
ENCRYPTION_KEY = os.getenv('AGENT_ENCRYPTION_KEY')

def get_encryption_key():
    """Get or generate encryption key"""
    global ENCRYPTION_KEY
    
    if not ENCRYPTION_KEY:
        # Generate a key from the WEBUI_SECRET_KEY
        secret_key = os.getenv('WEBUI_SECRET_KEY', 'default-secret-key-change-this')
        
        # Use PBKDF2 to derive a key
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b'agent_encryption_salt',  # Fixed salt for consistency
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(secret_key.encode()))
        ENCRYPTION_KEY = key
    
    return ENCRYPTION_KEY


def encrypt_api_key(api_key: str) -> str:
    """
    Encrypt an API key for secure storage
    
    Args:
        api_key: The API key to encrypt
        
    Returns:
        Encrypted API key as base64 string
    """
    try:
        key = get_encryption_key()
        f = Fernet(key)
        encrypted = f.encrypt(api_key.encode())
        return base64.urlsafe_b64encode(encrypted).decode()
    except Exception as e:
        log.error(f"Error encrypting API key: {e}")
        raise


def decrypt_api_key(encrypted_api_key: str) -> str:
    """
    Decrypt an API key for use
    
    Args:
        encrypted_api_key: The encrypted API key as base64 string
        
    Returns:
        Decrypted API key
    """
    try:
        key = get_encryption_key()
        f = Fernet(key)
        encrypted_bytes = base64.urlsafe_b64decode(encrypted_api_key.encode())
        decrypted = f.decrypt(encrypted_bytes)
        return decrypted.decode()
    except Exception as e:
        log.error(f"Error decrypting API key: {e}")
        raise


def mask_api_key(api_key: str) -> str:
    """
    Mask an API key for display purposes
    
    Args:
        api_key: The API key to mask
        
    Returns:
        Masked API key showing only first 8 and last 4 characters
    """
    if not api_key:
        return ""
    
    if len(api_key) <= 12:
        # If key is too short, mask most of it
        return api_key[:2] + "*" * (len(api_key) - 4) + api_key[-2:]
    
    # Show first 8 and last 4 characters
    return api_key[:8] + "*" * (len(api_key) - 12) + api_key[-4:]


def validate_api_key_format(api_key: str) -> bool:
    """
    Validate API key format (should be id.secret)
    
    Args:
        api_key: The API key to validate
        
    Returns:
        True if format is valid, False otherwise
    """
    try:
        parts = api_key.split(".", 1)
        return len(parts) == 2 and len(parts[0]) > 0 and len(parts[1]) > 0
    except:
        return False