"""Router for Phase 5 — COM Channel Analysis."""
import logging

from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from models.com_channel import ChannelModel, COMResult
from services.pdf_extractor import extract_text_from_pdf
from services.com_extractor import extract_channel_from_text
from services.com_calculator import calculate_com
from services.com_export import (
    generate_channel_ces_script,
    generate_hyperlynx_csv,
    generate_summary_report,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# POST /api/com/extract-channel
# ---------------------------------------------------------------------------

@router.post("/com/extract-channel")
async def extract_channel(file: UploadFile = File(...)):
    """Accept a PDF (datasheet / stackup report) and use AI to extract
    channel parameters for COM analysis.

    Returns a pre-populated ChannelModel for the engineer to review.
    """
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    contents = await file.read()
    extracted = extract_text_from_pdf(contents)

    try:
        channel = extract_channel_from_text(extracted["text"], channel_name=file.filename or "Extracted Channel")
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        logger.exception("AI channel extraction failed")
        raise HTTPException(status_code=502, detail=f"AI channel extraction failed: {exc}")

    return {
        "filename": file.filename,
        "page_count": extracted["page_count"],
        "channel": channel.model_dump(),
    }


# ---------------------------------------------------------------------------
# POST /api/com/calculate
# ---------------------------------------------------------------------------

class CalculateRequest(BaseModel):
    channel: ChannelModel


@router.post("/com/calculate")
async def calculate(payload: CalculateRequest):
    """Compute estimated COM for a ChannelModel.

    Returns COMResult with pass/fail, eye dimensions, and warnings.
    """
    if not payload.channel.segments:
        raise HTTPException(status_code=400, detail="Channel must have at least one segment.")

    result = calculate_com(payload.channel)
    return {
        "channel": payload.channel.model_dump(),
        "result": result.model_dump(),
    }


# ---------------------------------------------------------------------------
# POST /api/com/export
# ---------------------------------------------------------------------------

class ExportRequest(BaseModel):
    channel: ChannelModel
    result: COMResult
    format: str = "summary"  # "ces", "hyperlynx", "summary"


@router.post("/com/export")
async def export(payload: ExportRequest):
    """Generate downloadable export files from a channel + COM result.

    Supported formats: 'ces', 'hyperlynx', 'summary'.
    """
    fmt = payload.format.lower()

    if fmt == "ces":
        script = generate_channel_ces_script(payload.channel, payload.result)
        return PlainTextResponse(
            content=script,
            media_type="text/x-python",
            headers={"Content-Disposition": 'attachment; filename="xpedition_channel_ces.py"'},
        )
    elif fmt == "hyperlynx":
        csv_content = generate_hyperlynx_csv(payload.channel)
        return PlainTextResponse(
            content=csv_content,
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="hyperlynx_channel.csv"'},
        )
    elif fmt == "summary":
        report = generate_summary_report(payload.channel, payload.result)
        return PlainTextResponse(
            content=report,
            media_type="text/markdown",
            headers={"Content-Disposition": 'attachment; filename="com_analysis_report.md"'},
        )
    else:
        raise HTTPException(status_code=400, detail=f"Unknown export format: '{fmt}'. Use 'ces', 'hyperlynx', or 'summary'.")
