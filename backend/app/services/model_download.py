"""Integrity-checked downloads for the local model files ARIA fetches on first use.

Model files are executable graphs pulled over the network, so each one is
pinned by SHA-256 and only moved into place once the hash matches.
"""

import hashlib
import logging
import urllib.request
from pathlib import Path

logger = logging.getLogger(__name__)


class ModelDownloadError(RuntimeError):
    """A model file couldn't be downloaded, or didn't match its pinned hash."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ensure_model_file(path: Path, url: str, expected_sha256: str, *, timeout: float = 60) -> Path:
    """Return `path`, downloading and verifying it first if it's missing or wrong."""
    if path.exists() and sha256(path) == expected_sha256:
        return path

    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(path.name + ".part")
    logger.info("Downloading model file %s…", path.name)
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response, partial.open("wb") as out:
            while chunk := response.read(1 << 20):
                out.write(chunk)
    except Exception as exc:
        partial.unlink(missing_ok=True)
        raise ModelDownloadError(f"Couldn't download {path.name}.") from exc

    if sha256(partial) != expected_sha256:
        partial.unlink(missing_ok=True)
        raise ModelDownloadError(f"{path.name} failed its integrity check.")
    partial.replace(path)
    return path
