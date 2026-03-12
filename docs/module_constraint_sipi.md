# Module: Constraint Editor + SI/PI Design Guide

These two backend routers (`constraint.py` and `sipi.py`) serve the same frontend page (`/constraints` → `SiPiGuide.jsx`). They handle two complementary workflows:

1. **Constraint Extraction** — upload a component datasheet or design spec PDF, use AI to pull out explicit SI/PI constraints (impedance targets, timing budgets, spacing rules), then export them as an Xpedition CES automation script
2. **SI/PI Design Rule Guide** — browse a hardcoded knowledge base of SI/PI rules for standard interfaces, calculate channel loss budgets, and ask an AI advisor questions with rule context

---

## Files

| File | Role |
|------|------|
| `routers/constraint.py` | Constraint extraction from PDFs |
| `routers/sipi.py` | Interface knowledge base, loss budget, AI advisor |
| `services/constraint_extractor.py` | AI constraint extraction logic |
| `services/xpedition_ces_export.py` | Xpedition CES Python script generator |
| `services/sipi_knowledge_base.py` | Hardcoded SI/PI rules per interface |
| `services/loss_budget_calculator.py` | Analytical channel loss budgeting |
| `models/sipi_guide.py` | Pydantic schemas |

---

## Constraint Extraction Endpoints

### `POST /api/extract-constraints`
**Request:** PDF file (multipart)

**Processing:**
1. Extract text via PyMuPDF
2. Send to LLM with a system prompt instructing extraction of: impedance targets, trace length constraints, timing budgets, spacing/clearance rules, termination requirements, power delivery specs
3. Parse + validate `DesignConstraint` Pydantic models
4. Return `{filename, page_count, extracted_text, constraints: [...], warnings: [...]}`

**Error codes:** 503 (no API key), 502 (AI/network error), 400 (not PDF)

### `POST /api/export-ces-script`
**Request:** `{constraints: [...]}`

**Response:** Python file download (`xpedition_ces_update.py`)

The script uses `win32com.client` to connect to Xpedition's Constraint Editor System (CES) and programmatically apply each constraint rule — impedance, length, spacing — to the specified net classes.

---

## `services/constraint_extractor.py`

Follows the same AI call pattern as `ai_extractor.py`. System prompt instructs the model to return:
```json
{
  "constraints": [
    {
      "parameter": "Differential Impedance",
      "value": "100",
      "tolerance": "±10",
      "unit": "Ohm",
      "net_class": "DDR4_DQ",
      "notes": "From JEDEC JESD79-4B Table 5"
    }
  ]
}
```

The `DesignConstraint` model accepts these fields. The extractor includes salvage logic for flat LLM responses (same pattern as `ai_extractor.py`).

---

## `services/xpedition_ces_export.py`

Generates a standalone Python script targeting Xpedition's CES COM API. The script:
- Imports `win32com.client`
- Dispatches `"MgcPCB.Application"` (Xpedition PCB)
- Opens the CES via `.ConstraintEditorSystem`
- For each constraint: finds or creates the net class, sets the parameter value and tolerance

The script is meant to be run in Xpedition's embedded Python environment, not the server process.

---

## SI/PI Guide Endpoints

### `GET /api/sipi/interfaces`
Returns all supported interfaces from the knowledge base. No parameters.

Example interfaces: `DDR4`, `PCIe_Gen3`, `USB3`, `HDMI2`, `LVDS`, `CAN`, `SpaceWire`.

Each interface has: `id`, `name`, `description`, `max_data_rate_gbps`, `typical_impedance_ohm`.

### `GET /api/sipi/interface/{iface_id}`
Full spec for one interface including all its design rules.

### `POST /api/sipi/rules`
**Body:** `{interfaces: [str], categories: [str]}`

Returns combined rules for the selected interfaces, optionally filtered by category (e.g. `"Impedance"`, `"Timing"`, `"Spacing"`, `"Via"`, `"Termination"`).

