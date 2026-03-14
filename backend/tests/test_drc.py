"""Tests for Phase 7 — Schematic DRC.

Covers: Pydantic models, netlist parser (CSV/ASC/OrCAD), all 13 deterministic
rules, AI checker mock, router endpoints, export formats.
"""
import json
import pytest
from unittest.mock import patch, MagicMock
from io import BytesIO
from fastapi.testclient import TestClient

from models.schematic_drc import (
    DRCReport,
    DRCViolation,
    Netlist,
    NetlistComponent,
    NetlistNet,
    NetlistPin,
    NetlistSummary,
    PinType,
    Severity,
    ViolationCategory,
    AIViolationBatch,
)
from services.netlist_parser import (
    detect_format,
    is_ground_net,
    is_power_net,
    parse_csv_netlist,
    parse_netlist,
    parse_orcad_netlist,
    parse_xpedition_asc,
)
from services.drc_rules_engine import (
    ALL_RULES,
    rule_conn_001,
    rule_conn_002,
    rule_gnd_001,
    rule_name_001,
    rule_pwr_001,
    rule_pwr_002,
    rule_pwr_003,
    rule_spc_001,
    rule_spc_002,
    rule_spc_003,
    rule_spc_004,
    rule_spc_005,
    rule_term_001,
    run_deterministic_rules,
)
from services.drc_ai_checker import run_ai_checks, _netlist_to_summary


# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------

SAMPLE_CSV_NETLIST = """\
Ref Des,Pin Name,Pin Number,Net,Part Number,Value
U1,VCC,1,VDD_3V3,LM317,
U1,GND,2,GND,LM317,
U1,OUT,3,SIG_OUT,LM317,
C1,1,1,VDD_3V3,,100nF
C1,2,2,GND,,100nF
R1,1,1,SIG_OUT,,1k
R1,2,2,NET_LOAD,,1k
U2,VDD,1,VDD_3V3,CY7C1041,SRAM
U2,VSS,2,GND,CY7C1041,SRAM
U2,DQ0,3,DATA0,CY7C1041,SRAM
"""

SAMPLE_ASC_NETLIST = """\
*COMP U1 LM317
*PIN 1 VCC VDD_3V3
*PIN 2 GND GND
*PIN 3 OUT SIG_OUT
*COMP C1 CAP_100NF
*PIN 1 P1 VDD_3V3
*PIN 2 P2 GND
*COMP R1 RES_1K
*PIN 1 P1 SIG_OUT
*PIN 2 P2 NET_LOAD
"""

SAMPLE_ORCAD_NETLIST = """\
{ U1 LM317
}
{ C1 CAP_100NF
}
{ R1 RES_1K
}
( VDD_3V3
U1-1
C1-1
)
( GND
U1-2
C1-2
)
( SIG_OUT
U1-3
R1-1
)
( NET_LOAD
R1-2
)
"""

# A richer netlist for space-compliance rule testing
def _space_netlist(
    *,
    include_efuse=False,
    include_wdt=False,
    include_supervisor=False,
    vreg_count=1,
    include_memory=False,
    include_edac=False,
):
    """Build a Netlist fixture with configurable space-compliance components."""
    comps = [
        NetlistComponent(ref_des="U1", part_number="XC7A35T", value="FPGA"),
    ]
    nets = [
        NetlistNet(name="VDD_3V3", pins=[
            NetlistPin(ref_des="U1", pin_name="VCC", pin_type=PinType.Power),
        ]),
        NetlistNet(name="GND", pins=[
            NetlistPin(ref_des="U1", pin_name="GND", pin_type=PinType.Ground),
        ]),
    ]
    power_nets = ["VDD_3V3"]
    ground_nets = ["GND"]

    # Voltage regulator(s)
    for i in range(vreg_count):
        ref = f"U{10+i}"
        comps.append(NetlistComponent(ref_des=ref, part_number="TPS62140", value="REG"))
        nets[0].pins.append(NetlistPin(ref_des=ref, pin_name="VOUT", pin_type=PinType.Output))

    if include_efuse:
        comps.append(NetlistComponent(ref_des="U20", part_number="TPS2592", value="eFuse"))
    if include_wdt:
        comps.append(NetlistComponent(ref_des="U21", part_number="MAX6369", value="watchdog"))
    if include_supervisor:
        comps.append(NetlistComponent(ref_des="U22", part_number="TPS3700", value="supervisor"))
    if include_memory:
        comps.append(NetlistComponent(ref_des="U30", part_number="CY7C1041", value="SRAM"))
    if include_edac:
        comps.append(NetlistComponent(ref_des="U31", part_number="EDAC_CTRL", value="ECC"))

    return Netlist(components=comps, nets=nets, power_nets=power_nets, ground_nets=ground_nets)


