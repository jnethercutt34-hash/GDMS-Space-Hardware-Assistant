"""Deterministic DRC rule engine for Phase 7 — Schematic DRC.

Implements hard-coded rules that run fast without AI:
  PWR-001: Unconnected power pins
  PWR-002: Missing decoupling capacitors
  PWR-003: Power net high fan-out without filter
  GND-001: Split ground detection
  TERM-001: Unterminated high-speed nets
  CONN-001: Single-pin nets (floating signals)
  CONN-002: Unconnected component pins
  NAME-001: Net naming conventions
  SPC-001: No SEL/latch-up current limiter on CMOS power paths
  SPC-002: No watchdog timer IC
  SPC-003: No reset supervisor IC
  SPC-004: Single-point failure on power supply (no redundancy)
  SPC-005: Memory ICs without SEU/EDAC mitigation
"""
import re
from typing import Dict, List, Set

from models.schematic_drc import (
    DRCViolation,
    Netlist,
    NetlistNet,
    PinType,
    Severity,
    ViolationCategory,
)


# ---------------------------------------------------------------------------
# Space-compliance keyword patterns
# ---------------------------------------------------------------------------

# Part numbers / values that indicate a current-limiter or eFuse (SEL protection)
_SEL_LIMITER_PATTERNS = [
    re.compile(r"efuse", re.IGNORECASE),
    re.compile(r"TPS259\d", re.IGNORECASE),
    re.compile(r"LTC4364", re.IGNORECASE),
    re.compile(r"LTC4380", re.IGNORECASE),
    re.compile(r"LT4356", re.IGNORECASE),
    re.compile(r"MAX1614[56]", re.IGNORECASE),
    re.compile(r"ISL738[0-9]{2}", re.IGNORECASE),
    re.compile(r"LATCH.?UP", re.IGNORECASE),
    re.compile(r"current.?lim", re.IGNORECASE),
]

# Part numbers / values that indicate a watchdog timer
_WATCHDOG_PATTERNS = [
    re.compile(r"MAX63[0-9]{2}", re.IGNORECASE),
    re.compile(r"TPS3813", re.IGNORECASE),
    re.compile(r"LTC2926", re.IGNORECASE),
    re.compile(r"watchdog", re.IGNORECASE),
    re.compile(r"WDT", re.IGNORECASE),
]

# Part numbers / values that indicate a reset supervisor
_RESET_SUPERVISOR_PATTERNS = [
    re.compile(r"TPS370\d", re.IGNORECASE),
    re.compile(r"MCP130", re.IGNORECASE),
    re.compile(r"MAX632[0-9]", re.IGNORECASE),
    re.compile(r"ADM6316", re.IGNORECASE),
    re.compile(r"supervisor", re.IGNORECASE),
    re.compile(r"VOL.?DET", re.IGNORECASE),
    re.compile(r"\bPOR\b", re.IGNORECASE),
]

# Part numbers / values that indicate memory
_MEMORY_PATTERNS = [
    re.compile(r"\bSRAM\b", re.IGNORECASE),
    re.compile(r"\bFLASH\b", re.IGNORECASE),
    re.compile(r"\bEEPROM\b", re.IGNORECASE),
    re.compile(r"\bSDRAM\b", re.IGNORECASE),
    re.compile(r"\bDDR[0-9]?\b", re.IGNORECASE),
    re.compile(r"\bNOR\b", re.IGNORECASE),
    re.compile(r"\bNAND\b", re.IGNORECASE),
    re.compile(r"CY7C", re.IGNORECASE),
    re.compile(r"IS61", re.IGNORECASE),
    re.compile(r"M5M", re.IGNORECASE),
]

