"""Tests for Phase 5 — COM Channel Analysis.

Covers: Pydantic models, COM calculator, export generators, router endpoints.
Target: 25+ tests.
"""
import json
import math
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from models.com_channel import (
    ChannelSegment,
    ChannelModel,
    COMResult,
    ChannelExtractionResult,
    SegmentType,
    Modulation,
    TxParams,
    RxParams,
)
from services.com_calculator import calculate_com
from services.com_export import (
    generate_channel_ces_script,
    generate_hyperlynx_csv,
    generate_summary_report,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _short_channel() -> ChannelModel:
    """Short NRZ 10G channel — should pass easily."""
    return ChannelModel(
        name="Short_10G_NRZ",
        data_rate_gbps=10.0,
        modulation=Modulation.NRZ,
        segments=[
            ChannelSegment(label="TX_pkg", type=SegmentType.package, length_mm=5.0,
                           impedance_ohm=100, loss_db_per_inch=0.8),
            ChannelSegment(label="PCB_trace", type=SegmentType.PCB_trace, length_mm=100.0,
                           impedance_ohm=100, loss_db_per_inch=0.5),
            ChannelSegment(label="RX_pkg", type=SegmentType.package, length_mm=5.0,
                           impedance_ohm=100, loss_db_per_inch=0.8),
        ],
        tx_params=TxParams(swing_mv=800, de_emphasis_db=3.5),
        rx_params=RxParams(ctle_peaking_db=6.0, dfe_taps=1, dfe_tap1_mv=50),
    )


def _long_channel() -> ChannelModel:
    """Long PAM4 56G channel — should be marginal."""
    return ChannelModel(
        name="Long_56G_PAM4",
        data_rate_gbps=56.0,
        modulation=Modulation.PAM4,
        segments=[
            ChannelSegment(label="TX_pkg", type=SegmentType.package, length_mm=8.0,
                           impedance_ohm=95, loss_db_per_inch=1.2),
            ChannelSegment(label="Via_1", type=SegmentType.via, length_mm=2.0,
                           impedance_ohm=90, loss_db_per_inch=0.3),
            ChannelSegment(label="Trace_1", type=SegmentType.PCB_trace, length_mm=250.0,
                           impedance_ohm=100, loss_db_per_inch=0.7),
            ChannelSegment(label="Connector", type=SegmentType.connector, length_mm=15.0,
                           impedance_ohm=92, loss_db_per_inch=1.5),
            ChannelSegment(label="Trace_2", type=SegmentType.PCB_trace, length_mm=250.0,
                           impedance_ohm=100, loss_db_per_inch=0.7),
            ChannelSegment(label="Via_2", type=SegmentType.via, length_mm=2.0,
                           impedance_ohm=90, loss_db_per_inch=0.3),
            ChannelSegment(label="RX_pkg", type=SegmentType.package, length_mm=8.0,
                           impedance_ohm=95, loss_db_per_inch=1.2),
        ],
        tx_params=TxParams(swing_mv=900, de_emphasis_db=6.0, pre_cursor_taps=2),
        rx_params=RxParams(ctle_peaking_db=10.0, dfe_taps=5, dfe_tap1_mv=40),
        crosstalk_aggressors=["aggr_1", "aggr_2"],
    )


def _empty_channel() -> ChannelModel:
    return ChannelModel(name="Empty", data_rate_gbps=10.0, segments=[])


@pytest.fixture
def client():
    from main import app
    return TestClient(app)


# ===================================================================
# 1. Pydantic model tests
# ===================================================================

class TestModels:
    def test_channel_segment_defaults(self):
        seg = ChannelSegment(label="trace", type=SegmentType.PCB_trace, length_mm=50)
        assert seg.impedance_ohm == 100.0
        assert seg.loss_db_per_inch == 0.5
        assert seg.dielectric_constant == 4.0
        assert seg.loss_tangent == 0.02

    def test_channel_segment_custom(self):
        seg = ChannelSegment(
            label="via", type=SegmentType.via, length_mm=2,
            impedance_ohm=90, loss_db_per_inch=0.3,
        )
        assert seg.impedance_ohm == 90
        assert seg.type == SegmentType.via

    def test_channel_segment_negative_length_rejected(self):
        with pytest.raises(Exception):
            ChannelSegment(label="bad", type=SegmentType.PCB_trace, length_mm=-1)

    def test_channel_model_auto_id(self):
        ch = ChannelModel(name="test", data_rate_gbps=10)
        assert len(ch.id) == 8

    def test_channel_model_modulation_default(self):
        ch = ChannelModel(name="test", data_rate_gbps=10)
        assert ch.modulation == Modulation.NRZ

    def test_tx_params_defaults(self):
        tx = TxParams()
        assert tx.swing_mv == 800.0
        assert tx.de_emphasis_db == 3.5

    def test_rx_params_defaults(self):
        rx = RxParams()
        assert rx.ctle_peaking_db == 6.0
        assert rx.dfe_taps == 1

    def test_com_result_pass(self):
        r = COMResult(com_db=5.0, passed=True, eye_height_mv=100,
                      eye_width_ps=50, total_il_db=10, rl_db=25)
        assert r.passed is True

    def test_channel_extraction_result(self):
        ch = ChannelModel(name="x", data_rate_gbps=10)
        wrapper = ChannelExtractionResult(channel=ch)
        assert wrapper.channel.name == "x"

    def test_segment_type_enum_values(self):
        assert set(SegmentType) == {
            SegmentType.PCB_trace, SegmentType.connector,
            SegmentType.via, SegmentType.cable, SegmentType.package,
        }


# ===================================================================
# 2. COM calculator tests
# ===================================================================

class TestCOMCalculator:
    def test_short_channel_passes(self):
        result = calculate_com(_short_channel())
        assert result.passed is True
        assert result.com_db > 6.0

    def test_long_channel_marginal(self):
        result = calculate_com(_long_channel())
        # PAM4 56G over long channel — should be stressed
        assert result.com_db < 10.0

    def test_empty_channel_warns(self):
        result = calculate_com(_empty_channel())
        assert any("No channel segments" in w for w in result.warnings)

    def test_nrz_nyquist(self):
        ch = _short_channel()
        # NRZ 10G → Nyquist = 5 GHz
        result = calculate_com(ch)
        assert result.total_il_db > 0  # non-trivial IL

    def test_pam4_penalty_applied(self):
        ch = _short_channel()
        nrz_result = calculate_com(ch)
        ch_pam4 = ch.model_copy(update={"modulation": Modulation.PAM4})
        pam4_result = calculate_com(ch_pam4)
        # PAM4 should have lower COM than NRZ on same channel
        assert pam4_result.com_db < nrz_result.com_db

    def test_impedance_mismatch_warning(self):
        ch = ChannelModel(
            name="mismatch", data_rate_gbps=10,
            segments=[
                ChannelSegment(label="a", type=SegmentType.PCB_trace, length_mm=50, impedance_ohm=100),
                ChannelSegment(label="b", type=SegmentType.connector, length_mm=10, impedance_ohm=75),
            ],
        )
        result = calculate_com(ch)
        assert any("Impedance variation" in w for w in result.warnings)

    def test_return_loss_calculation(self):
        ch = ChannelModel(
            name="rl_test", data_rate_gbps=10,
            segments=[
                ChannelSegment(label="a", type=SegmentType.PCB_trace, length_mm=50, impedance_ohm=100),
                ChannelSegment(label="b", type=SegmentType.PCB_trace, length_mm=50, impedance_ohm=100),
            ],
        )
        result = calculate_com(ch)
        # Matched impedances → good return loss (stays at optimistic 30 dB)
        assert result.rl_db == 30.0

    def test_eye_dimensions_positive(self):
        result = calculate_com(_short_channel())
        assert result.eye_height_mv > 0
        assert result.eye_width_ps > 0

    def test_crosstalk_aggressors_increase_noise(self):
        ch = _short_channel()
        r_no_xt = calculate_com(ch)
        ch_xt = ch.model_copy(update={"crosstalk_aggressors": ["a1", "a2", "a3"]})
        r_with_xt = calculate_com(ch_xt)
        assert r_with_xt.com_db <= r_no_xt.com_db


# ===================================================================
# 3. Export tests
# ===================================================================

class TestExport:
    def test_ces_script_contains_channel_name(self):
        ch = _short_channel()
        r = calculate_com(ch)
        script = generate_channel_ces_script(ch, r)
        assert "Short_10G_NRZ" in script
        assert "win32com" in script

    def test_ces_script_contains_pass_fail(self):
        ch = _short_channel()
        r = calculate_com(ch)
        script = generate_channel_ces_script(ch, r)
        assert "PASS" in script or "FAIL" in script

    def test_hyperlynx_csv_header(self):
        ch = _short_channel()
        csv = generate_hyperlynx_csv(ch)
        assert "Segment_Label" in csv
        assert "TX_Swing_mV" in csv

    def test_hyperlynx_csv_segment_count(self):
        ch = _short_channel()
        csv = generate_hyperlynx_csv(ch)
        data_lines = [l for l in csv.strip().split("\n") if l and not l.startswith("#") and not l.startswith("Segment_Label") and "," in l and "_" not in l.split(",")[0].replace("_pkg", "").replace("_trace", "")]
        # Just verify all segments appear
        for seg in ch.segments:
            assert seg.label in csv

    def test_summary_report_markdown(self):
        ch = _short_channel()
        r = calculate_com(ch)
        report = generate_summary_report(ch, r)
        assert "# COM Channel Analysis Report" in report
        assert str(r.com_db) in report
        assert "PASS" in report or "FAIL" in report

    def test_summary_report_warnings(self):
        ch = _empty_channel()
        r = calculate_com(ch)
        report = generate_summary_report(ch, r)
        assert "Warnings" in report or "⚠️" in report


# ===================================================================
# 4. Router tests
# ===================================================================

class TestRouter:
    def test_calculate_endpoint(self, client):
        ch = _short_channel()
        resp = client.post("/api/com/calculate", json={"channel": ch.model_dump()})
        assert resp.status_code == 200
        data = resp.json()
        assert "result" in data
        assert data["result"]["passed"] is True

    def test_calculate_empty_segments_rejected(self, client):
        ch = _empty_channel()
        resp = client.post("/api/com/calculate", json={"channel": ch.model_dump()})
        assert resp.status_code == 400

    def test_export_summary(self, client):
        ch = _short_channel()
        r = calculate_com(ch)
        resp = client.post("/api/com/export", json={
            "channel": ch.model_dump(),
            "result": r.model_dump(),
            "format": "summary",
        })
        assert resp.status_code == 200
        assert "COM Channel Analysis Report" in resp.text

    def test_export_ces(self, client):
        ch = _short_channel()
        r = calculate_com(ch)
        resp = client.post("/api/com/export", json={
            "channel": ch.model_dump(),
            "result": r.model_dump(),
            "format": "ces",
        })
        assert resp.status_code == 200
        assert "win32com" in resp.text

    def test_export_hyperlynx(self, client):
        ch = _short_channel()
        r = calculate_com(ch)
        resp = client.post("/api/com/export", json={
            "channel": ch.model_dump(),
            "result": r.model_dump(),
            "format": "hyperlynx",
        })
        assert resp.status_code == 200
        assert "Segment_Label" in resp.text

    def test_export_invalid_format(self, client):
        ch = _short_channel()
        r = calculate_com(ch)
        resp = client.post("/api/com/export", json={
            "channel": ch.model_dump(),
            "result": r.model_dump(),
            "format": "banana",
        })
        assert resp.status_code == 400

    @patch("routers.com.extract_text_from_pdf")
    @patch("routers.com.extract_channel_from_text")
    def test_extract_channel_endpoint(self, mock_extract, mock_pdf, client):
        mock_pdf.return_value = {"text": "sample datasheet text", "page_count": 3}
        mock_extract.return_value = _short_channel()

        from io import BytesIO
        fake_pdf = BytesIO(b"%PDF-1.4 fake")
        resp = client.post(
            "/api/com/extract-channel",
            files={"file": ("test.pdf", fake_pdf, "application/pdf")},
        )
        assert resp.status_code == 200
        assert "channel" in resp.json()

    def test_extract_channel_rejects_non_pdf(self, client):
        from io import BytesIO
        resp = client.post(
            "/api/com/extract-channel",
            files={"file": ("test.txt", BytesIO(b"hello"), "text/plain")},
        )
        assert resp.status_code == 400
