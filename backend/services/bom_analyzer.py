"""BOM ingestion, parsing, and Part Library cross-reference (Phase 6).

Handles CSV BOM files from Xpedition, Altium, OrCAD, and generic formats.
Cross-references each line item against the internal Part Library.
"""
import csv
import io
import re
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple

from models.bom import (
    BOMLineItem,
    BOMAnalysisResult,
    BOMReport,
    BOMSummary,
    LifecycleStatus,
    RadiationGrade,
    RiskLevel,
)
from services.part_library import get_all as get_library

# ---------------------------------------------------------------------------
# Column mapping — canonical names → common header variations
# ---------------------------------------------------------------------------

_COLUMN_ALIASES: Dict[str, List[str]] = {
    "ref_des": [
        "ref_des", "refdes", "reference", "reference designator",
        "ref des", "ref", "designator", "component",
    ],
    "part_number": [
        "part_number", "part number", "partnumber", "part_no", "part no",
        "pn", "mpn", "mfr part", "mfg part", "manufacturer part",
        "mfr_part_number", "mfr part number",
    ],
    "manufacturer": [
        "manufacturer", "mfr", "mfg", "vendor", "supplier",
        "manufacturer_name", "mfr name",
    ],
    "description": [
        "description", "desc", "part description", "component description",
    ],
    "quantity": [
        "quantity", "qty", "count", "qty per board",
    ],
    "value": [
        "value", "val", "component value",
    ],
    "package": [
        "package", "footprint", "case", "pkg", "package type",
        "case/package", "case_package",
    ],
    "dnp": [
        "dnp", "do not populate", "no stuff", "nostuff", "do_not_populate",
    ],
}


def _normalize_header(raw: str) -> str:
    """Lowercase, strip whitespace/quotes/underscores for fuzzy header matching."""
    return re.sub(r"[^a-z0-9 ]", " ", raw.lower()).strip()


def _detect_column_mapping(headers: List[str]) -> Dict[str, int]:
    """Map canonical field names to column indices."""
    mapping: Dict[str, int] = {}
    normalised = [_normalize_header(h) for h in headers]

    for field, aliases in _COLUMN_ALIASES.items():
        for alias in aliases:
            norm_alias = _normalize_header(alias)
            for idx, norm_hdr in enumerate(normalised):
                if norm_alias == norm_hdr or norm_alias in norm_hdr:
                    if field not in mapping:
                        mapping[field] = idx
                    break
            if field in mapping:
                break

    return mapping


def _normalize_part_number(pn: str) -> str:
    """Strip whitespace, trailing suffixes like -ND, /TR, #PBF for matching."""
    pn = pn.strip().upper()
    # Strip common distributor/packaging suffixes
    pn = re.sub(r"[-/](ND|TR|CT|DKR?|MOUSER|PBF|REEL|TAPE)$", "", pn, flags=re.IGNORECASE)
    return pn


