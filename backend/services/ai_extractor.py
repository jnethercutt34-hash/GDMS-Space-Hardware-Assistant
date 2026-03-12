"""AI extraction service — OpenAI-compatible, enterprise-ready.

Uses the standard `openai` Python package so the app can be pointed at any
OpenAI-compatible gateway (internal or public) via environment variables.

Includes robust salvage logic to handle small/local LLMs (e.g. llama3.1:8b)
that may not follow the requested JSON schema precisely.
"""
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from pydantic import ValidationError

from models.component import ComponentData, ComponentExtractionResult
from services.ai_client import get_client, get_model

logger = logging.getLogger(__name__)

# Maximum characters of PDF text sent to the model.
# Keeps token costs predictable and avoids context-window errors.
# For local models with small context windows (e.g. llama3.1:8b @ 4096 tokens),
# keep this low. ~4000 chars ≈ 1000 tokens, leaving room for the system prompt
# and the generated response. Increase for cloud models with larger contexts.
_MAX_TEXT_CHARS = int(os.environ.get("MAX_PDF_CHARS", "4000"))

_MAX_CHUNK_CHARS = int(os.environ.get("MAX_CHUNK_CHARS",     "6000"))
_CHUNK_OVERLAP   = int(os.environ.get("CHUNK_OVERLAP_CHARS", "300"))
_MAX_CHUNKS      = int(os.environ.get("MAX_CHUNKS",          "5"))


def _build_system_prompt() -> str:
    """Build a concise system prompt that works well with both large and small LLMs."""
    return """You are an electronics data extraction engine. Extract component parameters from datasheet text.

Return a JSON object with this EXACT structure:
{"components": [{"Part_Number": "...", "Manufacturer": "...", "Value": null, "Tolerance": null, "Voltage_Rating": null, "Package_Type": null, "Pin_Count": null, "Operating_Temperature_Range": null, "Thermal_Resistance": null, "Radiation_TID": null, "Radiation_SEL_Threshold": null, "Radiation_SEU_Rate": null, "Summary": null}]}

Field extraction hints — look for these patterns in the text:
- Pin_Count: number of pins (e.g. "28-pin" means "28", "100-ball BGA" means "100")
- Voltage_Rating: input/output voltage range (e.g. "2.25V to 6.5V" or "output 3.3V")
- Operating_Temperature_Range: look for "operating temperature", "TJ", "TA" ranges (e.g. "-55 to +125 C")
- Thermal_Resistance: junction-to-ambient θJA (e.g. "35 C/W")
- Radiation_TID: Total Ionizing Dose (e.g. "100 krad(Si)")
- Radiation_SEL_Threshold: SEL LET threshold (e.g. "75 MeV·cm²/mg")
- Radiation_SEU_Rate: SEU cross-section or rate
- Package_Type: package name (e.g. "HTSSOP", "SOIC-8", "QFP-100")
- Summary: one sentence describing what the component is

Rules:
- Part_Number and Manufacturer are REQUIRED. Skip any component missing either.
- Include units in values (e.g. "3.3 V", "100 krad(Si)", "-55 to +125 C", "35 C/W").
- Set unknown fields to null. Do NOT guess.
- If a datasheet covers MULTIPLE part number variants (different packages/ordering numbers), create one entry per variant.
- Put the BASE / GENERIC part number FIRST in the list (e.g. "TPS7H1111-SEP" before "5962R2120301VXC" or "TPS7H1111MPWPTSEP"). The base part is usually the shortest commercial name shown on the datasheet title page.
- Return ONLY the JSON object. No markdown, no commentary."""


# ---------------------------------------------------------------------------
# Field-name mapping for LLM responses that use non-standard keys
# ---------------------------------------------------------------------------