# Part numbers / values that indicate SEU/EDAC mitigation hardware
_EDAC_PATTERNS = [
    re.compile(r"EDAC", re.IGNORECASE),
    re.compile(r"\bECC\b", re.IGNORECASE),
    re.compile(r"hamming", re.IGNORECASE),
    re.compile(r"SCRUB", re.IGNORECASE),
    re.compile(r"\bTMR\b", re.IGNORECASE),
    re.compile(r"SEU.?mit", re.IGNORECASE),
]

# Voltage regulator heuristics
_VREG_PATTERNS = [
    re.compile(r"\bLDO\b", re.IGNORECASE),
    re.compile(r"\bREG\b", re.IGNORECASE),
    re.compile(r"DC.?DC", re.IGNORECASE),
    re.compile(r"\bVRM\b", re.IGNORECASE),
    re.compile(r"TPS6[0-9]{4}", re.IGNORECASE),
    re.compile(r"LM317", re.IGNORECASE),
    re.compile(r"LM723", re.IGNORECASE),
]


def _matches_any(text: str, patterns: list) -> bool:
    return any(p.search(text) for p in patterns)


def _comp_tokens(comp) -> str:
    return f"{comp.part_number} {comp.value}"

# ---------------------------------------------------------------------------
# High-speed signal name patterns
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Space-compliance keyword patterns
# ---------------------------------------------------------------------------

# Part numbers / values that indicate a current-limiter or eFuse (SEL protection)
_SEL_LIMITER_PATTERNS = [
    re.compile(r"efuse", re.IGNORECASE),
    re.compile(r"TPS259\d", re.IGNORECASE),
    re.compile(r"LTC4364", re.IGNORECASE),
    re.compile(r"LTC4380", re.IGNORECASE),
    re.compile(r"LT4356", re.IGNORECASE),
    re.compile(r"MAX1614[56]", re.IGNORECASE),
    re.compile(r"ISL738[0-9]{2}", re.IGNORECASE),
    re.compile(r"LATCH.?UP", re.IGNORECASE),
    re.compile(r"current.?lim", re.IGNORECASE),
]

# Part numbers / values that indicate a watchdog timer
_WATCHDOG_PATTERNS = [
    re.compile(r"MAX63[0-9]{2}", re.IGNORECASE),
    re.compile(r"TPS3813", re.IGNORECASE),
    re.compile(r"LTC2926", re.IGNORECASE),
    re.compile(r"watchdog", re.IGNORECASE),
    re.compile(r"WDT", re.IGNORECASE),
    re.compile(r"ISL73[0-9]{3}WDT", re.IGNORECASE),
]

# Part numbers / values that indicate a reset supervisor
_RESET_SUPERVISOR_PATTERNS = [
    re.compile(r"TPS370\d", re.IGNORECASE),
    re.compile(r"MCP130", re.IGNORECASE),
    re.compile(r"MAX632[0-9]", re.IGNORECASE),
    re.compile(r"ADM6316", re.IGNORECASE),
    re.compile(r"supervisor", re.IGNORECASE),
    re.compile(r"VOL.?DET", re.IGNORECASE),
    re.compile(r"RESET.?IC", re.IGNORECASE),
    re.compile(r"POR", re.IGNORECASE),  # Power-On Reset
]

# Part numbers / values that indicate memory
_MEMORY_PATTERNS = [
    re.compile(r"\bSRAM\b", re.IGNORECASE),
    re.compile(r"\bFLASH\b", re.IGNORECASE),
    re.compile(r"\bEEPROM\b", re.IGNORECASE),
    re.compile(r"\bSDRAM\b", re.IGNORECASE),
    re.compile(r"\bDDR[0-9]?\b", re.IGNORECASE),
    re.compile(r"\bNOR\b", re.IGNORECASE),
    re.compile(r"\bNAND\b", re.IGNORECASE),
    re.compile(r"CY7C", re.IGNORECASE),   # Cypress SRAM family
    re.compile(r"IS61", re.IGNORECASE),    # ISSI SRAM family
    re.compile(r"M5M", re.IGNORECASE),     # Renesas SRAM
]

