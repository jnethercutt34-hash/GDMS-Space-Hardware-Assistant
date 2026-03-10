"""Tests for Phase 2 Steps 1 & 2: FPGA delta engine + compare endpoint."""
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


def _post_csvs(baseline=BASELINE_CSV, new=NEW_CSV):
    return client.post(
        "/api/compare-fpga-pins",
        files={
            "baseline_csv": ("baseline.csv", baseline, "text/csv"),
            "new_csv":      ("new.csv",      new,      "text/csv"),
        },
    )


# ---------------------------------------------------------------------------
# Endpoint — happy path
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


def test_ai_risk_assessment_is_null_at_step2():
    """AI_Risk_Assessment must be None until Step 3 is wired in."""
    for swap in _post_csvs().json()["swapped_pins"]:
        assert swap["AI_Risk_Assessment"] is None


def test_no_swaps_returns_empty_list():
    data = _post_csvs(new=ALL_SAME_CSV).json()
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
