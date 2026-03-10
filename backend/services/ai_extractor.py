"""AI extraction service — OpenAI-compatible, enterprise-ready.

Uses the standard `openai` Python package so the app can be pointed at any
OpenAI-compatible gateway (internal or public) via environment variables.
"""
import json
import os
from typing import List

from openai import OpenAI
from pydantic import ValidationError

from models.component import ComponentData, ComponentExtractionResult

# Maximum characters of PDF text sent to the model.
# Keeps token costs predictable and avoids context-window errors.
_MAX_TEXT_CHARS = 14_000


def _get_client() -> OpenAI:
    api_key = os.environ.get("INTERNAL_API_KEY")
    base_url = os.environ.get("INTERNAL_BASE_URL", "https://api.openai.com/v1")

    if not api_key:
        raise RuntimeError(
            "INTERNAL_API_KEY is not set. Add it to your .env file and restart the server."
        )

    return OpenAI(api_key=api_key, base_url=base_url)


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
- Return ONLY the JSON object. No prose, no markdown code fences, no commentary."""


def extract_components_from_text(text: str) -> List[ComponentData]:
    """Send extracted PDF text to the LLM and return a validated list of ComponentData.

    Args:
        text: Full text extracted from the PDF datasheet.

    Returns:
        List of validated ComponentData instances (may be empty if nothing parseable found).

    Raises:
        RuntimeError: If INTERNAL_API_KEY is not configured.
        Exception:    Propagated from the OpenAI client for network/API errors.
    """
    client = _get_client()
    model = os.environ.get("INTERNAL_MODEL_NAME", "gpt-4o-mini")

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
                    + text[:_MAX_TEXT_CHARS]
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
        return validated

    return result.components
