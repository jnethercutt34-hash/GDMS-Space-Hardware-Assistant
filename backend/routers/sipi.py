"""Router for the SI/PI Design Guide.

Serves the interface knowledge base, generates design rules,
calculates loss budgets, provides AI advisory, and exports
constraint scripts.
"""
import logging
import os
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from models.sipi_guide import (
    AISiPiAnswer,
    AISiPiQuestion,
    DesignRule,
    InterfaceSpec,
    LossBudgetResult,
)
from services.sipi_knowledge_base import (
    get_all_interfaces,
    get_interface,
    get_rules_for_interfaces,
)
from services.loss_budget_calculator import calculate_loss_budget
from services.xpedition_ces_export import generate_ces_script

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------

class RulesRequest(BaseModel):
    interfaces: List[str] = Field(description="List of InterfaceId values")
    categories: List[str] = Field(default_factory=list, description="Filter by category (optional)")


class LossBudgetRequest(BaseModel):
    interface: str
    trace_length_inches: float = 6.0
    num_vias: int = 4
    num_connectors: int = 0
    include_package: bool = True
    material: str = "fr4"
    custom_max_loss_db: Optional[float] = None


class ExportRulesRequest(BaseModel):
    rules: List[dict] = Field(description="Design rules to export")
    format: str = Field(default="ces", description="'ces' for Xpedition CES script, 'markdown' for doc")


# ---------------------------------------------------------------------------
# GET /api/sipi/interfaces — list all supported interfaces
# ---------------------------------------------------------------------------

@router.get("/sipi/interfaces")
async def list_interfaces():
    """Return all supported interfaces with metadata (no rules)."""
    interfaces = get_all_interfaces()
    return {"interfaces": [i.model_dump() for i in interfaces]}


# ---------------------------------------------------------------------------
# GET /api/sipi/interface/{iface_id} — single interface with full rules
# ---------------------------------------------------------------------------

@router.get("/sipi/interface/{iface_id}")
async def get_interface_detail(iface_id: str):
    """Return full spec + rules for one interface."""
    spec = get_interface(iface_id)
    if not spec:
        raise HTTPException(404, f"Interface '{iface_id}' not found.")
    return spec.model_dump()


# ---------------------------------------------------------------------------
# POST /api/sipi/rules — get combined rules for selected interfaces
# ---------------------------------------------------------------------------

@router.post("/sipi/rules")
async def generate_rules(req: RulesRequest):
    """Return design rules for the selected interfaces, optionally filtered."""
    rules = get_rules_for_interfaces(req.interfaces)

    if req.categories:
        cat_set = set(req.categories)
        rules = [r for r in rules if r.category.value in cat_set]

    return {
        "count": len(rules),
        "rules": [r.model_dump() for r in rules],
    }


# ---------------------------------------------------------------------------
# POST /api/sipi/loss-budget — calculate channel loss budget
# ---------------------------------------------------------------------------

@router.post("/sipi/loss-budget")
async def compute_loss_budget(req: LossBudgetRequest):
    """Build a COM-informed loss budget for a high-speed channel."""
    result = calculate_loss_budget(
        interface=req.interface,
        trace_length_inches=req.trace_length_inches,
        num_vias=req.num_vias,
        num_connectors=req.num_connectors,
        include_package=req.include_package,
        material=req.material,
        custom_max_loss_db=req.custom_max_loss_db,
    )
    return result.model_dump()


# ---------------------------------------------------------------------------
# POST /api/sipi/advisor — AI SI/PI advisory
# ---------------------------------------------------------------------------

@router.post("/sipi/advisor")
async def sipi_advisor(req: AISiPiQuestion):
    """Ask the AI advisor an SI/PI design question with context."""
    api_key = os.getenv("OPENAI_API_KEY", "")

    # Gather relevant rules as context
    context_rules = get_rules_for_interfaces(req.interfaces) if req.interfaces else []
    rules_text = "\n".join(
        f"- [{r.rule_id}] {r.interface} / {r.category.value}: "
        f"{r.parameter} = {r.target} {r.tolerance} {r.unit} — {r.rationale}"
        for r in context_rules
    )

    system_prompt = (
        "You are an expert signal-integrity and power-integrity engineer "
        "specializing in aerospace and defense PCB design. You give practical, "
        "spec-referenced advice. When possible, cite specific standards "
        "(JEDEC, PCI-SIG, IEEE, ECSS, MIL-STD). Keep answers concise and actionable.\n\n"
        "The engineer's board uses these interfaces and rules:\n"
        f"{rules_text}\n"
    )
    if req.board_details:
        system_prompt += f"\nBoard details: {req.board_details}\n"

    if not api_key:
        # Offline fallback — provide rule-based answer
        answer = _offline_advisor(req.question, context_rules)
        return AISiPiAnswer(
            answer=answer,
            referenced_rules=[r.rule_id for r in context_rules[:10]],
        ).model_dump()

    try:
        from services.ai_client import get_openai_client
        client = get_openai_client()
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": req.question},
            ],
            max_tokens=1000,
            temperature=0.3,
        )
        ai_answer = response.choices[0].message.content

        # Find which rules the AI referenced
        referenced = [
            r.rule_id for r in context_rules
            if r.rule_id in ai_answer or r.parameter.lower() in ai_answer.lower()
        ]

        return AISiPiAnswer(
            answer=ai_answer,
            referenced_rules=referenced,
        ).model_dump()

    except Exception as exc:
        logger.warning("AI advisor failed, using offline fallback: %s", exc)
        answer = _offline_advisor(req.question, context_rules)
        return AISiPiAnswer(
            answer=f"(AI unavailable — rule-based response)\n\n{answer}",
            referenced_rules=[r.rule_id for r in context_rules[:10]],
        ).model_dump()


