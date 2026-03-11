"""Tests for Phase 2: FPGA delta engine, compare endpoint, and AI risk assessment."""
import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)

# ---------------------------------------------------------------------------
# Fixture CSV data
# ---------------------------------------------------------------------------

# Baseline: 5 signals at their original Xpedition positions
BASELINE_CSV = (
    b"Signal_Name,Pin,Bank\n"
    b"CLK_IN,A1,34\n"
    b"DATA_0,B2,34\n"
    b"DATA_1,C3,34\n"
    b"ADDR_0,D4,12\n"
    b"STABLE,E5,12\n"
)

# New Vivado export:
#   CLK_IN  — unchanged
#   DATA_0  — Pin AND Bank changed  (B2/34 → F6/35)
#   DATA_1  — Bank changed only     (C3/34 → C3/35)
#   ADDR_0  — unchanged
#   STABLE  — unchanged
NEW_CSV = (
    b"Signal_Name,Pin,Bank\n"
    b"CLK_IN,A1,34\n"
    b"DATA_0,F6,35\n"
    b"DATA_1,C3,35\n"
    b"ADDR_0,D4,12\n"
    b"STABLE,E5,12\n"
)

# A CSV where every signal matches baseline exactly
ALL_SAME_CSV = BASELINE_CSV

# CSV missing the required Bank column
MISSING_COL_CSV = (
    b"Signal_Name,Pin\n"
    b"CLK_IN,A1\n"
    b"DATA_0,F6\n"
)


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------

def _make_openai_mock(json_payload: dict) -> MagicMock:
    """Build a mock OpenAI client whose chat.completions.create returns json_payload."""
    mock_message = MagicMock()
    mock_message.content = json.dumps(json_payload)

    mock_choice = MagicMock()
    mock_choice.message = mock_message

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_response
    return mock_client


def _risk_payload_for_swaps():
    """Standard AI response payload for the DATA_0 / DATA_1 swap fixture."""
    return {
        "assessments": [
            {
                "Signal_Name": "DATA_0",
                "AI_Risk_Assessment": "High Risk: Pin and bank change detected — verify VCCIO compatibility and routing.",
            },
            {
                "Signal_Name": "DATA_1",
                "AI_Risk_Assessment": "Medium Risk: Bank change only — confirm I/O standard match.",
            },
        ]
    }


def _post_csvs(baseline=BASELINE_CSV, new=NEW_CSV):
    """Post CSVs with the AI risk assessor mocked to return standard assessments."""
    mock_client = _make_openai_mock(_risk_payload_for_swaps())
    with patch("services.fpga_risk_assessor._get_client", return_value=mock_client):
        return client.post(
            "/api/compare-fpga-pins",
            files={
                "baseline_csv": ("baseline.csv", baseline, "text/csv"),
                "new_csv":      ("new.csv",      new,      "text/csv"),
            },
        )


def _post_csvs_no_ai(baseline=BASELINE_CSV, new=NEW_CSV):
    """Post CSVs with the AI risk assessor raising RuntimeError (no API key)."""
    with patch(
        "services.fpga_risk_assessor._get_client",
        side_effect=RuntimeError("INTERNAL_API_KEY is not set"),
    ):
        return client.post(
            "/api/compare-fpga-pins",
            files={
                "baseline_csv": ("baseline.csv", baseline, "text/csv"),
                "new_csv":      ("new.csv",      new,      "text/csv"),
            },
        )


# ---------------------------------------------------------------------------
# Endpoint — happy path (with mocked AI)
# ---------------------------------------------------------------------------

def test_compare_returns_200():
    assert _post_csvs().status_code == 200


def test_compare_response_has_required_keys():
    data = _post_csvs().json()
    assert "total_swaps" in data
    assert "swapped_pins" in data


def test_compare_detects_correct_swap_count():
    """DATA_0 and DATA_1 changed; the other three are stable."""
    data = _post_csvs().json()
    assert data["total_swaps"] == 2
    assert len(data["swapped_pins"]) == 2


def test_compare_swapped_pin_has_all_columns():
    swap = _post_csvs().json()["swapped_pins"][0]
    for key in ("Signal_Name", "Old_Pin", "New_Pin", "Old_Bank", "New_Bank", "AI_Risk_Assessment"):
        assert key in swap


def test_compare_data0_values_correct():
    swaps = {s["Signal_Name"]: s for s in _post_csvs().json()["swapped_pins"]}
    assert "DATA_0" in swaps
    s = swaps["DATA_0"]
    assert s["Old_Pin"] == "B2"
    assert s["New_Pin"] == "F6"
    assert s["Old_Bank"] == "34"
    assert s["New_Bank"] == "35"