# Map of common LLM variations → our canonical field names
_FIELD_ALIASES: Dict[str, str] = {
    # Part number
    "part number": "Part_Number",
    "part_number": "Part_Number",
    "partnumber": "Part_Number",
    "part_no": "Part_Number",
    "part no": "Part_Number",
    "pn": "Part_Number",
    # Manufacturer
    "manufacturer": "Manufacturer",
    "mfr": "Manufacturer",
    "mfg": "Manufacturer",
    # Value
    "value": "Value",
    # Tolerance
    "tolerance": "Tolerance",
    # Voltage
    "voltage_rating": "Voltage_Rating",
    "voltage rating": "Voltage_Rating",
    "voltage": "Voltage_Rating",
    "input voltage": "Voltage_Rating",
    "input_voltage": "Voltage_Rating",
    "input voltage range": "Voltage_Rating",
    # Package
    "package_type": "Package_Type",
    "package type": "Package_Type",
    "package": "Package_Type",
    # Pin count
    "pin_count": "Pin_Count",
    "pin count": "Pin_Count",
    "pins": "Pin_Count",
    "pin_no": "Pin_Count",
    # Operating temperature
    "operating_temperature_range": "Operating_Temperature_Range",
    "operating temperature range": "Operating_Temperature_Range",
    "operating temperature": "Operating_Temperature_Range",
    "temperature range": "Operating_Temperature_Range",
    "temperature": "Operating_Temperature_Range",
    "temp range": "Operating_Temperature_Range",
    # Thermal resistance
    "thermal_resistance": "Thermal_Resistance",
    "thermal resistance": "Thermal_Resistance",
    "theta_ja": "Thermal_Resistance",
    "θja": "Thermal_Resistance",
    # Radiation
    "radiation_tid": "Radiation_TID",
    "radiation tid": "Radiation_TID",
    "tid": "Radiation_TID",
    "total ionizing dose": "Radiation_TID",
    "radiation_sel_threshold": "Radiation_SEL_Threshold",
    "radiation sel threshold": "Radiation_SEL_Threshold",
    "sel threshold": "Radiation_SEL_Threshold",
    "sel": "Radiation_SEL_Threshold",
    "radiation_seu_rate": "Radiation_SEU_Rate",
    "radiation seu rate": "Radiation_SEU_Rate",
    "seu rate": "Radiation_SEU_Rate",
    "seu": "Radiation_SEU_Rate",
    # Summary
    "summary": "Summary",
    "description": "Summary",
    "desc": "Summary",
}


def _normalize_keys(d: Dict[str, Any]) -> Dict[str, Any]:
    """Map LLM field names to our canonical ComponentData field names."""
    result = {}
    for k, v in d.items():
        canonical = _FIELD_ALIASES.get(k.lower().strip())
        if canonical:
            result[canonical] = v
        # Also accept already-correct keys
        elif k in ComponentData.model_fields:
            result[k] = v
    return result


def _salvage_flat_response(parsed: Dict[str, Any], datasheet_text: str) -> List[Dict[str, Any]]:
    """Handle the case where the LLM returns a flat dict instead of {"components": [...]}.

    Small models often return a single flat object with keys like "Part Number",
    "Package", "Pinout", "Specifications" etc. We try to extract what we can.
    """
    normalized = _normalize_keys(parsed)
    if not normalized.get("Part_Number") and not normalized.get("Manufacturer"):
        return []

    # Try to enrich from the original text if the LLM missed fields
    enriched = _enrich_from_text(normalized, datasheet_text)

    return [enriched] if enriched.get("Part_Number") else []


def _enrich_from_text(component: Dict[str, Any], text: str) -> Dict[str, Any]:
    """Fill in missing fields by scanning the original datasheet text with regex.

    This is a fallback for when the LLM fails to populate fields that are
    clearly present in the text.
    """
    first_text = text if text else ""

    # Pin count: look for "N-pin" or "N-Pin" patterns
    if not component.get("Pin_Count"):
        m = re.search(r'(\d+)[- ]?[Pp]in', first_text)
        if m:
            component["Pin_Count"] = m.group(1)

    # Operating temperature range: look for military temp range pattern
    if not component.get("Operating_Temperature_Range"):
        m = re.search(r'[–-]\s*55\s*°?\s*C\s*to\s*\+?\s*125\s*°?\s*C', first_text)
        if m:
            component["Operating_Temperature_Range"] = "-55 to +125 C"
        else:
            m = re.search(r'[–-]\s*40\s*°?\s*C\s*to\s*\+?\s*85\s*°?\s*C', first_text)
            if m:
                component["Operating_Temperature_Range"] = "-40 to +85 C"

    # Radiation TID
    if not component.get("Radiation_TID"):
        m = re.search(r'(\d+)\s*krad\s*\(?Si\)?', first_text, re.IGNORECASE)
        if m:
            component["Radiation_TID"] = f"{m.group(1)} krad(Si)"

    # SEL threshold — look for LET threshold near SEL mentions
    if not component.get("Radiation_SEL_Threshold"):
        # Pattern 1: "SEL...immune...LET...= 75 MeV" or "SEL immune to 80 MeV"
        m = re.search(
            r'(?:SEL|latchup|single.event.latchup).*?(?:immune|free).*?(?:LET\s*[=:])?\s*(\d+)\s*MeV',
            first_text, re.IGNORECASE | re.DOTALL,
        )
        if m:
            component["Radiation_SEL_Threshold"] = f"SEL immune to {m.group(1)} MeV-cm2/mg"
        else:
            # Pattern 2: "LET = 75 MeV" near SEL context
            m = re.search(r'LET\s*[=:]\s*(\d+)\s*MeV', first_text, re.IGNORECASE)
            if m:
                component["Radiation_SEL_Threshold"] = f"{m.group(1)} MeV-cm2/mg"

    # Voltage rating (input voltage range)
    if not component.get("Voltage_Rating"):
        m = re.search(r'[Ii]nput\s+voltage\s+(?:range\s+)?(?:from\s+)?(\d+\.?\d*)\s*V?\s*to\s*(\d+\.?\d*)\s*V', first_text)
        if m:
            component["Voltage_Rating"] = f"{m.group(1)} V to {m.group(2)} V"

    # Thermal resistance (θJA)
    if not component.get("Thermal_Resistance"):
        m = re.search(r'(?:θ|theta)\s*JA.*?(\d+\.?\d*)\s*°?\s*C/W', first_text, re.IGNORECASE)
        if m:
            component["Thermal_Resistance"] = f"{m.group(1)} C/W"

    return component