# Part numbers / values that indicate SEU/EDAC mitigation hardware
_EDAC_PATTERNS = [
    re.compile(r"EDAC", re.IGNORECASE),
    re.compile(r"ECC", re.IGNORECASE),
    re.compile(r"hamming", re.IGNORECASE),
    re.compile(r"SCRUB", re.IGNORECASE),
    re.compile(r"TMR", re.IGNORECASE),     # Triple Modular Redundancy
    re.compile(r"SEU.?mit", re.IGNORECASE),
]

# Voltage regulator heuristics (U* components with "REG", "LDO", "DCDC", "VRM" in part or value)
_VREG_PATTERNS = [
    re.compile(r"\bLDO\b", re.IGNORECASE),
    re.compile(r"\bREG\b", re.IGNORECASE),
    re.compile(r"DC.?DC", re.IGNORECASE),
    re.compile(r"\bVRM\b", re.IGNORECASE),
    re.compile(r"TPS6[0-9]{4}", re.IGNORECASE),
    re.compile(r"LT\d{4}", re.IGNORECASE),
    re.compile(r"LM317", re.IGNORECASE),
    re.compile(r"LM723", re.IGNORECASE),
]


def _matches_any(text: str, patterns: list) -> bool:
    return any(p.search(text) for p in patterns)


def _comp_tokens(comp) -> str:
    """Concatenate part_number and value for pattern matching."""
    return f"{comp.part_number} {comp.value}"


# ---------------------------------------------------------------------------
_HIGHSPEED_PATTERNS = [
    re.compile(r"CLK", re.IGNORECASE),
    re.compile(r"_DP$", re.IGNORECASE),
    re.compile(r"_DN$", re.IGNORECASE),
    re.compile(r"_P$", re.IGNORECASE),
    re.compile(r"_N$", re.IGNORECASE),
    re.compile(r"SERDES", re.IGNORECASE),
    re.compile(r"LVDS", re.IGNORECASE),
    re.compile(r"PCIE", re.IGNORECASE),
    re.compile(r"USB", re.IGNORECASE),
    re.compile(r"SGMII", re.IGNORECASE),
    re.compile(r"GTX?[PR]", re.IGNORECASE),
]

_AUTO_NET_PATTERNS = [
    re.compile(r"^N\$", re.IGNORECASE),
    re.compile(r"^NET\d", re.IGNORECASE),
    re.compile(r"^Net-", re.IGNORECASE),
    re.compile(r"^unnamed", re.IGNORECASE),
    re.compile(r"^unconnected", re.IGNORECASE),
]

# Max fan-out before flagging a power net
_POWER_FANOUT_THRESHOLD = 20


def _is_capacitor(ref_des: str) -> bool:
    return ref_des.upper().startswith("C")


def _is_resistor(ref_des: str) -> bool:
    return ref_des.upper().startswith("R")


def _is_ferrite(ref_des: str) -> bool:
    return ref_des.upper().startswith(("FB", "L"))


def _is_ic(ref_des: str) -> bool:
    return ref_des.upper().startswith("U")


def _is_highspeed_net(name: str) -> bool:
    return any(p.search(name) for p in _HIGHSPEED_PATTERNS)


def _is_auto_named_net(name: str) -> bool:
    return any(p.search(name) for p in _AUTO_NET_PATTERNS)


def _unique_refs_on_net(net: NetlistNet) -> Set[str]:
    return {p.ref_des for p in net.pins}


# ---------------------------------------------------------------------------
# Build helper indexes
# ---------------------------------------------------------------------------

def _build_component_nets(netlist: Netlist) -> Dict[str, List[str]]:
    """Map ref_des → list of net names the component connects to."""
    comp_nets: Dict[str, List[str]] = {}
    for net in netlist.nets:
        for pin in net.pins:
            comp_nets.setdefault(pin.ref_des, []).append(net.name)
    return comp_nets


