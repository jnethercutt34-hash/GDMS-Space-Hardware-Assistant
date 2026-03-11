"""Tests for Phase 3: SI/PI Constraint Editor — models, extraction, CES export, router."""
import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from main import app
from models.constraint import ConstraintRule, ConstraintExtractionResult

client = TestClient(app)

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_MOCK_PDF_EXTRACTION = {
    "page_count": 8,
    "text": (
        "DDR4 Interface Timing Requirements\n"
        "Characteristic impedance: 40-50 Ω (single-ended), 80-100 Ω (differential)\n"
        "Setup time: 0.5 ns min, Hold time: 0.3 ns min\n"
        "VCCIO: 1.2 V ±5%\n"
        "Max trace length: 6 inches\n"
    ),
}

_SAMPLE_CONSTRAINTS = [
    ConstraintRule(
        Signal_Class="DDR4_DQ",
        Rule_Type="Impedance",
        Min="40 Ω",
        Typ="50 Ω",
        Max=None,
        Unit="Ω",
        Source_Page="3",
        Notes="Single-ended characteristic impedance",
    ),
    ConstraintRule(
        Signal_Class="DDR4_DQ",
        Rule_Type="Impedance",
        Min="80 Ω",
        Typ="100 Ω",
        Max=None,
        Unit="Ω",
        Source_Page="3",
        Notes="Differential impedance",
    ),
    ConstraintRule(
        Signal_Class="DDR4_CLK",
        Rule_Type="Skew",
        Min=None,
        Typ=None,
        Max="5 ps",
        Unit="ps",
        Source_Page="5",
        Notes="Intra-pair skew for differential clock",
    ),
    ConstraintRule(
        Signal_Class="DDR4_DQ",
        Rule_Type="Max_Length",
        Min=None,
        Typ=None,
        Max="6 in",
        Unit="in",
        Source_Page="7",
        Notes=None,
    ),
    ConstraintRule(
        Signal_Class="VCCIO_DDR",
        Rule_Type="Voltage_Level",
        Min="1.14 V",
        Typ="1.2 V",
        Max="1.26 V",
        Unit="V",
        Source_Page="4",
        Notes="±5% tolerance",
    ),
]


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


def _post_pdf(constraints=None):
    """Helper: POST a fake PDF to /api/extract-constraints with mocked services."""
    if constraints is None:
        constraints = _SAMPLE_CONSTRAINTS
    with (
        patch("routers.constraint.extract_text_from_pdf", return_value=_MOCK_PDF_EXTRACTION),
        patch("routers.constraint.extract_constraints_from_text", return_value=constraints),
    ):
        return client.post(
            "/api/extract-constraints",
            files={"file": ("ddr4_datasheet.pdf", b"%PDF-1.4", "application/pdf")},
        )


# ===========================================================================
# Model validation tests
# ===========================================================================

class TestConstraintRuleModel:
    def test_valid_rule_all_fields(self):
        rule = _SAMPLE_CONSTRAINTS[0]
        assert rule.Signal_Class == "DDR4_DQ"
        assert rule.Rule_Type == "Impedance"
        assert rule.Min == "40 Ω"
        assert rule.Typ == "50 Ω"
        assert rule.Max is None
        assert rule.Unit == "Ω"
        assert rule.Source_Page == "3"

    def test_valid_rule_minimal(self):
        rule = ConstraintRule(Signal_Class="NET_A", Rule_Type="Other")
        assert rule.Signal_Class == "NET_A"
        assert rule.Min is None
        assert rule.Notes is None

    def test_missing_required_signal_class(self):
        with pytest.raises(Exception):
            ConstraintRule(Rule_Type="Impedance")

    def test_missing_required_rule_type(self):
        with pytest.raises(Exception):
            ConstraintRule(Signal_Class="DDR4_DQ")

    def test_model_dump_roundtrip(self):
        rule = _SAMPLE_CONSTRAINTS[4]
        d = rule.model_dump()
        restored = ConstraintRule.model_validate(d)
        assert restored == rule

    def test_extraction_result_wrapper(self):
        result = ConstraintExtractionResult(constraints=_SAMPLE_CONSTRAINTS)
        assert len(result.constraints) == 5
        assert result.constraints[0].Rule_Type == "Impedance"

    def test_extraction_result_empty(self):
        result = ConstraintExtractionResult(constraints=[])
        assert result.constraints == []

    def test_extraction_result_json_schema(self):
        schema = ConstraintExtractionResult.model_json_schema()
        assert "constraints" in schema["properties"]


