"""Netlist parser for Phase 7 — Schematic DRC.

Supports:
  - Xpedition ASCII netlist (.asc)
  - Generic CSV netlist (ref_des, pin, net columns)
  - OrCAD/Allegro netlist format

Auto-classifies power and ground nets by name convention.
"""
import csv
import io
import re
from typing import Dict, List, Optional, Tuple

from models.schematic_drc import (
    Netlist,
    NetlistComponent,
    NetlistNet,
    NetlistPin,
    PinType,
)

# ---------------------------------------------------------------------------
# Power / ground net classification
# ---------------------------------------------------------------------------

_POWER_PATTERNS = [
    re.compile(r"^V(CC|DD|IN|OUT|REF|BAT|BUS|CORE|IO|AUX)", re.IGNORECASE),
    re.compile(r"^(\+\d|P\d|PWR|POWER|SUPPLY|DVDD|AVDD|PVDD)", re.IGNORECASE),
    re.compile(r"^\+\d+V", re.IGNORECASE),
    re.compile(r"^V\d+P\d+", re.IGNORECASE),  # V3P3, V1P8 etc.
]

_GROUND_PATTERNS = [
    re.compile(r"^(GND|VSS|AGND|DGND|PGND|SGND|GNDA|GNDD)", re.IGNORECASE),
    re.compile(r"^(GROUND|0V)", re.IGNORECASE),
]


def is_power_net(name: str) -> bool:
    return any(p.search(name) for p in _POWER_PATTERNS)


def is_ground_net(name: str) -> bool:
    return any(p.search(name) for p in _GROUND_PATTERNS)


def _classify_pin_type(pin_name: str, net_name: str) -> PinType:
    """Best-effort pin type classification from name heuristics."""
    pn = pin_name.upper()
    nn = net_name.upper() if net_name else ""

    if pn in ("NC", "N/C", "NO_CONNECT", "DNC"):
        return PinType.NC
    if is_ground_net(nn) or pn in ("GND", "VSS", "GNDA", "GNDD"):
        return PinType.Ground
    if is_power_net(nn) or pn in ("VCC", "VDD", "VDDIO", "VCORE", "VIN"):
        return PinType.Power
    if "CLK" in pn or "OUT" in pn or "TX" in pn or "DO" in pn or "MOSI" in pn:
        return PinType.Output
    if "IN" in pn or "RX" in pn or "DI" in pn or "MISO" in pn or "CS" in pn:
        return PinType.Input
    if "SDA" in pn or "DATA" in pn or "IO" in pn or "DQ" in pn:
        return PinType.Bidirectional
    return PinType.Unknown


# ---------------------------------------------------------------------------
# CSV netlist parser
# ---------------------------------------------------------------------------

_CSV_COLUMN_ALIASES: Dict[str, List[str]] = {
    "ref_des": ["ref_des", "refdes", "reference", "component", "ref des", "reference designator"],
    "pin_name": ["pin_name", "pin name", "pin", "signal", "function"],
    "pin_number": ["pin_number", "pin number", "pin_num", "pin no", "pin#"],
    "net": ["net", "net_name", "net name", "netname", "signal_name", "node"],
    "part_number": ["part_number", "part number", "pn", "mpn", "part", "device"],
    "value": ["value", "val"],
}


def _norm_header(h: str) -> str:
    return re.sub(r"[^a-z0-9 ]", " ", h.lower()).strip()


def _detect_csv_columns(headers: List[str]) -> Dict[str, int]:
    mapping: Dict[str, int] = {}
    normalised = [_norm_header(h) for h in headers]
    for field, aliases in _CSV_COLUMN_ALIASES.items():
        for alias in aliases:
            na = _norm_header(alias)
            for idx, nh in enumerate(normalised):
                if na == nh or na in nh:
                    if field not in mapping:
                        mapping[field] = idx
                    break
            if field in mapping:
                break
    return mapping


