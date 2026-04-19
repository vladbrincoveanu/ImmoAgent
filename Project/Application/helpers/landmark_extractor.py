"""Landmark hint extraction utility for geocoding."""

import re
from typing import Optional


def extract_landmark_hint(text: str) -> Optional[str]:
    """Extract a landmark hint from listing title/description.

    Parses listing titles for U-Bahn and Straßenbahn landmark patterns
    and returns a geocodable address string.

    U-Bahn patterns (case-insensitive):
        - "nahe/nahen [Station Name] U-Bahn" -> "[Station Name] U-Bahn, Wien, Austria"
        - "[Station Name] U-Bahn" anywhere in string -> same extraction

    Straßenbahn patterns (case-insensitive):
        - "[Name] Straßenbahn" -> "[Name], Wien, Austria"
        - "Straßenbahn [Name]" -> "[Name], Wien, Austria"

    Args:
        text: The listing title or description to parse.

    Returns:
        A geocodable address string like "Station Name U-Bahn, Wien, Austria",
        or None if no landmark hint is found.
    """
    if not text:
        return None

    text_lower = text.lower()

    # U-Bahn patterns
    # Pattern 1: "nahe [Station Name] U-Bahn" or "nahen [Station Name] U-Bahn"
    ubahn_nahe_pattern = re.compile(
        r'\b(?:nahe|nahen)\s+([A-Za-zÄäÖöÜüßáàâéèêíìîóòôúùû]+(?:\s+[A-Za-zÄäÖöÜüßáàâéèêíìîóòôúùû]+)*)\s+U-Bahn',
        re.IGNORECASE
    )
    match = ubahn_nahe_pattern.search(text)
    if match:
        station_name = match.group(1).strip()
        return f"{station_name} U-Bahn, Wien, Austria"

    # Pattern 2: "[Station Name] U-Bahn" anywhere in string
    ubahn_standalone_pattern = re.compile(
        r'\b([A-Za-zÄäÖöÜüßáàâéèêíìîóòôúùû]+(?:\s+[A-Za-zÄäÖöÜüßáàâéèêíìîóòôúùû]+)*)\s+U-Bahn\b',
        re.IGNORECASE
    )
    match = ubahn_standalone_pattern.search(text)
    if match:
        station_name = match.group(1).strip()
        return f"{station_name} U-Bahn, Wien, Austria"

    # Straßenbahn patterns
    # For "[Name] Straßenbahn", extract just the last word before Straßenbahn
    # This avoids capturing prepositions like "von", "in", "der", "Nähe"
    strassenbahn_pattern1 = re.compile(r'(\w+)\s+Straßenbahn\b', re.IGNORECASE)
    match = strassenbahn_pattern1.search(text)
    if match:
        name = match.group(1).strip()
        return f"{name}, Wien, Austria"

    # Pattern 2: "Straßenbahn [Name]"
    strassenbahn_pattern2 = re.compile(
        r'\bStraßenbahn\s+([A-Za-zÄäÖöÜüßáàâéèêíìîóòôúùû]+(?:\s+[A-Za-zÄäÖöÜüßáàâéèêíìîóòôúùû]+)*)\b',
        re.IGNORECASE
    )
    match = strassenbahn_pattern2.search(text)
    if match:
        name = match.group(1).strip()
        return f"{name}, Wien, Austria"

    return None