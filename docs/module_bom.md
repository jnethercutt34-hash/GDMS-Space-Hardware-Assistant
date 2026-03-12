# Module: BOM Analyzer

## What It Does

The BOM Analyzer takes an Xpedition (or generic) BOM CSV and runs a multi-stage risk analysis pipeline. For every IC on the BOM it determines: lifecycle status (active/NRND/obsolete), radiation qualification level (space-grade, hi-rel, commercial), and an overall risk level. It cross-references against the part library for any radiation data already in the system, and optionally calls the AI for deeper risk assessment on ambiguous parts. Output is a full `BOMReport` with per-line results, a summary, and export to annotated CSV or Markdown report.

---

## Files

| File | Role |
|------|------|
| `routers/bom.py` | HTTP endpoints |
| `services/bom_analyzer.py` | Full analysis pipeline |
| `services/bom_export.py` | CSV and Markdown export |
| `models/bom.py` | Pydantic schemas |

---

## Data Model (`models/bom.py`)

```python
class LifecycleStatus(str, Enum):
    Active = "Active"
    NRND = "NRND"       # Not Recommended for New Design
    Obsolete = "Obsolete"
    Unknown = "Unknown"

class RadiationLevel(str, Enum):
    SpaceGrade = "Space Grade"
    HiRel = "Hi-Rel"
    Industrial = "Industrial"
    Commercial = "Commercial"
    Unknown = "Unknown"

class RiskLevel(str, Enum):
    Low = "Low"
    Medium = "Medium"
    High = "High"
    Critical = "Critical"

class BOMLineItem(BaseModel):
    ref_des: str
    part_number: str
    manufacturer: str
    description: str
    quantity: int
    lifecycle_status: LifecycleStatus
    radiation_level: RadiationLevel
    risk_level: RiskLevel
    risk_reasons: List[str]
    ai_assessment: str | None    # AI-generated text if called
    alternate_parts: List[AlternatePart]
    in_library: bool             # True if part found in library.json

class BOMSummary(BaseModel):
    total_line_items: int
    unique_parts: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    obsolete_count: int
    space_grade_count: int

class BOMReport(BaseModel):
    filename: str
    line_items: List[BOMLineItem]
    summary: BOMSummary
```

---

## API Endpoints

### `POST /api/bom/analyze`
**Request:** CSV file (multipart). Accepts `text/csv`, `application/vnd.ms-excel`, `text/plain`.

**Processing:** Calls `analyze_bom(csv_text, filename, skip_ai=False)`

**Response:** Full `BOMReport` as JSON.

**Error codes:** 400 (CSV parse error / empty BOM), 500 (unexpected failure)

### `POST /api/bom/export`
**Body:** `{report: BOMReport, format: "csv" | "summary"}`

- `"csv"` → annotated BOM CSV with risk columns added
- `"summary"` → Markdown risk report

---

## `services/bom_analyzer.py` — Deep Dive

### BOM Parsing (`parse_bom_csv`)

The parser handles both Xpedition's native export format and generic BOMs.

**Column detection (flexible header mapping):**
- `Ref Des` / `RefDes` / `Reference` → ref_des
- `Part Number` / `PN` / `MPN` → part_number
- `Manufacturer` / `Mfr` → manufacturer
- `Description` / `Desc` → description
- `Quantity` / `Qty` / `Count` → quantity
- `Package` / `Footprint` → package
- `Value` → value
- `DNP` / `Do Not Place` → is_dnp flag

**Xpedition-specific:** Xpedition BOM CSVs sometimes have a `BOM_UTF8` magic marker as the first line and use `\t` delimiters. The parser detects both.

**DNP handling:** Parts marked `DNP` (Do Not Place) are included in the report but always get `RiskLevel.Low` — they're not assembled so they can't cause in-circuit failures.

### Risk Scoring Pipeline (per part)

```
parse_bom_csv()
  ↓ for each line item:
  ↓ _determine_lifecycle_status(part_number, description)
  ↓ _determine_radiation_level(part_number, description, library_lookup)
  ↓ _compute_risk_level(lifecycle, radiation, ref_des, is_dnp)
  ↓ [optional] _ai_assess_batch(high_risk_parts)
```

### Lifecycle Status Detection (`_determine_lifecycle_status`)