def parse_csv_netlist(content: str) -> Netlist:
    """Parse a generic CSV netlist.

    Expected columns: ref_des, pin_name/pin_number, net.
    Optional: part_number, value.
    """
    reader = csv.reader(io.StringIO(content))
    rows = list(reader)
    if not rows:
        raise ValueError("Netlist CSV is empty.")

    # Detect header
    mapping: Dict[str, int] = {}
    header_idx = 0
    for i, row in enumerate(rows[:5]):
        candidate = _detect_csv_columns(row)
        if len(candidate) >= 2:
            mapping = candidate
            header_idx = i
            break

    if "ref_des" not in mapping or "net" not in mapping:
        raise ValueError(
            "Could not detect netlist columns. Need at least 'Ref Des' and 'Net' columns."
        )

    # Parse rows
    components_map: Dict[str, NetlistComponent] = {}
    nets_map: Dict[str, NetlistNet] = {}

    for row in rows[header_idx + 1:]:
        if not row or all(c.strip() == "" for c in row):
            continue

        def _get(field: str, default: str = "") -> str:
            idx = mapping.get(field)
            if idx is not None and idx < len(row):
                return row[idx].strip()
            return default

        ref = _get("ref_des")
        net_name = _get("net")
        pin_name = _get("pin_name")
        pin_number = _get("pin_number")
        part_number = _get("part_number")
        value = _get("value")

        if not ref:
            continue

        pin_type = _classify_pin_type(pin_name or pin_number, net_name)

        pin = NetlistPin(
            ref_des=ref,
            pin_name=pin_name,
            pin_number=pin_number,
            pin_type=pin_type,
        )

        # Track component
        if ref not in components_map:
            components_map[ref] = NetlistComponent(
                ref_des=ref,
                part_number=part_number,
                value=value,
            )
        comp = components_map[ref]
        comp.pins.append(pin)
        if part_number and not comp.part_number:
            comp.part_number = part_number
        if value and not comp.value:
            comp.value = value

        # Track net
        if net_name:
            if net_name not in nets_map:
                nets_map[net_name] = NetlistNet(name=net_name)
            nets_map[net_name].pins.append(pin)

    return _build_netlist(components_map, nets_map)


# ---------------------------------------------------------------------------
# Xpedition ASCII netlist parser (.asc)
# ---------------------------------------------------------------------------

def parse_xpedition_asc(content: str) -> Netlist:
    """Parse Xpedition ViewDraw ASCII netlist format.

    The format has sections:
      *COMP <ref_des> <part_number>
      *PIN <pin_number> <pin_name> <net>
      ...
      *NET <net_name>
      *PIN <ref_des>.<pin_number>
    """
    components_map: Dict[str, NetlistComponent] = {}
    nets_map: Dict[str, NetlistNet] = {}

    current_comp: Optional[str] = None
    current_net: Optional[str] = None

    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("//") or line.startswith("#"):
            continue

        # Component declaration
        comp_match = re.match(r"\*COMP\s+(\S+)\s*(.*)", line)
        if comp_match:
            ref = comp_match.group(1)
            part = comp_match.group(2).strip()
            current_comp = ref
            current_net = None
            if ref not in components_map:
                components_map[ref] = NetlistComponent(
                    ref_des=ref, part_number=part
                )
            continue

        # Net declaration
        net_match = re.match(r"\*NET\s+(\S+)", line)
        if net_match:
            net_name = net_match.group(1)
            current_net = net_name
            current_comp = None
            if net_name not in nets_map:
                nets_map[net_name] = NetlistNet(name=net_name)
            continue

        # Pin under component: *PIN <pin_num> <pin_name> <net>
        if current_comp:
            pin_match = re.match(r"\*PIN\s+(\S+)\s+(\S+)\s+(\S+)", line)
            if pin_match:
                pin_num = pin_match.group(1)
                pin_name = pin_match.group(2)
                net_name = pin_match.group(3)

                pin_type = _classify_pin_type(pin_name, net_name)
                pin = NetlistPin(
                    ref_des=current_comp,
                    pin_name=pin_name,
                    pin_number=pin_num,
                    pin_type=pin_type,
                )
                components_map[current_comp].pins.append(pin)

                if net_name not in nets_map:
                    nets_map[net_name] = NetlistNet(name=net_name)
                nets_map[net_name].pins.append(pin)
                continue

        # Pin under net: *PIN <ref_des>.<pin_num>
        if current_net:
            pin_match = re.match(r"\*PIN\s+(\S+)\.(\S+)", line)
            if pin_match:
                ref = pin_match.group(1)
                pin_num = pin_match.group(2)
                pin = NetlistPin(
                    ref_des=ref,
                    pin_name="",
                    pin_number=pin_num,
                    pin_type=_classify_pin_type("", current_net),
                )
                nets_map[current_net].pins.append(pin)

                if ref not in components_map:
                    components_map[ref] = NetlistComponent(ref_des=ref)
                components_map[ref].pins.append(pin)
                continue

    return _build_netlist(components_map, nets_map)


