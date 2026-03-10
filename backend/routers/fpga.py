from fastapi import APIRouter, HTTPException, UploadFile, File

from services.csv_delta import compute_pin_delta

router = APIRouter()


@router.post("/compare-fpga-pins")
async def compare_fpga_pins(
    baseline_csv: UploadFile = File(..., description="Baseline pinout CSV from Xpedition."),
    new_csv: UploadFile = File(..., description="Updated pinout CSV from Vivado."),
):
    """Compare two FPGA pinout CSVs and return only the signals that have moved.

    Both files must be UTF-8 CSVs with at minimum the columns:
    Signal_Name, Pin, Bank.
    """
    baseline_bytes = await baseline_csv.read()
    new_bytes = await new_csv.read()

    try:
        swapped_pins = compute_pin_delta(baseline_bytes, new_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return {
        "total_swaps": len(swapped_pins),
        "swapped_pins": swapped_pins,
    }
