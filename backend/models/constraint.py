"""Pydantic schemas for the SI/PI Constraint Editor (Phase 3)."""
from typing import List, Optional

from pydantic import BaseModel, Field


class ConstraintRule(BaseModel):
    """A single SI/PI design constraint extracted from a datasheet."""

    Signal_Class: str = Field(
        description=(
            "Signal class or net group this rule applies to "
            "(e.g. 'DDR4_DQ', 'LVDS_CLK', 'PCIE_TX', 'Power_Rail_3V3')."
        )
    )
    Rule_Type: str = Field(
        description=(
            "Type of constraint. One of: 'Impedance', 'Propagation_Delay', "
            "'Skew', 'Rise_Time', 'Fall_Time', 'Voltage_Level', 'Spacing', "
            "'Max_Length', 'Differential_Pair', 'Overshoot', 'Undershoot', "
            "'Crosstalk', 'Other'."
        )
    )
    Min: Optional[str] = Field(
        default=None,
        description="Minimum value with units (e.g. '85 Ω', '0.3 ns').",
    )
    Typ: Optional[str] = Field(
        default=None,
        description="Typical/nominal value with units (e.g. '100 Ω', '1.2 V').",
    )
    Max: Optional[str] = Field(
        default=None,
        description="Maximum value with units (e.g. '115 Ω', '5 mil').",
    )
    Unit: Optional[str] = Field(
        default=None,
        description="Unit of measure if not embedded in Min/Typ/Max (e.g. 'Ω', 'ns', 'mil', 'V').",
    )
    Source_Page: Optional[str] = Field(
        default=None,
        description="Datasheet page number or section where this rule was found.",
    )
    Notes: Optional[str] = Field(
        default=None,
        description="Additional context — conditions, temperature range, test setup, etc.",
    )


class ConstraintExtractionResult(BaseModel):
    """Wrapper the LLM must return — a JSON object containing the constraints list."""

    constraints: List[ConstraintRule] = Field(
        description="Array of all SI/PI constraint rules found in the datasheet."
    )
