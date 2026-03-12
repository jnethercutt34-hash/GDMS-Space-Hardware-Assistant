# Module: FPGA I/O Bridge

## What It Does

The FPGA I/O Bridge addresses a specific workflow pain point: when FPGA pin assignments change between the schematic tool (Xpedition) and the synthesis tool (Vivado), engineers need to identify what moved and whether those moves create SI/PI problems. The module takes two CSV pinout exports, computes the delta (only signals that changed), asks the AI to assess each swap's risk, and can generate a Python automation script to apply the changes in Xpedition's I/O Designer.

---

## Files

| File | Role |
|------|------|
| `routers/fpga.py` | HTTP entry points |
| `services/csv_delta.py` | Pandas-based pin-swap computation |
| `services/fpga_risk_assessor.py` | AI SI/PI risk classification |
| `services/xpedition_io_export.py` | Xpedition I/O update script generator |
| `models/fpga.py` | Pydantic schemas (PinSwap, PinDeltaResponse) |

---

## API Endpoints

### `POST /api/compare-fpga-pins`
**Request:** `multipart/form-data` with two files:
- `baseline_csv` — the Xpedition schematic's pinout export (source of truth)
- `new_csv` — the updated Vivado pinout export (proposed changes)

**Processing:**
1. `compute_pin_delta(baseline_bytes, new_bytes)` → list of changed signals
2. If swaps found and API key is set: `assess_pin_risks(swapped_pins)` → fills `AI_Risk_Assessment` per swap
3. Return `{total_swaps: int, swapped_pins: [...]}`

**Error responses:**
- `400` — CSV parse error or missing required columns
- `503` — AI key not configured
- `502` — AI/network error

### `POST /api/export-io-script`
**Request:** `{swapped_pins: [...]}` — the array from `/compare-fpga-pins`

**Response:** Python script file download (`xpedition_pin_update.py`) that when run in Xpedition's scripting environment applies all pin reassignments.

---

## `services/csv_delta.py` — Deep Dive

### Required CSV Schema

Both CSVs must have at minimum these columns: `Signal_Name`, `Pin`, `Bank`. Additional columns are ignored.

Example Xpedition export header:
```
Signal_Name,Pin,Bank,Direction,IO_Standard
CLK_IN_P,H4,34,Input,LVDS
```

### Algorithm

```python
def compute_pin_delta(baseline_bytes, new_bytes) -> List[dict]:
```

1. Parse both CSVs with `pd.read_csv(io.BytesIO(data))`
2. Validate required columns (`REQUIRED_COLUMNS = {"Signal_Name", "Pin", "Bank"}`)
3. Strip whitespace from all three columns (common source of false mismatches)
4. **Inner join** on `Signal_Name` — only signals present in BOTH files are compared. Signals added or removed entirely are not reported (that's a different problem than a swap).
5. Filter for rows where `Pin_old != Pin_new` OR `Bank_old != Bank_new`
6. Return list of dicts with `{Signal_Name, Old_Pin, New_Pin, Old_Bank, New_Bank, AI_Risk_Assessment: None}`

**Why inner join:** If Vivado added a new signal that's not in Xpedition yet, it's not a "swap" — it's a net addition that the schematic capture team handles separately. Inner join avoids false positives.

**Whitespace normalization:** Xpedition sometimes pads fields with spaces. Without `.str.strip()`, `" H4"` != `"H4"` would create spurious swap reports.

---

## `services/fpga_risk_assessor.py` — Deep Dive

### What It Assesses

Each pin swap gets classified by SI/PI impact:
- **High Risk** — pin AND bank change; high-speed signals crossing VCCIO domains; timing skew likely
- **Medium Risk** — only bank changes; moderate I/O standard implications
- **Low Risk** — intra-bank move; negligible SI/PI impact

### How It Works

The LLM receives all swaps in one call (batch inference, not one call per swap):

```python
swap_summary = [
    {
        "Signal_Name": "CLK_IN_P",
        "Old_Pin": "H4",  "New_Pin": "G3",
        "Old_Bank": "34", "New_Bank": "35",
    },
    ...
]
```

System prompt instructs the model to return:
```json
{
  "assessments": [
    {
      "Signal_Name": "CLK_IN_P",
      "AI_Risk_Assessment": "High Risk: Clock signal crossing bank boundary..."
    }
  ]
}
```

After parsing, a `{Signal_Name: assessment}` lookup dict is built and merged back into the original swap dicts. Any swap whose Signal_Name is missing from the LLM response gets `AI_Risk_Assessment = None`.

### UI Badge Coloring

The frontend `DeltaTable.jsx` applies badge colors based on the assessment prefix:
- Starts with `"HIGH"` (case-insensitive) → red badge
- Starts with `"MEDIUM"` → yellow badge
- Anything else (Low, None) → green badge

---

## `services/xpedition_io_export.py`

Generates a self-contained Python script that uses `win32com.client` to drive Xpedition's I/O Designer and reassign pins. The script is designed to be dropped into Xpedition's scripting console and run there — it does not require the main server process.

The script includes:
- Import of `win32com.client`
- Xpedition application dispatch
- Loop over each pin swap with the new assignment
- Error handling per swap with print output

---

## Frontend — `pages/FpgaBridge.jsx`

**Workflow:**
1. `DualCsvUpload` component — two separate upload targets labeled "Baseline (Xpedition)" and "Updated (Vivado)"
2. On both files selected: POST to `/api/compare-fpga-pins`
3. Loading state shown while AI processes (can take 10-30s for large pin lists)
4. `DeltaTable` renders results: signal name, old/new pin, old/new bank, risk badge
5. Export button → POST to `/api/export-io-script` → downloads `.py` file

**`components/DeltaTable.jsx`:**
- Sortable columns
- Risk badge coloring as described above
- Empty state shown when no swaps found ("All pins match — no changes detected")