def test_compare_data1_bank_change_detected():
    """DATA_1 pin is unchanged but bank flipped — must still appear in delta."""
    swaps = {s["Signal_Name"]: s for s in _post_csvs().json()["swapped_pins"]}
    assert "DATA_1" in swaps
    s = swaps["DATA_1"]
    assert s["Old_Pin"] == s["New_Pin"] == "C3"
    assert s["Old_Bank"] == "34"
    assert s["New_Bank"] == "35"


def test_unchanged_signals_excluded():
    swaps = {s["Signal_Name"] for s in _post_csvs().json()["swapped_pins"]}
    assert "CLK_IN" not in swaps
    assert "ADDR_0" not in swaps
    assert "STABLE" not in swaps


def test_no_swaps_returns_empty_list():
    # No swaps → AI is never called, so no mock needed
    mock_client = _make_openai_mock({"assessments": []})
    with patch("services.fpga_risk_assessor._get_client", return_value=mock_client):
        response = client.post(
            "/api/compare-fpga-pins",
            files={
                "baseline_csv": ("baseline.csv", ALL_SAME_CSV, "text/csv"),
                "new_csv":      ("new.csv",      ALL_SAME_CSV, "text/csv"),
            },
        )
    data = response.json()
    assert data["total_swaps"] == 0
    assert data["swapped_pins"] == []


# ---------------------------------------------------------------------------
# Endpoint — validation errors
# ---------------------------------------------------------------------------

def test_missing_required_column_returns_400():
    response = _post_csvs(new=MISSING_COL_CSV)
    assert response.status_code == 400
    assert "Bank" in response.json()["detail"]


def test_missing_baseline_file_returns_422():
    response = client.post(
        "/api/compare-fpga-pins",
        files={"new_csv": ("new.csv", NEW_CSV, "text/csv")},
    )
    assert response.status_code == 422


def test_missing_new_file_returns_422():
    response = client.post(
        "/api/compare-fpga-pins",
        files={"baseline_csv": ("baseline.csv", BASELINE_CSV, "text/csv")},
    )
    assert response.status_code == 422


def test_unparseable_csv_returns_400():
    garbage = b"\x00\x01\x02\x03 not a csv at all \xff\xfe"
    response = _post_csvs(new=garbage)
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# csv_delta service — unit tests (no HTTP layer)
# ---------------------------------------------------------------------------

from services.csv_delta import compute_pin_delta


def test_service_returns_list():
    result = compute_pin_delta(BASELINE_CSV, NEW_CSV)
    assert isinstance(result, list)


def test_service_count_matches():
    assert len(compute_pin_delta(BASELINE_CSV, NEW_CSV)) == 2


def test_service_raises_on_missing_column():
    with pytest.raises(ValueError, match="Bank"):
        compute_pin_delta(BASELINE_CSV, MISSING_COL_CSV)


def test_service_raises_on_bad_bytes():
    with pytest.raises(ValueError):
        compute_pin_delta(b"", b"")


def test_service_signal_only_in_one_file_excluded():
    """Signals present in only one file (added / removed) must not appear in delta."""
    extra = BASELINE_CSV + b"NEW_SIG,Z9,99\n"
    result = compute_pin_delta(extra, NEW_CSV)
    signal_names = [r["Signal_Name"] for r in result]
    assert "NEW_SIG" not in signal_names


def test_service_whitespace_trimmed_in_signal_name():
    """Leading/trailing whitespace in Signal_Name must not prevent matching."""
    baseline = b"Signal_Name,Pin,Bank\n CLK_IN ,A1,34\n"
    new      = b"Signal_Name,Pin,Bank\nCLK_IN,B9,35\n"
    result = compute_pin_delta(baseline, new)
    assert len(result) == 1
    assert result[0]["Signal_Name"] == "CLK_IN"


# ---------------------------------------------------------------------------
# AI Risk Assessment — service unit tests
# ---------------------------------------------------------------------------

from services.fpga_risk_assessor import assess_pin_risks


def test_risk_assessor_populates_ai_field():
    """assess_pin_risks should fill AI_Risk_Assessment on each swap dict."""
    swaps = [
        {"Signal_Name": "DATA_0", "Old_Pin": "B2", "New_Pin": "F6",
         "Old_Bank": "34", "New_Bank": "35", "AI_Risk_Assessment": None},
        {"Signal_Name": "DATA_1", "Old_Pin": "C3", "New_Pin": "C3",
         "Old_Bank": "34", "New_Bank": "35", "AI_Risk_Assessment": None},
    ]
    mock_client = _make_openai_mock(_risk_payload_for_swaps())

    with patch("services.fpga_risk_assessor._get_client", return_value=mock_client):
        result = assess_pin_risks(swaps)

    assert len(result) == 2
    risk_map = {r["Signal_Name"]: r["AI_Risk_Assessment"] for r in result}
    assert risk_map["DATA_0"].startswith("High Risk:")
    assert risk_map["DATA_1"].startswith("Medium Risk:")


