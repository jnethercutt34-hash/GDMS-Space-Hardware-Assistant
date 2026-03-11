"""AI-assisted channel parameter extraction from datasheets.

Uses the same OpenAI-compatible client pattern as other extractors.
"""
import json
import logging

from pydantic import ValidationError

from models.com_channel import ChannelModel, ChannelExtractionResult
from services.ai_client import get_client, get_model

logger = logging.getLogger(__name__)

_MAX_TEXT_CHARS = 14_000


def _build_system_prompt() -> str:
    schema = ChannelExtractionResult.model_json_schema()
    return f"""\
You are a high-speed serial link channel parameter extraction engine for aerospace hardware engineers.

Given datasheet/stackup text, extract channel segment parameters for COM analysis:
- PCB trace segments (length, impedance, loss per inch, dielectric properties)
- Connectors, vias, cables, packages — each as a ChannelSegment
- TX parameters: swing, de-emphasis/pre-cursor taps
- RX parameters: CTLE peaking, DFE taps
- Data rate, modulation (NRZ or PAM4)

You MUST return a JSON object conforming to this schema:

{json.dumps(schema, indent=2)}

Rules:
- Use reasonable defaults for any parameter not explicitly stated in the text.
- Set data_rate_gbps and modulation based on the interface type described.
- If a field cannot be determined, use a sensible default — do NOT leave required fields empty.
- Return ONLY the JSON object. No prose, no code fences."""


def extract_channel_from_text(text: str, channel_name: str = "Extracted Channel") -> ChannelModel:
    """Send extracted PDF text to the LLM and return a validated ChannelModel."""
    client = get_client()
    model = get_model()

    # Warn if text is truncated
    truncated_text = text[:_MAX_TEXT_CHARS]
    if len(text) > _MAX_TEXT_CHARS:
        pct = round(len(truncated_text) / len(text) * 100)
        logger.warning(
            "COM extractor: PDF text truncated %d → %d chars (%d%% of full text). "
            "Channel parameters deep in the datasheet may be missed.",
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
                    f"Extract channel parameters for '{channel_name}' from:\n\n"
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

    try:
        result = ChannelExtractionResult.model_validate(parsed)
        return result.channel
    except ValidationError:
        pass

    try:
        return ChannelModel.model_validate(parsed)
    except ValidationError:
        if "channel" in parsed and isinstance(parsed["channel"], dict):
            return ChannelModel.model_validate(parsed["channel"])
        raise ValueError("LLM response does not match ChannelModel schema")
