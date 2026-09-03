import pytest
from app.utils.security import (
    hash_password,
    verify_password,
    sanitize_filename,
    generate_stored_filename,
    create_session_token,
    verify_session_token
)
from app.services.storage_service import storage_service

def test_password_hashing():
    pwd = "SecretPassword123!"
    hashed = hash_password(pwd)
    assert hashed != pwd
    assert verify_password(pwd, hashed) is True
    assert verify_password("WrongPassword", hashed) is False

def test_session_token_integrity():
    secret = "test_secret_key_32_characters_long_now"
    data = {"user_id": 1, "username": "admin"}
    token = create_session_token(data, secret, expires_hours=1)
    
    # Valid verification
    payload = verify_session_token(token, secret)
    assert payload is not None
    assert payload["user_id"] == 1
    assert payload["username"] == "admin"

    # Tampered token should fail
    tampered = token[:-4] + "abcd"
    assert verify_session_token(tampered, secret) is None

    # Wrong secret should fail
    assert verify_session_token(token, "wrong_secret_key") is None

def test_path_traversal_sanitization():
    dangerous_names = [
        "../../etc/passwd",
        "..\\..\\windows\\system32\\cmd.exe",
        "nested/path/to/file.pdf",
        "/absolute/path/cv.pdf"
    ]
    for d in dangerous_names:
        clean = sanitize_filename(d)
        assert "/" not in clean
        assert "\\" not in clean
        assert ".." not in clean

def test_file_header_validation():
    # Real PDF header
    valid_pdf = b"%PDF-1.7\n..."
    assert storage_service.validate_file_header(valid_pdf, "test.pdf") is True

    # Fake PDF (executable disguised as PDF)
    fake_pdf = b"MZ\x90\x00\x03\x00\x00\x00"
    assert storage_service.validate_file_header(fake_pdf, "malware.pdf") is False

    # Real DOCX (ZIP container)
    valid_docx = b"PK\x03\x04\x14\x00\x06\x00"
    assert storage_service.validate_file_header(valid_docx, "doc.docx") is True

def test_file_size_limit():
    small_bytes = b"x" * 1024 # 1 KB
    assert storage_service.validate_file_size(small_bytes) is True

    huge_bytes = b"x" * (16 * 1024 * 1024) # 16 MB (exceeds 15MB limit)
    assert storage_service.validate_file_size(huge_bytes) is False
