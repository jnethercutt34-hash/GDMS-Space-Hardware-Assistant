"""Tests for Phase 6 — BOM Analyzer.

Covers: Pydantic models, BOM parsing, library cross-reference,
risk assessment, export generators, router endpoints.
Target: 25+ tests.
"""
import json
import pytest
from unittest.mock import patch, MagicMock
from io import BytesIO
from fastapi.testclient import TestClient

from models.bom import (
    BOMLineItem,
    BOMAnalysisResult,
    BOMReport,
    BOMSummary,
    AlternatePart,
    AIRiskAssessment,
    AIBatchRiskAssessment,
    LifecycleStatus,
    RadiationGrade,
    RiskLevel,
)
from services.bom_analyzer import (
    parse_bom_csv,
    cross_reference_library,
    assign_risk_levels,
    compute_summary,
    analyze_bom,
)
from services.bom_export import generate_annotated_csv, generate_risk_summary


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_CSV = """Ref Des,Part Number,Manufacturer,Description,Quantity,Value,Package,DNP
U1,XC7A35T-1CPG236C,Xilinx,Artix-7 FPGA,1,,BGA-236,No
R1,ERJ-3EKF1001V,Panasonic,Thick Film Resistor,10,1kΩ,0402,No
C1,GRM155R71C104KA88D,Murata,MLCC Capacitor,20,100nF,0402,No
R99,DNP-RES,Unknown,Placeholder resistor,1,10kΩ,0603,Yes
U2,AD7124-8BCPZ,Analog Devices,24-bit Sigma-Delta ADC,2,,LFCSP-32,No
"""

XPEDITION_CSV = """Reference Designator,MFR Part Number,Manufacturer_Name,Part Description,Qty,Component Value,Case/Package
U1,LTC6908-1,Linear Technology,Dual Output Oscillator,1,,TSOT-23-6
C1,C0402C104K4RACTU,KEMET,MLCC 100nF 16V,5,100nF,0402
"""

SAMPLE_LIBRARY = [
    {
        "Part_Number": "XC7A35T-1CPG236C",
        "Manufacturer": "Xilinx",
        "Description": "Artix-7 FPGA — commercial grade COTS",
        "Voltage_Rating": "1.0V core",
        "Operating_Temperature": "-40 to 100 °C",
    },
    {
        "Part_Number": "AD7124-8BCPZ",
        "Manufacturer": "Analog Devices",
        "Description": "24-bit ADC, MIL-STD-883 compliant, active production",
        "Voltage_Rating": "2.7V to 3.6V",
        "Operating_Temperature": "-40 to 125 °C",
    },
]


@pytest.fixture
def client():
    from main import app
    return TestClient(app)


# ===================================================================
# 1. Pydantic model tests
# ===================================================================

class TestModels:
    def test_bom_line_item_defaults(self):
        item = BOMLineItem(ref_des="R1", part_number="ERJ-3EKF1001V")
        assert item.manufacturer == "Unknown"
        assert item.quantity == 1
        assert item.dnp is False
        assert item.value is None

    def test_bom_line_item_full(self):
        item = BOMLineItem(
            ref_des="C1", part_number="GRM155R71C104KA88D",
            manufacturer="Murata", description="MLCC",
            quantity=20, value="100nF", package="0402", dnp=False,
        )
        assert item.quantity == 20
        assert item.package == "0402"

    def test_analysis_result_defaults(self):
        item = BOMLineItem(ref_des="U1", part_number="TEST")
        result = BOMAnalysisResult(line_item=item)
        assert result.library_match is False
        assert result.lifecycle_status == LifecycleStatus.Unknown
        assert result.radiation_grade == RadiationGrade.Unknown
        assert result.risk_level == RiskLevel.Medium

    def test_lifecycle_enum_values(self):
        assert set(LifecycleStatus) == {
            LifecycleStatus.Active, LifecycleStatus.NRND,
            LifecycleStatus.Obsolete, LifecycleStatus.Unknown,
        }

    def test_radiation_enum_values(self):
        assert set(RadiationGrade) == {
            RadiationGrade.Commercial, RadiationGrade.MIL,
            RadiationGrade.RadTolerant, RadiationGrade.RadHard,
            RadiationGrade.Unknown,
        }

    def test_risk_level_enum_values(self):
        assert set(RiskLevel) == {
            RiskLevel.Low, RiskLevel.Medium, RiskLevel.High, RiskLevel.Critical,
        }

    def test_alternate_part(self):
        alt = AlternatePart(part_number="XYZ-123", manufacturer="Acme", notes="Pin compatible")
        assert alt.part_number == "XYZ-123"

    def test_bom_summary_defaults(self):
        s = BOMSummary()
        assert s.total_line_items == 0
        assert s.library_matched_pct == 0.0

    def test_ai_risk_assessment_defaults(self):
        a = AIRiskAssessment()
        assert a.lifecycle_status == LifecycleStatus.Unknown
        assert a.assessment == ""

    def test_ai_batch_assessment(self):
        batch = AIBatchRiskAssessment(assessments=[AIRiskAssessment(), AIRiskAssessment()])
        assert len(batch.assessments) == 2


