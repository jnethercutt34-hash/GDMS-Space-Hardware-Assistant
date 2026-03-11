"""Pydantic schemas for the Block Diagram Builder (Phase 4)."""
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class BlockCategory(str, Enum):
    FPGA = "FPGA"
    Memory = "Memory"
    Power = "Power"
    Connector = "Connector"
    Processor = "Processor"
    Optics = "Optics"
    Custom = "Custom"


class PortDirection(str, Enum):
    IN = "IN"
    OUT = "OUT"
    BIDIR = "BIDIR"


class Port(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex[:8])
    label: str
    direction: PortDirection = PortDirection.BIDIR
    bus_width: int = 1
    interface_type: Optional[str] = Field(
        default=None,
        description="e.g. DDR4, PCIe, LVDS, SPI, Power, GPIO",
    )


class Block(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex[:8])
    label: str
    part_number: Optional[str] = Field(default=None, description="Links to Part Library")
    category: BlockCategory = BlockCategory.Custom
    x: float = 0.0
    y: float = 0.0
    ports: List[Port] = Field(default_factory=list)


class Connection(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex[:8])
    source_block_id: str
    source_port_id: str
    target_block_id: str
    target_port_id: str
    signal_name: Optional[str] = None
    net_class: Optional[str] = Field(
        default=None, description="Ties to SI/PI constraints"
    )


class BlockDiagram(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex[:8])
    name: str
    description: Optional[str] = None
    blocks: List[Block] = Field(default_factory=list)
    connections: List[Connection] = Field(default_factory=list)
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class BlockDiagramGenerationResult(BaseModel):
    """Wrapper the LLM must return."""
    diagram: BlockDiagram