def _build_net_refs(netlist: Netlist) -> Dict[str, Set[str]]:
    """Map net_name → set of ref_des connected to it."""
    net_refs: Dict[str, Set[str]] = {}
    for net in netlist.nets:
        net_refs[net.name] = _unique_refs_on_net(net)
    return net_refs


# ---------------------------------------------------------------------------
# Individual rules
# ---------------------------------------------------------------------------

def rule_pwr_001(netlist: Netlist) -> List[DRCViolation]:
    """PWR-001: Unconnected power pins.

    Flags IC power/supply pins that are not connected to any net.
    """
    violations: List[DRCViolation] = []
    # Build set of (ref_des, pin_name/pin_number) that appear on a net
    connected: Set[tuple] = set()
    for net in netlist.nets:
        for pin in net.pins:
            connected.add((pin.ref_des, pin.pin_name, pin.pin_number))

    for comp in netlist.components:
        if not _is_ic(comp.ref_des):
            continue
        for pin in comp.pins:
            if pin.pin_type == PinType.Power:
                key = (pin.ref_des, pin.pin_name, pin.pin_number)
                if key not in connected:
                    violations.append(DRCViolation(
                        rule_id="PWR-001",
                        severity=Severity.Error,
                        category=ViolationCategory.Power,
                        message=f"Power pin {pin.pin_name or pin.pin_number} on {comp.ref_des} is not connected to any net.",
                        affected_nets=[],
                        affected_components=[comp.ref_des],
                        recommendation="Connect this power pin to the appropriate supply rail.",
                    ))
    return violations


def rule_pwr_002(netlist: Netlist) -> List[DRCViolation]:
    """PWR-002: Missing decoupling capacitors.

    For each IC, check that its power nets also have at least one capacitor
    connected (1-hop check: cap on the same net as the IC power pin).
    """
    violations: List[DRCViolation] = []
    net_refs = _build_net_refs(netlist)

    ic_refs = {c.ref_des for c in netlist.components if _is_ic(c.ref_des)}

    for net_name in netlist.power_nets:
        refs = net_refs.get(net_name, set())
        ics_on_net = refs & ic_refs
        caps_on_net = {r for r in refs if _is_capacitor(r)}

        if ics_on_net and not caps_on_net:
            violations.append(DRCViolation(
                rule_id="PWR-002",
                severity=Severity.Warning,
                category=ViolationCategory.Decoupling,
                message=f"Power net '{net_name}' supplies {sorted(ics_on_net)} but has no decoupling capacitor.",
                affected_nets=[net_name],
                affected_components=sorted(ics_on_net),
                recommendation="Add bypass/decoupling capacitor(s) close to the IC power pin(s) on this net.",
            ))
    return violations


def rule_pwr_003(netlist: Netlist) -> List[DRCViolation]:
    """PWR-003: Power net fan-out without filter.

    Flag power nets driving many components without a ferrite/inductor.
    """
    violations: List[DRCViolation] = []
    net_refs = _build_net_refs(netlist)

    for net_name in netlist.power_nets:
        refs = net_refs.get(net_name, set())
        if len(refs) > _POWER_FANOUT_THRESHOLD:
            has_filter = any(_is_ferrite(r) for r in refs)
            if not has_filter:
                violations.append(DRCViolation(
                    rule_id="PWR-003",
                    severity=Severity.Warning,
                    category=ViolationCategory.Power,
                    message=f"Power net '{net_name}' has {len(refs)} connections with no ferrite/filter.",
                    affected_nets=[net_name],
                    affected_components=sorted(refs),
                    recommendation=f"Consider adding a ferrite bead or LC filter. Fan-out > {_POWER_FANOUT_THRESHOLD} may cause noise issues.",
                ))
    return violations