def _find_components_in_parsed(parsed: Any) -> List[Dict[str, Any]]:
    """Try various strategies to locate component dicts in the LLM response."""
    # Strategy 1: Standard {"components": [...]}
    if isinstance(parsed, dict) and "components" in parsed:
        items = parsed["components"]
        if isinstance(items, list):
            return items

    # Strategy 2: Bare list
    if isinstance(parsed, list):
        return parsed

    # Strategy 3: Single flat component with Part_Number
    if isinstance(parsed, dict) and "Part_Number" in parsed:
        return [parsed]

    # Strategy 4: Single flat component with "Part Number" (space) or other alias
    if isinstance(parsed, dict):
        normalized = _normalize_keys(parsed)
        if normalized.get("Part_Number"):
            return [normalized]

    return []


def extract_components_from_text(text: str) -> Tuple[List[ComponentData], List[str]]:
    """Send extracted PDF text to the LLM and return a validated list of ComponentData.

    Args:
        text: Full text extracted from the PDF datasheet.

    Returns:
        Tuple of (list of validated ComponentData instances, list of warning strings).

    Raises:
        RuntimeError: If INTERNAL_API_KEY is not configured.
        Exception:    Propagated from the OpenAI client for network/API errors.
    """
    client = get_client()
    model = get_model()
    warnings: List[str] = []

    # Check for truncation and warn
    truncated_text = text[:_MAX_TEXT_CHARS]
    if len(text) > _MAX_TEXT_CHARS:
        pct = round(len(truncated_text) / len(text) * 100)
        warnings.append(
            f"PDF text was truncated from {len(text):,} to {_MAX_TEXT_CHARS:,} characters "
            f"({pct}% of full text). Parameters deep in the datasheet may be missed."
        )
        logger.warning(
            "PDF text truncated: %d → %d chars (%d%%)",
            len(text), _MAX_TEXT_CHARS, pct,
        )

    response = client.chat.completions.create(
        model=model,
        response_format={"type": "json_object"},
        temperature=0.0,
        messages=[
            {"role": "system", "content": _build_system_prompt()},
            {
                "role": "user",
                "content": (
                    "Extract all component parameters from the following datasheet text:\n\n"
                    + truncated_text
                ),
            },
        ],
    )

    raw_json = response.choices[0].message.content
    logger.info("Raw LLM response (first 2000 chars): %s", raw_json[:2000] if raw_json else "<empty>")

    # Parse the raw string first so we can give a clear error on bad JSON
    try:
        parsed = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM returned non-JSON content: {exc}") from exc

    logger.info(
        "Parsed JSON keys: %s",
        list(parsed.keys()) if isinstance(parsed, dict) else f"type={type(parsed).__name__}",
    )

    # --- Try clean validation first ---
    try:
        result = ComponentExtractionResult.model_validate(parsed)
        components = result.components
        # Enrich any components that have missing fields we can fill from text
        enriched = []
        for comp in components:
            d = comp.model_dump()
            d = _enrich_from_text(d, text)
            try:
                enriched.append(ComponentData.model_validate(d))
            except ValidationError:
                enriched.append(comp)
        return enriched, warnings
    except ValidationError as ve:
        logger.warning("ComponentExtractionResult validation failed: %s", ve)

    # --- Salvage: try to find component data in whatever the LLM returned ---
    components_list = _find_components_in_parsed(parsed)

    if not components_list and isinstance(parsed, dict):
        # Last resort: treat the entire response as a single flat component
        components_list = _salvage_flat_response(parsed, text)
        if components_list:
            logger.info("Salvage: recovered flat component from non-standard LLM response")

    logger.info("Salvage: found %d items to try", len(components_list))
    validated = []
    for i, item in enumerate(components_list):
        # Normalize keys in case LLM used different names
        if isinstance(item, dict):
            item = _normalize_keys(item) if not item.get("Part_Number") else item
            item = _enrich_from_text(item, text)
        try:
            validated.append(ComponentData.model_validate(item))
        except ValidationError as item_ve:
            logger.warning(
                "Row %d validation failed: %s — data: %s",
                i, item_ve, json.dumps(item)[:500],
            )

    if not validated and components_list:
        warnings.append(
            "LLM returned component data but it could not be validated. "
            "Try uploading again or use a more capable model."
        )

    return validated, warnings