@pytest.fixture
def client():
    from main import app
    with TestClient(app) as c:
        yield c


# ===================================================================
# 1. Pydantic model tests
# ===================================================================

class TestModels:
    def test_severity_enum_values(self):
        assert Severity.Error.value == "Error"
        assert Severity.Warning.value == "Warning"
        assert Severity.Info.value == "Info"

    def test_violation_category_includes_space_compliance(self):
        assert ViolationCategory.SpaceCompliance.value == "SpaceCompliance"

    def test_pin_type_enum(self):
        assert PinType.Power.value == "Power"
        assert PinType.NC.value == "NC"

    def test_drc_violation_defaults(self):
        v = DRCViolation(rule_id="TEST-001")
        assert v.severity == Severity.Warning
        assert v.ai_generated is False
        assert v.affected_nets == []

    def test_netlist_summary_defaults(self):
        s = NetlistSummary()
        assert s.component_count == 0
        assert s.net_count == 0

    def test_drc_report_defaults(self):
        r = DRCReport()
        assert r.overall_status == "PASS"
        assert r.violations == []

    def test_ai_violation_batch_round_trip(self):
        batch = AIViolationBatch(violations=[
            DRCViolation(rule_id="AI-PWR-001", message="test", ai_generated=True),
        ])
        raw = batch.model_dump_json()
        parsed = AIViolationBatch.model_validate_json(raw)
        assert len(parsed.violations) == 1
        assert parsed.violations[0].ai_generated is True


# ===================================================================
# 2. Netlist parser tests
# ===================================================================

