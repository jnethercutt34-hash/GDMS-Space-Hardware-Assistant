"""Pydantic schemas for BOM Analyzer (Phase 6)."""
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class LifecycleStatus(str, Enum):
    Active = "Active"
    NRND = "NRND"
    Obsolete = "Obsolete"
    Unknown = "Unknown"


class RadiationGrade(str, Enum):
    Commercial = "Commercial"
    MIL = "MIL"
    RadTolerant = "RadTolerant"
    RadHard = "RadHard"
    Unknown = "Unknown"


class RiskLevel(str, Enum):
    Low = "Low"
    Medium = "Medium"
    High = "High"
    Critical = "Critical"


class BOMLineItem(BaseModel):
    ref_des: str = Field(description="Reference designator (e.g. U1, R12, C3)")
    part_number: str = Field(description="Manufacturer part number")
    manufacturer: str = Field(default="Unknown")
    description: str = Field(default="")
    quantity: int = Field(default=1, ge=0)
    value: Optional[str] = Field(default=None, description="Component value (e.g. 100nF, 10kΩ)")
    package: Optional[str] = Field(default=None, description="Package/footprint (e.g. 0402, QFP-144)")
    dnp: bool = Field(default=False, description="Do Not Populate")


class AlternatePart(BaseModel):
    part_number: str
    manufacturer: str = ""
    notes: str = ""


class BOMAnalysisResult(BaseModel):
    line_item: BOMLineItem
    library_match: bool = Field(default=False, description="Found in Part Library?")
    library_part_number: Optional[str] = Field(default=None, description="Matched library part number")
    lifecycle_status: LifecycleStatus = LifecycleStatus.Unknown
    radiation_grade: RadiationGrade = RadiationGrade.Unknown
    alt_parts: List[AlternatePart] = Field(default_factory=list)
    risk_flags: List[str] = Field(default_factory=list)
    risk_level: RiskLevel = RiskLevel.Medium
    ai_assessment: Optional[str] = Field(default=None, description="AI-generated assessment text")


class BOMSummary(BaseModel):
    total_line_items: int = 0
    unique_parts: int = 0
    total_placements: int = 0
    library_matched: int = 0
    library_matched_pct: float = 0.0
    lifecycle_active: int = 0
    lifecycle_nrnd: int = 0
    lifecycle_obsolete: int = 0
    lifecycle_unknown: int = 0
    rad_commercial: int = 0
    rad_mil: int = 0
    rad_tolerant: int = 0
    rad_hard: int = 0
    rad_unknown: int = 0
    risk_critical: int = 0
    risk_high: int = 0
    risk_medium: int = 0
    risk_low: int = 0


class BOMReport(BaseModel):
    filename: str = ""
    results: List[BOMAnalysisResult] = Field(default_factory=list)
    summary: BOMSummary = Field(default_factory=BOMSummary)


class AIRiskAssessment(BaseModel):
    """Schema the LLM must return for a single part."""
    lifecycle_status: LifecycleStatus = LifecycleStatus.Unknown
    radiation_grade: RadiationGrade = RadiationGrade.Unknown
    risk_flags: List[str] = Field(default_factory=list)
    alt_parts: List[AlternatePart] = Field(default_factory=list)
    assessment: str = Field(default="", description="Brief assessment text")


class AIBatchRiskAssessment(BaseModel):
    """Wrapper for batch AI assessment."""
    assessments: List[AIRiskAssessment] = Field(default_factory=list)
