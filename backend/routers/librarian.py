from typing import List

from fastapi import APIRouter, HTTPException, Query, UploadFile, File
from pydantic import BaseModel

from models.component import ComponentData
from services.pdf_extractor import extract_text_from_pdf
from services.ai_extractor import extract_components_from_text
from services.xpedition_stub import simulate_xpedition_push
from services import part_library

router = APIRouter()


# ---------------------------------------------------------------------------
# POST /api/upload-datasheet
# ---------------------------------------------------------------------------

@router.post("/upload-datasheet")
async def upload_datasheet(file: UploadFile = File(...)):
    """Accept a PDF datasheet, extract its text, run AI parameter extraction,
    and return the validated Databook rows alongside the raw text.
    Extracted parts are automatically saved to the part library."""

    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    contents = await file.read()
    extracted = extract_text_from_pdf(contents)

    try:
        rows = extract_components_from_text(extracted["text"])
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"AI extraction failed: {exc}")

    rows_dicts = [row.model_dump() for row in rows]

    # Auto-save every successfully extracted component to the library
    if rows_dicts:
        part_library.upsert_parts(rows_dicts, source_file=file.filename)

    return {
        "filename": file.filename,
        "page_count": extracted["page_count"],
        "extracted_text": extracted["text"],
        "rows": rows_dicts,
    }


# ---------------------------------------------------------------------------
# POST /api/push-to-databook
# ---------------------------------------------------------------------------

class PushToDatabookRequest(BaseModel):
    rows: List[ComponentData]


@router.post("/push-to-databook")
def push_to_databook(payload: PushToDatabookRequest):
    """Receive verified component rows from the frontend and push each one
    to the Xpedition Databook via the COM stub.

    Returns a per-row result list so the UI can show granular status.
    """
    if not payload.rows:
        raise HTTPException(status_code=400, detail="No component rows provided.")

    results = []
    for row in payload.rows:
        stub_result = simulate_xpedition_push(row.model_dump_json())
        results.append({
            "Part_Number": row.Part_Number,
            "status": stub_result["status"],
            "message": stub_result["message"],
        })

    return {"results": results}


# ---------------------------------------------------------------------------
# GET /api/library
# ---------------------------------------------------------------------------

@router.get("/library")
def get_library():
    """Return all parts currently stored in the library."""
    return {"parts": part_library.get_all()}


# ---------------------------------------------------------------------------
# GET /api/library/search
# ---------------------------------------------------------------------------

@router.get("/library/search")
def search_library(q: str = Query(default="", description="Search query")):
    """Search the library by part number, manufacturer, summary, or any field."""
    return {"parts": part_library.search(q)}