# ---------------------------------------------------------------------------
# OrCAD / Allegro netlist parser
# ---------------------------------------------------------------------------

def parse_orcad_netlist(content: str) -> Netlist:
    """Parse simplified OrCAD/Allegro netlist format.

    Format (NET section):
      ( <net_name>
        <ref_des>-<pin_number>
        ...
      )
    And COMP section:
      { <ref_des> <part_number>
        ...
      }
    """
    components_map: Dict[str, NetlistComponent] = {}
    nets_map: Dict[str, NetlistNet] = {}

    current_net: Optional[str] = None
    in_comp_section = False

    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("//") or line.startswith("#"):
            continue

        # Component definition: { REF PART
        comp_match = re.match(r"\{\s*(\S+)\s+(\S+)", line)
        if comp_match:
            ref = comp_match.group(1)
            part = comp_match.group(2)
            in_comp_section = True
            if ref not in components_map:
                components_map[ref] = NetlistComponent(ref_des=ref, part_number=part)
            continue

        if line.startswith("}"):
            in_comp_section = False
            continue

        # Net definition: ( NET_NAME
        net_match = re.match(r"\(\s*(\S+)", line)
        if net_match:
            current_net = net_match.group(1)
            if current_net not in nets_map:
                nets_map[current_net] = NetlistNet(name=current_net)
            continue

        if line.startswith(")"):
            current_net = None
            continue

        # Pin in net: REF-PIN
        if current_net:
            pin_match = re.match(r"(\S+)-(\S+)", line)
            if pin_match:
                ref = pin_match.group(1)
                pin_num = pin_match.group(2)
                pin = NetlistPin(
                    ref_des=ref,
                    pin_number=pin_num,
                    pin_type=_classify_pin_type("", current_net),
                )
                nets_map[current_net].pins.append(pin)
                if ref not in components_map:
                    components_map[ref] = NetlistComponent(ref_des=ref)
                components_map[ref].pins.append(pin)

    return _build_netlist(components_map, nets_map)


# ---------------------------------------------------------------------------
# Common builder
# ---------------------------------------------------------------------------

def _build_netlist(
    components_map: Dict[str, NetlistComponent],
    nets_map: Dict[str, NetlistNet],
) -> Netlist:
    """Build a Netlist from component/net maps, auto-classifying power/ground."""
    power_nets = [n for n in nets_map if is_power_net(n)]
    ground_nets = [n for n in nets_map if is_ground_net(n)]

    return Netlist(
        components=list(components_map.values()),
        nets=list(nets_map.values()),
        power_nets=power_nets,
        ground_nets=ground_nets,
    )


# ---------------------------------------------------------------------------
# Auto-detect and parse
# ---------------------------------------------------------------------------

def detect_format(content: str) -> str:
    """Detect netlist format from content.

    Returns: 'asc', 'orcad', or 'csv'.
    """
    stripped = content.strip()
    if re.search(r"^\*COMP\s", stripped, re.MULTILINE):
        return "asc"
    if re.search(r"^\*NET\s", stripped, re.MULTILINE) and not re.search(r"^\*COMP\s", stripped, re.MULTILINE):
        # Could be ASC with only NET section
        return "asc"
    if re.search(r"^\{\s*\S+\s+\S+", stripped, re.MULTILINE) or re.search(r"^\(\s*\S+", stripped, re.MULTILINE):
        return "orcad"
    return "csv"


def parse_netlist(content: str, format_hint: Optional[str] = None) -> Netlist:
    """Parse a netlist, auto-detecting format if not specified.

    Args:
        content: Raw netlist text.
        format_hint: 'asc', 'orcad', or 'csv'. Auto-detected if None.

    Returns:
        Parsed Netlist.
    """
    fmt = format_hint or detect_format(content)

    if fmt == "asc":
        return parse_xpedition_asc(content)
    elif fmt == "orcad":
        return parse_orcad_netlist(content)
    else:
        return parse_csv_netlist(content)