def test_risk_assessor_empty_list_returns_immediately():
    """Empty swap list should return immediately without calling AI."""
    result = assess_pin_risks([])
    assert result == []


def test_risk_assessor_raises_when_no_api_key():
    """Should propagate RuntimeError when INTERNAL_API_KEY is missing."""
    swaps = [
        {"Signal_Name": "CLK", "Old_Pin": "A1", "New_Pin": "B2",
         "Old_Bank": "34", "New_Bank": "35", "AI_Risk_Assessment": None},
    ]
    with patch(
        "services.fpga_risk_assessor._get_client",
        side_effect=RuntimeError("INTERNAL_API_KEY is not set"),
    ):
        with pytest.raises(RuntimeError, match="INTERNAL_API_KEY"):
            assess_pin_risks(swaps)


def test_risk_assessor_low_risk_for_same_bank():
    """LLM returns Low Risk for intra-bank move — verify it passes through."""
    payload = {
        "assessments": [
            {
                "Signal_Name": "GPIO_0",
                "AI_Risk_Assessment": "Low Risk: Pin change is within the same bank — minimal SI/PI impact.",
            }
        ]
    }
    swaps = [
        {"Signal_Name": "GPIO_0", "Old_Pin": "A1", "New_Pin": "A2",
         "Old_Bank": "34", "New_Bank": "34", "AI_Risk_Assessment": None},
    ]
    mock_client = _make_openai_mock(payload)

    with patch("services.fpga_risk_assessor._get_client", return_value=mock_client):
        result = assess_pin_risks(swaps)

    assert result[0]["AI_Risk_Assessment"].startswith("Low Risk:")


def test_risk_assessor_calls_llm_with_correct_signal_names():
    """Verify the LLM receives the correct signal names in its prompt."""
    swaps = [
        {"Signal_Name": "MY_SIG", "Old_Pin": "X1", "New_Pin": "Y2",
         "Old_Bank": "10", "New_Bank": "20", "AI_Risk_Assessment": None},
    ]
    payload = {
        "assessments": [
            {"Signal_Name": "MY_SIG", "AI_Risk_Assessment": "Low Risk: No concern."}
        ]
    }
    mock_client = _make_openai_mock(payload)

    with patch("services.fpga_risk_assessor._get_client", return_value=mock_client):
        assess_pin_risks(swaps)

    # Inspect the user message sent to the LLM
    call_args = mock_client.chat.completions.create.call_args
    messages = call_args.kwargs.get("messages") or call_args[1].get("messages")
    user_msg = messages[-1]["content"]
    assert "MY_SIG" in user_msg


# ---------------------------------------------------------------------------
# Endpoint — AI error handling
# ---------------------------------------------------------------------------

def test_endpoint_returns_503_when_api_key_missing():
    """503 when INTERNAL_API_KEY is not set."""
    response = _post_csvs_no_ai()
    assert response.status_code == 503
    assert "unavailable" in response.json()["detail"].lower()


def test_endpoint_returns_502_on_ai_network_error():
    """502 when the AI API call fails for non-key reasons."""
    with patch(
        "services.fpga_risk_assessor._get_client",
        side_effect=ConnectionError("Network unreachable"),
    ):
        response = client.post(
            "/api/compare-fpga-pins",
            files={
                "baseline_csv": ("baseline.csv", BASELINE_CSV, "text/csv"),
                "new_csv":      ("new.csv",      NEW_CSV, "text/csv"),
            },
        )
    assert response.status_code == 502
    assert "failed" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Endpoint — AI risk values in response
# ---------------------------------------------------------------------------

def test_endpoint_returns_risk_assessments_in_response():
    """When AI succeeds, response must contain non-null AI_Risk_Assessment."""
    data = _post_csvs().json()
    swaps = {s["Signal_Name"]: s for s in data["swapped_pins"]}
    assert swaps["DATA_0"]["AI_Risk_Assessment"].startswith("High Risk:")
    assert swaps["DATA_1"]["AI_Risk_Assessment"].startswith("Medium Risk:")


