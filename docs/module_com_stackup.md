# Module: COM Channel Analysis + PCB Stackup Designer

These two modules address the physical layer design workflow: characterizing high-speed channel loss budgets (COM) and designing the PCB layer stackup to meet those budgets.

---

## Part 1: COM Channel Analysis

### What It Does

Channel Operating Margin (COM) is the IEEE 802.3 standard metric for high-speed serial link viability. The module extracts channel parameters from PDFs (stackup reports, component datasheets), computes an estimated COM score, and exports results in formats usable by Xpedition CES and HyperLynx.

### Files

| File | Role |
|------|------|
| `routers/com.py` | HTTP endpoints |
| `services/com_extractor.py` | AI channel parameter extraction from PDF |
| `services/com_calculator.py` | Deterministic COM estimation |
| `services/com_export.py` | CES script, HyperLynx CSV, Markdown report |
| `models/com_channel.py` | ChannelModel, Segment, COMResult |

### Data Model (`models/com_channel.py`)

```python
class Segment(BaseModel):
    name: str
    segment_type: str    # "trace" | "via" | "connector" | "package"
    length_mm: float | None
    insertion_loss_db: float | None
    reflection_db: float | None
    bandwidth_ghz: float | None

class ChannelModel(BaseModel):
    name: str
    data_rate_gbps: float
    segments: List[Segment]
    tx_eq_dB: float | None    # transmitter equalization
    rx_ctle_dB: float | None  # receiver CTLE
    rx_dfe_taps: int | None   # receiver DFE taps

class COMResult(BaseModel):
    com_db: float              # COM in dB (positive = passing)
    pass_fail: str             # "PASS" | "FAIL" | "MARGINAL"
    eye_height_mV: float | None
    eye_width_ps: float | None
    total_insertion_loss_db: float
    margin_db: float
    warnings: List[str]
```

### API Endpoints

#### `POST /api/com/extract-channel`
**Request:** PDF file (datasheet or stackup report)

Extracts text via PyMuPDF, sends to `com_extractor.extract_channel_from_text()`. The AI returns a pre-populated `ChannelModel` that the engineer reviews and adjusts.

**Response:** `{filename, page_count, channel: ChannelModel}`

#### `POST /api/com/calculate`
**Body:** `{channel: ChannelModel}`

Runs `calculate_com(channel)` — deterministic, no AI.

**Response:** `{channel, result: COMResult}`

#### `POST /api/com/export`
**Body:** `{channel, result, format: "ces" | "hyperlynx" | "summary"}`

- `"ces"` → Python script for Xpedition CES with channel constraint entries
- `"hyperlynx"` → HyperLynx channel import CSV
- `"summary"` → Markdown report with COM breakdown table

### `services/com_extractor.py`

The AI is prompted to extract from the PDF:
- Data rate (Gbps)
- Per-segment: type, length, insertion loss
- Equalization settings (TX EQ, RX CTLE gain, DFE tap count)

The system prompt includes examples of how these values appear in stackup reports and device datasheets. The output is validated as a `ChannelModel`.

### `services/com_calculator.py`

**Algorithm (simplified COM per IEEE 802.3):**

1. Sum insertion loss across all segments: `IL_total = Σ segment.insertion_loss_db`
2. Apply TX equalization: `IL_eq = IL_total - tx_eq_dB`
3. Apply RX CTLE: `IL_after_ctle = IL_eq - rx_ctle_dB`
4. Estimate ISI penalty from remaining loss: `ISI = f(IL_after_ctle, data_rate)`
5. Apply DFE tap benefit: `ISI_after_dfe = ISI - dfe_benefit(rx_dfe_taps)`
6. Compute COM: `COM = eye_opening - noise_floor`

This is an analytical estimate, not a full IBIS or S-parameter simulation. For fabrication sign-off, run the actual IEEE 802.3 COM MATLAB script.

**Pass/fail thresholds:** COM ≥ 3 dB → PASS; 0–3 dB → MARGINAL; < 0 → FAIL.

---

## Part 2: PCB Stackup Designer

### What It Does

The Stackup Designer provides PCB layer stack templates for common layer counts, an impedance calculator (microstrip and stripline), architecture analysis that recommends a stackup given a set of interfaces, and CRUD persistence for saving stackup designs. Stackups can be exported as Markdown fabrication notes.

### Files

| File | Role |
|------|------|
| `routers/stackup.py` | HTTP endpoints |
| `services/stackup_engine.py` | Templates, impedance formulas, analysis, persistence |
| `models/stackup.py` | Stackup, StackupLayer, ImpedanceTarget |

### Data Model (`models/stackup.py`)