# ---------------------------------------------------------------------------
# Chunked extraction helpers
# ---------------------------------------------------------------------------

def _chunk_text(
    text: str,
    chunk_size: int = _MAX_CHUNK_CHARS,
    overlap: int = _CHUNK_OVERLAP,
    max_chunks: int = _MAX_CHUNKS,
) -> List[str]:
    """Split *text* into overlapping chunks bounded by *max_chunks*.

    Returns a list of strings.  If the full text fits in one chunk the
    original string is returned as a single-element list (fast path).
    """
    if len(text) <= chunk_size:
        return [text]

    stride = chunk_size - overlap
    chunks: List[str] = []
    start = 0
    while start < len(text):
        chunks.append(text[start: start + chunk_size])
        start += stride

    if len(chunks) > max_chunks:
        logger.warning(
            "Document produced %d chunks; capping at %d. "
            "Last chunk covers remaining %d chars.",
            len(chunks), max_chunks, len(text) - (max_chunks - 1) * stride,
        )
        # Keep first (max_chunks-1) normal chunks, then one oversized tail chunk
        tail_start = (max_chunks - 1) * stride
        chunks = chunks[: max_chunks - 1] + [text[tail_start:]]

    return chunks


def _merge_component_results(
    chunk_results: List[Tuple[List[ComponentData], List[str]]],
) -> Tuple[List[ComponentData], List[str]]:
    """Merge ComponentData lists from multiple chunks.

    Deduplication key: ``Part_Number.lower()``.
    Merge policy: first non-None value per field wins (from earlier chunks).
    Warning strings are deduplicated while preserving first-seen order.
    """
    seen_parts: Dict[str, ComponentData] = {}  # key → merged ComponentData
    order: List[str] = []
    seen_warnings: Dict[str, None] = {}  # ordered set via dict

    for components, warnings in chunk_results:
        for comp in components:
            key = comp.Part_Number.lower()
            if key not in seen_parts:
                seen_parts[key] = comp
                order.append(key)
            else:
                # Fill null fields from the later chunk
                existing = seen_parts[key].model_dump()
                incoming = comp.model_dump()
                for field, val in incoming.items():
                    if existing.get(field) is None and val is not None:
                        existing[field] = val
                seen_parts[key] = ComponentData.model_validate(existing)

        for w in warnings:
            if w not in seen_warnings:
                seen_warnings[w] = None

    merged_components = [seen_parts[k] for k in order]
    merged_warnings = list(seen_warnings.keys())
    return merged_components, merged_warnings


def extract_components_from_text_chunked(
    text: str,
) -> Tuple[List[ComponentData], List[str]]:
    """Extract components from arbitrarily long text using overlapping chunks.

    Fast path: if the text fits in a single chunk, delegates directly to
    ``extract_components_from_text`` to avoid overhead.

    Args:
        text: Full text extracted from the PDF datasheet.

    Returns:
        Tuple of (list of validated ComponentData instances, list of warning strings).

    Raises:
        RuntimeError: If INTERNAL_API_KEY is not configured.
    """
    if len(text) <= _MAX_CHUNK_CHARS:
        return extract_components_from_text(text)

    chunks = _chunk_text(text, _MAX_CHUNK_CHARS, _CHUNK_OVERLAP, _MAX_CHUNKS)
    all_warnings: List[str] = []

    if len(chunks) >= _MAX_CHUNKS:
        all_warnings.append(
            f"Document exceeded the {_MAX_CHUNKS}-chunk cap "
            f"({len(text):,} chars total). "
            "Parameters in the final section of the datasheet may be missed."
        )

    chunk_results: List[Tuple[List[ComponentData], List[str]]] = []
    for idx, chunk in enumerate(chunks):
        logger.info("Processing chunk %d/%d (%d chars)", idx + 1, len(chunks), len(chunk))
        try:
            result = extract_components_from_text(chunk)
            chunk_results.append(result)
        except RuntimeError:
            raise  # missing API key — abort immediately
        except Exception as exc:  # noqa: BLE001
            logger.warning("Chunk %d extraction failed: %s", idx + 1, exc)

    merged_rows, merged_warnings = _merge_component_results(chunk_results)
    return merged_rows, all_warnings + merged_warnings
