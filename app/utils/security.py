import os
import re
import uuid
import bcrypt
import hmac
import hashlib
import time
import json
import base64
from typing import Optional, Dict, Any

def hash_password(password: str) -> str:
    pwd_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception:
        return False

def sanitize_filename(filename: str) -> str:
    # Normalize both forward and backward slashes
    normalized = filename.replace("\\", "/")
    base = os.path.basename(normalized)
    
    # Strip dangerous leading/trailing dots or spaces
    base = base.strip(" .")
    
    # Replace non-alphanumeric characters (allow . - _)
    clean = re.sub(r"[^a-zA-Z0-9_.-]", "_", base)
    
    # Neutralize any directory traversal dots
    while ".." in clean:
        clean = clean.replace("..", "_")
        
    return clean[:100] if clean else f"file_{uuid.uuid4().hex[:8]}"

def generate_stored_filename(original_filename: str) -> str:
    sanitized = sanitize_filename(original_filename)
    unique_id = uuid.uuid4().hex[:12]
    timestamp = int(time.time())
    return f"{timestamp}_{unique_id}_{sanitized}"

def create_session_token(data: Dict[str, Any], secret_key: str, expires_hours: int = 24) -> str:
    payload = data.copy()
    payload['exp'] = int(time.time()) + (expires_hours * 3600)
    payload_json = json.dumps(payload, sort_keys=True).encode('utf-8')
    payload_b64 = base64.urlsafe_b64encode(payload_json).decode('utf-8').rstrip('=')
    
    signature = hmac.new(secret_key.encode('utf-8'), payload_b64.encode('utf-8'), hashlib.sha256).hexdigest()
    return f"{payload_b64}.{signature}"

def verify_session_token(token: str, secret_key: str) -> Optional[Dict[str, Any]]:
    if not token or '.' not in token:
        return None
    try:
        payload_b64, signature = token.split('.', 1)
        expected_sig = hmac.new(secret_key.encode('utf-8'), payload_b64.encode('utf-8'), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected_sig):
            return None
        
        padding = 4 - (len(payload_b64) % 4)
        if padding != 4:
            payload_b64 += '=' * padding
            
        payload_json = base64.urlsafe_b64decode(payload_b64).decode('utf-8')
        payload = json.loads(payload_json)
        
        if payload.get('exp', 0) < time.time():
            return None
        return payload
    except Exception:
        return None
