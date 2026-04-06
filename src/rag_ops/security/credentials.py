"""Credential encryption helpers."""

from __future__ import annotations

import base64
import hashlib


def encrypt_secret(secret_value: str, key_material: str) -> tuple[str, str]:
    """Encrypt a provider secret and return ciphertext plus key identifier."""
    fernet = _build_fernet(key_material)
    ciphertext = fernet.encrypt(secret_value.encode("utf-8")).decode("utf-8")
    key_id = hashlib.sha256(key_material.encode("utf-8")).hexdigest()[:16]
    return ciphertext, key_id


def decrypt_secret(ciphertext: str, key_material: str) -> str:
    """Decrypt a previously stored provider secret."""
    fernet = _build_fernet(key_material)
    return fernet.decrypt(ciphertext.encode("utf-8")).decode("utf-8")


def _build_fernet(key_material: str):
    from cryptography.fernet import Fernet

    digest = hashlib.sha256(key_material.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))
