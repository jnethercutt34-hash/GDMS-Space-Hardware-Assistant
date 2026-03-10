"""Tests for Phase 1 Steps 2, 3 & 4: ingestion, AI extraction, Xpedition push."""
import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from main import app
from models.component import ComponentData, ComponentExtractionResult

client = TestClient(app)

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_MOCK_PDF_EXTRACTION = {
    "page_count": 2,
    "text": "HS9-5104RH radiation-hardened CMOS 4-bit binary counter",
    "pages": [
        "HS9-5104RH radiation-hardened CMOS 4-bit binary counter",
        "Package: CLCC-28  Voltage: 5 V",
    ],
}

_MOCK_COMPONENT = ComponentData(
    Part_Number="HS9-5104RH",
    Manufacturer="Renesas",
    Value=None,
    Tolerance=None,
    Voltage_Rating="5 V",
    Package_Type="CLCC-28",
    Pin_Count="28",
    Thermal_Resistance=None,
    Summary="Radiation-hardened CMOS 4-bit binary counter for space applications.",
)

_MOCK_EXTRACTION_RESULT = ComponentExtractionResult(components=[_MOCK_COMPONENT])


def _post_pdf(rows=None):
    """Helper: POST a fake PDF to /api/upload-datasheet with mocked services."""
    if rows is None:
        rows = [_MOCK_COMPONENT]
    mock_result = ComponentExtractionResult(components=rows)
    with (
        patch("routers.librarian.extract_text_from_pdf", return_value=_MOCK_PDF_EXTRACTION),
        patch("routers.librarian.extract_components_from_text", return_value=rows),
        patch("services.part_library.upsert_parts", return_value=None),
    ):
        return client.post(
            "/api/upload-datasheet",
            files={"file": ("test.pdf", b"%PDF-1.4", "application/pdf")},
        )


# ---------------------------------------------------------------------------
# Step 2: /api/upload-datasheet — endpoint tests
# ---------------------------------------------------------------------------


def test_upload_returns_200_with_rows_key():
    response = _post_pdf()
    assert response.status_code == 200
    assert "rows" in response.json()


def test_upload_returns_correct_row_count():
    response = _post_pdf()
    assert len(response.json()["rows"]) == 1


def test_upload_requires_pdf_file():
    response = client.post(
        "/api/upload-datasheet",
        files={"file": ("test.txt", b"not a pdf", "text/plain")},
    )
    assert response.status_code == 400


def test_upload_missing_file_returns_422():
    response = client.post("/api/upload-datasheet")
    assert response.status_code == 422


def test_rows_contain_all_nine_columns():
    expected_keys = {
        "Part_Number", "Manufacturer", "Value", "Tolerance",
        "Voltage_Rating", "Package_Type", "Pin_Count", "Thermal_Resistance",
        "Summary",
    }
    data = _post_pdf().json()
    assert len(data["rows"]) == 1
    assert expected_keys == set(data["rows"][0].keys())


def test_rows_values_match_mock():
    data = _post_pdf().json()
    row = data["rows"][0]
    assert row["Part_Number"] == "HS9-5104RH"
    assert row["Manufacturer"] == "Renesas"
    assert row["Voltage_Rating"] == "5 V"
    assert row["Package_Type"] == "CLCC-28"
    assert row["Pin_Count"] == "28"
    # Absent fields serialise as None
    assert row["Value"] is None
    assert row["Thermal_Resistance"] is None


def test_empty_rows_returned_when_ai_finds_nothing():
    data = _post_pdf(rows=[]).json()
    assert data["rows"] == []


# ---------------------------------------------------------------------------
# Step 3: AI extraction — error handling
# ---------------------------------------------------------------------------


def test_missing_api_key_returns_503():
    with (
        patch("routers.librarian.extract_text_from_pdf", return_value=_MOCK_PDF_EXTRACTION),
        patch(
            "routers.librarian.extract_components_from_text",
            side_effect=RuntimeError("INTERNAL_API_KEY is not set."),
        ),
    ):
        response = client.post(
            "/api/upload-datasheet",
            files={"file": ("test.pdf", b"%PDF-1.4", "application/pdf")},
        )
    assert response.status_code == 503
    assert "INTERNAL_API_KEY" in response.json()["detail"]


