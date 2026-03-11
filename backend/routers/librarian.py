import re
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Query, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel

from models.component import ComponentData
from services.pdf_extractor import extract_text_from_pdf
from services.ai_extractor import extract_components_from_text
from services.xpedition_stub import simulate_xpedition_push
from services import part_library
from services.bom_analyzer import parse_bom_csv
from services import datasheet_store

router = APIRouter()


# ---------------------------------------------------------------------------
# POST /api/upload-datasheet  (extract only — does NOT auto-save to library)
# ---------------------------------------------------------------------------

@router.post("/upload-datasheet")
async def upload_datasheet(file: UploadFile = File(...)):
    """Accept a PDF datasheet, extract text, run AI parameter extraction.

    The PDF is saved to the datasheet store immediately (so it's available
    for download later), but extracted parts are NOT auto-saved to the
    library — the frontend must call POST /api/library/accept-parts to
    commit reviewed parts.
    """
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    contents = await file.read()

    # Save PDF to datasheet store
    stored_filename = datasheet_store.save(contents, file.filename)

    extracted = extract_text_from_pdf(contents)

    try:
        rows, ai_warnings = extract_components_from_text(extracted["text"])
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"AI extraction failed: {exc}")

    rows_dicts = [row.model_dump() for row in rows]

    # Consolidate variants for preview (but don't save yet)
    consolidated = None
    if rows_dicts:
        consolidated = part_library.consolidate_variants(rows_dicts, source_file=stored_filename)

    return {
        "filename": file.filename,
        "stored_filename": stored_filename,
        "page_count": extracted["page_count"],
        "extracted_text": extracted["text"],
        "rows": rows_dicts,
        "consolidated": consolidated,
        "primary_part": consolidated.get("Part_Number") if consolidated else None,
        "variant_count": len(consolidated.get("variants", [])) if consolidated else 0,
        "warnings": ai_warnings,
    }


# ---------------------------------------------------------------------------
# POST /api/library/accept-parts  (commit reviewed parts to library)
# ---------------------------------------------------------------------------

class AcceptPartsRequest(BaseModel):
    parts: List[Dict[str, Any]]
    source_file: str
    datasheet_file: str | None = None


@router.post("/library/accept-parts")
def accept_parts(payload: AcceptPartsRequest):
    """Save engineer-reviewed parts to the library.

    Called after upload-datasheet when the engineer accepts the extraction.
    """
    if not payload.parts:
        raise HTTPException(status_code=400, detail="No parts provided.")

    added = part_library.upsert_parts(
        payload.parts,
        source_file=payload.source_file,
        datasheet_file=payload.datasheet_file,
    )

    return {
        "status": "accepted",
        "added": added,
        "source_file": payload.source_file,
    }


# ---------------------------------------------------------------------------
# GET /api/datasheets/{filename}  (serve stored PDF)
# ---------------------------------------------------------------------------

@router.get("/datasheets/{filename}")
def get_datasheet(filename: str):
    """Serve a stored PDF datasheet file."""
    path = datasheet_store.get_path(filename)
    if path is None:
        raise HTTPException(status_code=404, detail="Datasheet not found.")
    return FileResponse(path, media_type="application/pdf", filename=filename)


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
# POST /api/library/import-bom
# ---------------------------------------------------------------------------

# Reference designator prefixes that indicate ICs / active devices
_IC_PREFIXES = re.compile(
    r"^(U|IC|Q|D|CR|VR|Y|J|P|FL|FB|T|L)\d",
    re.IGNORECASE,
)

# Keywords in description or part number that strongly suggest passives (skip)
_PASSIVE_KEYWORDS = re.compile(
    r"\b(resistor|capacitor|cap\b|res\b|inductor|ferrite|fuse|jumper|testpoint|test point|fiducial|standoff|screw|washer|nut|spacer|label|barcode)\b",
    re.IGNORECASE,
)

# Reference designator prefixes for passives — these are skipped
_PASSIVE_REFDES = re.compile(r"^(R|C|L|F|FB|TP|FID|MH)\d", re.IGNORECASE)


