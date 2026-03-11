"""AI-assisted heuristic DRC checks for Phase 7 — Schematic DRC.

Passes netlist subsets to an LLM for higher-level design-intent checks:
  - Interface protocol validation (I2C pull-ups, SPI CS, JTAG chain, DDR grouping)
  - Power sequencing (enable/PG chains)
  - Decoupling strategy (cap values/quantities appropriate for IC)
  - Cross-domain checks (signals crossing power domains without level shifters)
"""
import json
import logging
from typing import List, Optional

from pydantic import ValidationError

from models.schematic_drc import (
    AIViolationBatch,
    DRCViolation,
    Netlist,
    Severity,
    ViolationCategory,
)
from services.ai_client import get_client, get_model

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are an expert schematic design-rule-check (DRC) assistant for space / aerospace hardware.

You will be given a parsed netlist (components and their net connections). Your job is to find
higher-level design-intent issues that deterministic rules cannot catch. Focus on:

1. **Interface Protocol Validation**
   - I2C buses must have pull-up resistors on SDA and SCL
   - SPI buses need a separate CS line per slave device
   - JTAG chains must be complete (TDI→TDO daisy-chain, TCK/TMS to all)
   - DDR interfaces should have proper address/data bus grouping

2. **Power Sequencing**
   - If components have enable (EN) and power-good (PG/PGOOD) pins, verify
     sequencing chains are present (PG of one regulator → EN of next)

3. **Decoupling Strategy**
   - Check if decoupling cap count and values look reasonable for each IC
     (typically 100nF per power pin + bulk cap)

4. **Cross-Domain Checks**
   - Flag signals that appear to cross between different power domains
     (e.g. 3.3V domain to 1.8V domain) without a level shifter

Return ONLY valid JSON matching this schema:
{
  "violations": [
    {
      "rule_id": "AI-<category>-NNN",
      "severity": "Error" | "Warning" | "Info",
      "category": "Power" | "Decoupling" | "Termination" | "Interface" | "Connectivity" | "Naming",
      "message": "description of the issue",
      "affected_nets": ["net1", "net2"],
      "affected_components": ["U1", "R2"],
      "recommendation": "what to do about it",
      "ai_generated": true
    }
  ]
}

If no issues are found, return {"violations": []}.
Be precise. Only flag clear issues, not speculative ones.
"""


def _netlist_to_summary(netlist: Netlist) -> str:
    """Convert netlist to a concise text summary for the LLM prompt."""
    lines = []
    lines.append(f"=== NETLIST SUMMARY ===")
    lines.append(f"Components: {len(netlist.components)}")
    lines.append(f"Nets: {len(netlist.nets)}")
    lines.append(f"Power nets: {netlist.power_nets}")
    lines.append(f"Ground nets: {netlist.ground_nets}")
    lines.append("")

    lines.append("=== COMPONENTS ===")
    for comp in netlist.components[:100]:  # Cap at 100 for token limits
        pin_summary = ", ".join(
            f"{p.pin_name or p.pin_number}({p.pin_type.value})"
            for p in comp.pins[:30]
        )
        lines.append(f"{comp.ref_des} [{comp.part_number}] val={comp.value}: {pin_summary}")
    if len(netlist.components) > 100:
        lines.append(f"... and {len(netlist.components) - 100} more components")
    lines.append("")

    lines.append("=== NETS ===")
    for net in netlist.nets[:200]:  # Cap at 200
        pin_list = ", ".join(
            f"{p.ref_des}.{p.pin_name or p.pin_number}"
            for p in net.pins[:20]
        )
        extra = f" (+{len(net.pins) - 20} more)" if len(net.pins) > 20 else ""
        lines.append(f"{net.name}: {pin_list}{extra}")
    if len(netlist.nets) > 200:
        lines.append(f"... and {len(netlist.nets) - 200} more nets")

    return "\n".join(lines)


def run_ai_checks(netlist: Netlist) -> List[DRCViolation]:
    """Run AI-assisted DRC checks on the netlist.

    Returns a list of DRCViolation with ai_generated=True.
    Failures are logged but do not raise — AI checks are best-effort.
    """
    try:
        client = get_client()
    except RuntimeError as e:
        logger.warning("AI DRC skipped: %s", e)
        return []

    summary_text = _netlist_to_summary(netlist)
    model = get_model()

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": f"Analyze this netlist for design issues:\n\n{summary_text}"},
            ],
            temperature=0.2,
            max_tokens=4000,
            response_format={"type": "json_object"},
        )

        raw = response.choices[0].message.content or "{}"

        # Parse and validate
        batch = AIViolationBatch.model_validate_json(raw)

        # Ensure ai_generated flag
        for v in batch.violations:
            v.ai_generated = True

        return batch.violations

    except ValidationError as e:
        logger.warning("AI DRC response did not match schema: %s", e)
        return []
    except Exception as e:
        logger.warning("AI DRC failed: %s", e)
        return []