def _fuzzy_match_score(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


# ---------------------------------------------------------------------------
# Trigram index for fast fuzzy-match candidate filtering
# ---------------------------------------------------------------------------

def _trigrams(s: str) -> set:
    """Return the set of 3-character substrings of *s* (padded to length ≥ 3)."""
    s = s.ljust(3)
    return {s[i:i + 3] for i in range(len(s) - 2)}


class _TrigramIndex:
    """Inverted trigram index mapping 3-grams → set of library part-number keys.

    Reduces fuzzy-match cost from O(n×m) to O(n × k) where k is typically
    a small candidate set, even for large libraries.
    """

    def __init__(self, keys: List[str]) -> None:
        self._index: Dict[str, set] = {}
        for key in keys:
            for tg in _trigrams(key):
                self._index.setdefault(tg, set()).add(key)
        self._all_keys = keys  # fallback if no trigrams match

    def candidates(self, query: str, min_shared: int = 1) -> List[str]:
        """Return library keys that share at least *min_shared* trigrams with *query*.

        Falls back to the full key list for very short queries (len < 3).
        """
        if len(query) < 3:
            return self._all_keys
        hits: Dict[str, int] = {}
        for tg in _trigrams(query):
            for key in self._index.get(tg, ()):
                hits[key] = hits.get(key, 0) + 1
        return [k for k, cnt in hits.items() if cnt >= min_shared]


# ---------------------------------------------------------------------------
# BOM parsing
# ---------------------------------------------------------------------------

def parse_bom_csv(content: str) -> List[BOMLineItem]:
    """Parse a CSV BOM string into a list of BOMLineItem.

    Auto-detects column mapping from header row.
    Raises ValueError if no recognisable columns found.
    """
    reader = csv.reader(io.StringIO(content))
    rows = list(reader)

    if not rows:
        raise ValueError("BOM file is empty.")

    # Find header row (first row with ≥2 recognised columns)
    header_idx = 0
    mapping: Dict[str, int] = {}
    for i, row in enumerate(rows[:5]):  # check first 5 rows for headers
        candidate = _detect_column_mapping(row)
        if len(candidate) >= 2:
            mapping = candidate
            header_idx = i
            break

    if "part_number" not in mapping and "ref_des" not in mapping:
        raise ValueError(
            "Could not detect BOM columns. Expected at least 'Part Number' and 'Reference Designator' columns."
        )

    items: List[BOMLineItem] = []
    for row in rows[header_idx + 1:]:
        if not row or all(c.strip() == "" for c in row):
            continue

        def _get(field: str, default: str = "") -> str:
            idx = mapping.get(field)
            if idx is not None and idx < len(row):
                return row[idx].strip()
            return default

        pn = _get("part_number")
        ref = _get("ref_des")
        if not pn and not ref:
            continue

        qty_str = _get("quantity", "1")
        try:
            qty = int(float(qty_str))
        except (ValueError, TypeError):
            qty = 1

        dnp_str = _get("dnp", "").lower()
        dnp = dnp_str in ("yes", "true", "1", "dnp", "y")

        items.append(BOMLineItem(
            ref_des=ref or "?",
            part_number=pn or "UNKNOWN",
            manufacturer=_get("manufacturer", "Unknown"),
            description=_get("description"),
            quantity=max(qty, 0),
            value=_get("value") or None,
            package=_get("package") or None,
            dnp=dnp,
        ))

    return items


# ---------------------------------------------------------------------------
# Library cross-reference
# ---------------------------------------------------------------------------

def cross_reference_library(
    items: List[BOMLineItem],
    library: Optional[List[Dict[str, Any]]] = None,
) -> List[BOMAnalysisResult]:
    """Cross-reference BOM line items against the Part Library.

    Returns a BOMAnalysisResult per line item with library_match populated.
    """
    if library is None:
        library = get_library()

    # Build lookup: normalised part number → library entry
    lib_index: Dict[str, Dict[str, Any]] = {}
    for entry in library:
        pn = entry.get("Part_Number", "")
        if pn:
            lib_index[_normalize_part_number(pn)] = entry

    # Build trigram index once (O(m)) so candidate lookup per item is O(k) not O(m)
    tg_index = _TrigramIndex(list(lib_index.keys()))

    results: List[BOMAnalysisResult] = []
    for item in items:
        norm_pn = _normalize_part_number(item.part_number)
        result = BOMAnalysisResult(line_item=item)

        # Exact match
        if norm_pn in lib_index:
            result.library_match = True
            result.library_part_number = lib_index[norm_pn].get("Part_Number", norm_pn)
        else:
            # Fuzzy match — only evaluate trigram candidates (fast O(k) path)
            candidates = tg_index.candidates(norm_pn, min_shared=1)
            best_score = 0.0
            best_pn = None
            for lib_pn in candidates:
                score = _fuzzy_match_score(norm_pn, lib_pn)
                if score > best_score:
                    best_score = score
                    best_pn = lib_pn
            if best_score >= 0.85 and best_pn:
                result.library_match = True
                result.library_part_number = lib_index[best_pn].get("Part_Number", best_pn)
                result.risk_flags.append(
                    f"Fuzzy library match ({best_score:.0%}) — verify part number"
                )

        # If in library, try to infer lifecycle/rad from library data
        if result.library_match and result.library_part_number:
            lib_entry = lib_index.get(
                _normalize_part_number(result.library_part_number), {}
            )
            _enrich_from_library(result, lib_entry)

        results.append(result)

    return results


def _enrich_from_library(result: BOMAnalysisResult, lib_entry: Dict[str, Any]) -> None:
    """Populate lifecycle/radiation/risk from library entry data."""
    # Check for radiation keywords in description or any field
    all_text = " ".join(str(v) for v in lib_entry.values() if v).lower()

    if any(kw in all_text for kw in ["rad hard", "radhard", "qml-v", "qml v"]):
        result.radiation_grade = RadiationGrade.RadHard
    elif any(kw in all_text for kw in ["rad tolerant", "radtolerant", "qml-q"]):
        result.radiation_grade = RadiationGrade.RadTolerant
    elif any(kw in all_text for kw in ["mil-std", "mil std", "883", "qml"]):
        result.radiation_grade = RadiationGrade.MIL
    elif any(kw in all_text for kw in ["commercial", "cots", "industrial"]):
        result.radiation_grade = RadiationGrade.Commercial

    # Lifecycle — check for obsolete/nrnd keywords
    if any(kw in all_text for kw in ["obsolete", "discontinued", "eol"]):
        result.lifecycle_status = LifecycleStatus.Obsolete
    elif any(kw in all_text for kw in ["nrnd", "not recommended", "last buy"]):
        result.lifecycle_status = LifecycleStatus.NRND
    elif any(kw in all_text for kw in ["active", "in production"]):
        result.lifecycle_status = LifecycleStatus.Active

    # Check for missing critical fields
    voltage = lib_entry.get("Voltage_Rating")
    if not voltage:
        result.risk_flags.append("Voltage rating missing in library data")
    temp = lib_entry.get("Operating_Temperature_Range")
    if not temp:
        result.risk_flags.append("Operating temperature range missing in library data")


# ---------------------------------------------------------------------------
# Risk level assignment
# ---------------------------------------------------------------------------

def assign_risk_levels(results: List[BOMAnalysisResult]) -> List[BOMAnalysisResult]:
    """Assign risk_level for each result based on lifecycle, rad grade, and flags."""
    for r in results:
        if r.line_item.dnp:
            r.risk_level = RiskLevel.Low
            continue

        score = 0

        # Lifecycle
        if r.lifecycle_status == LifecycleStatus.Obsolete:
            score += 4
            if "Obsolete" not in " ".join(r.risk_flags):
                r.risk_flags.append("Part is obsolete — find replacement")
        elif r.lifecycle_status == LifecycleStatus.NRND:
            score += 3
            if "NRND" not in " ".join(r.risk_flags):
                r.risk_flags.append("Part is NRND — plan for end-of-life")
        elif r.lifecycle_status == LifecycleStatus.Unknown:
            score += 1

        # Radiation
        if r.radiation_grade == RadiationGrade.Commercial:
            score += 2
            if "commercial" not in " ".join(r.risk_flags).lower():
                r.risk_flags.append("Commercial grade — verify radiation tolerance for space use")
        elif r.radiation_grade == RadiationGrade.Unknown:
            score += 1

        # Library match
        if not r.library_match:
            score += 1
            if "not found" not in " ".join(r.risk_flags).lower():
                r.risk_flags.append("Part not found in library — manual review required")

        # No alternates
        if not r.alt_parts:
            score += 1

        # Determine level
        if score >= 5:
            r.risk_level = RiskLevel.Critical
        elif score >= 3:
            r.risk_level = RiskLevel.High
        elif score >= 2:
            r.risk_level = RiskLevel.Medium
        else:
            r.risk_level = RiskLevel.Low

    return results


# ---------------------------------------------------------------------------
# Summary computation
# ---------------------------------------------------------------------------

def compute_summary(results: List[BOMAnalysisResult]) -> BOMSummary:
    """Compute aggregate statistics from analysis results."""
    unique_pns = set()
    total_placements = 0

    summary = BOMSummary(total_line_items=len(results))

    for r in results:
        unique_pns.add(r.line_item.part_number)
        total_placements += r.line_item.quantity

        if r.library_match:
            summary.library_matched += 1

        # Lifecycle counts
        if r.lifecycle_status == LifecycleStatus.Active:
            summary.lifecycle_active += 1
        elif r.lifecycle_status == LifecycleStatus.NRND:
            summary.lifecycle_nrnd += 1
        elif r.lifecycle_status == LifecycleStatus.Obsolete:
            summary.lifecycle_obsolete += 1
        else:
            summary.lifecycle_unknown += 1

        # Radiation counts
        if r.radiation_grade == RadiationGrade.Commercial:
            summary.rad_commercial += 1
        elif r.radiation_grade == RadiationGrade.MIL:
            summary.rad_mil += 1
        elif r.radiation_grade == RadiationGrade.RadTolerant:
            summary.rad_tolerant += 1
        elif r.radiation_grade == RadiationGrade.RadHard:
            summary.rad_hard += 1
        else:
            summary.rad_unknown += 1

        # Risk counts
        if r.risk_level == RiskLevel.Critical:
            summary.risk_critical += 1
        elif r.risk_level == RiskLevel.High:
            summary.risk_high += 1
        elif r.risk_level == RiskLevel.Medium:
            summary.risk_medium += 1
        else:
            summary.risk_low += 1

    summary.unique_parts = len(unique_pns)
    summary.total_placements = total_placements
    summary.library_matched_pct = (
        round(summary.library_matched / len(results) * 100, 1) if results else 0.0
    )

    return summary


# ---------------------------------------------------------------------------
# Full analysis pipeline
# ---------------------------------------------------------------------------

def analyze_bom(
    csv_content: str,
    filename: str = "bom.csv",
    library: Optional[List[Dict[str, Any]]] = None,
    skip_ai: bool = False,
) -> BOMReport:
    """Run the full BOM analysis pipeline.

    1. Parse CSV → BOMLineItems
    2. Cross-reference Part Library
    3. (Optionally) AI risk assessment for unmatched parts
    4. Assign risk levels
    5. Compute summary

    Args:
        csv_content: Raw CSV string.
        filename: Original filename for the report.
        library: Override library (for testing). If None, loads from disk.
        skip_ai: If True, skip AI risk assessment.

    Returns:
        Complete BOMReport.
    """
    items = parse_bom_csv(csv_content)
    results = cross_reference_library(items, library=library)

    if not skip_ai:
        try:
            from services.bom_risk_assessor import assess_risks_batch
            # Only assess parts that aren't fully characterised
            needs_ai = [
                i for i, r in enumerate(results)
                if not r.library_match
                or r.lifecycle_status == LifecycleStatus.Unknown
                or r.radiation_grade == RadiationGrade.Unknown
            ]
            if needs_ai:
                items_for_ai = [results[i].line_item for i in needs_ai]
                assessments = assess_risks_batch(items_for_ai)
                for idx, assessment in zip(needs_ai, assessments):
                    r = results[idx]
                    if r.lifecycle_status == LifecycleStatus.Unknown:
                        r.lifecycle_status = assessment.lifecycle_status
                    if r.radiation_grade == RadiationGrade.Unknown:
                        r.radiation_grade = assessment.radiation_grade
                    r.risk_flags.extend(assessment.risk_flags)
                    r.alt_parts.extend(assessment.alt_parts)
                    r.ai_assessment = assessment.assessment
        except Exception:
            pass  # AI is best-effort; continue without it

    results = assign_risk_levels(results)
    summary = compute_summary(results)

    return BOMReport(filename=filename, results=results, summary=summary)
