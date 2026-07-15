"""
Listing validation and fingerprinting utilities for scraping module.
Includes source-independent deduplication for cross-source matching.
"""

import hashlib
import re
import unicodedata


def _norm(s: str) -> str:
    """Lowercase, fold umlauts/ß, collapse whitespace, strip non-alnum runs to single space."""
    s = s.lower().strip()
    s = s.replace("ß", "ss")
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def compute_xsrc_fingerprint(listing) -> "str | None":
    """Source-INDEPENDENT fingerprint for co-op units so the same unit on
    Willhaben and on its Bauträger site collapse to one record.
    Key = md5(norm(bautraeger)|norm(address)|round(area)|rooms). No source, no price.
    Returns None when bautraeger or address is missing (weak key → don't collapse)."""
    if not getattr(listing, "bautraeger", None) or not getattr(listing, "address", None):
        return None
    area = listing.area_m2
    area_key = str(int(round(area))) if area else ""
    rooms_key = str(listing.rooms) if listing.rooms is not None else ""
    raw = f"{_norm(listing.bautraeger)}|{_norm(listing.address)}|{area_key}|{rooms_key}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()
