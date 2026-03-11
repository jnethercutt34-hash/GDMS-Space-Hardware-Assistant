# Phase 7: Schematic DRC (Design Rule Check)

## Objective
Build a module within the GDMS Space Hardware Assistant that performs AI-assisted design rule checks on schematic netlists. The tool ingests a netlist (exported from Xpedition ViewDraw) and applies a combination of deterministic rules and AI-powered heuristic checks to catch common schematic errors before layout.

## Background
Xpedition has built-in DRC, but it focuses on connectivity and ERC (electrical rule checks). It doesn't catch higher-level design intent issues: missing decoupling caps, incorrect pull-up/pull-down networks, power sequencing violations, unconnected sense pins, or interface protocol mismatches. An AI layer can catch these "soft" errors that normally require a senior engineer's review.

## Step-by-Step Implementation Plan

### Step 1: Data Model — Netlist & DRC Rules
* Create Pydantic models in `backend/models/schematic_drc.py`:
  - `NetlistNet` — a single net: `name`, `pins[]` (list of `{ref_des, pin_name, pin_number, pin_type}`)
  - `NetlistComponent` — a component instance: `ref_des`, `part_number`, `value`, `pins[]`
  - `Netlist` — full netlist: `components[]`, `nets[]`, `power_nets[]`, `ground_nets[]`
  - `DRCViolation` — a single finding: `rule_id`, `severity` (Error / Warning / Info), `category` (enum: Power, Decoupling, Termination, Interface, Connectivity, Naming), `message`, `affected_nets[]`, `affected_components[]`, `recommendation`
  - `DRCReport` — full report: `netlist_summary` (component count, net count), `violations[]`, `pass_count`, `warning_count`, `error_count`

### Step 2: Backend — Netlist Parser
* Create `backend/services/netlist_parser.py`
* Add endpoint `POST /api/drc/upload-netlist` — accepts:
  - Xpedition ASCII netlist (`.asc`)
  - Generic CSV netlist (ref_des, pin, net columns)
  - OrCAD/Allegro netlist format (for cross-tool support)
* Parse into the `Netlist` Pydantic model
* Auto-classify power and ground nets (by name convention: VCC*, VDD*, GND*, VSS*, etc.)

### Step 3: Deterministic Rule Engine
* Create `backend/services/drc_rules_engine.py`
* Implement hard-coded rules that run first (fast, no AI needed):
  - **PWR-001: Unconnected power pins** — any power/supply pin on a component with no net connection
  - **PWR-002: Missing decoupling** — power pin with no capacitor within 1-hop net connectivity (checks for caps on the same power net local to a component)
  - **PWR-003: Power net fan-out** — flag power nets driving > N components without a ferrite/filter
  - **GND-001: Split ground** — detect multiple ground net names that may indicate unintentional ground splits
  - **TERM-001: Unterminated high-speed nets** — nets with known high-speed signal name patterns (CLK*, *_DP, *_DN, SERDES*) that lack termination resistors
  - **CONN-001: Single-pin nets** — nets connected to only one pin (floating signals)
  - **CONN-002: Unconnected component pins** — pins on ICs that are not connected to any net and not marked NC
  - **NAME-001: Net naming conventions** — flag nets with auto-generated names (N$*, NET*, unnamed)

### Step 4: AI-Assisted Heuristic Checks
* Create `backend/services/drc_ai_checker.py`
* Add endpoint `POST /api/drc/analyze` — runs both deterministic + AI checks
* Pass the netlist (or relevant subsets) to the AI (OpenAI-compatible) with a system prompt for:
  - **Interface protocol validation**: Given component part numbers and their connected nets, verify that interface connections follow protocol specs (e.g., I2C needs pull-ups, SPI needs CS per device, JTAG chain is complete, DDR has proper address/data grouping)
  - **Power sequencing**: If known sequencing requirements exist in the Part Library data, check that enable/PG (power-good) signal chains are present
  - **Decoupling strategy**: Evaluate if decoupling cap values and quantities are appropriate for the IC (cross-reference Part Library if available)
  - **Cross-domain checks**: Flag signals crossing between power domains without level shifters
* AI returns structured `DRCViolation[]` — validated against Pydantic model

### Step 5: Frontend — DRC Dashboard
* Create `frontend/src/pages/SchematicDrc.jsx` — new page, add to Navbar
* **Upload section**: drag-and-drop for netlist file
* **Summary bar** (after analysis):
  - Errors (red count badge), Warnings (amber), Info (blue)
  - Component count, Net count
  - Pass/Fail overall status
* **Violations table**: sortable by severity and category
  - Severity badge (Error=red, Warning=amber, Info=blue)
  - Category badge
  - Affected components and nets (clickable/expandable)
  - AI recommendation text
  - Deterministic vs. AI-generated indicator
* **Filter controls**: by severity, category, component
* **Export button**: download DRC report as CSV or Markdown

### Step 6: Tests
* Create `backend/tests/test_schematic_drc.py`
* Test: netlist parsing (multiple formats), each deterministic rule with pass/fail fixtures, AI checker (mocked), report generation
* Include test netlists:
  - Clean netlist (no violations expected)
  - Deliberately broken netlist (missing decap, floating pins, unterminated clocks, missing I2C pull-ups)
* Target: 30+ tests