def test_api_failure_returns_502():
    with (
        patch("routers.librarian.extract_text_from_pdf", return_value=_MOCK_PDF_EXTRACTION),
        patch(
            "routers.librarian.extract_components_from_text",
            side_effect=Exception("connection timeout"),
        ),
    ):
        response = client.post(
            "/api/upload-datasheet",
            files={"file": ("test.pdf", b"%PDF-1.4", "application/pdf")},
        )
    assert response.status_code == 502
    assert "AI extraction failed" in response.json()["detail"]


# ---------------------------------------------------------------------------
# Step 3: ai_extractor service — unit tests (OpenAI client mocked)
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


def test_ai_extractor_returns_validated_component_list():
    payload = {
        "components": [
            {
                "Part_Number": "LM317",
                "Manufacturer": "Texas Instruments",
                "Value": "1.25–37 V",
                "Tolerance": None,
                "Voltage_Rating": "40 V",
                "Package_Type": "TO-220",
                "Pin_Count": "3",
                "Thermal_Resistance": "65 °C/W",
            }
        ]
    }
    mock_client = _make_openai_mock(payload)

    with patch("services.ai_extractor._get_client", return_value=mock_client):
        from services.ai_extractor import extract_components_from_text
        result = extract_components_from_text("LM317 voltage regulator datasheet text")

    assert len(result) == 1
    assert isinstance(result[0], ComponentData)
    assert result[0].Part_Number == "LM317"
    assert result[0].Voltage_Rating == "40 V"
    assert result[0].Pin_Count == "3"


def test_ai_extractor_skips_rows_missing_required_fields():
    """Rows without Part_Number or Manufacturer must be dropped after validation."""
    payload = {
        "components": [
            {"Part_Number": "GOOD-PART", "Manufacturer": "Acme"},
            {"Value": "10 nF"},  # missing required fields — should be skipped
        ]
    }
    mock_client = _make_openai_mock(payload)

    with patch("services.ai_extractor._get_client", return_value=mock_client):
        from services.ai_extractor import extract_components_from_text
        result = extract_components_from_text("some text")

    assert len(result) == 1
    assert result[0].Part_Number == "GOOD-PART"


def test_ai_extractor_handles_empty_components_list():
    payload = {"components": []}
    mock_client = _make_openai_mock(payload)

    with patch("services.ai_extractor._get_client", return_value=mock_client):
        from services.ai_extractor import extract_components_from_text
        result = extract_components_from_text("blank page")

    assert result == []


def test_ai_extractor_raises_runtime_error_when_key_missing():
    with patch.dict("os.environ", {}, clear=True):
        # Ensure INTERNAL_API_KEY is absent
        import os
        os.environ.pop("INTERNAL_API_KEY", None)

        from services.ai_extractor import extract_components_from_text
        with pytest.raises(RuntimeError, match="INTERNAL_API_KEY"):
            extract_components_from_text("some text")


# ---------------------------------------------------------------------------
# Step 2: pdf_extractor service — unit tests (unchanged from Step 2)
# ---------------------------------------------------------------------------


def test_extract_text_service_returns_correct_structure():
    mock_page = MagicMock()
    mock_page.extract_text.return_value = "GDMS Component Data"

    mock_pdf_cm = MagicMock()
    mock_pdf_cm.__enter__ = MagicMock(return_value=mock_pdf_cm)
    mock_pdf_cm.__exit__ = MagicMock(return_value=False)
    mock_pdf_cm.pages = [mock_page, mock_page]

    with patch("services.pdf_extractor.pdfplumber.open", return_value=mock_pdf_cm):
        from services.pdf_extractor import extract_text_from_pdf
        result = extract_text_from_pdf(b"fake pdf bytes")

    assert result["page_count"] == 2
    assert result["text"] == "GDMS Component Data\n\nGDMS Component Data"
    assert result["pages"] == ["GDMS Component Data", "GDMS Component Data"]


def test_extract_text_service_handles_empty_pages():
    mock_page = MagicMock()
    mock_page.extract_text.return_value = None

    mock_pdf_cm = MagicMock()
    mock_pdf_cm.__enter__ = MagicMock(return_value=mock_pdf_cm)
    mock_pdf_cm.__exit__ = MagicMock(return_value=False)
    mock_pdf_cm.pages = [mock_page]

    with patch("services.pdf_extractor.pdfplumber.open", return_value=mock_pdf_cm):
        from services.pdf_extractor import extract_text_from_pdf
        result = extract_text_from_pdf(b"fake pdf bytes")

    assert result["pages"] == [""]
    assert result["text"] == ""