def _is_ic_candidate(ref_des: str, part_number: str, description: str) -> bool:
    """Heuristic: return True if the BOM line looks like an IC or active device."""
    # Skip obviously passive ref-des
    if _PASSIVE_REFDES.match(ref_des):
        return False
    # Skip passive-sounding descriptions
    if description and _PASSIVE_KEYWORDS.search(description):
        return False
    # Accept known IC ref-des prefixes
    if _IC_PREFIXES.match(ref_des):
        return True
    # Accept anything that doesn't look passive — connectors, oscillators, etc.
    # The engineer can always delete unwanted entries from the library.
    if ref_des and not _PASSIVE_REFDES.match(ref_des):
        return True
    return False


@router.post("/library/import-bom")
async def import_bom_to_library(file: UploadFile = File(...)):
    """Parse an Xpedition (or generic) BOM CSV and add IC / active-device
    entries to the part library as placeholders awaiting datasheet upload.

    Passives (R, C, L, ferrites, test points, fiducials) are skipped.
    Parts that already exist in the library are not overwritten.
    """
    content = (await file.read()).decode("utf-8-sig", errors="replace")

    try:
        bom_items = parse_bom_csv(content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if not bom_items:
        raise HTTPException(status_code=400, detail="No parts found in BOM.")

    # Deduplicate by part number — keep first occurrence
    seen = set()
    placeholder_parts = []
    skipped_passives = 0
    for item in bom_items:
        pn = item.part_number.strip()
        if not pn or pn == "UNKNOWN":
            continue
        if pn in seen:
            continue

        if not _is_ic_candidate(item.ref_des, pn, item.description):
            skipped_passives += 1
            continue

        seen.add(pn)
        placeholder_parts.append({
            "Part_Number": pn,
            "Manufacturer": item.manufacturer if item.manufacturer != "Unknown" else None,
            "Package_Type": item.package,
            "Value": item.value,
            "Summary": item.description or None,
        })

    if not placeholder_parts:
        raise HTTPException(
            status_code=400,
            detail=f"No IC / active-device parts found. {skipped_passives} passive components were skipped.",
        )

    result = part_library.upsert_placeholder_parts(
        placeholder_parts,
        source_file=file.filename or "bom_import.csv",
    )

    return {
        "filename": file.filename,
        "total_bom_lines": len(bom_items),
        "ic_candidates": len(placeholder_parts),
        "passives_skipped": skipped_passives,
        "added_to_library": result["added"],
        "already_in_library": result["skipped"],
        "parts": placeholder_parts,
    }


# ---------------------------------------------------------------------------
# GET /api/library
# ---------------------------------------------------------------------------

@router.get("/library")
def get_library():
    """Return all parts currently stored in the library."""
    return {"parts": part_library.get_all()}


# ---------------------------------------------------------------------------
# GET /api/library/search  (must be before {part_number} to avoid conflict)
# ---------------------------------------------------------------------------

@router.get("/library/search")
def search_library(q: str = Query(default="", description="Search query")):
    """Search the library by part number, manufacturer, summary, or any field."""
    return {"parts": part_library.search(q)}


# ---------------------------------------------------------------------------
# GET /api/library/{part_number}
# ---------------------------------------------------------------------------

@router.get("/library/{part_number}")
def get_library_part(part_number: str):
    """Return a single part by part number."""
    part = part_library.get_by_part_number(part_number)
    if part is None:
        raise HTTPException(status_code=404, detail=f"Part '{part_number}' not found in library.")
    return part


# ---------------------------------------------------------------------------
# PATCH /api/library/{part_number}
# ---------------------------------------------------------------------------

class PatchPartRequest(BaseModel):
    Program: str | None = None


@router.patch("/library/{part_number}")
def patch_library_part(part_number: str, payload: PatchPartRequest):
    """Update mutable fields on a library part (e.g. Program assignment)."""
    updated = part_library.patch_part(part_number, payload.model_dump(exclude_unset=True))
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Part '{part_number}' not found in library.")
    return updated
