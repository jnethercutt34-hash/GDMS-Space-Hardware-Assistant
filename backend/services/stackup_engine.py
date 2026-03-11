"""Stackup design engine — templates, analysis, and impedance estimation.

Provides:
  - Common stackup templates (4/6/8/10/12/14/16 layer)
  - Architecture-aware analysis (reads block diagram interfaces)
  - Impedance estimation (microstrip / stripline)
  - Rule-based suggestions for layer count, material, and routing
"""
import json
import math
import os
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from models.stackup import (
    CopperWeight,
    ImpedanceTarget,
    Layer,
    LayerType,
    Material,
    Stackup,
    StackupAnalysisResult,
    StackupSuggestion,
)

# ---------------------------------------------------------------------------
# Persistence (JSON file backed, same pattern as block_diagram_store)
# ---------------------------------------------------------------------------

_STORE_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "stackups.json")
_lock = threading.Lock()


def _load_all() -> List[Dict[str, Any]]:
    if not os.path.exists(_STORE_PATH):
        return []
    with open(_STORE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_all(stackups: List[Dict[str, Any]]) -> None:
    os.makedirs(os.path.dirname(_STORE_PATH), exist_ok=True)
    with open(_STORE_PATH, "w", encoding="utf-8") as f:
        json.dump(stackups, f, indent=2, ensure_ascii=False)


def list_stackups() -> List[Dict[str, Any]]:
    return _load_all()


def get_stackup(stackup_id: str) -> Optional[Dict[str, Any]]:
    for s in _load_all():
        if s.get("id") == stackup_id:
            return s
    return None


def save_stackup(stackup: Dict[str, Any]) -> Dict[str, Any]:
    with _lock:
        all_s = _load_all()
        # Update if exists, else append
        found = False
        for i, s in enumerate(all_s):
            if s.get("id") == stackup.get("id"):
                stackup["updated_at"] = datetime.now(timezone.utc).isoformat()
                stackup.setdefault("created_at", s.get("created_at"))
                all_s[i] = stackup
                found = True
                break
        if not found:
            all_s.append(stackup)
        _save_all(all_s)
    return stackup


def delete_stackup(stackup_id: str) -> bool:
    with _lock:
        all_s = _load_all()
        new = [s for s in all_s if s.get("id") != stackup_id]
        if len(new) == len(all_s):
            return False
        _save_all(new)
    return True


# ---------------------------------------------------------------------------
# Stackup Templates
# ---------------------------------------------------------------------------

def _layer(order, name, ltype, cu="1 oz", diel=4.0, mat=Material.FR4_STANDARD, notes=""):
    return Layer(
        id=uuid4().hex[:8], order=order, name=name, layer_type=ltype,
        copper_weight=CopperWeight(cu), dielectric_thickness_mil=diel,
        dielectric_material=mat, notes=notes,
    )


TEMPLATES: Dict[int, Dict[str, Any]] = {
    4: {
        "name": "4-Layer Standard",
        "description": "Minimum viable stackup for simple designs. Top and bottom signal, two inner reference planes.",
        "layers": [
            _layer(1, "L1 — Top Signal", LayerType.SIGNAL, notes="Component side, high-speed routing preferred"),
            _layer(2, "L2 — Ground", LayerType.GROUND, notes="Primary reference plane for L1"),
            _layer(3, "L3 — Power", LayerType.POWER, notes="Power plane, reference for L4"),
            _layer(4, "L4 — Bottom Signal", LayerType.SIGNAL, notes="Secondary signal layer"),
        ],
    },
    6: {
        "name": "6-Layer Signal-Plane-Signal",
        "description": "Good balance for moderate complexity. Two dedicated ground planes, one power plane, and signal routing on three layers.",
        "layers": [
            _layer(1, "L1 — Top Signal", LayerType.SIGNAL, notes="High-speed, microstrip"),
            _layer(2, "L2 — Ground", LayerType.GROUND, notes="Reference plane for L1"),
            _layer(3, "L3 — Signal (inner)", LayerType.SIGNAL, diel=5.0, notes="Stripline, clock/critical signals"),
            _layer(4, "L4 — Power", LayerType.POWER, diel=5.0, notes="Power plane, reference for L3/L5"),
            _layer(5, "L5 — Ground", LayerType.GROUND, notes="Reference for L6"),
            _layer(6, "L6 — Bottom Signal", LayerType.SIGNAL, notes="Low-speed, microstrip"),
        ],
    },
    8: {
        "name": "8-Layer High-Speed",
        "description": "Standard for designs with DDR4 + one high-speed serial interface. Every signal layer has an adjacent ground plane.",
        "layers": [
            _layer(1, "L1 — Top Signal", LayerType.SIGNAL, notes="High-speed, microstrip"),
            _layer(2, "L2 — Ground", LayerType.GROUND, notes="Reference for L1"),
            _layer(3, "L3 — Signal", LayerType.SIGNAL, diel=5.0, notes="DDR4 data, stripline"),
            _layer(4, "L4 — Power (Core)", LayerType.POWER, diel=10.0, notes="Core power plane"),
            _layer(5, "L5 — Ground", LayerType.GROUND, diel=10.0, notes="Reference for L3 & L6"),
            _layer(6, "L6 — Signal", LayerType.SIGNAL, diel=5.0, notes="PCIe / high-speed serial, stripline"),
            _layer(7, "L7 — Ground", LayerType.GROUND, notes="Reference for L8"),
            _layer(8, "L8 — Bottom Signal", LayerType.SIGNAL, notes="Low-speed, microstrip"),
        ],
    },
    10: {
        "name": "10-Layer Multi-Interface",
        "description": "Supports DDR4 + multiple high-speed serial links. Extra signal layers with dedicated references.",
        "layers": [
            _layer(1, "L1 — Top Signal", LayerType.SIGNAL, notes="High-speed, microstrip"),
            _layer(2, "L2 — Ground", LayerType.GROUND),
            _layer(3, "L3 — Signal", LayerType.SIGNAL, diel=5.0, notes="DDR4 / LVDS"),
            _layer(4, "L4 — Ground", LayerType.GROUND, diel=5.0),
            _layer(5, "L5 — Signal", LayerType.SIGNAL, diel=4.0, notes="PCIe / SerDes"),
            _layer(6, "L6 — Power", LayerType.POWER, diel=4.0),
            _layer(7, "L7 — Signal", LayerType.SIGNAL, diel=5.0, notes="Misc routing"),
            _layer(8, "L8 — Ground", LayerType.GROUND, diel=5.0),
            _layer(9, "L9 — Power", LayerType.POWER),
            _layer(10, "L10 — Bottom Signal", LayerType.SIGNAL, notes="Low-speed, microstrip"),
        ],
    },
    12: {
        "name": "12-Layer Complex Design",
        "description": "For dense FPGA designs with DDR4, multiple PCIe lanes, and Ethernet. Optimized ground plane coverage.",
        "layers": [
            _layer(1, "L1 — Top Signal", LayerType.SIGNAL, notes="BGA breakout, high-speed"),
            _layer(2, "L2 — Ground", LayerType.GROUND),
            _layer(3, "L3 — Signal", LayerType.SIGNAL, diel=4.5, notes="DDR4 byte lanes"),
            _layer(4, "L4 — Power", LayerType.POWER, diel=4.0),
            _layer(5, "L5 — Signal", LayerType.SIGNAL, diel=4.5, notes="PCIe / 10G Ethernet"),
            _layer(6, "L6 — Ground (Core)", LayerType.GROUND, diel=10.0),
            _layer(7, "L7 — Ground", LayerType.GROUND, diel=10.0),
            _layer(8, "L8 — Signal", LayerType.SIGNAL, diel=4.5, notes="LVDS / SerDes"),
            _layer(9, "L9 — Power", LayerType.POWER, diel=4.0),
            _layer(10, "L10 — Signal", LayerType.SIGNAL, diel=4.5, notes="Low-speed control"),
            _layer(11, "L11 — Ground", LayerType.GROUND),
            _layer(12, "L12 — Bottom Signal", LayerType.SIGNAL, notes="Low-speed, microstrip"),
        ],
    },
    14: {
        "name": "14-Layer Dense FPGA",
        "description": "Dense BGA breakout with multiple power domains. Space/defense grade design with full ground pour.",
        "layers": [
            _layer(1, "L1 — Top Signal", LayerType.SIGNAL),
            _layer(2, "L2 — Ground", LayerType.GROUND),
            _layer(3, "L3 — Signal", LayerType.SIGNAL, diel=4.0),
            _layer(4, "L4 — Ground", LayerType.GROUND, diel=4.0),
            _layer(5, "L5 — Signal", LayerType.SIGNAL, diel=4.5),
            _layer(6, "L6 — Power", LayerType.POWER, diel=4.0),
            _layer(7, "L7 — Signal (Core)", LayerType.SIGNAL, diel=10.0),
            _layer(8, "L8 — Ground (Core)", LayerType.GROUND, diel=10.0),
            _layer(9, "L9 — Power", LayerType.POWER, diel=4.0),
            _layer(10, "L10 — Signal", LayerType.SIGNAL, diel=4.5),
            _layer(11, "L11 — Ground", LayerType.GROUND, diel=4.0),
            _layer(12, "L12 — Signal", LayerType.SIGNAL, diel=4.0),
            _layer(13, "L13 — Ground", LayerType.GROUND),
            _layer(14, "L14 — Bottom Signal", LayerType.SIGNAL),
        ],
    },
    16: {
        "name": "16-Layer High-Density",
        "description": "Maximum layer count template. Multiple power domains, dense BGA fanout, backplane-grade designs.",
        "layers": [
            _layer(1, "L1 — Top Signal", LayerType.SIGNAL),
            _layer(2, "L2 — Ground", LayerType.GROUND),
            _layer(3, "L3 — Signal", LayerType.SIGNAL, diel=4.0),
            _layer(4, "L4 — Power", LayerType.POWER, diel=4.0),
            _layer(5, "L5 — Signal", LayerType.SIGNAL, diel=4.5),
            _layer(6, "L6 — Ground", LayerType.GROUND, diel=4.0),
            _layer(7, "L7 — Signal", LayerType.SIGNAL, diel=4.5),
            _layer(8, "L8 — Power (Core)", LayerType.POWER, diel=10.0),
            _layer(9, "L9 — Ground (Core)", LayerType.GROUND, diel=10.0),
            _layer(10, "L10 — Signal", LayerType.SIGNAL, diel=4.5),
            _layer(11, "L11 — Power", LayerType.POWER, diel=4.0),
            _layer(12, "L12 — Signal", LayerType.SIGNAL, diel=4.5),
            _layer(13, "L13 — Ground", LayerType.GROUND, diel=4.0),
            _layer(14, "L14 — Signal", LayerType.SIGNAL, diel=4.0),
            _layer(15, "L15 — Ground", LayerType.GROUND),
            _layer(16, "L16 — Bottom Signal", LayerType.SIGNAL),
        ],
    },
}


def get_template(layer_count: int) -> Optional[Dict[str, Any]]:
    tpl = TEMPLATES.get(layer_count)
    if not tpl:
        return None
    stackup = Stackup(
        name=tpl["name"],
        description=tpl["description"],
        layer_count=layer_count,
        layers=tpl["layers"],
    )
    stackup.total_thickness_mil = _compute_total_thickness(tpl["layers"])
    return stackup.model_dump()


def get_available_templates() -> List[Dict[str, Any]]:
    result = []
    for lc, tpl in sorted(TEMPLATES.items()):
        result.append({
            "layer_count": lc,
            "name": tpl["name"],
            "description": tpl["description"],
        })
    return result


# ---------------------------------------------------------------------------
# Architecture Analysis — read block diagram to suggest stackup
# ---------------------------------------------------------------------------

# Interface → requirements mapping
INTERFACE_REQUIREMENTS = {
    "DDR4": {
        "min_signal_layers": 2, "needs_ground_ref": True,
        "impedance": [
            {"type": "Single-ended", "target": 40, "tolerance": 10, "group": "DQ/DQS/DM"},
            {"type": "Differential", "target": 80, "tolerance": 10, "group": "CLK"},
        ],
        "material_min": "FR-4 Standard",
        "routing_note": "Route DDR4 on stripline layers adjacent to ground plane",
    },
    "DDR5": {
        "min_signal_layers": 3, "needs_ground_ref": True,
        "impedance": [
            {"type": "Single-ended", "target": 40, "tolerance": 10, "group": "DQ/DQS"},
            {"type": "Differential", "target": 80, "tolerance": 10, "group": "CLK"},
        ],
        "material_min": "FR-4 Mid-Loss",
        "routing_note": "DDR5 higher data rates may need mid-loss material",
    },
    "PCIe": {
        "min_signal_layers": 1, "needs_ground_ref": True,
        "impedance": [
            {"type": "Differential", "target": 85, "tolerance": 15, "group": "TX/RX"},
        ],
        "material_min": "FR-4 Standard",
        "routing_note": "PCIe Gen3 can route on FR-4; Gen4+ needs low-loss",
    },
    "PCIe_Gen3": {
        "min_signal_layers": 1, "needs_ground_ref": True,
        "impedance": [{"type": "Differential", "target": 85, "tolerance": 15, "group": "TX/RX"}],
        "material_min": "FR-4 Standard",
    },
    "PCIe_Gen4": {
        "min_signal_layers": 1, "needs_ground_ref": True,
        "impedance": [{"type": "Differential", "target": 85, "tolerance": 10, "group": "TX/RX"}],
        "material_min": "FR-4 Mid-Loss",
        "routing_note": "Gen4 at 16 GT/s — strongly recommend low-loss laminate",
    },
    "PCIe_Gen5": {
        "min_signal_layers": 2, "needs_ground_ref": True,
        "impedance": [{"type": "Differential", "target": 85, "tolerance": 10, "group": "TX/RX"}],
        "material_min": "Megtron-6",
        "routing_note": "Gen5 at 32 GT/s — requires low-loss laminate, tightly controlled impedance",
    },
    "USB3": {
        "min_signal_layers": 1, "needs_ground_ref": True,
        "impedance": [{"type": "Differential", "target": 90, "tolerance": 10, "group": "SuperSpeed TX/RX"}],
        "material_min": "FR-4 Standard",
    },
    "Ethernet_10G": {
        "min_signal_layers": 1, "needs_ground_ref": True,
        "impedance": [{"type": "Differential", "target": 100, "tolerance": 10, "group": "TX/RX"}],
        "material_min": "FR-4 Mid-Loss",
    },
    "LVDS": {
        "min_signal_layers": 1, "needs_ground_ref": True,
        "impedance": [{"type": "Differential", "target": 100, "tolerance": 10, "group": "Data/Clock"}],
        "material_min": "FR-4 Standard",
    },
    "SpaceWire": {
        "min_signal_layers": 1, "needs_ground_ref": True,
        "impedance": [{"type": "Differential", "target": 100, "tolerance": 10, "group": "Data/Strobe"}],
        "material_min": "FR-4 Standard",
    },
    "SpaceFibre": {
        "min_signal_layers": 1, "needs_ground_ref": True,
        "impedance": [{"type": "Differential", "target": 100, "tolerance": 10, "group": "TX/RX"}],
        "material_min": "FR-4 Mid-Loss",
    },
    "MIL-STD-1553": {
        "min_signal_layers": 1, "needs_ground_ref": False,
        "impedance": [],
        "material_min": "FR-4 Standard",
        "routing_note": "1553 is cable-based; PCB routing is board-to-connector only",
    },
    "SPI": {"min_signal_layers": 1, "needs_ground_ref": False, "impedance": [], "material_min": "FR-4 Standard"},
    "I2C": {"min_signal_layers": 1, "needs_ground_ref": False, "impedance": [], "material_min": "FR-4 Standard"},
}


def analyze_architecture(diagram_data: Optional[Dict] = None, interfaces: Optional[List[str]] = None) -> StackupAnalysisResult:
    """Analyze architecture (from diagram or explicit interface list) and suggest stackup parameters."""
    detected: List[str] = []

    # Extract interfaces from block diagram connections/ports
    if diagram_data:
        for block in diagram_data.get("blocks", []):
            for port in block.get("ports", []):
                itype = port.get("interface_type")
                if itype and itype not in detected:
                    detected.append(itype)
        # Also check connection signal names
        for conn in diagram_data.get("connections", []):
            sig = (conn.get("signal_name") or "").upper()
            for iface in INTERFACE_REQUIREMENTS:
                if iface.upper() in sig and iface not in detected:
                    detected.append(iface)

    # Merge explicit interfaces
    if interfaces:
        for iface in interfaces:
            if iface not in detected:
                detected.append(iface)

    suggestions: List[StackupSuggestion] = []
    impedance_targets: List[ImpedanceTarget] = []
    total_signal_layers = 0
    needs_low_loss = False
    highest_material = "FR-4 Standard"
    material_rank = {
        "FR-4 Standard": 0, "FR-4 Mid-Loss": 1,
        "Megtron-6": 2, "I-Tera MT40": 2,
        "Nelco N4000-13SI": 1, "Rogers 4350B": 2,
    }

    for iface in detected:
        req = INTERFACE_REQUIREMENTS.get(iface, {})
        total_signal_layers += req.get("min_signal_layers", 1)

        # Material
        mat_min = req.get("material_min", "FR-4 Standard")
        if material_rank.get(mat_min, 0) > material_rank.get(highest_material, 0):
            highest_material = mat_min

        # Impedance targets
        for imp in req.get("impedance", []):
            impedance_targets.append(ImpedanceTarget(
                interface=iface,
                impedance_type=imp["type"],
                target_ohms=imp["target"],
                tolerance_pct=imp["tolerance"],
            ))

        # Routing note
        if req.get("routing_note"):
            suggestions.append(StackupSuggestion(
                category="Routing",
                message=req["routing_note"],
                severity="Recommendation",
                related_interface=iface,
            ))

    # Determine minimum layer count
    # Rule: signal layers + at least 1 ground per 2 signal layers + 1 power
    ground_layers = max(2, math.ceil(total_signal_layers / 1.5))
    power_layers = 1 if total_signal_layers <= 4 else 2
    min_layers = total_signal_layers + ground_layers + power_layers

    # Round up to nearest even number
    if min_layers % 2 != 0:
        min_layers += 1
    # Minimum 4 layers
    min_layers = max(4, min_layers)

    # Snap to available template
    available = sorted(TEMPLATES.keys())
    recommended_count = min_layers
    for lc in available:
        if lc >= min_layers:
            recommended_count = lc
            break
    else:
        recommended_count = available[-1]

    suggestions.insert(0, StackupSuggestion(
        category="Layer Count",
        message=(
            f"Based on {len(detected)} interface(s) requiring ~{total_signal_layers} signal layers, "
            f"{ground_layers} ground planes, and {power_layers} power plane(s), "
            f"a minimum of **{recommended_count} layers** is recommended."
        ),
        severity="Recommendation",
    ))

    # Material suggestion
    if material_rank.get(highest_material, 0) >= 1:
        suggestions.append(StackupSuggestion(
            category="Material",
            message=(
                f"Your interfaces include high-speed links that benefit from "
                f"**{highest_material}** or better. Standard FR-4 (Df≈0.02) "
                f"may cause excessive insertion loss at multi-GHz frequencies."
            ),
            severity="Recommendation" if material_rank.get(highest_material, 0) == 1 else "Requirement",
        ))
    else:
        suggestions.append(StackupSuggestion(
            category="Material",
            message="Standard FR-4 should be adequate for your interface mix.",
            severity="Info",
        ))

    # Ground reference suggestion
    hs_count = sum(1 for i in detected if INTERFACE_REQUIREMENTS.get(i, {}).get("needs_ground_ref", False))
    if hs_count > 0:
        suggestions.append(StackupSuggestion(
            category="Ground Reference",
            message=(
                f"{hs_count} of your interfaces require impedance-controlled routing "
                f"adjacent to a continuous ground plane. Ensure every signal layer has "
                f"an adjacent ground (not power) reference layer."
            ),
            severity="Requirement",
        ))

    # Space/defense note
    space_ifaces = [i for i in detected if i in ("SpaceWire", "SpaceFibre", "MIL-STD-1553")]
    if space_ifaces:
        suggestions.append(StackupSuggestion(
            category="Space / Defense",
            message=(
                f"Detected space-grade interfaces ({', '.join(space_ifaces)}). "
                f"Consider polyimide base material for thermal resilience, "
                f"conformal coating compatibility, and outgassing requirements. "
                f"Verify fabricator is QPL/ITAR certified."
            ),
            severity="Recommendation",
        ))

    return StackupAnalysisResult(
        suggestions=suggestions,
        recommended_layer_count=recommended_count,
        interfaces_detected=detected,
        impedance_targets=impedance_targets,
    )


# ---------------------------------------------------------------------------
# Impedance Estimation (simplified microstrip / stripline)
# ---------------------------------------------------------------------------

def estimate_impedance_microstrip(
    trace_width_mil: float,
    dielectric_height_mil: float,
    dk: float = 4.2,
    copper_oz: float = 1.0,
) -> float:
    """Estimate single-ended microstrip impedance (IPC-2141 approximation)."""
    w = trace_width_mil
    h = dielectric_height_mil
    t = copper_oz * 1.37  # oz to mil
    # Effective width
    we = w + (t / math.pi) * (1 + math.log(2 * h / t)) if t > 0 else w
    if h <= 0 or we <= 0:
        return 0
    z0 = (87 / math.sqrt(dk + 1.41)) * math.log(5.98 * h / (0.8 * we + t))
    return round(max(z0, 0), 1)


def estimate_impedance_stripline(
    trace_width_mil: float,
    dielectric_height_mil: float,
    dk: float = 4.2,
    copper_oz: float = 1.0,
) -> float:
    """Estimate single-ended stripline impedance (simplified)."""
    w = trace_width_mil
    h = dielectric_height_mil  # distance to ONE reference plane (total separation = 2h)
    t = copper_oz * 1.37
    we = w + (t / math.pi) * (1 + math.log(4 * h / t)) if t > 0 else w
    if h <= 0 or we <= 0:
        return 0
    z0 = (60 / math.sqrt(dk)) * math.log(4 * h / (0.67 * (0.8 * we + t)))
    return round(max(z0, 0), 1)


def estimate_differential_impedance(
    se_impedance: float,
    trace_spacing_mil: float,
    dielectric_height_mil: float,
) -> float:
    """Rough differential impedance from SE impedance and coupling factor."""
    if dielectric_height_mil <= 0:
        return se_impedance * 2
    s_over_h = trace_spacing_mil / dielectric_height_mil
    # Coupling factor decreases as spacing increases
    coupling = math.exp(-2 * s_over_h) if s_over_h < 3 else 0
    z_diff = 2 * se_impedance * (1 - coupling * 0.3)
    return round(z_diff, 1)


def _compute_total_thickness(layers: list) -> float:
    """Sum up copper + dielectric thickness."""
    total = 0
    cu_thickness = {"0.5 oz": 0.7, "1 oz": 1.37, "2 oz": 2.74}
    for layer in layers:
        if isinstance(layer, Layer):
            total += cu_thickness.get(layer.copper_weight.value, 1.37)
            total += layer.dielectric_thickness_mil
        elif isinstance(layer, dict):
            total += cu_thickness.get(layer.get("copper_weight", "1 oz"), 1.37)
            total += layer.get("dielectric_thickness_mil", 4.0)
    return round(total, 1)