# ---------------------------------------------------------------------------
# Step 4: /api/push-to-databook — endpoint tests (stub mocked)
# ---------------------------------------------------------------------------

_PUSH_PAYLOAD = {
    "rows": [
        {
            "Part_Number": "HS9-5104RH",
            "Manufacturer": "Renesas",
            "Value": None,
            "Tolerance": None,
            "Voltage_Rating": "5 V",
            "Package_Type": "CLCC-28",
            "Pin_Count": "28",
            "Thermal_Resistance": None,
        }
    ]
}

_STUB_SUCCESS = {"status": "success", "message": "Simulated push to Xpedition successful."}
_STUB_SIM     = {"status": "simulation_only", "message": "Xpedition not running. Data logged to console.", "data_payload": {}}


def test_push_returns_200_with_results_key():
    with patch("routers.librarian.simulate_xpedition_push", return_value=_STUB_SUCCESS):
        response = client.post("/api/push-to-databook", json=_PUSH_PAYLOAD)
    assert response.status_code == 200
    assert "results" in response.json()


def test_push_result_contains_part_number_and_status():
    with patch("routers.librarian.simulate_xpedition_push", return_value=_STUB_SUCCESS):
        data = client.post("/api/push-to-databook", json=_PUSH_PAYLOAD).json()
    result = data["results"][0]
    assert result["Part_Number"] == "HS9-5104RH"
    assert result["status"] == "success"
    assert result["message"] == "Simulated push to Xpedition successful."


def test_push_simulation_only_status_propagated():
    """The 'simulation_only' status from the stub must pass through unchanged."""
    with patch("routers.librarian.simulate_xpedition_push", return_value=_STUB_SIM):
        data = client.post("/api/push-to-databook", json=_PUSH_PAYLOAD).json()
    assert data["results"][0]["status"] == "simulation_only"


def test_push_calls_stub_once_per_row():
    two_rows = {
        "rows": [
            {**_PUSH_PAYLOAD["rows"][0]},
            {**_PUSH_PAYLOAD["rows"][0], "Part_Number": "LM317"},
        ]
    }
    with patch("routers.librarian.simulate_xpedition_push", return_value=_STUB_SUCCESS) as mock_stub:
        client.post("/api/push-to-databook", json=two_rows)
    assert mock_stub.call_count == 2


def test_push_empty_rows_returns_400():
    response = client.post("/api/push-to-databook", json={"rows": []})
    assert response.status_code == 400


def test_push_missing_body_returns_422():
    response = client.post("/api/push-to-databook")
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Step 4: xpedition_stub service — unit tests (win32com mocked)
# ---------------------------------------------------------------------------


def test_stub_returns_success_when_dispatch_works():
    """When win32com.client.Dispatch succeeds, status must be 'success'."""
    mock_vdapp = MagicMock()
    mock_win32 = MagicMock()
    mock_win32.Dispatch.return_value = mock_vdapp

    component = json.dumps({"Part_Number": "LM317", "Manufacturer": "TI"})

    with patch.dict("sys.modules", {"win32com": mock_win32, "win32com.client": mock_win32}):
        from services import xpedition_stub
        import importlib
        importlib.reload(xpedition_stub)
        result = xpedition_stub.simulate_xpedition_push(component)

    assert result["status"] == "success"
    assert "successful" in result["message"]


def test_stub_returns_simulation_only_when_dispatch_fails():
    """When win32com is unavailable (ImportError), status must be 'simulation_only'.

    Sets sys.modules entries to None so that the lazy 'import win32com.client'
    inside simulate_xpedition_push raises ImportError, which the stub catches.
    """
    import sys

    component = json.dumps({"Part_Number": "LM317", "Manufacturer": "TI"})

    from services.xpedition_stub import simulate_xpedition_push

    with patch.dict("sys.modules", {"win32com": None, "win32com.client": None}):
        result = simulate_xpedition_push(component)

    assert result["status"] == "simulation_only"
    assert "data_payload" in result
    assert result["data_payload"]["Part_Number"] == "LM317"