Heuristics applied in order:
1. **Suffix matching:** PNs ending in `-SEP`, `-SER`, `-QPL`, `QMLV`, `QMLQ` → space-grade → `Active` (space programs buy new production)
2. **Military SMD numbers** (`5962...`): check against known obsolete date ranges in the heuristic table
3. **Description keywords:** `"obsolete"`, `"discontinued"`, `"last-time buy"` → `Obsolete`; `"nrnd"`, `"not recommended"` → `NRND`
4. **Default:** `Unknown`

### Radiation Level Detection (`_determine_radiation_level`)

1. **Library cross-reference:** Look up part in `library.json`. If `Radiation_TID` is populated → `SpaceGrade`. If `Radiation_SEL_Threshold` is populated → at minimum `HiRel`.
2. **PN suffix heuristics:**
   - `-SEP`, `QMLV`, `QMLQ`, `-SER`, `-QPL` → `SpaceGrade`
   - `5962...` military SMD → `SpaceGrade`
   - `-MIL`, `-883`, `HFT` → `HiRel`
   - `-AEC` (automotive), `-AUT` → `Industrial`
3. **Description keywords:** `"radiation hardened"`, `"rad-hard"`, `"space grade"` → `SpaceGrade`; `"hi-rel"`, `"military"` → `HiRel`; `"industrial temperature"` → `Industrial`
4. **Default:** `Commercial`

### Risk Level Computation (`_compute_risk_level`)

```python
if is_dnp:
    return RiskLevel.Low, ["DNP — not assembled"]

if lifecycle == Obsolete and radiation == Commercial:
    return RiskLevel.Critical, ["Obsolete commercial part — cannot source for new build"]

if lifecycle == Obsolete:
    return RiskLevel.High, ["Obsolete — find qualified replacement"]

if radiation == Commercial and ref_des_suggests_ic(ref_des):
    return RiskLevel.High, ["Commercial grade — no radiation data; unqualified for space"]

if radiation == Commercial:
    return RiskLevel.Medium, ["Commercial grade — verify environment suitability"]

if lifecycle == NRND:
    return RiskLevel.Medium, ["NRND — plan for replacement in next revision"]

return RiskLevel.Low, []
```

### AI Risk Assessment (`_ai_assess_batch`)

Only called for `High` and `Critical` parts (to limit API calls). Sends all high-risk parts in one batch call. The LLM provides:
- Specific risk explanation
- Suggested qualified replacement part numbers
- Qualification path recommendation (QPL search, heritage data, etc.)

The response is parsed and `ai_assessment` field is populated per part.

### Library Cross-Reference

The analyzer calls `part_library.get_all()` once and builds an in-memory `{part_number: part_dict}` lookup. It then checks each BOM line against this lookup using normalized PN matching:
- Exact match first
- Strip common suffixes (`-SEP`, `/883B`, etc.) for partial match
- Case-insensitive

Parts found in the library have `in_library = True` and inherit their radiation data from the library record.

---

## `services/bom_export.py`

### `generate_annotated_csv(report) → str`

Takes the original BOM rows and appends columns: `Risk_Level`, `Lifecycle_Status`, `Radiation_Level`, `Risk_Reasons`, `AI_Assessment`, `In_Library`. Output is a valid CSV that can be opened in Excel and attached to a CDR/PDR review package.

### `generate_risk_summary(report) → str`

Generates a Markdown document with:
- Executive summary table (counts by risk level)
- Critical items section (full details for each)
- High risk items section
- Recommendations section (keyed to risk reasons)

---

## Frontend — `pages/BomAnalyzer.jsx`

**Workflow:**
1. Upload zone for BOM CSV
2. POST to `/api/bom/analyze` — typically fast (1-5s without AI, 10-30s with)
3. Summary cards showing counts: Total Parts, Critical, High, Obsolete, Space Grade
4. BOM table with color-coded risk levels and expandable row detail
5. Export buttons: "Annotated CSV" and "Risk Report (Markdown)"

**`components/StackBar.jsx`:**
Used on the summary to show the risk distribution as a horizontal bar (green=Low, yellow=Medium, orange=High, red=Critical). The proportion is computed from the summary counts.

**`components/SummaryCard.jsx`:**
Used for the metric cards (Total, Critical, High, Obsolete, Space Grade). Each card shows a label and a large number. Critical and High counts turn red if nonzero.
