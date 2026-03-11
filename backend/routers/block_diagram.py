"""Router for Phase 4 — Block Diagram Builder."""
import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from models.block_diagram import BlockDiagram
from services.block_diagram_store import list_all, get_by_id, create, update, delete
from services.block_diagram_generator import generate_from_parts, generate_from_text
from services.block_diagram_export import generate_netlist_csv, generate_netlist_script
from services.pdf_extractor import extract_text_from_pdf

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class GenerateFromPartsRequest(BaseModel):
    part_numbers: List[str]
    diagram_name: str = "Auto-generated Diagram"


class GenerateFromTextRequest(BaseModel):
    description: str
    diagram_name: str = "Auto-generated Diagram"


class GenerateFromPdfRequest(BaseModel):
    diagram_name: str = "Auto-generated Diagram"


# ---------------------------------------------------------------------------
# CRUD endpoints
# ---------------------------------------------------------------------------

@router.get("/diagrams")
async def list_diagrams():
    """List all saved diagrams (summary only: id, name, block count)."""
    diagrams = list_all()
    return [
        {
            "id": d["id"],
            "name": d.get("name", "Untitled"),
            "block_count": len(d.get("blocks", [])),
            "connection_count": len(d.get("connections", [])),
            "created_at": d.get("created_at"),
            "updated_at": d.get("updated_at"),
        }
        for d in diagrams
    ]


@router.post("/diagrams")
async def create_diagram(diagram: BlockDiagram):
    """Create a new block diagram."""
    data = diagram.model_dump()
    result = create(data)
    return result


@router.get("/diagrams/{diagram_id}")
async def get_diagram(diagram_id: str):
    """Fetch a single diagram by ID."""
    d = get_by_id(diagram_id)
    if d is None:
        raise HTTPException(status_code=404, detail="Diagram not found.")
    return d


@router.put("/diagrams/{diagram_id}")
async def update_diagram(diagram_id: str, diagram: BlockDiagram):
    """Update an existing diagram (save positions, connections, etc.)."""
    data = diagram.model_dump()
    result = update(diagram_id, data)
    if result is None:
        raise HTTPException(status_code=404, detail="Diagram not found.")
    return result


@router.delete("/diagrams/{diagram_id}")
async def delete_diagram(diagram_id: str):
    """Delete a diagram."""
    if not delete(diagram_id):
        raise HTTPException(status_code=404, detail="Diagram not found.")
    return {"detail": "Deleted."}


# ---------------------------------------------------------------------------
# AI generation endpoints
# ---------------------------------------------------------------------------

@router.post("/diagrams/generate")
async def generate_diagram(payload: GenerateFromPartsRequest):
    """Generate a block diagram from a list of Part Library part numbers."""
    from services.part_library import get_all

    all_parts = get_all()
    matched = [p for p in all_parts if p.get("Part_Number") in payload.part_numbers]
    if not matched:
        raise HTTPException(
            status_code=400,
            detail="No matching parts found in the Part Library.",
        )

    try:
        diagram = generate_from_parts(matched, payload.diagram_name)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        logger.exception("AI block diagram generation failed")
        raise HTTPException(status_code=502, detail=f"AI generation failed: {exc}")

    # Auto-save the generated diagram
    data = diagram.model_dump()
    create(data)
    return data


@router.post("/diagrams/generate-from-text")
async def generate_diagram_from_text(payload: GenerateFromTextRequest):
    """Generate a block diagram from a free-text system description."""
    if not payload.description.strip():
        raise HTTPException(status_code=400, detail="Description text is required.")

    try:
        diagram = generate_from_text(payload.description, payload.diagram_name)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        logger.exception("AI block diagram generation from text failed")
        raise HTTPException(status_code=502, detail=f"AI generation failed: {exc}")

    data = diagram.model_dump()
    create(data)
    return data


@router.post("/diagrams/generate-from-pdf")
async def generate_diagram_from_pdf(
    file: UploadFile = File(...),
    diagram_name: str = "Auto-generated Diagram",
):
    """Generate a block diagram from an uploaded PDF architecture document."""
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    contents = await file.read()
    extracted = extract_text_from_pdf(contents)

    try:
        diagram = generate_from_text(extracted["text"], diagram_name)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        logger.exception("AI block diagram generation from PDF failed")
        raise HTTPException(status_code=502, detail=f"AI generation failed: {exc}")

    data = diagram.model_dump()
    create(data)
    return data


# ---------------------------------------------------------------------------
# Export endpoints
# ---------------------------------------------------------------------------

@router.post("/diagrams/{diagram_id}/export-netlist")
async def export_netlist(diagram_id: str, format: str = "script"):
    """Export a diagram as a netlist seed (script or CSV)."""
    d = get_by_id(diagram_id)
    if d is None:
        raise HTTPException(status_code=404, detail="Diagram not found.")

    if format == "csv":
        csv_content = generate_netlist_csv(d)
        return PlainTextResponse(
            content=csv_content,
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="netlist_seed.csv"'},
        )
    else:
        script = generate_netlist_script(d)
        return PlainTextResponse(
            content=script,
            media_type="text/x-python",
            headers={
                "Content-Disposition": 'attachment; filename="xpedition_netlist_seed.py"'
            },
        )
