"""Co-op unit identity.

Two distinct keys, deliberately kept apart:

* ``coop_uid`` — the WITHIN-source identity of one apartment. It is what an
  upsert keys on. Before it existed, upserts keyed on ``url``, and every mygewo
  unit from RPC page 1 onward falls back to the builder's *project* reservation
  page — one URL shared by every apartment in the project — so those units
  overwrote one another, silently.

* ``content_fingerprint_xsrc`` (in ``listing_validator``) — the CROSS-source
  identity, collapsing "same flat on Willhaben and on the Bauträger's own site"
  into one record. That key had no unit identifier at all, so eight distinct
  3-Zimmer/68 m² flats at one address produced eight identical fingerprints and
  seven were dropped as duplicates.

``strengthened_fingerprint`` is re-exported here so both keys are discoverable
in one place; the implementation stays in ``listing_validator`` because
``main.py`` and ``mongodb_handler`` already import it from there and a second
implementation would be free to drift.
"""
import hashlib
from typing import Any, Optional

from Application.helpers.listing_validator import (  # noqa: F401  (re-export)
    compute_xsrc_fingerprint as strengthened_fingerprint,
    _norm,
)


def coop_uid(source: str, unit_id: Any) -> Optional[str]:
    """``"<source>:<unit_id>"`` — the stable per-unit key.

    Namespaced by source so two builders' independently-numbered ids can never
    collide. Returns None when the source gave us no id: a missing id must
    degrade to the old url-keyed path, never to a shared empty key that would
    collapse every id-less unit into one document.
    """
    if not source:
        return None
    uid = str(unit_id).strip() if unit_id is not None else ""
    return f"{source}:{uid}" if uid else None


def derive_unit_id(*parts: Any) -> str:
    """Synthesise a unit id for builders whose site exposes none.

    DERIVED, not stable: it hashes the unit's own visible fields, so a site
    redesign that changes how street/Top/area are rendered churns the id and
    the affected units re-insert as new. Adapters using this must say so in
    their docstring. Prefer any site-side id over calling this.
    """
    raw = "|".join(_norm(str(p)) if p is not None else "" for p in parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
