"""Pydantic schemas for the SI/PI Design Guide."""
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class InterfaceId(str, Enum):
    DDR4 = "DDR4"
    DDR5 = "DDR5"
    PCIE_GEN3 = "PCIe_Gen3"
    PCIE_GEN4 = "PCIe_Gen4"
    PCIE_GEN5 = "PCIe_Gen5"
    USB2 = "USB2"
    USB3 = "USB3"
    USB4 = "USB4"
    ETH_1G = "Ethernet_1G"
    ETH_10G = "Ethernet_10G"
    ETH_25G = "Ethernet_25G"
    LVDS = "LVDS"
    SPI = "SPI"
    I2C = "I2C"
    JTAG = "JTAG"
    UART = "UART"
    SPACEFIBRE = "SpaceFibre"
    SPACEWIRE = "SpaceWire"
    MIL1553 = "MIL-STD-1553"
    CUSTOM = "Custom"


class RuleCategory(str, Enum):
    Impedance = "Impedance"
    LengthMatch = "Length Matching"
    Spacing = "Spacing / Crosstalk"
    Via = "Via Budget"
    Termination = "Termination"
    Decoupling = "Decoupling"
    Timing = "Timing"
    General = "General"


class DesignRule(BaseModel):
    """A single SI/PI design rule or recommendation."""
    rule_id: str = Field(description="Short rule ID, e.g. DDR4-IMP-001")
    interface: str = Field(description="Interface this rule applies to")
    category: RuleCategory
    signal_group: str = Field(default="All", description="e.g. DQ, CLK, ADDR, TX/RX")
    parameter: str = Field(description="What is being constrained")
    target: str = Field(description="Target value or range")
    tolerance: str = Field(default="", description="Acceptable tolerance")
    unit: str = Field(default="")
    rationale: str = Field(default="", description="Why this matters for SI/PI")
    spec_source: str = Field(default="", description="JEDEC, IEEE, etc.")
    severity: str = Field(default="Required", description="Required / Recommended / Advisory")


class InterfaceSpec(BaseModel):
    """Full specification profile for one interface."""
    id: InterfaceId
    name: str
    description: str
    data_rate: str = Field(default="", description="e.g. '3.2 GT/s per lane'")
    signaling: str = Field(default="", description="e.g. 'Differential, NRZ'")
    typical_use: str = Field(default="")
    rules: List[DesignRule] = Field(default_factory=list)


class LossBudgetSegment(BaseModel):
    """One segment of a channel loss budget."""
    segment: str = Field(description="e.g. 'PCB Trace', 'Via', 'Connector'")
    loss_db: float = Field(description="Insertion loss in dB at Nyquist")
    notes: str = ""


class LossBudgetResult(BaseModel):
    """COM-informed loss budget for a high-speed link."""
    interface: str
    nyquist_ghz: float
    max_channel_loss_db: float = Field(description="Max IL allowed per spec/COM")
    segments: List[LossBudgetSegment] = Field(default_factory=list)
    total_loss_db: float = 0
    margin_db: float = 0
    passes: bool = True
    recommendations: List[str] = Field(default_factory=list)


class AISiPiQuestion(BaseModel):
    question: str
    interfaces: List[str] = Field(default_factory=list, description="Context: which interfaces the board has")
    board_details: str = Field(default="", description="Optional: stackup, layer count, etc.")


class AISiPiAnswer(BaseModel):
    answer: str
    referenced_rules: List[str] = Field(default_factory=list)
