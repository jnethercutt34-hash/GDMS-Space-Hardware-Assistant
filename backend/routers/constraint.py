"""Router for Phase 3 — SI/PI Constraint Editor."""
import logging
from typing import List

from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from services.pdf_extractor import extract_text_from_pdf
from services.constraint_extractor import extract_constraints_from_text
from services.xpedition_ces_export import generate_ces_script

logger = logging.getLogger(__name__)

router = APIRouter()


class ExportCesRequest(BaseModel):
    """Payload for the export-ces-script endpoint."""
    constraints: List[dict]


# ---------------------------------------------------------------------------
# POST /api/extract-constraints
# ---------------------------------------------------------------------------

@router.post("/extract-constraints")
async def extract_constraints(file: UploadFile = File(...)):
    """Accept a PDF datasheet, extract its text, and use AI to identify
    all SI/PI design constraints (impedance, timing, spacing, etc.).

    Returns the structured constraint list alongside raw extracted text.
    """
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    contents = await file.read()
    extracted = extract_text_from_pdf(contents)

    try:
        constraints, ai_warnings = extract_constraints_from_text(extracted["text"])
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        logger.exception("AI constraint extraction failed")
        raise HTTPException(status_code=502, detail=f"AI constraint extraction failed: {exc}")

    constraints_dicts = [c.model_dump() for c in constraints]

    return {
        "filename": file.filename,
        "page_count": extracted["page_count"],
        "extracted_text": extracted["text"],
        "constraints": constraints_dicts,
        "warnings": ai_warnings,
    }


# ---------------------------------------------------------------------------
# POST /api/export-ces-script
# ---------------------------------------------------------------------------

@router.post("/export-ces-script")
async def export_ces_script(payload: ExportCesRequest):
    """Generate a downloadable Python script that pushes SI/PI constraints
    into the Xpedition Constraint Editor System (CES) via COM.

    Accepts the constraints array (as returned by /extract-constraints) and
    returns a self-contained .py script as a file download.
    """
    if not payload.constraints:
        raise HTTPException(status_code=400, detail="No constraints provided.")

    script = generate_ces_script(payload.constraints)

    return PlainTextResponse(
        content=script,
        media_type="text/x-python",
        headers={
            "Content-Disposition": 'attachment; filename="xpedition_ces_update.py"'
        },
    )
