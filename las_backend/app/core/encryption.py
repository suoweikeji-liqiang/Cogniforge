from cryptography.fernet import Fernet
from app.core.config import get_settings
import base64
import hashlib

def _get_fernet_key() -> bytes:
    settings = get_settings()
    key = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
    return base64.urlsafe_b64encode(key)

def encrypt_password(password: str) -> str:
    if not password:
        return ""
    f = Fernet(_get_fernet_key())
    return f.encrypt(password.encode()).decode()

def decrypt_password(encrypted: str) -> str:
    if not encrypted:
        return ""
    f = Fernet(_get_fernet_key())
    return f.decrypt(encrypted.encode()).decode()
