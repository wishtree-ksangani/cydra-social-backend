from cryptography.fernet import Fernet, InvalidToken
from app.core.config import settings


def encrypt_token(token: str) -> str:
    """
    Encrypt a token using Fernet symmetric encryption.
    
    Args:
        token: Plain text token to encrypt
        
    Returns:
        Base64 encoded encrypted token
    """
    if not token:
        return ""
    
    if not settings.ENCRYPTION_KEY:
        raise ValueError("ENCRYPTION_KEY not configured")
    
    fernet = Fernet(settings.ENCRYPTION_KEY.encode())
    encrypted = fernet.encrypt(token.encode())
    return encrypted.decode()


def decrypt_token(encrypted_token: str) -> str:
    """
    Decrypt an encrypted token.
    
    Args:
        encrypted_token: Base64 encoded encrypted token
        
    Returns:
        Decrypted plain text token
        
    Raises:
        ValueError: If decryption fails
    """
    if not encrypted_token:
        return ""
    
    if not settings.ENCRYPTION_KEY:
        raise ValueError("ENCRYPTION_KEY not configured")
    
    try:
        fernet = Fernet(settings.ENCRYPTION_KEY.encode())
        decrypted = fernet.decrypt(encrypted_token.encode())
        return decrypted.decode()
    except InvalidToken:
        raise ValueError("Invalid or corrupted encrypted token")