class TestNetlistParser:
    # -- Net classification ---
    def test_is_power_net(self):
        assert is_power_net("VDD_3V3") is True
        assert is_power_net("VCC") is True
        assert is_power_net("V3P3") is True
        assert is_power_net("SIG_OUT") is False

    def test_is_ground_net(self):
        assert is_ground_net("GND") is True
        assert is_ground_net("AGND") is True
        assert is_ground_net("SIG_OUT") is False

    # -- Format detection ---
    def test_detect_format_asc(self):
        assert detect_format(SAMPLE_ASC_NETLIST) == "asc"

    def test_detect_format_orcad(self):
        assert detect_format(SAMPLE_ORCAD_NETLIST) == "orcad"

    def test_detect_format_csv(self):
        assert detect_format(SAMPLE_CSV_NETLIST) == "csv"

    # -- CSV parsing ---
    def test_parse_csv_components(self):
        nl = parse_csv_netlist(SAMPLE_CSV_NETLIST)
        refs = {c.ref_des for c in nl.components}
        assert "U1" in refs
        assert "C1" in refs
        assert "R1" in refs

    def test_parse_csv_nets(self):
        nl = parse_csv_netlist(SAMPLE_CSV_NETLIST)
        net_names = {n.name for n in nl.nets}
        assert "VDD_3V3" in net_names
        assert "GND" in net_names

    def test_parse_csv_power_ground_classification(self):
        nl = parse_csv_netlist(SAMPLE_CSV_NETLIST)
        assert "VDD_3V3" in nl.power_nets
        assert "GND" in nl.ground_nets

    def test_parse_csv_empty_raises(self):
        with pytest.raises(ValueError, match="empty"):
            parse_csv_netlist("")

    def test_parse_csv_missing_columns_raises(self):
        with pytest.raises(ValueError, match="columns"):
            parse_csv_netlist("Foo,Bar\n1,2\n")

    # -- ASC parsing ---
    def test_parse_asc_components(self):
        nl = parse_xpedition_asc(SAMPLE_ASC_NETLIST)
        refs = {c.ref_des for c in nl.components}
        assert refs == {"U1", "C1", "R1"}

    def test_parse_asc_nets(self):
        nl = parse_xpedition_asc(SAMPLE_ASC_NETLIST)
        net_names = {n.name for n in nl.nets}
        assert "VDD_3V3" in net_names
        assert "SIG_OUT" in net_names

    def test_parse_asc_pin_type_classification(self):
        nl = parse_xpedition_asc(SAMPLE_ASC_NETLIST)
        u1 = next(c for c in nl.components if c.ref_des == "U1")
        vcc_pin = next(p for p in u1.pins if p.pin_name == "VCC")
        assert vcc_pin.pin_type == PinType.Power

    # -- OrCAD parsing ---
    def test_parse_orcad_components(self):
        nl = parse_orcad_netlist(SAMPLE_ORCAD_NETLIST)
        refs = {c.ref_des for c in nl.components}
        assert "U1" in refs
        assert "R1" in refs

    def test_parse_orcad_nets(self):
        nl = parse_orcad_netlist(SAMPLE_ORCAD_NETLIST)
        net_names = {n.name for n in nl.nets}
        assert "VDD_3V3" in net_names
        assert "NET_LOAD" in net_names

    # -- Auto-detect entry point ---
    def test_parse_netlist_auto_csv(self):
        nl = parse_netlist(SAMPLE_CSV_NETLIST)
        assert len(nl.components) > 0

    def test_parse_netlist_auto_asc(self):
        nl = parse_netlist(SAMPLE_ASC_NETLIST)
        assert len(nl.components) > 0

    def test_parse_netlist_format_hint(self):
        nl = parse_netlist(SAMPLE_ASC_NETLIST, format_hint="asc")
        assert len(nl.components) == 3


# ===================================================================
# 3. Deterministic DRC rule tests
# ===================================================================

class TestRulePWR001:
    """PWR-001: Unconnected power pins."""

    def test_no_violation_when_all_power_pins_connected(self):
        nl = parse_csv_netlist(SAMPLE_CSV_NETLIST)
        assert all(v.rule_id != "PWR-001" for v in rule_pwr_001(nl))

    def test_violation_for_unconnected_power_pin(self):
        """IC with a Power pin that doesn't appear on any net."""
        nl = Netlist(
            components=[
                NetlistComponent(ref_des="U1", part_number="IC1", pins=[
                    NetlistPin(ref_des="U1", pin_name="VCC", pin_number="1", pin_type=PinType.Power),
                    NetlistPin(ref_des="U1", pin_name="OUT", pin_number="2", pin_type=PinType.Output),
                ]),
            ],
            nets=[
                NetlistNet(name="SIG", pins=[
                    NetlistPin(ref_des="U1", pin_name="OUT", pin_number="2", pin_type=PinType.Output),
                ]),
            ],
            power_nets=[],
            ground_nets=[],
        )
        violations = rule_pwr_001(nl)
        assert len(violations) == 1
        assert violations[0].rule_id == "PWR-001"
        assert violations[0].severity == Severity.Error


class TestRulePWR002:
    """PWR-002: Missing decoupling capacitors."""

    def test_no_violation_with_decoupling_cap(self):
        nl = parse_csv_netlist(SAMPLE_CSV_NETLIST)
        # VDD_3V3 has U1 and C1 — should pass
        violations = rule_pwr_002(nl)
        assert all(v.rule_id != "PWR-002" or "VDD_3V3" not in v.affected_nets for v in violations)

    def test_violation_when_no_cap_on_power_net(self):
        nl = Netlist(
            components=[
                NetlistComponent(ref_des="U1", part_number="IC1"),
            ],
            nets=[
                NetlistNet(name="VDD_3V3", pins=[
                    NetlistPin(ref_des="U1", pin_name="VCC", pin_type=PinType.Power),
                ]),
            ],
            power_nets=["VDD_3V3"],
            ground_nets=[],
        )
        violations = rule_pwr_002(nl)
        assert any(v.rule_id == "PWR-002" for v in violations)


