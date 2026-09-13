"""Encryption for face embeddings at rest.

An embedding is biometric data: it can't be revoked like a password, so it is
never stored in the clear. Fernet (AES-128-CBC + HMAC-SHA256) gives
authenticated encryption, so a tampered or wrong-key ciphertext fails to
decrypt instead of silently yielding a different identity.
"""

import base64
import logging

import numpy as np
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.core.config import settings

logger = logging.getLogger(__name__)

_EMBEDDING_DTYPE = "<f4"
_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        if settings.face_embedding_key:
            key = settings.face_embedding_key.encode()
        else:
            # Domain-separated from the JWT signing use of the same secret.
            derived = HKDF(
                algorithm=hashes.SHA256(),
                length=32,
                salt=b"aria-face-embedding-v1",
                info=b"identity-reference",
            ).derive(settings.jwt_secret.encode())
            key = base64.urlsafe_b64encode(derived)
        _fernet = Fernet(key)
    return _fernet


def encrypt_embedding(embedding: np.ndarray) -> str:
    return _get_fernet().encrypt(np.asarray(embedding, dtype=_EMBEDDING_DTYPE).tobytes()).decode()


def decrypt_embedding(token: str) -> np.ndarray | None:
    """The embedding, or None if the key changed or the ciphertext is invalid."""
    try:
        raw = _get_fernet().decrypt(token.encode())
    except (InvalidToken, ValueError, TypeError):
        logger.warning("A stored identity reference could not be decrypted; treating it as absent")
        return None
    return np.frombuffer(raw, dtype=_EMBEDDING_DTYPE).copy()
