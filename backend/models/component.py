"""Pydantic schemas for the Xpedition Databook component record."""
from typing import List, Optional

from pydantic import BaseModel, Field


class ComponentData(BaseModel):
    """Represents one row in the Xpedition Databook parameter table.

    All fields except Part_Number and Manufacturer are optional because
    not every datasheet publishes every parameter. Absent values are
    represented as None and rendered as '—' in the UI.
    """

    Part_Number: str = Field(
        description="Manufacturer part number exactly as printed on the datasheet."
    )
    Manufacturer: str = Field(
        description="Full manufacturer name (e.g. 'Texas Instruments', 'Renesas')."
    )
    Value: Optional[str] = Field(
        default=None,
        description="Primary electrical value with units (e.g. '100 nF', '10 kΩ', '3.3 V').",
    )
    Tolerance: Optional[str] = Field(
        default=None,
        description="Component tolerance (e.g. '±5%', '±1%', '10%').",
    )
    Voltage_Rating: Optional[str] = Field(
        default=None,
        description="Maximum rated voltage with units (e.g. '50 V', '3.6 V').",
    )
    Package_Type: Optional[str] = Field(
        default=None,
        description="Physical package identifier (e.g. 'SOIC-8', 'QFP-100', 'CLCC-28').",
    )
    Pin_Count: Optional[str] = Field(
        default=None,
        description="Total number of pins or balls as a plain integer string (e.g. '28', '256').",
    )
    Operating_Temperature_Range: Optional[str] = Field(
        default=None,
        description=(
            "Operating temperature range as a min/max string with units "
            "(e.g. '-55 to +125 C', '0 to +70 C', '-40 to +85 C'). "
            "Critical for space/defense grading: commercial (0-70C), "
            "industrial (-40-85C), military/space (-55 to +125C)."
        ),
    )
    Thermal_Resistance: Optional[str] = Field(
        default=None,
        description="Junction-to-ambient thermal resistance with units (e.g. '125 C/W', '45.3 C/W').",
    )
    Radiation_TID: Optional[str] = Field(
        default=None,
        description=(
            "Total Ionizing Dose (TID) rating with units "
            "(e.g. '100 krad(Si)', '300 krad(Si)', '> 1 Mrad(Si)'). "
            "Required for space qualification; omit if not stated in the datasheet."
        ),
    )
    Radiation_SEL_Threshold: Optional[str] = Field(
        default=None,
        description=(
            "Single Event Latchup (SEL) LET threshold with units "
            "(e.g. 'SEL immune to 80 MeV·cm²/mg', '> 75 MeV·cm²/mg', 'SEL-free'). "
            "Devices with SEL LET < 37 MeV·cm²/mg are unsuitable for unprotected space use."
        ),
    )
    Radiation_SEU_Rate: Optional[str] = Field(
        default=None,
        description=(
            "Single Event Upset (SEU) cross-section or upset rate from radiation test data "
            "(e.g. '1e-8 errors/bit/day in GEO orbit', 'σ = 4×10⁻¹⁴ cm²/bit @ 60 MeV·cm²/mg'). "
            "Used for system-level error budget calculations."
        ),
    )
    Summary: Optional[str] = Field(
        default=None,
        description=(
            "One concise sentence describing what this component is and its primary use case "
            "(e.g. 'Low-dropout 3.3 V LDO regulator designed for battery-powered aerospace systems.')."
        ),
    )


class ComponentExtractionResult(BaseModel):
    """Wrapper the LLM must return — a JSON object containing the components list."""

    components: List[ComponentData] = Field(
        description="Array of all distinct components found in the datasheet."
    )
