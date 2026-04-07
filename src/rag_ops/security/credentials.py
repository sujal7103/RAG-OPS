"""Credential encryption helpers with keyring rotation support."""

from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rag_ops.settings import ServiceSettings


@dataclass(frozen=True)
class CredentialKeyring:
    """Resolved keyring for provider-credential encryption."""

    active_key_id: str
    keys: dict[str, str]

    def get_key(self, key_id: str | None = None) -> str:
        resolved_key_id = key_id or self.active_key_id
        key_material = self.keys.get(resolved_key_id)
        if not key_material:
            raise KeyError(f"Credential key {resolved_key_id} is not configured")
        return key_material


def build_credential_keyring(source: "ServiceSettings | str") -> CredentialKeyring:
    """Build a credential keyring from service settings or a legacy raw key."""
    if isinstance(source, str):
        return CredentialKeyring(active_key_id="default", keys={"default": source})

    keyring: dict[str, str] = {}
    if source.credential_keys_json.strip():
        try:
            parsed = json.loads(source.credential_keys_json)
        except json.JSONDecodeError as exc:
            raise ValueError("RAG_OPS_CREDENTIAL_KEYS_JSON is not valid JSON") from exc
        if not isinstance(parsed, dict):
            raise ValueError("RAG_OPS_CREDENTIAL_KEYS_JSON must be a JSON object")
        for key_id, key_material in parsed.items():
            keyring[str(key_id)] = str(key_material)

    if not keyring:
        keyring[source.credential_active_key_id] = source.credential_key
    elif source.credential_active_key_id not in keyring:
        keyring[source.credential_active_key_id] = source.credential_key

    return CredentialKeyring(
        active_key_id=source.credential_active_key_id,
        keys=keyring,
    )


def encrypt_secret(secret_value: str, source: "ServiceSettings | str") -> tuple[str, str]:
    """Encrypt a provider secret and return ciphertext plus key identifier."""
    keyring = build_credential_keyring(source)
    active_key = keyring.get_key(keyring.active_key_id)
    fernet = _build_fernet(active_key)
    ciphertext = fernet.encrypt(secret_value.encode("utf-8")).decode("utf-8")
    return ciphertext, keyring.active_key_id


def decrypt_secret(
    ciphertext: str,
    source: "ServiceSettings | str",
    *,
    key_id: str | None = None,
) -> str:
    """Decrypt a previously stored provider secret."""
    keyring = build_credential_keyring(source)
    fernet = _build_fernet(keyring.get_key(key_id))
    return fernet.decrypt(ciphertext.encode("utf-8")).decode("utf-8")


def credential_needs_rotation(key_id: str, source: "ServiceSettings | str") -> bool:
    """Return whether a stored secret should be re-encrypted with the active key."""
    keyring = build_credential_keyring(source)
    return key_id != keyring.active_key_id


def rotate_secret(
    ciphertext: str,
    source: "ServiceSettings | str",
    *,
    key_id: str,
) -> tuple[str, str]:
    """Re-encrypt a stored secret with the active key material."""
    plaintext = decrypt_secret(ciphertext, source, key_id=key_id)
    return encrypt_secret(plaintext, source)


def credential_key_fingerprint(source: "ServiceSettings | str", *, key_id: str | None = None) -> str:
    """Return a short fingerprint for the selected key material."""
    keyring = build_credential_keyring(source)
    material = keyring.get_key(key_id)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


def _build_fernet(key_material: str):
    from cryptography.fernet import Fernet

    digest = hashlib.sha256(key_material.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))
