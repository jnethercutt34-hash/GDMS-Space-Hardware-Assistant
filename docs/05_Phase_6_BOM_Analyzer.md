# Phase 6: BOM Analyzer

## Objective
Build a module within the GDMS Space Hardware Assistant that ingests a Bill of Materials (BOM) — typically exported from Xpedition or a PLM system — and performs automated analysis: cross-referencing parts against the internal Part Library, flagging obsolescence risks, checking radiation tolerance for space applications, identifying second-source options, and summarizing BOM health.

## Background
Space hardware programs require rigorous parts management. Engineers manually cross-check BOMs against DMSMS (Diminishing Manufacturing Sources and Material Shortages) databases, radiation test reports, and qualified parts lists. This is tedious and error-prone. An AI-assisted BOM analyzer can automate the initial triage and flag issues early.

## Step-by-Step Implementation Plan

### Step 1: Data Model — BOM Schema
* Create Pydantic models in `backend/models/bom.py`:
  - `BOMLineItem` — one row from the BOM: `ref_des`, `part_number`, `manufacturer`, `description`, `quantity`, `value` (optional), `package` (optional), `dnp` (Do Not Populate, bool)
  - `BOMAnalysisResult` — per-line analysis: `line_item` (BOMLineItem), `library_match` (bool — found in Part Library?), `lifecycle_status` (enum: Active, NRND, Obsolete, Unknown), `radiation_grade` (enum: Commercial, MIL, RadTolerant, RadHard, Unknown), `alt_parts[]` (suggested alternates), `risk_flags[]` (string warnings), `risk_level` (Low / Medium / High / Critical)
  - `BOMReport` — full BOM analysis: `filename`, `total_line_items`, `unique_parts`, `results[]` (BOMAnalysisResult), `summary` (stats: % matched, % obsolete risk, % rad-hard, etc.)

### Step 2: Backend — BOM Ingestion & Library Cross-Reference
* Create `backend/services/bom_analyzer.py`
* Add endpoint `POST /api/bom/analyze` — accepts a CSV or Excel BOM file
* Parsing logic:
  - Auto-detect column mapping (handle common BOM formats: Xpedition, Altium, OrCAD, generic)
  - Normalize part numbers (strip whitespace, handle manufacturer prefixes)
* Cross-reference each part against `backend/data/library.json`:
  - Exact match on Part_Number
  - Fuzzy match fallback (handle suffixes like `-ND`, `/TR`, package variants)
  - Flag unmatched parts for review

### Step 3: AI-Assisted Risk Assessment
* Create `backend/services/bom_risk_assessor.py`
* For parts NOT in the library (or with incomplete data), call the AI (OpenAI-compatible) with:
  - Part number + manufacturer + description
  - System prompt instructing it to assess: lifecycle status, radiation tolerance, typical use in space/defense applications, and suggest alternates
* For parts IN the library, use stored data to determine risk programmatically (e.g., if `Voltage_Rating` or `Thermal_Resistance` is missing → flag for review)
* Assign `risk_level` per part:
  - **Critical**: Obsolete, single-source with no alternates, or commercial-grade on a rad-hard design
  - **High**: NRND status, or radiation grade unknown for a space application
  - **Medium**: Part is active but no second source identified
  - **Low**: Active, rad-qualified, multiple sources available

### Step 4: BOM Summary & Report Generation
* Compute aggregate statistics:
  - Total unique parts / total placements
  - % matched in Part Library
  - % with lifecycle risk (NRND + Obsolete)
  - % Commercial vs. MIL vs. RadHard
  - Top risk items (sorted by risk_level)
* Generate downloadable reports:
  - **Annotated BOM CSV** — original BOM + appended analysis columns
  - **Risk Summary PDF/MD** — executive summary with charts/tables

### Step 5: Frontend — BOM Dashboard
* Create `frontend/src/pages/BomAnalyzer.jsx` — new page, add to Navbar
* **Upload section**: drag-and-drop for BOM CSV/Excel
* **Summary cards** (top of page after analysis):
  - Total Parts / Unique Parts
  - Library Coverage (% matched)
  - Lifecycle Health (pie/bar: Active / NRND / Obsolete / Unknown)
  - Radiation Profile (pie/bar: RadHard / RadTolerant / MIL / Commercial / Unknown)
* **Results table**: sortable/filterable by risk level, lifecycle, radiation grade
  - Color-coded risk badges (Critical=red, High=amber, Medium=yellow, Low=green)
  - Expandable rows showing: library match details, AI assessment, alternate parts
* **Export buttons**: Annotated BOM CSV, Risk Summary report

### Step 6: Tests
* Create `backend/tests/test_bom.py`
* Test: BOM parsing (multiple formats), library cross-reference, AI risk assessment (mocked), summary statistics, report generation
* Target: 25+ tests