# ===================================================================
# 2. BOM parsing tests
# ===================================================================

class TestBOMParsing:
    def test_parse_standard_csv(self):
        items = parse_bom_csv(SAMPLE_CSV)
        assert len(items) == 5
        assert items[0].ref_des == "U1"
        assert items[0].part_number == "XC7A35T-1CPG236C"
        assert items[0].manufacturer == "Xilinx"

    def test_parse_quantities(self):
        items = parse_bom_csv(SAMPLE_CSV)
        assert items[1].quantity == 10  # R1
        assert items[2].quantity == 20  # C1

    def test_parse_dnp_flag(self):
        items = parse_bom_csv(SAMPLE_CSV)
        assert items[3].dnp is True   # R99
        assert items[0].dnp is False   # U1

    def test_parse_values_and_packages(self):
        items = parse_bom_csv(SAMPLE_CSV)
        assert items[1].value == "1kΩ"
        assert items[2].package == "0402"

    def test_parse_xpedition_format(self):
        items = parse_bom_csv(XPEDITION_CSV)
        assert len(items) == 2
        assert items[0].part_number == "LTC6908-1"
        assert items[0].manufacturer == "Linear Technology"

    def test_parse_empty_csv_raises(self):
        with pytest.raises(ValueError, match="empty"):
            parse_bom_csv("")

    def test_parse_no_headers_raises(self):
        with pytest.raises(ValueError, match="columns"):
            parse_bom_csv("foo,bar,baz\n1,2,3\n")

    def test_parse_handles_extra_whitespace(self):
        csv = "Ref Des , Part Number , Manufacturer\n U1 , ABC-123 , Acme \n"
        items = parse_bom_csv(csv)
        assert items[0].part_number == "ABC-123"
        assert items[0].manufacturer == "Acme"


# ===================================================================
# 3. Library cross-reference tests
# ===================================================================

class TestCrossReference:
    def test_exact_match(self):
        items = [BOMLineItem(ref_des="U1", part_number="XC7A35T-1CPG236C")]
        results = cross_reference_library(items, library=SAMPLE_LIBRARY)
        assert results[0].library_match is True

    def test_no_match(self):
        items = [BOMLineItem(ref_des="U1", part_number="NONEXISTENT-PART")]
        results = cross_reference_library(items, library=SAMPLE_LIBRARY)
        assert results[0].library_match is False

    def test_case_insensitive_match(self):
        items = [BOMLineItem(ref_des="U1", part_number="xc7a35t-1cpg236c")]
        results = cross_reference_library(items, library=SAMPLE_LIBRARY)
        assert results[0].library_match is True

    def test_suffix_stripped_match(self):
        items = [BOMLineItem(ref_des="U2", part_number="AD7124-8BCPZ-ND")]
        results = cross_reference_library(items, library=SAMPLE_LIBRARY)
        assert results[0].library_match is True

    def test_radiation_enrichment_from_library(self):
        items = [BOMLineItem(ref_des="U1", part_number="XC7A35T-1CPG236C")]
        results = cross_reference_library(items, library=SAMPLE_LIBRARY)
        # Library entry says "commercial grade COTS"
        assert results[0].radiation_grade == RadiationGrade.Commercial

    def test_mil_enrichment_from_library(self):
        items = [BOMLineItem(ref_des="U2", part_number="AD7124-8BCPZ")]
        results = cross_reference_library(items, library=SAMPLE_LIBRARY)
        assert results[0].radiation_grade == RadiationGrade.MIL

    def test_empty_library(self):
        items = [BOMLineItem(ref_des="R1", part_number="ERJ-3EKF1001V")]
        results = cross_reference_library(items, library=[])
        assert results[0].library_match is False


# ===================================================================
# 4. Risk level assignment tests
# ===================================================================

class TestRiskAssignment:
    def test_dnp_is_low(self):
        item = BOMLineItem(ref_des="R99", part_number="X", dnp=True)
        result = BOMAnalysisResult(line_item=item)
        [r] = assign_risk_levels([result])
        assert r.risk_level == RiskLevel.Low

    def test_obsolete_is_critical(self):
        item = BOMLineItem(ref_des="U1", part_number="X")
        result = BOMAnalysisResult(
            line_item=item,
            lifecycle_status=LifecycleStatus.Obsolete,
            radiation_grade=RadiationGrade.Commercial,
        )
        [r] = assign_risk_levels([result])
        assert r.risk_level == RiskLevel.Critical

    def test_active_radhard_matched_is_low(self):
        item = BOMLineItem(ref_des="U1", part_number="X")
        result = BOMAnalysisResult(
            line_item=item,
            library_match=True,
            lifecycle_status=LifecycleStatus.Active,
            radiation_grade=RadiationGrade.RadHard,
            alt_parts=[AlternatePart(part_number="Y")],
        )
        [r] = assign_risk_levels([result])
        assert r.risk_level == RiskLevel.Low

    def test_nrnd_unknown_rad_is_high(self):
        item = BOMLineItem(ref_des="U1", part_number="X")
        result = BOMAnalysisResult(
            line_item=item,
            lifecycle_status=LifecycleStatus.NRND,
            radiation_grade=RadiationGrade.Unknown,
        )
        [r] = assign_risk_levels([result])
        assert r.risk_level in (RiskLevel.High, RiskLevel.Critical)