```python
class StackupLayer(BaseModel):
    order: int
    name: str                   # e.g. "TOP", "GND", "PWR", "INNER_1", "BOT"
    layer_type: str             # "signal" | "plane" | "mixed"
    copper_weight: str          # e.g. "1 oz" | "2 oz" | "0.5 oz"
    dielectric_thickness_mil: float
    dielectric_material: str    # "FR-4" | "Megtron 6" | "Rogers 4350B"
    notes: str | None

class ImpedanceTarget(BaseModel):
    interface: str
    impedance_type: str         # "single_ended" | "differential"
    target_ohms: float
    tolerance_pct: float

class Stackup(BaseModel):
    id: str | None
    name: str
    layer_count: int
    total_thickness_mil: float
    board_material: str
    layers: List[StackupLayer]
    impedance_targets: List[ImpedanceTarget]
```

### API Endpoints

#### `GET /api/stackup/templates`
Returns summary of available templates (4L, 6L, 8L, 10L, 12L, 16L layer counts).

#### `GET /api/stackup/template/{layer_count}`
Returns a full pre-defined stackup for that layer count. Templates are based on common aerospace PCB stackups (e.g. the 8-layer template uses Top-GND-SIG-PWR-GND-SIG-GND-Bot configuration).

#### `POST /api/stackup/analyze`
**Body:** `{diagram_id: str | null, interfaces: [str]}`

Analyzes a system's requirements and recommends stackup parameters:
- If `diagram_id` provided: fetches the block diagram from the store, infers interfaces from block connections
- Merges with explicitly listed interfaces
- Returns recommended layer count, plane distribution, material recommendation, impedance targets per interface

#### `POST /api/stackup/impedance`
**Body:** `{trace_width_mil, dielectric_height_mil, dk, copper_oz, trace_spacing_mil, calc_type}`

Computes single-ended and differential impedance using closed-form approximations.

**Microstrip formula (IPC-2141A):**
```
Z0 = (87 / sqrt(Er + 1.41)) * ln(5.98 * H / (0.8 * W + T))
```
Where H = dielectric height, W = trace width, T = copper thickness, Er = dielectric constant.

**Stripline formula:**
```
Z0 = (60 / sqrt(Er)) * ln(4 * B / (0.67 * pi * (0.8 * W + T)))
```

**Differential impedance:**
```
Zdiff = 2 * Z0 * (1 - 0.347 * exp(-2.9 * S / H))
```
Where S = trace spacing.

These are industry-standard IPC-2141A approximations. For tight tolerances (±5% or better), use a 2D field solver.

#### CRUD (`GET/POST /api/stackups`, `GET/DELETE /api/stackups/{id}`)
Standard CRUD backed by a JSON file (`backend/data/stackups.json`). Same threading.Lock() pattern as other stores.

#### `POST /api/stackup/export/{stackup_id}`
Generates a Markdown document with:
- Layer table (order, name, type, copper weight, dielectric thickness, material)
- Impedance targets table
- Footer with generation attribution

Suitable for attaching to a fabrication package or design review document.

### `services/stackup_engine.py`

Contains:
- Hardcoded templates for common layer counts (4, 6, 8, 10, 12, 16)
- `estimate_impedance_microstrip()`, `estimate_impedance_stripline()`, `estimate_differential_impedance()` — the IPC-2141A formulas
- `analyze_architecture(diagram_data, interfaces)` — infers stackup needs from system architecture
- CRUD functions that load/save from `backend/data/stackups.json`

**Architecture analysis logic:**
- High-speed interfaces (PCIe Gen3+, DDR4) → recommend 8+ layers, Megtron 6 or Rogers
- Mixed analog/digital → recommend separate ground plane between analog and digital sections
- Power-dense designs → recommend 2 oz copper on power planes
- RF/mmWave → recommend Rogers 4350B

---

## Frontend

### `pages/BomAnalyzer.jsx` (COM is embedded in `/constraints`)

The COM Channel Analysis is accessible from the SI/PI Constraints page. Engineers upload a PDF to extract channel parameters, review/edit the `ChannelModel`, click Calculate, and see the COM result. Export buttons for CES, HyperLynx, and Markdown are shown after calculation.

### `pages/StackupDesigner.jsx`

**Sections:**
1. **Template picker** — buttons for each layer count; clicking populates the layer table
2. **Layer table** — editable rows (name, type, copper weight, thickness, material)
3. **Impedance calculator** — form inputs + instant calculation result (no server round-trip for the formula)
4. **Architecture analysis** — select from saved block diagrams + interface checkboxes → POST to analyze endpoint
5. **Impedance targets table** — auto-populated from analysis or manually entered
6. **Save and Export** — saves to library, exports Markdown doc
