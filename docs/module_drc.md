# Module: Schematic DRC

## What It Does

The Schematic DRC module runs a two-stage design rule check against an uploaded netlist file. Stage 1 is deterministic — 13 hard-coded rule checks covering power net naming, unconnected pins, net fan-out, ground return paths, and space-specific requirements (radiation protection pins, temperature derating). Stage 2 is AI-powered — the LLM looks for subtler architectural issues that deterministic rules can't catch (unusual net topologies, missing decoupling, suspicious power sequencing). Results are returned as a `DRCReport` and can be exported as Markdown or CSV.

---

## Files

| File | Role |
|------|------|
| `routers/drc.py` | HTTP endpoints |
| `services/netlist_parser.py` | Xpedition/OrCAD netlist parser |
| `services/drc_rules_engine.py` | 13 deterministic rule checks |
| `services/drc_ai_checker.py` | AI-powered violations |
| `models/schematic_drc.py` | Pydantic schemas |

---

## Data Model (`models/schematic_drc.py`)

```python
class Severity(str, Enum):
    Error = "Error"
    Warning = "Warning"
    Info = "Info"

class Category(str, Enum):
    Connectivity = "Connectivity"
    Power = "Power"
    Grounding = "Grounding"
    SpaceCompliance = "Space Compliance"
    BestPractice = "Best Practice"
    AI = "AI"

class DRCViolation(BaseModel):
    rule_id: str             # e.g. "DRC-001"
    severity: Severity
    category: Category
    message: str             # human-readable description
    affected_nets: List[str]
    affected_components: List[str]
    recommendation: str
    ai_generated: bool       # True if from AI stage

class NetlistSummary(BaseModel):
    component_count: int
    net_count: int
    power_net_count: int
    ground_net_count: int

class DRCReport(BaseModel):
    netlist_summary: NetlistSummary
    violations: List[DRCViolation]
    pass_count: int
    warning_count: int
    error_count: int
    info_count: int
    overall_status: str      # "PASS" | "WARNING" | "FAIL"
```

---

## API Endpoints

### `POST /api/drc/upload-netlist`
Parse only — no rule checks. Returns the parsed `ParsedNetlist` structure for inspection.

**Accepts:** `.asc` (Xpedition), `.csv`, or OrCAD format. UTF-8 with latin-1 fallback.

### `POST /api/drc/analyze`
Full DRC pipeline:
1. Parse netlist
2. Run all 13 deterministic rules
3. Run AI checks (best-effort — if AI fails, deterministic results still returned)
4. Compute counts and `overall_status`
5. Return full `DRCReport`

**Error codes:** 400 (parse error), 500 (unexpected failure)

### `POST /api/drc/export`
**Body:** `{report: DRCReport, format: "csv" | "markdown"}`

**CSV format:** One row per violation. Columns: Rule ID, Severity, Category, Message, Affected Nets, Affected Components, Recommendation, AI Generated.

**Markdown format:** Executive summary table + per-violation sections with severity icons (🔴/🟡/🔵). AI-generated violations tagged with `*(AI)*`.

---

## `services/netlist_parser.py`

### Supported Formats

**Xpedition `.asc` format:**
```
*PSTXNET
PSTXPRT 'U1' 'FPGA_TOP'
NET 'VCC_3P3' 'U1.VCC' 'U2.VCC' 'C1.+'
NET 'GND' 'U1.GND' 'U2.GND' 'C1.-'
```

**Xpedition CSV format:**
```
RefDes,PinNumber,NetName,SignalName
U1,VCC,VCC_3P3,VCC_3P3
```

**OrCAD format:**
```
.components
U1 FPGA
.nets
VCC_3P3 U1.VCC U2.VCC
```

### Output Structure

```python
class ParsedNetlist(BaseModel):
    components: Dict[str, str]      # {RefDes: PartName}
    nets: Dict[str, List[str]]      # {NetName: [RefDes.PinNum, ...]}
    power_nets: Set[str]            # nets matching VCC/VDD/PWR/+* patterns
    ground_nets: Set[str]           # nets matching GND/AGND/DGND patterns
```

Power and ground classification uses a regex: `r"^(VCC|VDD|PWR|AVDD|DVDD|\+[\d.]+V)"` and `r"^(GND|AGND|DGND|PGND|VSS|EARTH)"`. Everything else is a signal net.

---

## `services/drc_rules_engine.py` — The 13 Rules

### Connectivity Rules (DRC-001 to DRC-005)

