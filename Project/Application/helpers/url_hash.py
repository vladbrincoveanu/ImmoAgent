"""Stable URL identity used by delivery ledgers."""
import hashlib


def url_hash(url: str) -> str:
    """Return the stable SHA-256 identity for a listing URL."""
    return hashlib.sha256((url or "").encode("utf-8")).hexdigest()