def _offline_advisor(question: str, rules: List[DesignRule]) -> str:
    """Simple keyword-based offline advisor."""
    q = question.lower()
    relevant = []

    keywords_map = {
        "impedance": ["impedance", "ohm", "ω"],
        "length": ["length", "match", "skew"],
        "spacing": ["spacing", "crosstalk", "clearance"],
        "via": ["via", "stub", "back-drill", "backdrill"],
        "termination": ["termination", "terminator", "odt", "pull-up"],
        "decoupling": ["decoupling", "decap", "bypass", "capacitor"],
        "material": ["material", "laminate", "fr4", "fr-4", "megtron", "loss"],
    }

    for rule in rules:
        for topic, kws in keywords_map.items():
            if any(kw in q for kw in kws):
                if any(kw in rule.parameter.lower() or kw in rule.rationale.lower()
                       for kw in kws):
                    relevant.append(rule)
                    break

    if not relevant:
        relevant = rules[:5]

    lines = ["Based on the design rules for your selected interfaces:\n"]
    for r in relevant[:8]:
        lines.append(
            f"**{r.rule_id}** ({r.interface} — {r.category.value}): "
            f"{r.parameter} → {r.target} {r.tolerance} {r.unit}\n"
            f"  _{r.rationale}_\n"
            f"  Source: {r.spec_source} | Severity: {r.severity}\n"
        )

    lines.append(
        "\n_For more detailed analysis, configure an OpenAI API key to "
        "enable the AI advisor._"
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# POST /api/sipi/export — export rules as CES script or markdown
# ---------------------------------------------------------------------------

@router.post("/sipi/export")
async def export_rules(req: ExportRulesRequest):
    """Export design rules as Xpedition CES script or Markdown document."""
    if not req.rules:
        raise HTTPException(400, "No rules provided.")

    if req.format == "markdown":
        md = _rules_to_markdown(req.rules)
        return PlainTextResponse(
            content=md,
            media_type="text/markdown",
            headers={"Content-Disposition": 'attachment; filename="sipi_design_rules.md"'},
        )

    # Default: CES script
    # Convert rules to constraint-like dicts for the existing CES exporter
    constraints = []
    for r in req.rules:
        constraints.append({
            "parameter": r.get("parameter", ""),
            "value": r.get("target", ""),
            "tolerance": r.get("tolerance", ""),
            "unit": r.get("unit", ""),
            "net_class": r.get("signal_group", "All"),
            "notes": f"{r.get('interface', '')} — {r.get('rationale', '')}",
        })

    script = generate_ces_script(constraints)
    return PlainTextResponse(
        content=script,
        media_type="text/x-python",
        headers={"Content-Disposition": 'attachment; filename="xpedition_sipi_rules.py"'},
    )


def _rules_to_markdown(rules: list) -> str:
    """Format rules into a printable Markdown document."""
    lines = [
        "# SI/PI Design Rules Report",
        "",
        f"Generated by GDMS Space Hardware Assistant",
        "",
        "| Rule ID | Interface | Category | Signal Group | Parameter | Target | Tol. | Unit | Severity |",
        "|---------|-----------|----------|-------------|-----------|--------|------|------|----------|",
    ]

    for r in rules:
        lines.append(
            f"| {r.get('rule_id','')} "
            f"| {r.get('interface','')} "
            f"| {r.get('category','')} "
            f"| {r.get('signal_group','')} "
            f"| {r.get('parameter','')} "
            f"| {r.get('target','')} "
            f"| {r.get('tolerance','')} "
            f"| {r.get('unit','')} "
            f"| {r.get('severity','')} |"
        )

    lines.append("")
    lines.append("---")
    lines.append("")

    # Group rationales
    lines.append("## Rule Rationales")
    lines.append("")
    for r in rules:
        if r.get("rationale"):
            lines.append(f"**{r.get('rule_id', '')}**: {r.get('rationale', '')}")
            if r.get("spec_source"):
                lines.append(f"  _Source: {r['spec_source']}_")
            lines.append("")

    return "\n".join(lines)
