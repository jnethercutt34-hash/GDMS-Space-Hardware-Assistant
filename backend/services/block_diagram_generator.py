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


def _salvage_diagram(parsed: dict) -> dict:
    """Normalize common LLM deviations so Pydantic validation succeeds."""
    from uuid import uuid4

    # --- Unwrap nested diagram key ---
    if "diagram" in parsed and isinstance(parsed["diagram"], dict):
        parsed = parsed["diagram"]

    # --- Ensure required top-level fields ---
    if "name" not in parsed:
        parsed["name"] = parsed.get("title", parsed.get("diagram_name", "Untitled"))
    if "blocks" not in parsed:
        parsed["blocks"] = parsed.get("nodes", parsed.get("components", []))
    if "connections" not in parsed:
        parsed["connections"] = parsed.get("edges", parsed.get("links", parsed.get("wires", [])))

    _VALID_CATEGORIES = {"FPGA", "Memory", "Power", "Connector", "Processor", "Optics", "Custom"}
    _VALID_DIRECTIONS = {"IN", "OUT", "BIDIR"}

    # --- Map: block label → block id (for connection fixup) ---
    block_label_to_id = {}

    for blk in parsed.get("blocks", []):
        if not isinstance(blk, dict):
            continue
        # Ensure block id
        if "id" not in blk:
            blk["id"] = uuid4().hex[:8]

        # Normalize category
        cat = str(blk.get("category", "Custom")).strip()
        cat_upper = cat.upper()
        matched = next((v for v in _VALID_CATEGORIES if v.upper() == cat_upper), None)
        blk["category"] = matched or "Custom"

        # Normalize ports
        ports = blk.get("ports", [])
        if not isinstance(ports, list):
            ports = []
        for port in ports:
            if not isinstance(port, dict):
                continue
            if "id" not in port:
                port["id"] = uuid4().hex[:8]
            if "label" not in port:
                port["label"] = port.get("name", port.get("signal", "port"))
            d = str(port.get("direction", "BIDIR")).upper()
            port["direction"] = d if d in _VALID_DIRECTIONS else "BIDIR"
            if "bus_width" in port:
                try:
                    port["bus_width"] = int(port["bus_width"])
                except (ValueError, TypeError):
                    port["bus_width"] = 1
        blk["ports"] = ports

        # Track label → id for connection fixup
        block_label_to_id[blk.get("label", "").lower()] = blk["id"]
        if blk.get("part_number"):
            block_label_to_id[blk["part_number"].lower()] = blk["id"]

    # --- Build port lookup: block_id → first IN port id, first OUT port id ---
    block_ports = {}  # block_id → {"in": port_id, "out": port_id, "any": port_id}
    for blk in parsed.get("blocks", []):
        if not isinstance(blk, dict):
            continue
        bid = blk["id"]
        info: dict = {}
        for port in blk.get("ports", []):
            if not isinstance(port, dict):
                continue
            pid = port.get("id", "")
            d = port.get("direction", "BIDIR")
            if "any" not in info:
                info["any"] = pid
            if d == "IN" and "in" not in info:
                info["in"] = pid
            elif d == "OUT" and "out" not in info:
                info["out"] = pid
            elif d == "BIDIR" and "bidir" not in info:
                info["bidir"] = pid
        block_ports[bid] = info

    def _pick_port(block_id: str, role: str) -> str:
        """Pick a port id for a block; role is 'source' or 'target'."""
        info = block_ports.get(block_id, {})
        if role == "source":
            return info.get("out") or info.get("bidir") or info.get("any") or ""
        return info.get("in") or info.get("bidir") or info.get("any") or ""

    # --- Fix connections ---
    for conn in parsed.get("connections", []):
        if not isinstance(conn, dict):
            continue
        if "id" not in conn:
            conn["id"] = uuid4().hex[:8]

        # Resolve block references — LLMs sometimes use label/name instead of id
        for field, alt_fields in [
            ("source_block_id", ["source_id", "source", "from", "from_block", "from_block_id"]),
            ("target_block_id", ["target_id", "target", "to", "to_block", "to_block_id"]),
        ]:
            if field not in conn or conn[field] is None:
                for alt in alt_fields:
                    if alt in conn and conn[alt]:
                        conn[field] = conn.pop(alt)
                        break
            # If the value looks like a label, resolve to id
            val = str(conn.get(field, "")).lower()
            if val in block_label_to_id:
                conn[field] = block_label_to_id[val]

        # Resolve port references — fill missing with best-guess
        for port_field, block_field, alt_fields, role in [
            ("source_port_id", "source_block_id", ["source_port", "from_port", "from_port_id"], "source"),
            ("target_port_id", "target_block_id", ["target_port", "to_port", "to_port_id"], "target"),
        ]:
            if port_field not in conn or not conn[port_field]:
                for alt in alt_fields:
                    if alt in conn and conn[alt]:
                        conn[port_field] = conn.pop(alt)
                        break
            if not conn.get(port_field):
                conn[port_field] = _pick_port(conn.get(block_field, ""), role)

        # Normalize signal_name from alternatives
        if "signal_name" not in conn or not conn["signal_name"]:
            conn["signal_name"] = conn.get("name") or conn.get("signal") or conn.get("label")

    return parsed


def _parse_response(response) -> BlockDiagram:
    raw_json = response.choices[0].message.content
    try:
        parsed = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM returned non-JSON content: {exc}") from exc

    # Try full envelope first (strict)
    try:
        result = BlockDiagramGenerationResult.model_validate(parsed)
        return result.diagram
    except ValidationError:
        pass

    # Try bare diagram (strict)
    try:
        return BlockDiagram.model_validate(parsed)
    except ValidationError:
        pass

    # Salvage: normalize common LLM deviations, then retry
    try:
        salvaged = _salvage_diagram(parsed)
        logger.info("BlockDiagram strict parse failed; attempting salvage normalization")
        return BlockDiagram.model_validate(salvaged)
    except (ValidationError, Exception) as exc:
        logger.error("BlockDiagram salvage failed: %s", exc)
        logger.debug("Raw LLM JSON: %s", raw_json[:2000])
        raise ValueError(
            f"LLM response does not match BlockDiagram schema after salvage: {exc}"
        ) from exc