class TestRulePWR003:
    """PWR-003: Power net high fan-out without filter."""

    def test_no_violation_under_threshold(self):
        nl = parse_csv_netlist(SAMPLE_CSV_NETLIST)
        assert all(v.rule_id != "PWR-003" for v in rule_pwr_003(nl))

    def test_violation_high_fanout_no_ferrite(self):
        # Build a power net with 25 unique components, no ferrite
        pins = [
            NetlistPin(ref_des=f"U{i}", pin_name="VCC", pin_type=PinType.Power)
            for i in range(25)
        ]
        comps = [NetlistComponent(ref_des=f"U{i}") for i in range(25)]
        nl = Netlist(
            components=comps,
            nets=[NetlistNet(name="VDD_3V3", pins=pins)],
            power_nets=["VDD_3V3"],
            ground_nets=[],
        )
        violations = rule_pwr_003(nl)
        assert any(v.rule_id == "PWR-003" for v in violations)

    def test_no_violation_high_fanout_with_ferrite(self):
        pins = [
            NetlistPin(ref_des=f"U{i}", pin_name="VCC", pin_type=PinType.Power)
            for i in range(25)
        ]
        pins.append(NetlistPin(ref_des="FB1", pin_name="1", pin_type=PinType.Passive))
        comps = [NetlistComponent(ref_des=f"U{i}") for i in range(25)]
        comps.append(NetlistComponent(ref_des="FB1", value="Ferrite"))
        nl = Netlist(
            components=comps,
            nets=[NetlistNet(name="VDD_3V3", pins=pins)],
            power_nets=["VDD_3V3"],
            ground_nets=[],
        )
        violations = rule_pwr_003(nl)
        assert all(v.rule_id != "PWR-003" for v in violations)


class TestRuleGND001:
    """GND-001: Split ground detection."""

    def test_no_violation_single_ground(self):
        nl = Netlist(components=[], nets=[], power_nets=[], ground_nets=["GND"])
        assert rule_gnd_001(nl) == []

    def test_violation_multiple_grounds(self):
        nl = Netlist(components=[], nets=[], power_nets=[], ground_nets=["GND", "AGND"])
        violations = rule_gnd_001(nl)
        assert len(violations) == 1
        assert violations[0].rule_id == "GND-001"
        assert violations[0].severity == Severity.Info


class TestRuleTERM001:
    """TERM-001: Unterminated high-speed nets."""

    def test_violation_for_hs_net_without_resistor(self):
        nl = Netlist(
            components=[
                NetlistComponent(ref_des="U1"),
                NetlistComponent(ref_des="U2"),
            ],
            nets=[
                NetlistNet(name="CLK_100MHZ", pins=[
                    NetlistPin(ref_des="U1", pin_name="CLK_OUT"),
                    NetlistPin(ref_des="U2", pin_name="CLK_IN"),
                ]),
            ],
            power_nets=[],
            ground_nets=[],
        )
        violations = rule_term_001(nl)
        assert any(v.rule_id == "TERM-001" for v in violations)

    def test_no_violation_hs_net_with_resistor(self):
        nl = Netlist(
            components=[
                NetlistComponent(ref_des="U1"),
                NetlistComponent(ref_des="U2"),
                NetlistComponent(ref_des="R1"),
            ],
            nets=[
                NetlistNet(name="CLK_100MHZ", pins=[
                    NetlistPin(ref_des="U1", pin_name="CLK_OUT"),
                    NetlistPin(ref_des="U2", pin_name="CLK_IN"),
                    NetlistPin(ref_des="R1", pin_name="1"),
                ]),
            ],
            power_nets=[],
            ground_nets=[],
        )
        violations = rule_term_001(nl)
        assert all(v.rule_id != "TERM-001" for v in violations)


