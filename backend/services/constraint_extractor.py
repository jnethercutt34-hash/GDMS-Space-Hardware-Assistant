"""AI extraction service for SI/PI constraints from datasheets.

Extracts impedance, timing, voltage, spacing, and other design constraints.
"""
import json
import logging
from typing import List, Tuple

from pydantic import ValidationError

from models.constraint import ConstraintRule, ConstraintExtractionResult
from services.ai_client import get_client, get_model

logger = logging.getLogger(__name__)

# Maximum characters of PDF text sent to the model.
_MAX_TEXT_CHARS = 14_000


def _build_system_prompt() -> str:
    """Embed the ConstraintExtractionResult JSON schema directly in the prompt."""
    schema = ConstraintExtractionResult.model_json_schema()
    return f"""\
You are a precision SI/PI constraint extraction engine for aerospace hardware engineers.

Your task is to extract all signal integrity (SI) and power integrity (PI) design \
constraints from the given datasheet text and return them as structured JSON.

Target constraint types (extract ALL that appear):
- **Impedance**: characteristic impedance, differential impedance for signal classes
- **Propagation_Delay**: signal propagation delay budgets, max/min values
- **Skew**: intra-pair skew, inter-signal skew, clock-to-data skew
- **Rise_Time / Fall_Time**: edge rate specifications
- **Voltage_Level**: logic high/low thresholds, VCCIO levels, reference voltages
- **Spacing**: minimum clearance/spacing between signal classes
- **Max_Length**: maximum trace length constraints
- **Differential_Pair**: differential pair requirements (impedance, spacing, coupling)
- **Overshoot / Undershoot**: voltage overshoot/undershoot limits
- **Crosstalk**: crosstalk budget or victim/aggressor spacing rules
- **Other**: any SI/PI constraint that doesn't fit the above categories

You MUST return a JSON object that conforms exactly to this JSON Schema:

{json.dumps(schema, indent=2)}

Extraction rules:
- Group constraints by Signal_Class (e.g. 'DDR4_DQ', 'LVDS_CLK', 'PCIE_TX').
- Include units in Min/Typ/Max fields where possible (e.g. '100 Ω', '0.5 ns').
- If a constraint only specifies a single value, put it in Typ. Use Min/Max for ranges.
- Source_Page should reference the page or section where the value was found.
- If a field cannot be determined, set it to null — do NOT guess or fabricate values.
- Return ONLY the JSON object. No prose, no markdown code fences, no commentary."""


def extract_constraints_from_text(text: str) -> Tuple[List[ConstraintRule], List[str]]:
    """Send extracted PDF text to the LLM and return validated constraint rules.

    Args:
        text: Full text extracted from the PDF datasheet.

    Returns:
        Tuple of (list of validated ConstraintRule instances, list of warning strings).

    Raises:
        RuntimeError: If INTERNAL_API_KEY is not configured.
        Exception:    Propagated from the OpenAI client for network/API errors.
    """
    client = get_client()
    model = get_model()
    warnings = []

    truncated_text = text[:_MAX_TEXT_CHARS]
    if len(text) > _MAX_TEXT_CHARS:
        pct = round(len(truncated_text) / len(text) * 100)
        warnings.append(
            f"PDF text was truncated from {len(text):,} to {_MAX_TEXT_CHARS:,} characters "
            f"({pct}% of full text). Constraints deep in the datasheet may be missed."
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
                    "Extract all SI/PI design constraints from the following datasheet text:\n\n"
                    + truncated_text
                ),
            },
        ],
    )

    raw_json = response.choices[0].message.content

    try:
        parsed = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM returned non-JSON content: {exc}") from exc

    # Validate the full envelope against the Pydantic wrapper model
    try:
        result = ConstraintExtractionResult.model_validate(parsed)
    except ValidationError:
        # Try to salvage a bare list
        constraints_list = parsed.get("constraints", parsed if isinstance(parsed, list) else [])
        validated = []
        for item in constraints_list:
            try:
                validated.append(ConstraintRule.model_validate(item))
            except ValidationError:
                pass
        return validated, warnings

    return result.constraints, warnings
