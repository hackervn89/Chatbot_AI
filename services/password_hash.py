import hashlib
import os
import base64

def hash_password_pbkdf2(password: str, salt: bytes = None) -> str:
    """Hash password using PBKDF2-HMAC-SHA256 with salt"""
    if salt is None:
        salt = os.urandom(32)
    pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    return base64.b64encode(salt + pwd_hash).decode('ascii')

def verify_password(password: str, hash_str: str) -> bool:
    """Verify password against PBKDF2 or legacy SHA-256 hash"""
    # Try PBKDF2 first
    if len(hash_str) > 70:  # PBKDF2 base64 is longer
        try:
            decoded = base64.b64decode(hash_str.encode('ascii'))
            salt = decoded[:32]
            stored_hash = decoded[32:]
            new_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
            return new_hash == stored_hash
        except:
            pass
    
    # Fallback to legacy SHA-256
    legacy_hash = hashlib.sha256(password.encode('utf-8')).hexdigest()
    return hash_str == legacy_hash
