import logging
from typing import List

from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from services.csv_delta import compute_pin_delta
from services.fpga_risk_assessor import assess_pin_risks
from services.xpedition_io_export import generate_io_update_script

logger = logging.getLogger(__name__)

router = APIRouter()


class ExportRequest(BaseModel):
    """Payload for the export-io-script endpoint."""
    swapped_pins: List[dict]


@router.post("/compare-fpga-pins")
async def compare_fpga_pins(
    baseline_csv: UploadFile = File(..., description="Baseline pinout CSV from Xpedition."),
    new_csv: UploadFile = File(..., description="Updated pinout CSV from Vivado."),
):
    """Compare two FPGA pinout CSVs and return only the signals that have moved.

    Both files must be UTF-8 CSVs with at minimum the columns:
    Signal_Name, Pin, Bank.

    If an AI API key is configured, each swap also receives an SI/PI risk
    assessment. Otherwise swaps are returned with AI_Risk_Assessment = None.
    """
    baseline_bytes = await baseline_csv.read()
    new_bytes = await new_csv.read()

    try:
        swapped_pins = compute_pin_delta(baseline_bytes, new_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # --- AI risk assessment (best-effort) ---
    if swapped_pins:
        try:
            swapped_pins = assess_pin_risks(swapped_pins)
        except RuntimeError as exc:
            # INTERNAL_API_KEY not set — return 503
            raise HTTPException(
                status_code=503,
                detail=f"AI risk assessment unavailable: {exc}",
            )
        except Exception as exc:
            # Any other AI/network error — return 502
            logger.exception("AI risk assessment failed")
            raise HTTPException(
                status_code=502,
                detail=f"AI risk assessment failed: {exc}",
            )

    return {
        "total_swaps": len(swapped_pins),
        "swapped_pins": swapped_pins,
    }


@router.post("/export-io-script")
async def export_io_script(payload: ExportRequest):
    """Generate a downloadable Python script for Xpedition I/O Designer updates.

    Accepts the swapped_pins array (as returned by /compare-fpga-pins) and
    returns a self-contained .py script as a file download.
    """
    if not payload.swapped_pins:
        raise HTTPException(status_code=400, detail="No pin swaps provided.")

    script = generate_io_update_script(payload.swapped_pins)

    return PlainTextResponse(
        content=script,
        media_type="text/x-python",
        headers={
            "Content-Disposition": 'attachment; filename="xpedition_pin_update.py"'
        },
    )
