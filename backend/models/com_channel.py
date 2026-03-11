"""Pydantic schemas for COM Channel Analysis (Phase 5)."""
from enum import Enum
from typing import List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class SegmentType(str, Enum):
    PCB_trace = "PCB_trace"
    connector = "connector"
    via = "via"
    cable = "cable"
    package = "package"


class Modulation(str, Enum):
    NRZ = "NRZ"
    PAM4 = "PAM4"


class ChannelSegment(BaseModel):
    label: str
    type: SegmentType
    length_mm: float = Field(ge=0, description="Segment length in mm")
    impedance_ohm: float = Field(default=100.0, description="Characteristic impedance (Ω)")
    loss_db_per_inch: float = Field(default=0.5, description="Loss at Nyquist (dB/inch)")
    dielectric_constant: float = Field(default=4.0, ge=1.0)
    loss_tangent: float = Field(default=0.02, ge=0.0)


class TxParams(BaseModel):
    swing_mv: float = Field(default=800.0, description="TX differential swing (mV)")
    de_emphasis_db: float = Field(default=3.5, description="De-emphasis / pre-cursor (dB)")
    pre_cursor_taps: int = Field(default=1)


class RxParams(BaseModel):
    ctle_peaking_db: float = Field(default=6.0, description="CTLE peaking (dB)")
    dfe_taps: int = Field(default=1, ge=0)
    dfe_tap1_mv: float = Field(default=50.0, description="DFE tap 1 amplitude (mV)")


class ChannelModel(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex[:8])
    name: str
    data_rate_gbps: float = Field(gt=0, description="Data rate in Gbps")
    modulation: Modulation = Modulation.NRZ
    segments: List[ChannelSegment] = Field(default_factory=list)
    tx_params: TxParams = Field(default_factory=TxParams)
    rx_params: RxParams = Field(default_factory=RxParams)
    crosstalk_aggressors: List[str] = Field(
        default_factory=list,
        description="IDs of aggressor channels (for crosstalk estimation)",
    )


class COMResult(BaseModel):
    com_db: float = Field(description="Estimated Channel Operating Margin (dB)")
    passed: bool = Field(description="True if COM ≥ 3 dB")
    eye_height_mv: float = Field(description="Estimated eye height (mV)")
    eye_width_ps: float = Field(description="Estimated eye width (ps)")
    total_il_db: float = Field(description="Total insertion loss at Nyquist frequency (dB)")
    rl_db: float = Field(description="Worst-case return loss (dB)")
    warnings: List[str] = Field(default_factory=list)


class ChannelExtractionResult(BaseModel):
    """Wrapper the LLM must return."""
    channel: ChannelModel
