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
    Thermal_Resistance: Optional[str] = Field(
        default=None,
        description="Junction-to-ambient thermal resistance with units (e.g. '125 °C/W', '45.3 °C/W').",
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