class TestRuleCONN001:
    """CONN-001: Single-pin nets (floating signals)."""

    def test_violation_single_pin_net(self):
        nl = Netlist(
            components=[NetlistComponent(ref_des="U1")],
            nets=[
                NetlistNet(name="FLOATING_SIG", pins=[
                    NetlistPin(ref_des="U1", pin_name="OUT", pin_number="3"),
                ]),
            ],
            power_nets=[],
            ground_nets=[],
        )
        violations = rule_conn_001(nl)
        assert any(v.rule_id == "CONN-001" for v in violations)

    def test_no_violation_multi_pin_net(self):
        nl = Netlist(
            components=[
                NetlistComponent(ref_des="U1"),
                NetlistComponent(ref_des="U2"),
            ],
            nets=[
                NetlistNet(name="SIG", pins=[
                    NetlistPin(ref_des="U1", pin_name="OUT"),
                    NetlistPin(ref_des="U2", pin_name="IN"),
                ]),
            ],
            power_nets=[],
            ground_nets=[],
        )
        assert rule_conn_001(nl) == []

    def test_single_pin_power_net_ignored(self):
        """Power nets with single pins should NOT be flagged by CONN-001."""
        nl = Netlist(
            components=[NetlistComponent(ref_des="U1")],
            nets=[
                NetlistNet(name="VDD_3V3", pins=[
                    NetlistPin(ref_des="U1", pin_name="VCC", pin_type=PinType.Power),
                ]),
            ],
            power_nets=["VDD_3V3"],
            ground_nets=[],
        )
        assert all(v.rule_id != "CONN-001" for v in rule_conn_001(nl))


class TestRuleCONN002:
    """CONN-002: Unconnected component pins on ICs."""

    def test_violation_unconnected_ic_pin(self):
        nl = Netlist(
            components=[
                NetlistComponent(ref_des="U1", pins=[
                    NetlistPin(ref_des="U1", pin_name="VCC", pin_number="1", pin_type=PinType.Power),
                    NetlistPin(ref_des="U1", pin_name="ORPHAN", pin_number="2", pin_type=PinType.Output),
                ]),
            ],
            nets=[
                NetlistNet(name="VDD_3V3", pins=[
                    NetlistPin(ref_des="U1", pin_name="VCC", pin_number="1", pin_type=PinType.Power),
                ]),
            ],
            power_nets=["VDD_3V3"],
            ground_nets=[],
        )
        violations = rule_conn_002(nl)
        assert any(v.rule_id == "CONN-002" for v in violations)

    def test_nc_pin_ignored(self):
        nl = Netlist(
            components=[
                NetlistComponent(ref_des="U1", pins=[
                    NetlistPin(ref_des="U1", pin_name="NC", pin_number="5", pin_type=PinType.NC),
                ]),
            ],
            nets=[],
            power_nets=[],
            ground_nets=[],
        )
        assert rule_conn_002(nl) == []


class TestRuleNAME001:
    """NAME-001: Auto-generated net names."""

    def test_violation_auto_named_net(self):
        nl = Netlist(
            components=[NetlistComponent(ref_des="U1")],
            nets=[
                NetlistNet(name="N$123", pins=[
                    NetlistPin(ref_des="U1", pin_name="X"),
                ]),
            ],
            power_nets=[],
            ground_nets=[],
        )
        violations = rule_name_001(nl)
        assert any(v.rule_id == "NAME-001" for v in violations)

    def test_no_violation_named_net(self):
        nl = Netlist(
            components=[NetlistComponent(ref_des="U1")],
            nets=[NetlistNet(name="SPI_MOSI", pins=[NetlistPin(ref_des="U1")])],
            power_nets=[],
            ground_nets=[],
        )
        assert rule_name_001(nl) == []


# ---------------------------------------------------------------------------
# Space-compliance rules
# ---------------------------------------------------------------------------