def rule_gnd_001(netlist: Netlist) -> List[DRCViolation]:
    """GND-001: Split ground detection.

    Flag if multiple distinct ground net names exist — may indicate
    unintentional ground splits.
    """
    violations: List[DRCViolation] = []
    if len(netlist.ground_nets) > 1:
        violations.append(DRCViolation(
            rule_id="GND-001",
            severity=Severity.Info,
            category=ViolationCategory.Power,
            message=f"Multiple ground nets detected: {netlist.ground_nets}. Verify this is intentional (analog/digital split).",
            affected_nets=netlist.ground_nets,
            affected_components=[],
            recommendation="If this is not a deliberate analog/digital ground split, merge ground nets to avoid ground loop issues.",
        ))
    return violations


def rule_term_001(netlist: Netlist) -> List[DRCViolation]:
    """TERM-001: Unterminated high-speed nets.

    Nets with high-speed signal names that lack termination resistors.
    """
    violations: List[DRCViolation] = []
    net_refs = _build_net_refs(netlist)

    for net in netlist.nets:
        if net.name in netlist.power_nets or net.name in netlist.ground_nets:
            continue
        if not _is_highspeed_net(net.name):
            continue

        refs = net_refs.get(net.name, set())
        has_resistor = any(_is_resistor(r) for r in refs)

        if not has_resistor and len(refs) >= 2:
            violations.append(DRCViolation(
                rule_id="TERM-001",
                severity=Severity.Warning,
                category=ViolationCategory.Termination,
                message=f"High-speed net '{net.name}' has no termination resistor.",
                affected_nets=[net.name],
                affected_components=sorted(refs),
                recommendation="Add series or parallel termination resistor for signal integrity on high-speed nets.",
            ))
    return violations


def rule_conn_001(netlist: Netlist) -> List[DRCViolation]:
    """CONN-001: Single-pin nets (floating signals).

    Nets connected to only one pin — likely an error.
    """
    violations: List[DRCViolation] = []

    for net in netlist.nets:
        if net.name in netlist.power_nets or net.name in netlist.ground_nets:
            continue
        unique_refs = _unique_refs_on_net(net)
        if len(net.pins) == 1:
            violations.append(DRCViolation(
                rule_id="CONN-001",
                severity=Severity.Warning,
                category=ViolationCategory.Connectivity,
                message=f"Net '{net.name}' is connected to only one pin ({net.pins[0].ref_des}.{net.pins[0].pin_name or net.pins[0].pin_number}). Possible floating signal.",
                affected_nets=[net.name],
                affected_components=list(unique_refs),
                recommendation="Verify net connection. If intentional, add a no-connect marker.",
            ))
    return violations


def rule_conn_002(netlist: Netlist) -> List[DRCViolation]:
    """CONN-002: Unconnected component pins on ICs.

    IC pins not connected to any net and not marked NC.
    """
    violations: List[DRCViolation] = []
    # Build set of (ref_des, pin_number) on nets
    connected: Set[tuple] = set()
    for net in netlist.nets:
        for pin in net.pins:
            connected.add((pin.ref_des, pin.pin_number))
            connected.add((pin.ref_des, pin.pin_name))

    for comp in netlist.components:
        if not _is_ic(comp.ref_des):
            continue
        for pin in comp.pins:
            if pin.pin_type == PinType.NC:
                continue
            ident_num = (pin.ref_des, pin.pin_number)
            ident_name = (pin.ref_des, pin.pin_name)
            if ident_num not in connected and ident_name not in connected:
                violations.append(DRCViolation(
                    rule_id="CONN-002",
                    severity=Severity.Warning,
                    category=ViolationCategory.Connectivity,
                    message=f"Pin {pin.pin_name or pin.pin_number} on {comp.ref_des} is unconnected and not marked NC.",
                    affected_nets=[],
                    affected_components=[comp.ref_des],
                    recommendation="Connect the pin or explicitly mark it as No-Connect (NC).",
                ))
    return violations


