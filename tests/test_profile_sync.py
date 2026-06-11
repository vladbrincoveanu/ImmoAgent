"""Drift test: TS profile keys must match Python BUYER_PROFILES keys."""
import re
from pathlib import Path

from Application.buyer_profiles import BUYER_PROFILES

TS_FILE = Path(__file__).parent.parent / 'dashboard' / 'lib' / 'profile.ts'
ts_text = TS_FILE.read_text()
ts_keys = set(re.findall(r"key:\s*'([^']+)'", ts_text))
py_keys = set(BUYER_PROFILES.keys())


def test_keys_match():
    missing_in_ts = py_keys - ts_keys
    extra_in_ts = ts_keys - py_keys
    assert not missing_in_ts, f"Python profiles missing from TS: {missing_in_ts}"
    assert not extra_in_ts, f"TS profiles missing from Python: {extra_in_ts}"