class TestRuleSPC001:
    """SPC-001: No SEL current-limiter."""

    def test_violation_no_efuse(self):
        nl = _space_netlist(include_efuse=False)
        violations = rule_spc_001(nl)
        assert any(v.rule_id == "SPC-001" for v in violations)

    def test_no_violation_with_efuse(self):
        nl = _space_netlist(include_efuse=True)
        assert all(v.rule_id != "SPC-001" for v in rule_spc_001(nl))


class TestRuleSPC002:
    """SPC-002: No watchdog timer."""

    def test_violation_no_wdt(self):
        nl = _space_netlist(include_wdt=False)
        assert any(v.rule_id == "SPC-002" for v in rule_spc_002(nl))

    def test_no_violation_with_wdt(self):
        nl = _space_netlist(include_wdt=True)
        assert all(v.rule_id != "SPC-002" for v in rule_spc_002(nl))


class TestRuleSPC003:
    """SPC-003: No reset supervisor."""

    def test_violation_no_supervisor(self):
        nl = _space_netlist(include_supervisor=False)
        assert any(v.rule_id == "SPC-003" for v in rule_spc_003(nl))

    def test_no_violation_with_supervisor(self):
        nl = _space_netlist(include_supervisor=True)
        assert all(v.rule_id != "SPC-003" for v in rule_spc_003(nl))


class TestRuleSPC004:
    """SPC-004: Single-point failure on power supply."""

    def test_violation_single_regulator(self):
        nl = _space_netlist(vreg_count=1)
        assert any(v.rule_id == "SPC-004" for v in rule_spc_004(nl))

    def test_no_violation_multiple_regulators(self):
        nl = _space_netlist(vreg_count=2)
        assert all(v.rule_id != "SPC-004" for v in rule_spc_004(nl))

    def test_no_violation_zero_regulators(self):
        nl = _space_netlist(vreg_count=0)
        assert all(v.rule_id != "SPC-004" for v in rule_spc_004(nl))


class TestRuleSPC005:
    """SPC-005: Memory without EDAC."""

    def test_violation_memory_no_edac(self):
        nl = _space_netlist(include_memory=True, include_edac=False)
        assert any(v.rule_id == "SPC-005" for v in rule_spc_005(nl))

    def test_no_violation_memory_with_edac(self):
        nl = _space_netlist(include_memory=True, include_edac=True)
        assert all(v.rule_id != "SPC-005" for v in rule_spc_005(nl))

    def test_no_violation_no_memory(self):
        nl = _space_netlist(include_memory=False)
        assert rule_spc_005(nl) == []


class TestRunAllRules:
    def test_all_rules_list_has_13(self):
        assert len(ALL_RULES) == 13

    def test_run_deterministic_rules_returns_list(self):
        nl = parse_csv_netlist(SAMPLE_CSV_NETLIST)
        violations = run_deterministic_rules(nl)
        assert isinstance(violations, list)
        for v in violations:
            assert isinstance(v, DRCViolation)


# ===================================================================
# 4. AI checker tests (mocked)
# ===================================================================

class TestAIChecker:
    def test_netlist_to_summary_contains_key_sections(self):
        nl = parse_csv_netlist(SAMPLE_CSV_NETLIST)
        text = _netlist_to_summary(nl)
        assert "COMPONENTS" in text
        assert "NETS" in text
        assert "U1" in text

    @patch("services.drc_ai_checker.get_client")
    def test_run_ai_checks_returns_violations(self, mock_get_client):
        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock()]
        mock_resp.choices[0].message.content = json.dumps({
            "violations": [
                {
                    "rule_id": "AI-INTF-001",
                    "severity": "Warning",
                    "category": "Interface",
                    "message": "I2C SDA missing pull-up",
                    "affected_nets": ["I2C_SDA"],
                    "affected_components": ["U1"],
                    "recommendation": "Add 4.7k pull-up",
                    "ai_generated": True,
                }
            ]
        })
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_resp
        mock_get_client.return_value = mock_client

        nl = parse_csv_netlist(SAMPLE_CSV_NETLIST)
        violations = run_ai_checks(nl)
        assert len(violations) == 1
        assert violations[0].ai_generated is True
        assert violations[0].rule_id == "AI-INTF-001"

    @patch("services.drc_ai_checker.get_client", side_effect=RuntimeError("no key"))
    def test_run_ai_checks_no_api_key_returns_empty(self, _):
        nl = parse_csv_netlist(SAMPLE_CSV_NETLIST)
        assert run_ai_checks(nl) == []

    @patch("services.drc_ai_checker.get_client")
    def test_run_ai_checks_bad_json_returns_empty(self, mock_get_client):
        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock()]
        mock_resp.choices[0].message.content = "NOT JSON AT ALL"
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_resp
        mock_get_client.return_value = mock_client

        nl = parse_csv_netlist(SAMPLE_CSV_NETLIST)
        assert run_ai_checks(nl) == []


