"""Which Telegram channel a co-op hit belongs in.

Two feeds, deliberately not one: mygewo units arrive in bulk and get browsed,
while private Ablöse ads are first-come-first-served and are acted on within
minutes. Mixing them buries the urgent ones under the routine ones.

Context for the loud-failure design: TELEGRAM_COOP_CHANNEL_ID was never actually
created. The workflow warned non-fatally and the poll ran green for weeks while
sending nothing at all, because a missing channel looked exactly like a quiet
market. Absence of a channel is now reported, not inferred from silence.
"""
import os
from typing import List, Optional

_CHANNEL_BY_KIND = {
    "mygewo": "TELEGRAM_COOP_CHANNEL_ID",
    "private_transfer": "TELEGRAM_PRIVATE_COOP_CHANNEL_ID",
}


def route(coop_kind: str) -> Optional[str]:
    """Chat id for this kind of co-op hit, or None when its secret is unset.

    No cross-kind fallback on purpose — see the module docstring."""
    env_name = _CHANNEL_BY_KIND.get(coop_kind)
    if not env_name:
        return None
    return os.environ.get(env_name) or None


def missing_channels() -> List[str]:
    """Every channel secret that is unset, for one loud log line at startup."""
    return [name for name in _CHANNEL_BY_KIND.values() if not os.environ.get(name)]
