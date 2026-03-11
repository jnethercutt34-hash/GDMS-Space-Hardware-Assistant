# Phase 5: COM Channel Analysis (Channel Operating Margin)

## Objective
Build a module within the GDMS Space Hardware Assistant that helps engineers model high-speed serial link channels, compute Channel Operating Margin (COM) per IEEE 802.3, and generate constraint parameters for Xpedition CES / HyperLynx. This extends the Phase 3 SI/PI Constraint Editor with quantitative link-budget analysis.

## Background
For high-speed interfaces (PCIe Gen4/5, Ethernet 25G/100G, DDR5), simple impedance and spacing rules aren't enough. Engineers need to evaluate the full channel — including insertion loss, return loss, crosstalk, ISI, and equalization — to determine if a link will close. COM is the industry-standard figure of merit. Currently this analysis is done manually in spreadsheets or expensive tools. The assistant can automate parameter extraction and COM estimation to catch issues before layout.

## Step-by-Step Implementation Plan

### Step 1: Data Model — Channel Parameters
* Create Pydantic models in `backend/models/com_channel.py`:
  - `ChannelSegment` — a piece of the channel: `label`, `type` (enum: PCB_trace, connector, via, cable, package), `length_mm`, `impedance_ohm`, `loss_db_per_inch` (at Nyquist), `dielectric_constant`, `loss_tangent`
  - `ChannelModel` — full TX→RX path: `id`, `name`, `data_rate_gbps`, `modulation` (NRZ / PAM4), `segments[]`, `tx_params` (swing, de-emphasis/pre-cursor taps), `rx_params` (CTLE peaking, DFE taps), `crosstalk_aggressors[]` (optional references to other channels)
  - `COMResult` — computed output: `com_db`, `pass` (bool, typically COM ≥ 3 dB), `eye_height_mv`, `eye_width_ps`, `ild_db` (insertion loss at Nyquist), `rl_db` (worst-case return loss), `warnings[]`

### Step 2: AI-Assisted Parameter Extraction
* Create `backend/services/com_extractor.py`
* Add endpoint `POST /api/com/extract-channel` — accepts:
  - A PDF (connector/cable datasheet, PCB stackup report, or IC datasheet with channel specs)
  - OR a JSON with known parameters for manual entry
* The AI (OpenAI-compatible) extracts:
  - S-parameter summary data (IL, RL at key frequencies)
  - Impedance targets
  - Tx/Rx equalization capabilities from IC datasheets
  - Package parasitics
* Returns a pre-populated `ChannelModel` for the engineer to review and adjust

### Step 3: COM Computation Engine
* Create `backend/services/com_calculator.py`
* Implement a simplified COM estimation based on IEEE 802.3 Annex 93A methodology:
  - **Insertion Loss (IL)**: Sum segment losses at Nyquist frequency (data_rate / 2 for NRZ, data_rate / 4 for PAM4)
  - **Insertion Loss Deviation (ILD)**: Deviation from fitted IL curve — flags impedance discontinuities
  - **Return Loss (RL)**: Worst-case across segments
  - **Crosstalk**: FEXT/NEXT contributions from aggressor channels (if provided)
  - **ISI penalty**: Estimated from IL profile
  - **Equalization benefit**: CTLE + DFE tap reduction of ISI
  - **COM = 20 * log10(signal_amplitude / noise_amplitude)** where noise includes ISI residual + crosstalk + jitter
* This is an **estimation engine**, not a full-accuracy simulator — clearly label results as "estimated COM" with recommendation to verify in HyperLynx for final signoff
* Add endpoint `POST /api/com/calculate` — accepts `ChannelModel`, returns `COMResult`

### Step 4: Xpedition / HyperLynx Export
* Create `backend/services/com_export.py`
* Add endpoint `POST /api/com/export`
* Generate:
  - **CES constraint snippet** (`.py` script): impedance, max trace length, spacing rules derived from the channel model
  - **HyperLynx channel model** (`.csv` or `.json`): segment parameters formatted for import into HyperLynx LineSim/BoardSim
  - **Summary report** (`.txt` or `.md`): human-readable channel budget with pass/fail and recommendations

### Step 5: Frontend — Channel Builder UI
* Create `frontend/src/pages/ComAnalysis.jsx` — new page, add to Navbar
* **Channel Builder** section:
  - Visual pipeline of segments (TX → pkg → via → trace → connector → trace → via → pkg → RX) rendered as a horizontal strip diagram
  - Add/remove/reorder segments
  - Per-segment parameter inputs (length, impedance, loss)
  - TX/RX EQ parameter inputs
* **AI Extract** button: upload a PDF to auto-populate
* **Calculate COM** button: calls the compute endpoint, displays:
  - COM value with pass/fail badge (green ≥ 3 dB, amber 1–3 dB, red < 1 dB)
  - Eye diagram placeholder (simple estimated eye dimensions)
  - Per-segment loss breakdown bar chart
  - Warnings list
* **Export** dropdown: CES script, HyperLynx model, summary report

### Step 6: Tests
* Create `backend/tests/test_com_channel.py`
* Test: Pydantic models, AI extraction (mocked), COM calculation (known-good cases), export generation
* Include reference test vectors:
  - Short channel (< 6" trace, NRZ 10G) → COM should be > 6 dB
  - Long channel (20" trace + 2 connectors, PAM4 56G) → COM should be marginal
* Target: 25+ tests
