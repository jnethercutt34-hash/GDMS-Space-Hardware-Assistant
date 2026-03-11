"""Router for the PCB Stackup Designer."""
import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from models.stackup import Stackup
from services.stackup_engine import (
    analyze_architecture,
    delete_stackup,
    estimate_differential_impedance,
    estimate_impedance_microstrip,
    estimate_impedance_stripline,
    get_available_templates,
    get_stackup,
    get_template,
    list_stackups,
    save_stackup,
)
from services.block_diagram_store import get_by_id as get_diagram_by_id

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class AnalyzeRequest(BaseModel):
    diagram_id: Optional[str] = None
    interfaces: List[str] = Field(default_factory=list)


class ImpedanceCalcRequest(BaseModel):
    trace_width_mil: float = 5.0
    dielectric_height_mil: float = 4.0
    dk: float = 4.2
    copper_oz: float = 1.0
    trace_spacing_mil: float = 5.0
    calc_type: str = Field(default="microstrip", description="'microstrip' or 'stripline'")


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

@router.get("/stackup/templates")
async def templates():
    """List available stackup templates."""
    return {"templates": get_available_templates()}


@router.get("/stackup/template/{layer_count}")
async def template_detail(layer_count: int):
    """Get a full stackup template by layer count."""
    tpl = get_template(layer_count)
    if not tpl:
        raise HTTPException(404, f"No template for {layer_count} layers.")
    return tpl


# ---------------------------------------------------------------------------
# Architecture analysis
# ---------------------------------------------------------------------------

@router.post("/stackup/analyze")
async def analyze(req: AnalyzeRequest):
    """Analyze architecture and suggest stackup parameters."""
    diagram_data = None
    if req.diagram_id:
        diagram_data = get_diagram_by_id(req.diagram_id)
        if not diagram_data:
            raise HTTPException(404, f"Diagram '{req.diagram_id}' not found.")

    result = analyze_architecture(diagram_data, req.interfaces)
    return result.model_dump()


# ---------------------------------------------------------------------------
# Impedance calculator
# ---------------------------------------------------------------------------

@router.post("/stackup/impedance")
async def impedance_calc(req: ImpedanceCalcRequest):
    """Calculate impedance for given geometry."""
    if req.calc_type == "stripline":
        se = estimate_impedance_stripline(
            req.trace_width_mil, req.dielectric_height_mil, req.dk, req.copper_oz)
    else:
        se = estimate_impedance_microstrip(
            req.trace_width_mil, req.dielectric_height_mil, req.dk, req.copper_oz)

    diff = estimate_differential_impedance(
        se, req.trace_spacing_mil, req.dielectric_height_mil)

    return {
        "calc_type": req.calc_type,
        "single_ended_ohms": se,
        "differential_ohms": diff,
        "trace_width_mil": req.trace_width_mil,
        "dielectric_height_mil": req.dielectric_height_mil,
        "dk": req.dk,
        "trace_spacing_mil": req.trace_spacing_mil,
    }


# ---------------------------------------------------------------------------
# CRUD — save / load stackups
# ---------------------------------------------------------------------------

@router.get("/stackups")
async def list_all_stackups():
    """List saved stackups."""
    items = list_stackups()
    return [
        {
            "id": s.get("id"),
            "name": s.get("name", "Untitled"),
            "layer_count": s.get("layer_count", 0),
            "created_at": s.get("created_at"),
            "updated_at": s.get("updated_at"),
        }
        for s in items
    ]


@router.get("/stackups/{stackup_id}")
async def get_one_stackup(stackup_id: str):
    """Fetch a saved stackup."""
    s = get_stackup(stackup_id)
    if not s:
        raise HTTPException(404, "Stackup not found.")
    return s


@router.post("/stackups")
async def create_or_update_stackup(stackup: Stackup):
    """Save (create or update) a stackup."""
    data = stackup.model_dump()
    return save_stackup(data)


@router.delete("/stackups/{stackup_id}")
async def remove_stackup(stackup_id: str):
    """Delete a saved stackup."""
    if not delete_stackup(stackup_id):
        raise HTTPException(404, "Stackup not found.")
    return {"detail": "Deleted."}


# ---------------------------------------------------------------------------
# Export — stackup documentation
# ---------------------------------------------------------------------------

@router.post("/stackup/export/{stackup_id}")
async def export_stackup(stackup_id: str, format: str = "markdown"):
    """Export stackup as Markdown documentation or fabrication notes."""
    s = get_stackup(stackup_id)
    if not s:
        raise HTTPException(404, "Stackup not found.")

    md = _stackup_to_markdown(s)
    return PlainTextResponse(
        content=md,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="stackup_{stackup_id}.md"'},
    )


def _stackup_to_markdown(s: dict) -> str:
    lines = [
        f"# PCB Stackup: {s.get('name', 'Untitled')}",
        "",
        f"**Layer Count:** {s.get('layer_count', 0)}",
        f"**Total Thickness:** {s.get('total_thickness_mil', 'TBD')} mil",
        f"**Material:** {s.get('board_material', 'FR-4')}",
        "",
        "## Layer Table",
        "",
        "| # | Layer Name | Type | Cu Weight | Diel. Thickness | Material | Notes |",
        "|---|-----------|------|-----------|----------------|----------|-------|",
    ]

    for layer in s.get("layers", []):
        lines.append(
            f"| {layer.get('order', '')} "
            f"| {layer.get('name', '')} "
            f"| {layer.get('layer_type', '')} "
            f"| {layer.get('copper_weight', '1 oz')} "
            f"| {layer.get('dielectric_thickness_mil', '')} mil "
            f"| {layer.get('dielectric_material', 'FR-4')} "
            f"| {layer.get('notes', '')} |"
        )

    # Impedance targets
    targets = s.get("impedance_targets", [])
    if targets:
        lines.extend([
            "",
            "## Impedance Targets",
            "",
            "| Interface | Type | Target (Ω) | Tolerance |",
            "|-----------|------|-----------|-----------|",
        ])
        for t in targets:
            lines.append(
                f"| {t.get('interface', '')} "
                f"| {t.get('impedance_type', '')} "
                f"| {t.get('target_ohms', '')} "
                f"| ±{t.get('tolerance_pct', 10)}% |"
            )

    lines.extend([
        "",
        "---",
        f"_Generated by GDMS Space Hardware Assistant_",
    ])
    return "\n".join(lines)
