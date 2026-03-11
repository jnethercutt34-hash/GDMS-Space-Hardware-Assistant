"""Persistent part library — JSON file backed, thread-safe.

Parts are keyed by Part_Number. When a datasheet contains multiple part
number variants (different packages of the same IC), they are consolidated
into a single library entry under a primary part number, with the other
variants stored in a ``variants`` list.
"""
import json
import os
import re
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

_LIBRARY_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "library.json")
_lock = threading.Lock()


def _load() -> List[Dict[str, Any]]:
    if not os.path.exists(_LIBRARY_PATH):
        return []
    with open(_LIBRARY_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(parts: List[Dict[str, Any]]) -> None:
    os.makedirs(os.path.dirname(_LIBRARY_PATH), exist_ok=True)
    with open(_LIBRARY_PATH, "w", encoding="utf-8") as f:
        json.dump(parts, f, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Variant consolidation
# ---------------------------------------------------------------------------

# Military/SMD ordering numbers — these should be variants, not primary
_MILITARY_PN = re.compile(r"^5962[A-Z]?\d", re.IGNORECASE)
# Engineering samples / evaluation modules
_SAMPLE_PN = re.compile(r"(HFT|/EM|EVM|DBV|DBG)\b", re.IGNORECASE)
# Common ordering suffixes that make a PN longer than the base part
# e.g. TPS7H1111MPWPTSEP → base is TPS7H1111
_ORDERING_SUFFIX = re.compile(
    r"(MPWPT|MPWP|MDGN|MDCK|MRGN|MRGH|MPSP|SEP|QFN|RH|SP|EP|EM|HFT)$",
    re.IGNORECASE,
)

# Fields that can differ between variants
_VARIANT_FIELDS = [
    "Part_Number", "Package_Type", "Pin_Count",
    "Radiation_TID", "Thermal_Resistance",
]


def _base_pn(pn: str) -> str:
    """Strip ordering/suffix codes to get the base part family name."""
    # Repeatedly strip known suffixes
    base = pn.strip()
    for _ in range(3):
        m = _ORDERING_SUFFIX.search(base)
        if m:
            base = base[:m.start()]
        else:
            break
    # Strip trailing hyphens/dashes
    return base.rstrip("-/ ")


def _pick_primary(parts: List[Dict[str, Any]], source_file: str = "") -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Choose the best primary part number from a list of datasheet variants.

    Heuristic priority:
      1. Non-military, non-sample part numbers first
      2. Part number closest to the base family name (shortest after suffix stripping)
      3. Prefer shorter part numbers (more generic / base part)
      4. Fall back to the first item if all look equally specific
    """
    if len(parts) <= 1:
        return parts[0], []

    scored = []
    for i, p in enumerate(parts):
        pn = p.get("Part_Number", "")
        score = 0
        if _MILITARY_PN.match(pn):
            score += 1000  # push military PNs way down
        if _SAMPLE_PN.search(pn):
            score += 500   # push samples down
        # Prefer PNs whose base name is shorter (closer to the family name)
        base = _base_pn(pn)
        score += len(base) * 10  # weight base length heavily
        score += len(pn)         # tiebreak on full length
        scored.append((score, i, p))
    scored.sort(key=lambda x: (x[0], x[1]))

    primary = scored[0][2]
    variants = [s[2] for s in scored[1:]]
    return primary, variants


def _build_variant_entry(variant: Dict[str, Any], primary: Dict[str, Any]) -> Dict[str, Any]:
    """Build a compact variant record showing only the fields that differ or matter."""
    entry: Dict[str, Any] = {"Part_Number": variant["Part_Number"]}
    for field in _VARIANT_FIELDS:
        if field == "Part_Number":
            continue
        v_val = variant.get(field)
        p_val = primary.get(field)
        if v_val and v_val != p_val:
            entry[field] = v_val
    # If the variant has a Summary that differs, include it
    v_sum = variant.get("Summary")
    p_sum = primary.get("Summary")
    if v_sum and v_sum != p_sum:
        entry["Summary"] = v_sum
    return entry


def consolidate_variants(parts: List[Dict[str, Any]], source_file: str = "") -> Dict[str, Any]:
    """Consolidate a list of extracted parts into a single entry with variants.

    Returns the consolidated entry dict ready for library storage.
    """
    if not parts:
        return {}

    primary, variants = _pick_primary(parts, source_file=source_file)
    entry = dict(primary)

    if variants:
        entry["variants"] = [
            _build_variant_entry(v, primary) for v in variants
        ]
    return entry


def upsert_parts(
    new_parts: List[Dict[str, Any]],
    source_file: str,
    datasheet_file: Optional[str] = None,
) -> int:
    """Consolidate and save parts from a newly processed datasheet.

    Multiple part number variants from the same datasheet are merged into
    a single library entry. Returns the number of entries newly added.
    """
    if not new_parts:
        return 0

    timestamp = datetime.now(timezone.utc).isoformat()

    # Consolidate all extracted rows into one entry
    consolidated = consolidate_variants(new_parts)
    if not consolidated.get("Part_Number"):
        return 0

    consolidated["source_file"] = source_file
    consolidated["added_at"] = timestamp
    consolidated["needs_datasheet"] = False
    if datasheet_file:
        consolidated["datasheet_file"] = datasheet_file

    pn = consolidated["Part_Number"]

    with _lock:
        parts = _load()
        index: Dict[str, int] = {p["Part_Number"]: i for i, p in enumerate(parts)}

        # Also remove any old entries that match variant PNs (cleanup from
        # before consolidation was implemented)
        variant_pns = {v["Part_Number"] for v in consolidated.get("variants", [])}
        if variant_pns:
            parts = [p for p in parts if p["Part_Number"] not in variant_pns]
            # Rebuild index after removal
            index = {p["Part_Number"]: i for i, p in enumerate(parts)}

        if pn in index:
            parts[index[pn]] = consolidated
            _save(parts)
            return 0
        else:
            parts.append(consolidated)
            _save(parts)
            return 1


def upsert_placeholder_parts(
    parts: List[Dict[str, Any]],
    source_file: str,
) -> Dict[str, int]:
    """Add skeleton part entries from a BOM import (no datasheet data).

    Only creates entries for parts that do NOT already exist in the library.
    Existing parts are left untouched (we never overwrite datasheet data with
    less-complete BOM data).

    Returns dict with counts: {"added": N, "skipped": M}.
    """
    timestamp = datetime.now(timezone.utc).isoformat()
    with _lock:
        existing = _load()
        index = {p["Part_Number"]: i for i, p in enumerate(existing)}
        added = 0
        skipped = 0
        for part in parts:
            pn = part.get("Part_Number")
            if not pn:
                continue
            if pn in index:
                skipped += 1
                continue
            entry = {
                **part,
                "source_file": source_file,
                "added_at": timestamp,
                "needs_datasheet": True,
            }
            existing.append(entry)
            index[pn] = len(existing) - 1
            added += 1
        _save(existing)
    return {"added": added, "skipped": skipped}


def get_all() -> List[Dict[str, Any]]:
    return _load()


def get_by_part_number(part_number: str) -> Dict[str, Any] | None:
    """Look up a single part by Part_Number (exact match)."""
    for p in _load():
        if p.get("Part_Number") == part_number:
            return p
    return None


def patch_part(part_number: str, updates: Dict[str, Any]) -> Dict[str, Any] | None:
    """Update specific fields on a part by Part_Number. Returns updated part or None."""
    with _lock:
        parts = _load()
        for i, p in enumerate(parts):
            if p.get("Part_Number") == part_number:
                parts[i] = {**p, **updates}
                _save(parts)
                return parts[i]
    return None


def search(query: str) -> List[Dict[str, Any]]:
    """Case-insensitive substring search across all text fields, including variants."""
    q = query.lower().strip()
    if not q:
        return _load()
    results = []
    for part in _load():
        # Build haystack from all top-level values
        haystack = " ".join(str(v) for v in part.values() if v and not isinstance(v, list)).lower()
        # Also include variant part numbers in the search
        for variant in part.get("variants", []):
            haystack += " " + " ".join(str(v) for v in variant.values() if v).lower()
        if q in haystack:
            results.append(part)
    return results
