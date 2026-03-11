"""Built-in SI/PI knowledge base — interface specs and design rules.

All values are sourced from public industry standards:
  - JEDEC JESD79-4 (DDR4), JESD79-5 (DDR5)
  - PCI-SIG PCIe Base Specification 3.0, 4.0, 5.0
  - USB-IF USB 2.0, 3.2, USB4 specifications
  - IEEE 802.3 (Ethernet), IEEE 802.3bj Annex 93A (COM)
  - ANSI/TIA-644 (LVDS)
  - ECSS-E-ST-50-12C (SpaceWire), ECSS-E-ST-50-11C (SpaceFibre)
  - MIL-STD-1553B
"""
from typing import Dict, List

from models.sipi_guide import (
    DesignRule,
    InterfaceId,
    InterfaceSpec,
    RuleCategory,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _r(rule_id, iface, cat, signal_group, param, target, tol="", unit="",
       rationale="", spec="", severity="Required"):
    return DesignRule(
        rule_id=rule_id, interface=iface, category=cat,
        signal_group=signal_group, parameter=param, target=target,
        tolerance=tol, unit=unit, rationale=rationale,
        spec_source=spec, severity=severity,
    )


# ===================================================================
# DDR4
# ===================================================================

_DDR4_RULES: List[DesignRule] = [
    _r("DDR4-IMP-001", "DDR4", RuleCategory.Impedance, "DQ / DQS / DM",
       "Single-ended impedance", "40", "±10%", "Ω",
       "JEDEC specifies 40Ω nominal driver impedance for data signals. PCB trace impedance must match.",
       "JEDEC JESD79-4"),
    _r("DDR4-IMP-002", "DDR4", RuleCategory.Impedance, "CLK / CLK#",
       "Differential impedance", "80", "±10%", "Ω",
       "Clock is differential; 80Ω diff impedance = 2× 40Ω SE.",
       "JEDEC JESD79-4"),
    _r("DDR4-IMP-003", "DDR4", RuleCategory.Impedance, "ADDR / CMD / CTL",
       "Single-ended impedance", "40", "±10%", "Ω",
       "Address/command/control bus driven by controller; match to 40Ω.",
       "JEDEC JESD79-4"),
    _r("DDR4-LEN-001", "DDR4", RuleCategory.LengthMatch, "DQ to DQS (byte lane)",
       "Intra-byte-lane length match", "±25", "", "mil",
       "DQ bits must arrive within the DQS strobe window. Tight matching within each byte lane is critical.",
       "JEDEC JESD79-4"),
    _r("DDR4-LEN-002", "DDR4", RuleCategory.LengthMatch, "CLK to ADDR/CMD group",
       "CLK-to-address group match", "±100", "", "mil",
       "Address/command signals are captured on clock edge; looser match than data but still important.",
       "JEDEC JESD79-4"),
    _r("DDR4-LEN-003", "DDR4", RuleCategory.LengthMatch, "CLK+/CLK−",
       "Intra-pair skew (differential)", "±5", "", "mil",
       "Differential clock pair must be tightly matched to minimize common-mode noise.",
       "JEDEC JESD79-4"),
    _r("DDR4-SPC-001", "DDR4", RuleCategory.Spacing, "DQ / ADDR",
       "Minimum trace spacing", "3× trace width", "", "",
       "3W rule minimum to limit near-end and far-end crosstalk between adjacent DDR signals.",
       "Industry best practice", "Recommended"),
    _r("DDR4-SPC-002", "DDR4", RuleCategory.Spacing, "DQ byte lanes",
       "Inter-byte-lane spacing", "4× trace width", "", "",
       "Greater spacing between byte lanes reduces inter-lane crosstalk.",
       "Industry best practice", "Recommended"),
    _r("DDR4-VIA-001", "DDR4", RuleCategory.Via, "All DDR4 signals",
       "Maximum vias per signal", "2", "", "vias",
       "Each via adds ~0.3–0.5 nH inductance and impedance discontinuity. Minimize layer transitions.",
       "Industry best practice", "Recommended"),
    _r("DDR4-VIA-002", "DDR4", RuleCategory.Via, "All DDR4 signals",
       "Via stub length", "<10", "", "mil",
       "Via stubs at DDR4 data rates (1.2–1.6 GHz fundamental) can create resonance. Back-drill or use blind vias if stub > 10 mil.",
       "Industry best practice", "Advisory"),
    _r("DDR4-TERM-001", "DDR4", RuleCategory.Termination, "DQ / DQS",
       "On-die termination (ODT)", "RTT_NOM = 60Ω or 120Ω", "", "",
       "DDR4 uses on-die termination. Ensure ODT is configured in controller firmware. No external resistors needed for DQ.",
       "JEDEC JESD79-4"),
    _r("DDR4-TERM-002", "DDR4", RuleCategory.Termination, "CLK",
       "Clock termination", "Center-tap Thevenin or ODT", "", "",
       "Some designs use VTT center-tap termination on clock for cleaner eye.",
       "Industry best practice", "Recommended"),
    _r("DDR4-DECOUP-001", "DDR4", RuleCategory.Decoupling, "VDD / VDDQ / VTT",
       "Decoupling capacitors", "100nF per power pin + 10µF bulk per rail", "", "",
       "DDR4 has high transient current draw during burst writes. Place 100nF caps within 50 mil of each power pin.",
       "Industry best practice"),
    _r("DDR4-GEN-001", "DDR4", RuleCategory.General, "All",
       "Routing layers", "Route on adjacent layers to ground plane", "", "",
       "Stripline routing (sandwiched between ground planes) provides best impedance control and EMI shielding.",
       "Industry best practice", "Recommended"),
]

DDR4_SPEC = InterfaceSpec(
    id=InterfaceId.DDR4,
    name="DDR4 SDRAM",
    description="Double Data Rate 4 synchronous dynamic RAM. Parallel bus with 64-bit data width, source-synchronous clocking, and on-die termination.",
    data_rate="1.6–3.2 GT/s (DDR4-3200)",
    signaling="Single-ended data, differential clock, SSTL signaling",
    typical_use="Main memory for processors, FPGAs, SoCs",
    rules=_DDR4_RULES,
)


# ===================================================================
# PCIe Gen3
# ===================================================================

_PCIE3_RULES: List[DesignRule] = [
    _r("PCIE3-IMP-001", "PCIe_Gen3", RuleCategory.Impedance, "TX/RX pairs",
       "Differential impedance", "85", "±15%", "Ω",
       "PCI-SIG specifies 85Ω differential impedance for all PCIe lanes.",
       "PCI-SIG PCIe 3.0 Base Spec"),
    _r("PCIE3-LEN-001", "PCIe_Gen3", RuleCategory.LengthMatch, "TX+/TX− and RX+/RX−",
       "Intra-pair skew", "±5", "", "mil",
       "Tight P/N matching minimizes common-mode conversion and improves eye quality.",
       "PCI-SIG PCIe 3.0 Base Spec"),
    _r("PCIE3-LEN-002", "PCIe_Gen3", RuleCategory.LengthMatch, "REFCLK+/REFCLK−",
       "Reference clock intra-pair skew", "±2", "", "mil",
       "REFCLK is extremely sensitive to skew; tighter match than data lanes.",
       "PCI-SIG PCIe 3.0 Base Spec"),
    _r("PCIE3-SPC-001", "PCIe_Gen3", RuleCategory.Spacing, "Adjacent lanes",
       "Lane-to-lane spacing", "≥ 4× trace width (20 mil min)", "", "",
       "Far-end crosstalk between lanes degrades eye opening. Use ground guard traces on connectors.",
       "PCI-SIG PCIe 3.0 Base Spec", "Recommended"),
    _r("PCIE3-VIA-001", "PCIe_Gen3", RuleCategory.Via, "TX/RX",
       "Via stub length", "<10", "", "mil",
       "At 4 GHz Nyquist, via stubs >10 mil create resonance notch. Back-drill on thick boards.",
       "PCI-SIG PCIe 3.0 Base Spec"),
    _r("PCIE3-VIA-002", "PCIe_Gen3", RuleCategory.Via, "TX/RX",
       "Maximum vias per lane", "4", "", "vias",
       "Each via adds ~0.3 dB loss. Stay within channel loss budget.",
       "Industry best practice", "Recommended"),
    _r("PCIE3-LOSS-001", "PCIe_Gen3", RuleCategory.General, "TX/RX",
       "Max channel insertion loss at 4 GHz", "8", "", "dB",
       "Total channel IL at Nyquist must be within budget for the equalizer to recover the signal.",
       "PCI-SIG PCIe 3.0 Base Spec"),
    _r("PCIE3-TERM-001", "PCIe_Gen3", RuleCategory.Termination, "TX/RX",
       "On-chip termination", "Integrated in PHY (no external)", "", "",
       "PCIe uses CML drivers with on-chip 50Ω termination to VCC. No external resistors needed.",
       "PCI-SIG PCIe 3.0 Base Spec"),
    _r("PCIE3-AC-001", "PCIe_Gen3", RuleCategory.General, "TX",
       "AC coupling capacitors", "100nF–200nF per lane", "", "",
       "AC caps required on TX path. Place within 500 mil of transmitter. Low-ESL 0402 recommended.",
       "PCI-SIG PCIe 3.0 Base Spec"),
    _r("PCIE3-DECOUP-001", "PCIe_Gen3", RuleCategory.Decoupling, "AVDD / DVDD",
       "PHY power decoupling", "100nF + 1µF per power pin pair", "", "",
       "PCIe PHY is sensitive to supply noise. Place caps on the die side of any ferrite.",
       "Industry best practice"),
]

PCIE3_SPEC = InterfaceSpec(
    id=InterfaceId.PCIE_GEN3,
    name="PCI Express Gen3",
    description="High-speed serial interconnect at 8 GT/s per lane with 128b/130b encoding. Common for FPGAs, GPUs, NVMe storage, and bridge chips.",
    data_rate="8 GT/s per lane (≈985 MB/s per lane)",
    signaling="Differential, NRZ, 8 GT/s",
    typical_use="FPGA-to-FPGA, processor peripherals, NVMe storage",
    rules=_PCIE3_RULES,
)


# ===================================================================
# PCIe Gen4
# ===================================================================

_PCIE4_RULES: List[DesignRule] = [
    _r("PCIE4-IMP-001", "PCIe_Gen4", RuleCategory.Impedance, "TX/RX pairs",
       "Differential impedance", "85", "±10%", "Ω",
       "Tighter tolerance than Gen3 due to higher data rate. 85Ω ±10%.",
       "PCI-SIG PCIe 4.0 Base Spec"),
    _r("PCIE4-LEN-001", "PCIe_Gen4", RuleCategory.LengthMatch, "TX+/TX− and RX+/RX−",
       "Intra-pair skew", "±3", "", "mil",
       "Tighter than Gen3 — 3 mil max intra-pair skew.",
       "PCI-SIG PCIe 4.0 Base Spec"),
    _r("PCIE4-VIA-001", "PCIe_Gen4", RuleCategory.Via, "TX/RX",
       "Via stub length", "<5", "", "mil",
       "At 8 GHz Nyquist, stubs must be shorter. Back-drilling is typically mandatory on 12+ layer boards.",
       "PCI-SIG PCIe 4.0 Base Spec"),
    _r("PCIE4-LOSS-001", "PCIe_Gen4", RuleCategory.General, "TX/RX",
       "Max channel insertion loss at 8 GHz", "8", "", "dB",
       "Same dB budget as Gen3 but at 2× frequency — roughly halves allowable trace length.",
       "PCI-SIG PCIe 4.0 Base Spec"),
    _r("PCIE4-SPC-001", "PCIe_Gen4", RuleCategory.Spacing, "Adjacent lanes",
       "Lane-to-lane spacing", "≥ 5× trace width", "", "",
       "Crosstalk is more damaging at Gen4 rates. Wider spacing or ground shielding between lanes.",
       "PCI-SIG PCIe 4.0 Base Spec", "Recommended"),
    _r("PCIE4-MAT-001", "PCIe_Gen4", RuleCategory.General, "All",
       "PCB material", "Low-loss laminate (Dk ≤ 3.5, Df ≤ 0.005)", "", "",
       "Standard FR-4 may not meet loss budget at Gen4. Use Megtron-6, Panasonic R-5775, or similar.",
       "Industry best practice", "Recommended"),
    _r("PCIE4-AC-001", "PCIe_Gen4", RuleCategory.General, "TX",
       "AC coupling capacitors", "100nF, 0201 or 0402", "", "",
       "Smaller cap package = lower ESL. Place adjacent to transmitter pad.",
       "PCI-SIG PCIe 4.0 Base Spec"),
]

PCIE4_SPEC = InterfaceSpec(
    id=InterfaceId.PCIE_GEN4,
    name="PCI Express Gen4",
    description="16 GT/s per lane with NRZ signaling. Doubles Gen3 throughput. Requires careful material selection and via management.",
    data_rate="16 GT/s per lane (≈1.97 GB/s per lane)",
    signaling="Differential, NRZ, 16 GT/s",
    typical_use="High-bandwidth FPGA links, SSD storage, accelerators",
    rules=_PCIE4_RULES,
)


# ===================================================================
# USB 3.0 / 3.2 Gen1
# ===================================================================

_USB3_RULES: List[DesignRule] = [
    _r("USB3-IMP-001", "USB3", RuleCategory.Impedance, "SuperSpeed TX/RX",
       "Differential impedance", "90", "±10%", "Ω",
       "USB-IF specifies 90Ω differential for SuperSpeed pairs.",
       "USB 3.2 Specification"),
    _r("USB3-IMP-002", "USB3", RuleCategory.Impedance, "USB 2.0 D+/D−",
       "Differential impedance", "90", "±10%", "Ω",
       "Legacy USB 2.0 pair within the same connector must also be 90Ω.",
       "USB 2.0 Specification"),
    _r("USB3-LEN-001", "USB3", RuleCategory.LengthMatch, "TX+/TX− and RX+/RX−",
       "Intra-pair skew", "±5", "", "mil",
       "P/N matching for SuperSpeed differential pairs.",
       "USB 3.2 Specification"),
    _r("USB3-LEN-002", "USB3", RuleCategory.General, "SuperSpeed",
       "Maximum PCB trace length", "8", "", "inches",
       "Keep USB 3.0 SuperSpeed traces under 8 inches on PCB. Cable extends the channel.",
       "USB-IF Compliance", "Recommended"),
    _r("USB3-SPC-001", "USB3", RuleCategory.Spacing, "SS and USB2 pairs",
       "Spacing between SS and legacy pairs", "≥ 25 mil", "", "",
       "Avoid coupling between SuperSpeed and legacy USB 2.0 signals.",
       "Industry best practice", "Recommended"),
    _r("USB3-TERM-001", "USB3", RuleCategory.Termination, "SuperSpeed",
       "Termination", "On-chip (integrated in PHY)", "", "",
       "No external termination for USB 3.x. PHY handles it.",
       "USB 3.2 Specification"),
    _r("USB3-AC-001", "USB3", RuleCategory.General, "SuperSpeed TX",
       "AC coupling capacitors", "100nF per lane", "", "",
       "Required for DC blocking. Place near transmitter.",
       "USB 3.2 Specification"),
]

USB3_SPEC = InterfaceSpec(
    id=InterfaceId.USB3,
    name="USB 3.x (SuperSpeed)",
    description="5 Gbps (Gen1) to 20 Gbps (Gen2x2) serial link. Dual-simplex architecture with separate TX and RX pairs plus legacy USB 2.0 signals.",
    data_rate="5 GT/s (Gen1) / 10 GT/s (Gen2)",
    signaling="Differential, NRZ (Gen1/Gen2) or PAM3 (USB4)",
    typical_use="Peripheral connectivity, mass storage, debug interfaces",
    rules=_USB3_RULES,
)


# ===================================================================
# LVDS
# ===================================================================

_LVDS_RULES: List[DesignRule] = [
    _r("LVDS-IMP-001", "LVDS", RuleCategory.Impedance, "Data / Clock pairs",
       "Differential impedance", "100", "±10%", "Ω",
       "ANSI/TIA-644 specifies 100Ω differential impedance.",
       "ANSI/TIA-644"),
    _r("LVDS-LEN-001", "LVDS", RuleCategory.LengthMatch, "Differential pair",
       "Intra-pair skew", "±5", "", "mil",
       "Tight P/N matching maintains signal balance and reduces EMI.",
       "ANSI/TIA-644"),
    _r("LVDS-LEN-002", "LVDS", RuleCategory.LengthMatch, "Data to clock",
       "Data-to-clock length match", "±50", "", "mil",
       "Source-synchronous LVDS requires data signals to arrive within clock setup/hold window.",
       "Industry best practice", "Recommended"),
    _r("LVDS-TERM-001", "LVDS", RuleCategory.Termination, "All pairs",
       "Parallel termination at receiver", "100Ω across +/−", "", "",
       "Place 100Ω resistor as close to receiver pins as possible.",
       "ANSI/TIA-644"),
    _r("LVDS-SPC-001", "LVDS", RuleCategory.Spacing, "Adjacent pairs",
       "Pair-to-pair spacing", "≥ 3× trace width", "", "",
       "Avoid crosstalk between adjacent LVDS pairs, especially clock and data.",
       "Industry best practice", "Recommended"),
    _r("LVDS-GEN-001", "LVDS", RuleCategory.General, "All",
       "Maximum trace length", "~24 inches (600 mm)", "", "",
       "LVDS supports long runs. At higher speeds (>400 MHz), keep shorter and use low-loss materials.",
       "Industry best practice", "Advisory"),
]

LVDS_SPEC = InterfaceSpec(
    id=InterfaceId.LVDS,
    name="LVDS (Low-Voltage Differential Signaling)",
    description="Current-mode differential signaling at 350 mV swing. Common for inter-FPGA links, display interfaces, and ADC/DAC data buses in aerospace.",
    data_rate="Up to 655 Mbps (standard), multi-Gbps (FPGA LVDS)",
    signaling="Differential, current-mode, 350 mV swing",
    typical_use="FPGA I/O, serializer/deserializer, sensor interfaces",
    rules=_LVDS_RULES,
)


# ===================================================================
# SpaceWire
# ===================================================================

_SPACEWIRE_RULES: List[DesignRule] = [
    _r("SPW-IMP-001", "SpaceWire", RuleCategory.Impedance, "Data / Strobe pairs",
       "Differential impedance", "100", "±10%", "Ω",
       "ECSS-E-ST-50-12C specifies 100Ω differential.",
       "ECSS-E-ST-50-12C"),
    _r("SPW-LEN-001", "SpaceWire", RuleCategory.LengthMatch, "Differential pair",
       "Intra-pair skew", "±5", "", "mil",
       "Tight matching for data-strobe signaling scheme.",
       "ECSS-E-ST-50-12C"),
    _r("SPW-LEN-002", "SpaceWire", RuleCategory.LengthMatch, "Data pair to Strobe pair",
       "Inter-pair skew", "±50", "", "mil",
       "Data is sampled on strobe edge; keep data and strobe paths matched.",
       "ECSS-E-ST-50-12C", "Recommended"),
    _r("SPW-TERM-001", "SpaceWire", RuleCategory.Termination, "All pairs",
       "LVDS termination", "100Ω at receiver", "", "",
       "Uses standard LVDS termination scheme.",
       "ECSS-E-ST-50-12C"),
    _r("SPW-ESD-001", "SpaceWire", RuleCategory.General, "Connector interface",
       "ESD / EMI protection", "TVS diodes at connector", "", "",
       "SpaceWire cables between boxes need ESD and EMI protection per spacecraft EMC plan.",
       "ECSS-E-ST-50-12C", "Required"),
]

SPACEWIRE_SPEC = InterfaceSpec(
    id=InterfaceId.SPACEWIRE,
    name="SpaceWire",
    description="ESA/NASA standard for spacecraft on-board data handling. LVDS-based, data-strobe encoding, packet-switched network.",
    data_rate="2–400 Mbps (link rate, user selectable)",
    signaling="LVDS differential, data-strobe encoding",
    typical_use="Spacecraft bus, instrument data links, OBDH",
    rules=_SPACEWIRE_RULES,
)


# ===================================================================
# SPI
# ===================================================================

_SPI_RULES: List[DesignRule] = [
    _r("SPI-IMP-001", "SPI", RuleCategory.Impedance, "SCLK / MOSI / MISO / CS",
       "Impedance (if > 10 MHz)", "50", "±10%", "Ω",
       "At higher SPI clock rates, controlled impedance prevents ringing. Below 10 MHz, not critical.",
       "Industry best practice", "Recommended"),
    _r("SPI-LEN-001", "SPI", RuleCategory.General, "All SPI signals",
       "Maximum trace length", "6–8 inches at 50 MHz", "", "",
       "SPI is single-ended and sensitive to reflections on long stubs. Keep traces short.",
       "Industry best practice", "Recommended"),
    _r("SPI-TERM-001", "SPI", RuleCategory.Termination, "SCLK / MOSI",
       "Series termination", "22–33Ω at source", "", "",
       "At > 25 MHz, add series resistor near driver to damp reflections.",
       "Industry best practice", "Recommended"),
    _r("SPI-CS-001", "SPI", RuleCategory.General, "CS# lines",
       "Dedicated CS per slave", "One CS# per slave device", "", "",
       "Each SPI slave needs its own chip-select. Do not multiplex without careful timing analysis.",
       "Industry best practice"),
]

SPI_SPEC = InterfaceSpec(
    id=InterfaceId.SPI,
    name="SPI (Serial Peripheral Interface)",
    description="Simple 4-wire synchronous serial bus. Full-duplex, master-slave architecture. Common for ADCs, DACs, flash memory, sensors.",
    data_rate="Typically 1–100 MHz",
    signaling="Single-ended, CMOS levels",
    typical_use="ADC/DAC, configuration flash, sensor interface, FPGA boot",
    rules=_SPI_RULES,
)


# ===================================================================
# I2C
# ===================================================================

_I2C_RULES: List[DesignRule] = [
    _r("I2C-TERM-001", "I2C", RuleCategory.Termination, "SDA / SCL",
       "Pull-up resistors", "2.2kΩ–4.7kΩ to VDD", "", "",
       "I2C is open-drain — pull-ups are mandatory. Value depends on bus capacitance and speed mode.",
       "NXP I2C Specification"),
    _r("I2C-LEN-001", "I2C", RuleCategory.General, "SDA / SCL",
       "Maximum bus capacitance", "400 pF (standard/fast mode)", "", "",
       "Total bus capacitance limits trace length. ~50 pF per device + ~2 pF/inch trace.",
       "NXP I2C Specification"),
    _r("I2C-SPC-001", "I2C", RuleCategory.Spacing, "SDA / SCL",
       "Route SDA and SCL together", "Keep parallel, equal length", "", "",
       "Minimizes skew and crosstalk from external sources.",
       "Industry best practice", "Recommended"),
]

I2C_SPEC = InterfaceSpec(
    id=InterfaceId.I2C,
    name="I2C (Inter-Integrated Circuit)",
    description="Two-wire bidirectional serial bus. Open-drain with pull-ups. Used for slow control/configuration — temperature sensors, EEPROMs, PMICs.",
    data_rate="100 kHz (standard) / 400 kHz (fast) / 1 MHz (fast+) / 3.4 MHz (high-speed)",
    signaling="Open-drain, CMOS levels",
    typical_use="Housekeeping, sensor monitoring, PMIC configuration",
    rules=_I2C_RULES,
)


# ===================================================================
# MIL-STD-1553
# ===================================================================

_MIL1553_RULES: List[DesignRule] = [
    _r("1553-IMP-001", "MIL-STD-1553", RuleCategory.Impedance, "Bus A / Bus B",
       "Cable impedance", "70–85", "", "Ω",
       "MIL-STD-1553B specifies twinax cable impedance of 70–85Ω.",
       "MIL-STD-1553B"),
    _r("1553-TERM-001", "MIL-STD-1553", RuleCategory.Termination, "Bus ends",
       "Termination resistor", "70Ω ±2% at each bus end", "", "",
       "Both ends of the 1553 bus trunk must be terminated.",
       "MIL-STD-1553B"),
    _r("1553-XFMR-001", "MIL-STD-1553", RuleCategory.General, "All nodes",
       "Transformer coupling", "1:1.41 (direct) or 1:1 (stub)", "", "",
       "Isolation transformers are mandatory at each node for fault isolation.",
       "MIL-STD-1553B"),
    _r("1553-STUB-001", "MIL-STD-1553", RuleCategory.General, "Stub cables",
       "Maximum stub length", "20 ft (direct coupled) / 1 ft (transformer)", "", "",
       "Stub length is strictly limited to prevent reflections on the bus.",
       "MIL-STD-1553B"),
]

MIL1553_SPEC = InterfaceSpec(
    id=InterfaceId.MIL1553,
    name="MIL-STD-1553B",
    description="Military-standard serial data bus for avionics. Dual-redundant, transformer-coupled, deterministic command/response protocol.",
    data_rate="1 Mbps",
    signaling="Differential, transformer-coupled, Manchester II encoding",
    typical_use="Avionics bus, weapon systems, spacecraft command/telemetry",
    rules=_MIL1553_RULES,
)


# ===================================================================
# Ethernet 10G (10GBASE-KR / SFI)
# ===================================================================

_ETH10G_RULES: List[DesignRule] = [
    _r("10G-IMP-001", "Ethernet_10G", RuleCategory.Impedance, "TX/RX pairs",
       "Differential impedance", "100", "±10%", "Ω",
       "IEEE 802.3 specifies 100Ω differential for 10GBASE-KR backplane and SFI.",
       "IEEE 802.3"),
    _r("10G-LEN-001", "Ethernet_10G", RuleCategory.LengthMatch, "TX+/TX−",
       "Intra-pair skew", "±5", "", "mil",
       "Tight matching for multi-gigabit NRZ signaling.", "IEEE 802.3"),
    _r("10G-LOSS-001", "Ethernet_10G", RuleCategory.General, "TX/RX",
       "Max channel IL at 5.15 GHz", "~15 dB (KR backplane)", "", "dB",
       "10GBASE-KR has strong equalization but channel loss must stay within COM budget.",
       "IEEE 802.3 Annex 93A"),
    _r("10G-VIA-001", "Ethernet_10G", RuleCategory.Via, "TX/RX",
       "Via stub length", "<8", "", "mil",
       "Back-drill required on boards > 93 mil thick.", "Industry best practice"),
    _r("10G-MAT-001", "Ethernet_10G", RuleCategory.General, "All",
       "PCB material", "Low-loss (Df < 0.008 for long channels)", "", "",
       "For backplane traces > 10 inches, use mid-loss or low-loss laminate.",
       "Industry best practice", "Recommended"),
]

ETH10G_SPEC = InterfaceSpec(
    id=InterfaceId.ETH_10G,
    name="10 Gigabit Ethernet",
    description="10.3125 Gbps per lane (10GBASE-KR/SFI). Uses NRZ with DFE equalization. Common for backplane and SFP+ interfaces.",
    data_rate="10.3125 Gbps",
    signaling="Differential, NRZ, CML",
    typical_use="Switch fabric, backplane, SFP+ optical module interface",
    rules=_ETH10G_RULES,
)


# ===================================================================
# Registry
# ===================================================================

INTERFACE_REGISTRY: Dict[str, InterfaceSpec] = {
    InterfaceId.DDR4: DDR4_SPEC,
    InterfaceId.PCIE_GEN3: PCIE3_SPEC,
    InterfaceId.PCIE_GEN4: PCIE4_SPEC,
    InterfaceId.USB3: USB3_SPEC,
    InterfaceId.LVDS: LVDS_SPEC,
    InterfaceId.SPACEWIRE: SPACEWIRE_SPEC,
    InterfaceId.SPI: SPI_SPEC,
    InterfaceId.I2C: I2C_SPEC,
    InterfaceId.MIL1553: MIL1553_SPEC,
    InterfaceId.ETH_10G: ETH10G_SPEC,
}


def get_all_interfaces() -> List[InterfaceSpec]:
    """Return summary list (without rules) for the interface selector."""
    return [
        InterfaceSpec(
            id=spec.id, name=spec.name, description=spec.description,
            data_rate=spec.data_rate, signaling=spec.signaling,
            typical_use=spec.typical_use, rules=[],
        )
        for spec in INTERFACE_REGISTRY.values()
    ]


def get_interface(iface_id: str) -> InterfaceSpec | None:
    return INTERFACE_REGISTRY.get(iface_id)


def get_rules_for_interfaces(iface_ids: List[str]) -> List[DesignRule]:
    """Return combined rules for multiple selected interfaces."""
    rules = []
    for iid in iface_ids:
        spec = INTERFACE_REGISTRY.get(iid)
        if spec:
            rules.extend(spec.rules)
    return rules