# ===================================================================
# 5. Router endpoint tests
# ===================================================================

class TestDRCRouter:
    def test_upload_netlist_csv(self, client):
        resp = client.post(
            "/api/drc/upload-netlist",
            files={"file": ("test.csv", SAMPLE_CSV_NETLIST.encode(), "text/csv")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "components" in data
        assert "nets" in data

    def test_upload_netlist_asc(self, client):
        resp = client.post(
            "/api/drc/upload-netlist",
            files={"file": ("test.asc", SAMPLE_ASC_NETLIST.encode(), "text/plain")},
        )
        assert resp.status_code == 200
        assert len(resp.json()["components"]) == 3

    def test_upload_netlist_invalid(self, client):
        resp = client.post(
            "/api/drc/upload-netlist",
            files={"file": ("bad.csv", b"", "text/csv")},
        )
        assert resp.status_code == 400

    @patch("routers.drc.run_ai_checks", return_value=[])
    def test_analyze_returns_report(self, _, client):
        resp = client.post(
            "/api/drc/analyze",
            files={"file": ("test.csv", SAMPLE_CSV_NETLIST.encode(), "text/csv")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "overall_status" in data
        assert "violations" in data
        assert "netlist_summary" in data
        assert data["netlist_summary"]["component_count"] > 0

    @patch("routers.drc.run_ai_checks", return_value=[])
    def test_analyze_overall_status_logic(self, _, client):
        resp = client.post(
            "/api/drc/analyze",
            files={"file": ("test.csv", SAMPLE_CSV_NETLIST.encode(), "text/csv")},
        )
        data = resp.json()
        assert data["overall_status"] in ("PASS", "WARNING", "FAIL")

    def test_export_markdown(self, client):
        report = DRCReport(
            netlist_summary=NetlistSummary(component_count=3, net_count=5),
            violations=[
                DRCViolation(rule_id="PWR-001", severity=Severity.Error, message="test error"),
            ],
            error_count=1,
            overall_status="FAIL",
        )
        resp = client.post(
            "/api/drc/export",
            json={"report": report.model_dump(), "format": "markdown"},
        )
        assert resp.status_code == 200
        assert "# Schematic DRC Report" in resp.text
        assert "FAIL" in resp.text
        assert "PWR-001" in resp.text

    def test_export_csv(self, client):
        report = DRCReport(
            netlist_summary=NetlistSummary(component_count=2, net_count=3),
            violations=[
                DRCViolation(rule_id="GND-001", severity=Severity.Info, message="split grounds"),
            ],
            info_count=1,
            overall_status="PASS",
        )
        resp = client.post(
            "/api/drc/export",
            json={"report": report.model_dump(), "format": "csv"},
        )
        assert resp.status_code == 200
        assert "Rule ID" in resp.text
        assert "GND-001" in resp.text

    def test_export_unknown_format_400(self, client):
        report = DRCReport()
        resp = client.post(
            "/api/drc/export",
            json={"report": report.model_dump(), "format": "xlsx"},
        )
        assert resp.status_code == 400

    def test_export_empty_violations_markdown(self, client):
        report = DRCReport(overall_status="PASS")
        resp = client.post(
            "/api/drc/export",
            json={"report": report.model_dump(), "format": "markdown"},
        )
        assert resp.status_code == 200
        assert "No violations found" in resp.text
