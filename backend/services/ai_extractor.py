"""AI extraction service — OpenAI-compatible, enterprise-ready.

Uses the standard `openai` Python package so the app can be pointed at any
OpenAI-compatible gateway (internal or public) via environment variables.
"""
import json
import logging
import os
from typing import List, Tuple

from pydantic import ValidationError

from models.component import ComponentData, ComponentExtractionResult
from services.ai_client import get_client, get_model

logger = logging.getLogger(__name__)

# Maximum characters of PDF text sent to the model.
# Keeps token costs predictable and avoids context-window errors.
_MAX_TEXT_CHARS = 14_000


def _build_system_prompt() -> str:
    """Embed the ComponentExtractionResult JSON schema directly in the prompt."""
    schema = ComponentExtractionResult.model_json_schema()
    return f"""You are a precision electronics data extraction engine for aerospace hardware engineers.

Your task is to extract component electrical and physical parameters from datasheet text and
return them as a single structured JSON object.

You MUST return a JSON object that conforms exactly to this JSON Schema:

{json.dumps(schema, indent=2)}

Extraction rules:
- Identify every distinct component variant listed in the datasheet.
- Include units in every value field where applicable (e.g. "3.3 V", "100 nF", "±5%", "125 °C/W").
- If a field cannot be found in the text, set it to null — do NOT guess or fabricate values.
- Part_Number and Manufacturer are required for every row; skip any component where these cannot be determined.
- For the Summary field, write ONE concise sentence describing what the component is and its primary aerospace/electronics use case. This is required for every row.
- For Operating_Temperature_Range: prefer the full min-to-max string with units (e.g. "-55 to +125 C"). If only a grade is stated (MIL, industrial, commercial), infer the standard range for that grade.
- For Radiation_TID: extract the Total Ionizing Dose rating exactly as printed, including units (e.g. "100 krad(Si)"). Only populate if explicitly stated; never infer from part suffix alone.
- For Radiation_SEL_Threshold: extract the Single Event Latchup LET threshold verbatim (e.g. "> 80 MeV·cm²/mg", "SEL immune"). Set to null if not stated.
- For Radiation_SEU_Rate: extract the SEU cross-section or upset rate from radiation characterisation tables if present (e.g. "4×10⁻¹⁴ cm²/bit"). Set to null if not stated.
- Return ONLY the JSON object. No prose, no markdown code fences, no commentary."""


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
    warnings = []

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

    # Parse the raw string first so we can give a clear error on bad JSON
    try:
        parsed = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM returned non-JSON content: {exc}") from exc

    # Validate the full envelope against the Pydantic wrapper model
    try:
        result = ComponentExtractionResult.model_validate(parsed)
    except ValidationError:
        # If the top-level wrapper fails, try to salvage a bare list
        components_list = parsed.get("components", parsed if isinstance(parsed, list) else [])
        validated = []
        for item in components_list:
            try:
                validated.append(ComponentData.model_validate(item))
            except ValidationError:
                pass  # Skip malformed rows rather than failing the whole request
        return validated, warnings

    return result.components, warnings