# ===========================================================================
# AI constraint extractor tests
# ===========================================================================

class TestConstraintExtractor:
    def test_extract_returns_validated_rules(self):
        ai_response = {
            "constraints": [c.model_dump() for c in _SAMPLE_CONSTRAINTS[:2]]
        }
        mock_client = _make_openai_mock(ai_response)

        with patch("services.constraint_extractor._get_client", return_value=mock_client):
            from services.constraint_extractor import extract_constraints_from_text
            result = extract_constraints_from_text("dummy text")

        assert len(result) == 2
        assert result[0].Signal_Class == "DDR4_DQ"
        assert result[0].Rule_Type == "Impedance"

    def test_extract_empty_constraints(self):
        ai_response = {"constraints": []}
        mock_client = _make_openai_mock(ai_response)

        with patch("services.constraint_extractor._get_client", return_value=mock_client):
            from services.constraint_extractor import extract_constraints_from_text
            result = extract_constraints_from_text("no SI/PI info here")

        assert result == []

    def test_extract_salvages_partial_data(self):
        """If one rule is malformed, the others should still be returned."""
        from pydantic import ValidationError as PydanticValidationError

        ai_response = {
            "constraints": [
                _SAMPLE_CONSTRAINTS[0].model_dump(),
                {"bad": "data"},  # missing required fields
                _SAMPLE_CONSTRAINTS[2].model_dump(),
            ]
        }
        mock_client = _make_openai_mock(ai_response)

        # Force the ValidationError fallback path
        def _raise_validation(*args, **kwargs):
            raise PydanticValidationError.from_exception_data(
                "ConstraintExtractionResult", []
            )

        with patch("services.constraint_extractor._get_client", return_value=mock_client):
            with patch(
                "services.constraint_extractor.ConstraintExtractionResult.model_validate",
                side_effect=_raise_validation,
            ):
                from services.constraint_extractor import extract_constraints_from_text
                result = extract_constraints_from_text("mixed text")

        assert len(result) == 2

    def test_extract_raises_on_bad_json(self):
        mock_message = MagicMock()
        mock_message.content = "not json at all"
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response

        with patch("services.constraint_extractor._get_client", return_value=mock_client):
            from services.constraint_extractor import extract_constraints_from_text
            with pytest.raises(ValueError, match="non-JSON"):
                extract_constraints_from_text("text")

    def test_extract_no_api_key(self):
        with patch.dict("os.environ", {}, clear=True):
            # Clear any cached INTERNAL_API_KEY
            with patch("services.constraint_extractor._get_client", side_effect=RuntimeError("INTERNAL_API_KEY is not set")):
                from services.constraint_extractor import extract_constraints_from_text
                with pytest.raises(RuntimeError, match="INTERNAL_API_KEY"):
                    extract_constraints_from_text("text")


# ===========================================================================
# CES export tests
# ===========================================================================

