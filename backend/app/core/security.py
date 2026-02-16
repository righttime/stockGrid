import os
import base64
import platform
import subprocess
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.fernet import Fernet
from app.core.config import settings

def get_machine_uuid() -> str:
    """하드웨어 고유 식별자를 가져옵니다. (Windows 기준)"""
    try:
        if platform.system() == "Windows":
            cmd = 'wmic csproduct get uuid'
            output = subprocess.check_output(cmd, shell=True).decode()
            lines = [line.strip() for line in output.split('\n') if line.strip()]
            if len(lines) > 1:
                return lines[1]
            return lines[0]
        else:
            return platform.node()
    except Exception:
        return "fallback-uuid-for-dev"

def derive_key() -> bytes:
    """Machine ID와 환경 변수의 Salt를 조합하여 AES 키를 유도합니다."""
    # settings.SECURITY_SALT 사용
    salt = settings.SECURITY_SALT.encode()
    machine_id = get_machine_uuid().encode()
    
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(machine_id))
    return key

class SecretManager:
    def __init__(self):
        self._key = derive_key()
        self.fernet = Fernet(self._key)

    def encrypt(self, data: str) -> str:
        if not data: return ""
        return self.fernet.encrypt(data.encode()).decode()

    def decrypt(self, encrypted_data: str) -> str:
        if not encrypted_data: return ""
        try:
            return self.fernet.decrypt(encrypted_data.encode()).decode()
        except Exception:
            return "DECRYPTION_FAILED"

# Singleton Instance
secret_manager = SecretManager()
