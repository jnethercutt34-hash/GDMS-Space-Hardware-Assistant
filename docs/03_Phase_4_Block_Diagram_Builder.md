# Phase 4: Block Diagram Builder

## Objective
Build a module within the GDMS Space Hardware Assistant that lets an engineer visually construct or auto-generate a system-level block diagram showing major ICs, buses, power domains, and interconnects. The diagram serves as the single source of truth before schematic entry in Xpedition, and can be exported as a structured netlist seed.

## Background
Engineers typically sketch block diagrams in PowerPoint or Visio before starting schematic capture. This is error-prone — signal names drift, pin counts don't match, and the diagram becomes stale. By building the block diagram inside the assistant (backed by structured data), it stays synchronized with the Part Library and constraint data already in the tool.

## Step-by-Step Implementation Plan

### Step 1: Data Model — Block Diagram Schema
* Create Pydantic models in `backend/models/block_diagram.py`:
  - `Block` — represents a component/subsystem: `id`, `label`, `part_number` (optional, links to Part Library), `category` (enum: FPGA, Memory, Power, Connector, Processor, Optics, Custom), `x`/`y` position, `ports[]`
  - `Port` — named connection point on a block: `id`, `label`, `direction` (IN / OUT / BIDIR), `bus_width`, `interface_type` (e.g., DDR4, PCIe, LVDS, SPI, Power, GPIO)
  - `Connection` — link between two ports: `id`, `source_block_id`, `source_port_id`, `target_block_id`, `target_port_id`, `signal_name`, `net_class` (optional, ties to SI/PI constraints)
  - `BlockDiagram` — top-level container: `id`, `name`, `description`, `blocks[]`, `connections[]`, `created_at`, `updated_at`

### Step 2: Backend — CRUD + Persistence
* Create `backend/services/block_diagram_store.py` — JSON file store (similar to `part_library.py`) at `backend/data/diagrams.json`
* Create `backend/routers/block_diagram.py` with endpoints:
  - `GET /api/diagrams` — list all saved diagrams
  - `POST /api/diagrams` — create a new diagram
  - `GET /api/diagrams/{id}` — fetch a single diagram
  - `PUT /api/diagrams/{id}` — update (save block positions, connections, etc.)
  - `DELETE /api/diagrams/{id}` — delete a diagram

### Step 3: AI Auto-Generation from Datasheet / Part Library
* Create `backend/services/block_diagram_generator.py`
* Add endpoint `POST /api/diagrams/generate` — accepts either:
  - A list of part numbers (from the Part Library), OR
  - A PDF (system architecture doc or reference design)
* The AI service (OpenAI-compatible) receives the part data/extracted text and returns a structured `BlockDiagram` JSON with:
  - Blocks for each major IC
  - Inferred connections based on common interface pairings (e.g., FPGA ↔ DDR4 SDRAM, PMU → voltage rails)
  - Categorized ports with interface types
* Validate against the Pydantic model before returning

### Step 4: Frontend — Interactive Canvas
* Create `frontend/src/pages/BlockDiagram.jsx` — new page, add to Navbar
* Use a React canvas/diagramming library (recommended: **React Flow** / `reactflow`) for:
  - Draggable blocks rendered as themed cards (category icon + label + port list)
  - Ports shown as connection handles on block edges
  - Connections rendered as edges with signal name labels
  - Toolbar: Add Block, Auto-Generate (calls AI endpoint), Save, Load, Export
* Block editing panel (sidebar or modal):
  - Edit label, link to Part Library part, add/remove ports
  - Port editor: name, direction, bus width, interface type
* Connection creation by dragging between port handles
* Color-code blocks by category and connections by interface type

### Step 5: Export — Xpedition Netlist Seed
* Add endpoint `POST /api/diagrams/{id}/export-netlist`
* Create `backend/services/block_diagram_export.py`
* Generate a structured output (CSV or `.py` script) that can seed Xpedition ViewDraw with:
  - Component instances (symbols) from the diagram blocks
  - Net stubs named according to the connection signal names
  - Net class assignments for SI/PI constraint linkage
* Allow download from the frontend

### Step 6: Tests
* Create `backend/tests/test_block_diagram.py`
* Test: Pydantic model validation, CRUD operations, AI generation (mocked), export generation
* Target: 20+ tests
