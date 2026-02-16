import pytest
from app.core.security import secret_manager

def test_encryption_decryption():
    original_text = "my-secret-kiwoom-key-123"
    encrypted = secret_manager.encrypt(original_text)
    
    assert encrypted != original_text
    
    decrypted = secret_manager.decrypt(encrypted)
    assert decrypted == original_text

def test_decryption_failure():
    # 잘못된 암호화 데이터 처리
    result = secret_manager.decrypt("invalid-base64-string")
    assert result == "DECRYPTION_FAILED"