# ===================================================================
# 5. Summary computation tests
# ===================================================================

class TestSummary:
    def test_summary_counts(self):
        items = parse_bom_csv(SAMPLE_CSV)
        results = cross_reference_library(items, library=SAMPLE_LIBRARY)
        results = assign_risk_levels(results)
        summary = compute_summary(results)

        assert summary.total_line_items == 5
        assert summary.unique_parts == 5
        assert summary.total_placements == 34  # 1+10+20+1+2

    def test_summary_library_match_pct(self):
        items = parse_bom_csv(SAMPLE_CSV)
        results = cross_reference_library(items, library=SAMPLE_LIBRARY)
        summary = compute_summary(results)
        # 2 out of 5 should match
        assert summary.library_matched == 2
        assert summary.library_matched_pct == 40.0

    def test_summary_empty(self):
        summary = compute_summary([])
        assert summary.total_line_items == 0
        assert summary.library_matched_pct == 0.0


# ===================================================================
# 6. Export tests
# ===================================================================

class TestExport:
    def _make_report(self):
        items = parse_bom_csv(SAMPLE_CSV)
        results = cross_reference_library(items, library=SAMPLE_LIBRARY)
        results = assign_risk_levels(results)
        summary = compute_summary(results)
        return BOMReport(filename="test_bom.csv", results=results, summary=summary)

    def test_annotated_csv_header(self):
        report = self._make_report()
        csv = generate_annotated_csv(report)
        assert "Ref Des" in csv
        assert "Risk Level" in csv
        assert "Radiation Grade" in csv

    def test_annotated_csv_row_count(self):
        report = self._make_report()
        csv = generate_annotated_csv(report)
        lines = [l for l in csv.strip().split("\n") if l.strip()]
        assert len(lines) == 6  # 1 header + 5 data rows

    def test_risk_summary_markdown(self):
        report = self._make_report()
        md = generate_risk_summary(report)
        assert "# BOM Risk Analysis Report" in md
        assert "test_bom.csv" in md
        assert "Library Coverage" in md

    def test_risk_summary_lifecycle_section(self):
        report = self._make_report()
        md = generate_risk_summary(report)
        assert "Lifecycle Health" in md
        assert "Active" in md

    def test_risk_summary_radiation_section(self):
        report = self._make_report()
        md = generate_risk_summary(report)
        assert "Radiation Profile" in md


# ===================================================================
# 7. Full pipeline test
# ===================================================================

class TestPipeline:
    def test_analyze_bom_skip_ai(self):
        report = analyze_bom(SAMPLE_CSV, filename="test.csv", library=SAMPLE_LIBRARY, skip_ai=True)
        assert report.filename == "test.csv"
        assert len(report.results) == 5
        assert report.summary.total_line_items == 5
        assert report.summary.library_matched == 2


# ===================================================================
# 8. Router tests
# ===================================================================

class TestRouter:
    @patch("services.bom_analyzer.analyze_bom")
    def test_analyze_endpoint(self, mock_analyze, client):
        mock_report = BOMReport(
            filename="test.csv",
            results=[],
            summary=BOMSummary(total_line_items=0),
        )
        mock_analyze.return_value = mock_report

        resp = client.post(
            "/api/bom/analyze",
            files={"file": ("test.csv", BytesIO(SAMPLE_CSV.encode()), "text/csv")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "summary" in data
        assert "results" in data

    def test_analyze_rejects_non_csv(self, client):
        resp = client.post(
            "/api/bom/analyze",
            files={"file": ("test.pdf", BytesIO(b"%PDF-1.4"), "application/pdf")},
        )
        assert resp.status_code == 400

    def test_export_summary(self, client):
        report = analyze_bom(SAMPLE_CSV, library=SAMPLE_LIBRARY, skip_ai=True)
        resp = client.post("/api/bom/export", json={
            "report": report.model_dump(),
            "format": "summary",
        })
        assert resp.status_code == 200
        assert "BOM Risk Analysis Report" in resp.text

    def test_export_csv(self, client):
        report = analyze_bom(SAMPLE_CSV, library=SAMPLE_LIBRARY, skip_ai=True)
        resp = client.post("/api/bom/export", json={
            "report": report.model_dump(),
            "format": "csv",
        })
        assert resp.status_code == 200
        assert "Ref Des" in resp.text

    def test_export_invalid_format(self, client):
        report = analyze_bom(SAMPLE_CSV, library=SAMPLE_LIBRARY, skip_ai=True)
        resp = client.post("/api/bom/export", json={
            "report": report.model_dump(),
            "format": "banana",
        })
        assert resp.status_code == 400
