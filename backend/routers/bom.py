"""Router for Phase 6 — BOM Analyzer."""
import logging

from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from models.bom import BOMReport
from services.bom_analyzer import analyze_bom
from services.bom_export import generate_annotated_csv, generate_risk_summary

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# POST /api/bom/analyze
# ---------------------------------------------------------------------------

@router.post("/bom/analyze")
async def analyze(file: UploadFile = File(...)):
    """Accept a CSV BOM file and run the full analysis pipeline.

    Returns the complete BOMReport with per-line results and summary.
    """
    if file.content_type and file.content_type not in (
        "text/csv",
        "application/vnd.ms-excel",
        "application/octet-stream",
        "text/plain",
    ):
        raise HTTPException(
            status_code=400,
            detail=f"Expected a CSV file, got '{file.content_type}'.",
        )

    contents = await file.read()

    # Try UTF-8 first, fall back to latin-1
    try:
        csv_text = contents.decode("utf-8")
    except UnicodeDecodeError:
        csv_text = contents.decode("latin-1")

    try:
        report = analyze_bom(csv_text, filename=file.filename or "bom.csv", skip_ai=False)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("BOM analysis failed")
        raise HTTPException(status_code=500, detail=f"BOM analysis failed: {exc}")

    return report.model_dump()


# ---------------------------------------------------------------------------
# POST /api/bom/export
# ---------------------------------------------------------------------------

class ExportRequest(BaseModel):
    report: BOMReport
    format: str = "summary"  # "csv" or "summary"


@router.post("/bom/export")
async def export(payload: ExportRequest):
    """Generate a downloadable export from a BOMReport.

    Supported formats: 'csv' (annotated BOM), 'summary' (Markdown report).
    """
    fmt = payload.format.lower()

    if fmt == "csv":
        csv_content = generate_annotated_csv(payload.report)
        return PlainTextResponse(
            content=csv_content,
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="bom_annotated.csv"'},
        )
    elif fmt == "summary":
        report = generate_risk_summary(payload.report)
        return PlainTextResponse(
            content=report,
            media_type="text/markdown",
            headers={"Content-Disposition": 'attachment; filename="bom_risk_report.md"'},
        )
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown export format: '{fmt}'. Use 'csv' or 'summary'.",
        )