def rule_name_001(netlist: Netlist) -> List[DRCViolation]:
    """NAME-001: Auto-generated or unnamed nets.

    Flag nets with auto-generated names (N$*, NET*, unnamed).
    """
    violations: List[DRCViolation] = []

    for net in netlist.nets:
        if _is_auto_named_net(net.name):
            unique_refs = _unique_refs_on_net(net)
            violations.append(DRCViolation(
                rule_id="NAME-001",
                severity=Severity.Info,
                category=ViolationCategory.Naming,
                message=f"Net '{net.name}' appears to be auto-generated. Consider giving it a meaningful name.",
                affected_nets=[net.name],
                affected_components=sorted(unique_refs),
                recommendation="Rename this net to reflect its function for better schematic readability.",
            ))
    return violations




# ---------------------------------------------------------------------------
# Space-compliance rules (SPC-001 ... SPC-005)
# ---------------------------------------------------------------------------

def rule_spc_001(netlist: Netlist) -> List[DRCViolation]:
    """SPC-001: No SEL/latch-up current limiter on CMOS power paths."""
    violations: List[DRCViolation] = []
    ic_refs = [c for c in netlist.components if _is_ic(c.ref_des)]
    if not ic_refs:
        return violations
    has_limiter = any(_matches_any(_comp_tokens(c), _SEL_LIMITER_PATTERNS) for c in netlist.components)
    if not has_limiter:
        violations.append(DRCViolation(
            rule_id="SPC-001",
            severity=Severity.Warning,
            category=ViolationCategory.SpaceCompliance,
            message=(
                f"Design contains {len(ic_refs)} IC(s) but no SEL current-limiter "
                "(eFuse or hot-swap controller) was detected in the component list."
            ),
            affected_nets=netlist.power_nets[:5],
            affected_components=[c.ref_des for c in ic_refs[:10]],
            recommendation=(
                "Add a current-limiting eFuse or hot-swap controller on each power rail "
                "to protect CMOS ICs from Single Event Latchup (SEL) overcurrent damage. "
                "Per MIL-STD-461 and ECSS-E-ST-10-11C, current limiters must respond "
                "within 1 ms of SEL-induced overcurrent."
            ),
        ))
    return violations


def rule_spc_002(netlist: Netlist) -> List[DRCViolation]:
    """SPC-002: No watchdog timer IC."""
    violations: List[DRCViolation] = []
    ic_refs = [c for c in netlist.components if _is_ic(c.ref_des)]
    if not ic_refs:
        return violations
    has_wdt = any(_matches_any(_comp_tokens(c), _WATCHDOG_PATTERNS) for c in netlist.components)
    if not has_wdt:
        violations.append(DRCViolation(
            rule_id="SPC-002",
            severity=Severity.Warning,
            category=ViolationCategory.SpaceCompliance,
            message=(
                f"Design contains {len(ic_refs)} IC(s) but no hardware watchdog timer "
                "was found. Space processor designs require an independent WDT."
            ),
            affected_nets=[],
            affected_components=[c.ref_des for c in ic_refs[:10]],
            recommendation=(
                "Add a dedicated hardware watchdog timer IC (e.g. MAX6369, TPS3813). "
                "The watchdog must be independent of the CPU it monitors and must reset "
                "the system if the software fails to kick it within the defined window. "
                "Required by ECSS-Q-ST-60C for radiation-tolerant designs."
            ),
        ))
    return violations


