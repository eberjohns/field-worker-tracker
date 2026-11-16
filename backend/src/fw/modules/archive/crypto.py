"""Cryptographic utilities for yearly archive encryption and verification.

Implements AES-256-GCM authenticated encryption with SHA-256 checksums per docs/14-nonfunctional.md.
"""

import hashlib
import os
from typing import Final

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

NONCE_LENGTH_BYTES: Final[int] = 12  # Standard 96-bit nonce for AES-GCM


def derive_key(secret: str | bytes) -> bytes:
    """Derive a fixed 256-bit (32-byte) key from the configured archive encryption secret."""
    if isinstance(secret, str):
        secret_bytes = secret.encode("utf-8")
    else:
        secret_bytes = secret
    return hashlib.sha256(secret_bytes).digest()


def compute_sha256(data: bytes) -> str:
    """Compute the SHA-256 hexadecimal checksum of raw data."""
    return hashlib.sha256(data).hexdigest()


def encrypt_payload(data: bytes, secret: str | bytes) -> tuple[bytes, str]:
    """Encrypt payload using AES-256-GCM and return (encrypted_bytes, sha256_checksum).

    The resulting encrypted bytes format is:
      [12 bytes nonce] + [ciphertext and 16 bytes authentication tag]
    """
    key = derive_key(secret)
    aesgcm = AESGCM(key)
    nonce = os.urandom(NONCE_LENGTH_BYTES)
    ciphertext = aesgcm.encrypt(nonce, data, associated_data=None)
    encrypted_package = nonce + ciphertext
    checksum = compute_sha256(encrypted_package)
    return encrypted_package, checksum


def decrypt_payload(encrypted_package: bytes, secret: str | bytes) -> bytes:
    """Decrypt an AES-256-GCM package.

    Raises:
        ValueError: If package is too short or authentication tag is invalid (corrupted/tampered).
    """
    if len(encrypted_package) < NONCE_LENGTH_BYTES + 16:
        raise ValueError("Encrypted package is too short to be a valid AES-GCM payload.")

    key = derive_key(secret)
    aesgcm = AESGCM(key)
    nonce = encrypted_package[:NONCE_LENGTH_BYTES]
    ciphertext = encrypted_package[NONCE_LENGTH_BYTES:]

    try:
        decrypted_data = aesgcm.decrypt(nonce, ciphertext, associated_data=None)
        return decrypted_data
    except InvalidTag as err:
        raise ValueError("Archive decryption failed: authentication tag mismatch or corrupted file.") from err