**DRC-001 — Unconnected Power Pins** (Error)
Any net containing a power pin (`VCC`, `VDD`, etc.) that connects to fewer than 2 nodes. A power pin that connects to nothing means the component won't function.

**DRC-002 — Floating Net** (Error)
Nets with only one endpoint (single connection). Indicates an incomplete schematic capture.

**DRC-003 — High Fan-out Net** (Warning)
Nets with more than 20 endpoints. High fan-out can cause signal integrity issues. Threshold is configurable in the engine.

**DRC-004 — Missing Ground Return** (Error)
Any component (U*, Q*) that has no pin connected to any ground net. Every IC needs a ground return path.

**DRC-005 — Power Net Cross-connection** (Warning)
A single net that appears to connect multiple different voltage domains (e.g. VCC_3P3 and VCC_1P8 both connected to the same net name with mixed voltage hints in the name). Detected by looking for voltage hints in net names attached to the same component.

### Power Rules (DRC-006 to DRC-009)

**DRC-006 — Non-standard Power Net Naming** (Info)
Power nets that don't follow the naming convention (VCC/VDD prefix + voltage, e.g. `VCC_3P3`, `VDD_1P8`). Non-standard names make cross-referencing with the SI/PI design rules harder.

**DRC-007 — Missing Decoupling** (Warning)
Any VCC/VDD net that doesn't have at least one capacitor (`C*` ref-des) connected. Detected by checking whether any node on a power net has a `C` ref-des prefix.

**DRC-008 — Ground Plane Net** (Info)
Checks that at least one net is named `GND` (not just `DGND` or `AGND`). Most layout tools require a primary `GND` net for plane assignment.

**DRC-009 — Power Rail Naming Consistency** (Warning)
If both `VCC_3P3` and `VCC_3V3` exist as separate nets, they likely represent the same rail with inconsistent naming — a common schematic error.

### Space Compliance Rules (DRC-010 to DRC-013)

**DRC-010 — Radiation Protection Pin** (Warning)
For any component with "RAD" or "SEP" in its part name (radiation-hardened component), checks that there's an explicit radiation protection net connected (net named `RAD_*` or similar). Some rad-hard components have special protection pins.

**DRC-011 — Single-event Latchup Protection** (Info)
Checks that components marked as needing SEL protection have a current-limiting net annotation. This is a best-practice check, not a hard error.

**DRC-012 — Temperature Derating Net** (Info)
For power components, checks that the maximum voltage on the rail is within derating guidelines (uses voltage from net name, e.g. `VCC_5P0` implies 5.0V; at 80% derating for military components this should be ≤4.0V for a 5V-rated part).

**DRC-013 — Differential Pair Integrity** (Warning)
Checks that for every `_P` net there exists a corresponding `_N` net (and vice versa). Unpaired differential signals indicate incomplete schematic capture.

### Report Building (`_build_report`)

```python
total_rules_checked = 13
pass_count = max(total_rules_checked - len(set(v.rule_id for v in violations)), 0)
```

`overall_status`:
- Any `Error` → `"FAIL"`
- Any `Warning` but no `Error` → `"WARNING"`
- Only `Info` or none → `"PASS"`

---

## `services/drc_ai_checker.py`

Runs after deterministic rules. Sends the netlist summary (component list + net topology) to the LLM and asks for architectural observations that deterministic rules can't detect.

**What it looks for:**
- Unusual net topologies (e.g. output driving output without explicit isolation)
- Missing or suspicious power sequencing signals
- High-speed nets with inadequate termination (inferred from component types)
- Clock net fan-out concerns

**AI violations** have `ai_generated = True` in the schema and are tagged `*(AI)*` in the Markdown export. Engineers should treat AI violations as advisory — they may have false positives.

**Failure handling:** If the AI call fails (API key missing, network error), the DRC report is still returned with the deterministic results. The AI failure is logged as WARNING in `server.log` but not surfaced as a 503/502 to the client.

---

## Frontend — `pages/SchematicDrc.jsx`

**Workflow:**
1. Upload zone (accepts `.asc`, `.csv`, `.net` netlist files)
2. "Parse Only" button → shows netlist summary (component count, net count, power/ground nets)
3. "Run DRC" button → full analysis → shows report
4. Report sections: Summary counters, Violations list (filterable by severity/category)
5. Export buttons: "Export CSV" and "Export Markdown"

**Violation display:**
- Severity icon (🔴 Error, 🟡 Warning, 🔵 Info)
- Rule ID badge
- Category badge
- Message text
- Expandable "Recommendation" section
- Affected nets/components listed as tags
- AI-generated violations have a special "AI" badge