def rule_spc_003(netlist: Netlist) -> List[DRCViolation]:
    """SPC-003: No reset supervisor IC."""
    violations: List[DRCViolation] = []
    ic_refs = [c for c in netlist.components if _is_ic(c.ref_des)]
    if not ic_refs:
        return violations
    has_supervisor = any(_matches_any(_comp_tokens(c), _RESET_SUPERVISOR_PATTERNS) for c in netlist.components)
    if not has_supervisor:
        violations.append(DRCViolation(
            rule_id="SPC-003",
            severity=Severity.Info,
            category=ViolationCategory.SpaceCompliance,
            message=(
                f"No voltage supervisor / reset IC detected in {len(ic_refs)}-IC design. "
                "A reset supervisor is recommended to hold processors in reset during "
                "power rail brownouts following SEL current-limiting events."
            ),
            affected_nets=netlist.power_nets[:5],
            affected_components=[c.ref_des for c in ic_refs[:10]],
            recommendation=(
                "Add a power supervisor IC (e.g. MCP130, TPS3700, MAX6326) to assert a "
                "clean reset when supply voltage falls below the processor minimum. "
                "Prevents execution from undefined state during SEL power cycling."
            ),
        ))
    return violations


def rule_spc_004(netlist: Netlist) -> List[DRCViolation]:
    """SPC-004: Single-point failure on power supply."""
    violations: List[DRCViolation] = []
    vreg_comps = [
        c for c in netlist.components
        if _is_ic(c.ref_des) and _matches_any(_comp_tokens(c), _VREG_PATTERNS)
    ]
    if len(vreg_comps) == 1:
        violations.append(DRCViolation(
            rule_id="SPC-004",
            severity=Severity.Info,
            category=ViolationCategory.SpaceCompliance,
            message=(
                f"Only one voltage regulator ({vreg_comps[0].ref_des}) was identified. "
                "Single-regulator designs are a single-point failure for all downstream "
                "logic in a space environment."
            ),
            affected_nets=netlist.power_nets[:5],
            affected_components=[vreg_comps[0].ref_des],
            recommendation=(
                "Consider a redundant or fault-tolerant power architecture: "
                "dual-redundant regulators with OR-ing diodes/load switches, or "
                "a radiation-hardened PMIC with integrated fault management. "
                "Reference ECSS-E-ST-10-02C for system-level reliability requirements."
            ),
        ))
    return violations


def rule_spc_005(netlist: Netlist) -> List[DRCViolation]:
    """SPC-005: Memory ICs without SEU/EDAC mitigation."""
    violations: List[DRCViolation] = []
    mem_comps = [c for c in netlist.components if _matches_any(_comp_tokens(c), _MEMORY_PATTERNS)]
    if not mem_comps:
        return violations
    has_edac = any(_matches_any(_comp_tokens(c), _EDAC_PATTERNS) for c in netlist.components)
    if not has_edac:
        violations.append(DRCViolation(
            rule_id="SPC-005",
            severity=Severity.Warning,
            category=ViolationCategory.SpaceCompliance,
            message=(
                f"{len(mem_comps)} memory component(s) detected "
                f"({', '.join(c.ref_des for c in mem_comps[:5])}) "
                "but no EDAC/ECC hardware or indication was found."
            ),
            affected_nets=[],
            affected_components=[c.ref_des for c in mem_comps],
            recommendation=(
                "Implement EDAC (Error Detection and Correction) for all space memory: "
                "SECDED (Single-Error Correcting, Double-Error Detecting) at minimum. "
                "Use radiation-hardened SRAM with built-in ECC or add an external EDAC "
                "controller. Scrubbing interval must be shorter than the expected SEU "
                "accumulation time per MIL-HDBK-814."
            ),
        ))
    return violations

# ---------------------------------------------------------------------------
# Run all deterministic rules
# ---------------------------------------------------------------------------

ALL_RULES = [
    rule_pwr_001,
    rule_pwr_002,
    rule_pwr_003,
    rule_gnd_001,
    rule_term_001,
    rule_conn_001,
    rule_conn_002,
    rule_name_001,
    rule_spc_001,
    rule_spc_002,
    rule_spc_003,
    rule_spc_004,
    rule_spc_005,
]


def run_deterministic_rules(netlist: Netlist) -> List[DRCViolation]:
    """Execute all deterministic DRC rules and return combined violations."""
    violations: List[DRCViolation] = []
    for rule_fn in ALL_RULES:
        violations.extend(rule_fn(netlist))
    return violations
