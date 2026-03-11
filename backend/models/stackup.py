"""Pydantic schemas for the PCB Stackup Designer."""
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class LayerType(str, Enum):
    SIGNAL = "Signal"
    GROUND = "Ground"
    POWER = "Power"
    MIXED = "Mixed (Signal + Power)"


class CopperWeight(str, Enum):
    HALF_OZ = "0.5 oz"
    ONE_OZ = "1 oz"
    TWO_OZ = "2 oz"


class Material(str, Enum):
    FR4_STANDARD = "FR-4 Standard (Dk≈4.2, Df≈0.02)"
    FR4_MID_LOSS = "FR-4 Mid-Loss (Dk≈3.8, Df≈0.012)"
    MEGTRON6 = "Megtron-6 (Dk≈3.4, Df≈0.004)"
    ITERA_MT40 = "I-Tera MT40 (Dk≈3.45, Df≈0.005)"
    NELCO_4000_13SI = "Nelco N4000-13SI (Dk≈3.5, Df≈0.008)"
    ROGERS_4350B = "Rogers 4350B (Dk≈3.48, Df≈0.004)"
    POLYIMIDE = "Polyimide (Dk≈3.5, Df≈0.008)"
    CUSTOM = "Custom"


class Layer(BaseModel):
    """A single layer in the PCB stackup."""
    id: str = Field(default_factory=lambda: uuid4().hex[:8])
    order: int = Field(description="Layer order from top (1 = top)")
    name: str = Field(description="e.g. 'L1 - Top Signal', 'L2 - GND'")
    layer_type: LayerType
    copper_weight: CopperWeight = CopperWeight.ONE_OZ
    dielectric_thickness_mil: float = Field(default=4.0, description="Prepreg/core thickness in mil")
    dielectric_material: Material = Material.FR4_STANDARD
    notes: str = ""


class ImpedanceTarget(BaseModel):
    """An impedance target for the stackup."""
    id: str = Field(default_factory=lambda: uuid4().hex[:8])
    interface: str = Field(description="e.g. DDR4, PCIe Gen4")
    impedance_type: str = Field(description="Single-ended or Differential")
    target_ohms: float
    tolerance_pct: float = 10.0
    trace_width_mil: float = Field(default=0, description="Calculated or user-specified")
    trace_spacing_mil: float = Field(default=0, description="For differential pairs")
    reference_layer: str = Field(default="", description="Which ground/power layer")
    signal_layer: str = Field(default="", description="Which signal layer")


class Stackup(BaseModel):
    """Complete PCB stackup definition."""
    id: str = Field(default_factory=lambda: uuid4().hex[:8])
    name: str = Field(default="Untitled Stackup")
    description: str = ""
    layer_count: int = Field(default=8)
    total_thickness_mil: float = Field(default=0, description="Computed total")
    layers: List[Layer] = Field(default_factory=list)
    impedance_targets: List[ImpedanceTarget] = Field(default_factory=list)
    board_material: Material = Material.FR4_STANDARD
    diagram_id: Optional[str] = Field(default=None, description="Linked block diagram ID")
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class StackupSuggestion(BaseModel):
    """AI/rule-based suggestion for the stackup."""
    category: str = Field(description="e.g. 'Layer Count', 'Material', 'Impedance'")
    message: str
    severity: str = Field(default="Recommendation", description="Requirement / Recommendation / Info")
    related_interface: str = ""


class StackupAnalysisResult(BaseModel):
    """Result of analyzing a stackup against architecture needs."""
    suggestions: List[StackupSuggestion] = Field(default_factory=list)
    recommended_layer_count: int = 0
    interfaces_detected: List[str] = Field(default_factory=list)
    impedance_targets: List[ImpedanceTarget] = Field(default_factory=list)