class TestCesExport:
    def test_generate_script_contains_constraints(self):
        from services.xpedition_ces_export import generate_ces_script
        constraints = [c.model_dump() for c in _SAMPLE_CONSTRAINTS[:2]]
        script = generate_ces_script(constraints)

        assert "GDMS Space Hardware Assistant" in script
        assert "CONSTRAINTS" in script
        assert "DDR4_DQ" in script
        assert "Impedance" in script
        assert "win32com.client" in script

    def test_generate_script_empty_list(self):
        from services.xpedition_ces_export import generate_ces_script
        script = generate_ces_script([])
        assert "CONSTRAINTS = []" in script

    def test_generate_script_handles_none_fields(self):
        from services.xpedition_ces_export import generate_ces_script
        constraints = [{"Signal_Class": "NET_X", "Rule_Type": "Other"}]
        script = generate_ces_script(constraints)
        assert '"Signal_Class": "NET_X"' in script
        assert "None" in script  # Missing fields should appear as None

    def test_generate_script_has_ces_category_map(self):
        from services.xpedition_ces_export import generate_ces_script
        script = generate_ces_script([_SAMPLE_CONSTRAINTS[0].model_dump()])
        assert "CES_CATEGORY_MAP" in script
        assert "Electrical.Impedance" in script
        assert "Timing.PropDelay" in script

    def test_generate_script_escapes_quotes(self):
        from services.xpedition_ces_export import generate_ces_script
        constraints = [{"Signal_Class": 'NET "special"', "Rule_Type": "Other"}]
        script = generate_ces_script(constraints)
        assert '\\"special\\"' in script


# ===========================================================================
# Router / endpoint tests
# ===========================================================================

class TestExtractConstraintsEndpoint:
    def test_success(self):
        resp = _post_pdf()
        assert resp.status_code == 200
        data = resp.json()
        assert data["filename"] == "ddr4_datasheet.pdf"
        assert data["page_count"] == 8
        assert len(data["constraints"]) == 5
        assert data["constraints"][0]["Signal_Class"] == "DDR4_DQ"

    def test_rejects_non_pdf(self):
        resp = client.post(
            "/api/extract-constraints",
            files={"file": ("test.txt", b"hello", "text/plain")},
        )
        assert resp.status_code == 400
        assert "PDF" in resp.json()["detail"]

    def test_empty_constraints(self):
        resp = _post_pdf(constraints=[])
        assert resp.status_code == 200
        assert resp.json()["constraints"] == []

    def test_api_key_missing_returns_503(self):
        with (
            patch("routers.constraint.extract_text_from_pdf", return_value=_MOCK_PDF_EXTRACTION),
            patch(
                "routers.constraint.extract_constraints_from_text",
                side_effect=RuntimeError("INTERNAL_API_KEY is not set"),
            ),
        ):
            resp = client.post(
                "/api/extract-constraints",
                files={"file": ("test.pdf", b"%PDF-1.4", "application/pdf")},
            )
        assert resp.status_code == 503

    def test_ai_error_returns_502(self):
        with (
            patch("routers.constraint.extract_text_from_pdf", return_value=_MOCK_PDF_EXTRACTION),
            patch(
                "routers.constraint.extract_constraints_from_text",
                side_effect=Exception("AI model timeout"),
            ),
        ):
            resp = client.post(
                "/api/extract-constraints",
                files={"file": ("test.pdf", b"%PDF-1.4", "application/pdf")},
            )
        assert resp.status_code == 502


class TestExportCesScriptEndpoint:
    def test_success_download(self):
        constraints = [c.model_dump() for c in _SAMPLE_CONSTRAINTS[:2]]
        resp = client.post(
            "/api/export-ces-script",
            json={"constraints": constraints},
        )
        assert resp.status_code == 200
        assert "text/x-python" in resp.headers["content-type"]
        assert "xpedition_ces_update.py" in resp.headers["content-disposition"]
        assert "CONSTRAINTS" in resp.text
        assert "DDR4_DQ" in resp.text

    def test_empty_constraints_returns_400(self):
        resp = client.post("/api/export-ces-script", json={"constraints": []})
        assert resp.status_code == 400

    def test_missing_body_returns_422(self):
        resp = client.post("/api/export-ces-script", json={})
        assert resp.status_code == 422
