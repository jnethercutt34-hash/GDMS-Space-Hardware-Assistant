"""AI auto-generation of block diagrams from part data or PDF text."""
import json
import logging
from typing import List

from pydantic import ValidationError

from models.block_diagram import BlockDiagram, BlockDiagramGenerationResult
from services.ai_client import get_client, get_model

logger = logging.getLogger(__name__)

_MAX_TEXT_CHARS = 14_000


def _build_system_prompt() -> str:
    schema = BlockDiagramGenerationResult.model_json_schema()
    return f"""\
You are a system-level block diagram generator for aerospace hardware engineers.

Given a list of component parts (or architecture text), generate a structured block diagram JSON
showing major ICs, their ports, and inferred connections based on common interface pairings
(e.g. FPGA ↔ DDR4, PMU → voltage rails, Processor ↔ PCIe peripherals).

Rules:
- Create a Block for each major IC or subsystem.
- Assign appropriate categories: FPGA, Memory, Power, Connector, Processor, Optics, or Custom.
- Create Ports on each block with correct direction (IN/OUT/BIDIR), bus_width, and interface_type.
- Create Connections between compatible ports with descriptive signal_name values.
- Space blocks with reasonable x/y positions (grid of ~200px spacing).
- Each id field must be a unique short string (8 chars hex).
- Set the diagram name and description appropriately.

You MUST return a JSON object conforming to this schema:

{json.dumps(schema, indent=2)}

Return ONLY the JSON object. No prose, no markdown code fences."""


def generate_from_parts(parts: List[dict], diagram_name: str = "Auto-generated Diagram") -> BlockDiagram:
    """Generate a block diagram from a list of Part Library entries."""
    client = get_client()
    model = get_model()

    parts_text = json.dumps(parts, indent=2)[:_MAX_TEXT_CHARS]

    response = client.chat.completions.create(
        model=model,
        response_format={"type": "json_object"},
        temperature=0.2,
        messages=[
            {"role": "system", "content": _build_system_prompt()},
            {
                "role": "user",
                "content": (
                    f"Generate a block diagram named '{diagram_name}' for these components:\n\n"
                    + parts_text
                ),
            },
        ],
    )

    return _parse_response(response)


def generate_from_text(text: str, diagram_name: str = "Auto-generated Diagram") -> BlockDiagram:
    """Generate a block diagram from extracted PDF/architecture text."""
    client = get_client()
    model = get_model()

    truncated_text = text[:_MAX_TEXT_CHARS]
    if len(text) > _MAX_TEXT_CHARS:
        pct = round(len(truncated_text) / len(text) * 100)
        logger.warning(
            "PDF text truncated: %d → %d chars (%d%%)",
            len(text), _MAX_TEXT_CHARS, pct,
        )

    response = client.chat.completions.create(
        model=model,
        response_format={"type": "json_object"},
        temperature=0.2,
        messages=[
            {"role": "system", "content": _build_system_prompt()},
            {
                "role": "user",
                "content": (
                    f"Generate a block diagram named '{diagram_name}' from this architecture description:\n\n"
                    + truncated_text
                ),
            },
        ],
    )

    return _parse_response(response)


def _parse_response(response) -> BlockDiagram:
    raw_json = response.choices[0].message.content
    try:
        parsed = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM returned non-JSON content: {exc}") from exc

    # Try full envelope first
    try:
        result = BlockDiagramGenerationResult.model_validate(parsed)
        return result.diagram
    except ValidationError:
        pass

    # Try bare diagram
    try:
        return BlockDiagram.model_validate(parsed)
    except ValidationError:
        # Try nested under "diagram" key
        if "diagram" in parsed and isinstance(parsed["diagram"], dict):
            return BlockDiagram.model_validate(parsed["diagram"])
        raise ValueError("LLM response does not match BlockDiagram schema")