def test_endpoint_risk_badge_convention():
    """Verify risk strings match the DeltaTable.jsx badge convention."""
    data = _post_csvs().json()
    for swap in data["swapped_pins"]:
        assessment = swap["AI_Risk_Assessment"]
        assert assessment is not None
        upper = assessment.upper()
        assert (
            upper.startswith("HIGH RISK:")
            or upper.startswith("MEDIUM RISK:")
            or upper.startswith("LOW RISK:")
        ), f"Bad risk prefix: {assessment}"


# ---------------------------------------------------------------------------
# Xpedition I/O Export — service unit tests
# ---------------------------------------------------------------------------

from services.xpedition_io_export import generate_io_update_script


def test_export_generates_valid_python():
    """Generated script should be valid Python syntax."""
    swaps = [
        {"Signal_Name": "DATA_0", "Old_Pin": "B2", "New_Pin": "F6",
         "Old_Bank": "34", "New_Bank": "35", "AI_Risk_Assessment": "High Risk: Bank change."},
    ]
    script = generate_io_update_script(swaps)
    compile(script, "<export>", "exec")  # Raises SyntaxError if invalid


def test_export_contains_signal_names():
    """Script should embed the signal names from the swap data."""
    swaps = [
        {"Signal_Name": "CLK_NET", "Old_Pin": "A1", "New_Pin": "B2",
         "Old_Bank": "10", "New_Bank": "20", "AI_Risk_Assessment": None},
    ]
    script = generate_io_update_script(swaps)
    assert "CLK_NET" in script


def test_export_contains_win32com_import():
    """Script must reference win32com for Xpedition connectivity."""
    swaps = [
        {"Signal_Name": "SIG", "Old_Pin": "X", "New_Pin": "Y",
         "Old_Bank": "1", "New_Bank": "2", "AI_Risk_Assessment": None},
    ]
    script = generate_io_update_script(swaps)
    assert "win32com.client" in script


def test_export_contains_viewdraw_dispatch():
    """Script must dispatch to ViewDraw.Application."""
    swaps = [
        {"Signal_Name": "SIG", "Old_Pin": "X", "New_Pin": "Y",
         "Old_Bank": "1", "New_Bank": "2", "AI_Risk_Assessment": None},
    ]
    script = generate_io_update_script(swaps)
    assert "ViewDraw.Application" in script


def test_export_multiple_swaps():
    """Script should contain all swapped signals."""
    swaps = [
        {"Signal_Name": "A", "Old_Pin": "1", "New_Pin": "2",
         "Old_Bank": "10", "New_Bank": "20", "AI_Risk_Assessment": "Low Risk: ok"},
        {"Signal_Name": "B", "Old_Pin": "3", "New_Pin": "4",
         "Old_Bank": "30", "New_Bank": "40", "AI_Risk_Assessment": "High Risk: bad"},
    ]
    script = generate_io_update_script(swaps)
    assert '"A"' in script
    assert '"B"' in script


# ---------------------------------------------------------------------------
# Xpedition I/O Export — endpoint tests
# ---------------------------------------------------------------------------

def test_export_endpoint_returns_200():
    swaps = [
        {"Signal_Name": "DATA_0", "Old_Pin": "B2", "New_Pin": "F6",
         "Old_Bank": "34", "New_Bank": "35", "AI_Risk_Assessment": "High Risk: test"},
    ]
    response = client.post("/api/export-io-script", json={"swapped_pins": swaps})
    assert response.status_code == 200


def test_export_endpoint_content_type():
    swaps = [
        {"Signal_Name": "SIG", "Old_Pin": "X", "New_Pin": "Y",
         "Old_Bank": "1", "New_Bank": "2", "AI_Risk_Assessment": None},
    ]
    response = client.post("/api/export-io-script", json={"swapped_pins": swaps})
    assert "text/x-python" in response.headers["content-type"]


def test_export_endpoint_content_disposition():
    swaps = [
        {"Signal_Name": "SIG", "Old_Pin": "X", "New_Pin": "Y",
         "Old_Bank": "1", "New_Bank": "2", "AI_Risk_Assessment": None},
    ]
    response = client.post("/api/export-io-script", json={"swapped_pins": swaps})
    assert "xpedition_pin_update.py" in response.headers.get("content-disposition", "")


def test_export_endpoint_empty_swaps_returns_400():
    response = client.post("/api/export-io-script", json={"swapped_pins": []})
    assert response.status_code == 400


def test_export_endpoint_script_is_valid_python():
    swaps = [
        {"Signal_Name": "NET_A", "Old_Pin": "P1", "New_Pin": "P2",
         "Old_Bank": "5", "New_Bank": "6", "AI_Risk_Assessment": "Low Risk: minor."},
    ]
    response = client.post("/api/export-io-script", json={"swapped_pins": swaps})
    compile(response.text, "<export_endpoint>", "exec")
