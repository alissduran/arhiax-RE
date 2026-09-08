"""Hashing y HMAC para el envelope de evidencia."""
import hashlib
import hmac as _hmac


def sha256_hex(data):
    return hashlib.sha256(data).hexdigest()


def hmac_hex(data, key):
    """HMAC-SHA256 sobre data con key (str o bytes)."""
    if isinstance(key, str):
        key = key.encode()
    return _hmac.new(key, data, hashlib.sha256).hexdigest()