### `POST /api/sipi/loss-budget`
**Body:**
```json
{
  "interface": "PCIe_Gen3",
  "trace_length_inches": 8.0,
  "num_vias": 6,
  "num_connectors": 1,
  "include_package": true,
  "material": "fr4",
  "custom_max_loss_db": null
}
```

Returns a `LossBudgetResult` with per-element loss breakdown and pass/fail against the interface's loss budget limit.

### `POST /api/sipi/advisor`
**Body:** `{question: str, interfaces: [str], board_details: str | null}`

**Behavior:**
1. Fetch relevant rules from knowledge base for the selected interfaces
2. If `OPENAI_API_KEY` env var is set: send question + rules as context to GPT
3. If not: fall back to `_offline_advisor()` — keyword matching against rule parameters and rationales
4. Return `{answer: str, referenced_rules: [str]}`

**Note:** This endpoint currently checks `OPENAI_API_KEY` (not `INTERNAL_API_KEY`). This is a known inconsistency — the offline fallback is sufficient for most engineering questions.

### `POST /api/sipi/export`
**Body:** `{rules: [...], format: "ces" | "markdown"}`

Exports the selected rules either as an Xpedition CES script or a formatted Markdown document with a rule table and rationale section.

---

## `services/sipi_knowledge_base.py`

Hardcoded Python data structure — no database, no external file. Each interface is an `InterfaceSpec` with a list of `DesignRule` objects.

**Rule fields:** `rule_id`, `interface`, `category`, `signal_group`, `parameter`, `target`, `tolerance`, `unit`, `rationale`, `spec_source`, `severity`

**Example rule:**
```
DDR4-IMP-001 | DDR4 | Impedance | DQ_DQS | Differential Impedance | 100 | ±10% | Ohm
Rationale: JEDEC JESD79-4B requires 100Ω differential for signal integrity
Spec: JEDEC JESD79-4B
```

This is the definitive source for SI/PI rule data. When engineers ask why a rule has a specific value, the `rationale` and `spec_source` fields are the answer.

---

## `services/loss_budget_calculator.py`

**What it does:** Computes how much insertion loss (in dB) each channel element consumes at the Nyquist frequency for a given interface, then checks the total against the interface's maximum allowed loss.

**Inputs:**
- Interface ID (determines data rate and max loss budget)
- Trace length in inches
- Number of vias
- Number of connectors
- Whether to include IC package loss
- PCB material (`fr4` vs `megtron` vs `rogers`)

**Loss model (approximate, not IBIS-based):**
- Trace: `loss_db/inch * trace_length_inches` (material-dependent, frequency-scaled)
- Via: fixed dB per via (interface-dependent, accounts for stub effects)
- Connector: fixed dB per connector (interface-dependent)
- Package: fixed dB (interface-dependent)

**Return:**
```json
{
  "interface": "PCIe_Gen3",
  "total_loss_db": 12.4,
  "max_loss_db": 20.0,
  "margin_db": 7.6,
  "pass": true,
  "breakdown": {
    "trace": 8.0, "vias": 2.4, "connectors": 1.5, "package": 0.5
  }
}
```

This is an analytical estimate — for fabrication sign-off, use HyperLynx or Simbeor with actual stackup parameters.

---

## Frontend — `pages/SiPiGuide.jsx`

The page has two tabs:

**Constraint Extractor tab:**
- Upload zone for PDF
- Constraint results table (`ConstraintTable.jsx`) — editable rows
- Export CES Script button

**SI/PI Guide tab:**
- Interface multi-select checkboxes
- Category filter buttons
- Rules table showing all applicable rules for selected interfaces
- Loss budget calculator form
- AI advisor chat input
- Export rules buttons (CES or Markdown)

**`components/ConstraintTable.jsx`:**
- Editable cells — engineers can correct AI-extracted values before exporting
- Add/remove row controls
- Inline validation (empty `parameter` or `value` highlighted)
