"""Unit tests for the chunked PDF extraction pipeline.

Tests cover _chunk_text, _merge_component_results, and
extract_components_from_text_chunked from services.ai_extractor.
"""
import logging
import pytest
from unittest.mock import patch, call

from models.component import ComponentData
from services.ai_extractor import (
    _chunk_text,
    _merge_component_results,
    extract_components_from_text_chunked,
    _MAX_CHUNK_CHARS,
    _CHUNK_OVERLAP,
    _MAX_CHUNKS,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_comp(part_number: str, **kwargs) -> ComponentData:
    defaults = dict(
        Part_Number=part_number,
        Manufacturer="Acme",
        Value=None,
        Tolerance=None,
        Voltage_Rating=None,
        Package_Type=None,
        Pin_Count=None,
        Operating_Temperature_Range=None,
        Thermal_Resistance=None,
        Radiation_TID=None,
        Radiation_SEL_Threshold=None,
        Radiation_SEU_Rate=None,
        Summary=None,
    )
    defaults.update(kwargs)
    return ComponentData.model_validate(defaults)


# ---------------------------------------------------------------------------
# _chunk_text tests (3)
# ---------------------------------------------------------------------------

def test_chunk_text_single_chunk_fast_path():
    """Short text → returns list with the original string, no splitting."""
    text = "A" * 100
    result = _chunk_text(text, chunk_size=200, overlap=20, max_chunks=5)
    assert result == [text]


def test_chunk_text_overlap_correctness():
    """The first _CHUNK_OVERLAP chars of chunk[1] must match the tail of chunk[0]."""
    chunk_size = 100
    overlap = 20
    text = "X" * 300
    chunks = _chunk_text(text, chunk_size=chunk_size, overlap=overlap, max_chunks=10)
    assert len(chunks) > 1
    # The overlapping region
    assert chunks[0][-overlap:] == chunks[1][:overlap]


def test_chunk_text_max_chunks_cap(caplog):
    """When more chunks than max_chunks would be generated, a warning is logged
    and the list is capped at max_chunks entries."""
    # chunk_size=10, overlap=0, stride=10 → 100-char text → 10 chunks; cap at 3
    text = "A" * 100
    with caplog.at_level(logging.WARNING, logger="services.ai_extractor"):
        chunks = _chunk_text(text, chunk_size=10, overlap=0, max_chunks=3)
    assert len(chunks) == 3
    # Last chunk must cover the tail of the text
    assert chunks[-1] == text[20:]  # stride=10, first 2 chunks cover [0:10],[10:20], tail=[20:]
    assert any("capping" in r.message.lower() for r in caplog.records)


# ---------------------------------------------------------------------------
# _merge_component_results tests (3)
# ---------------------------------------------------------------------------

def test_merge_deduplicates_same_part_number():
    """Same Part_Number in two chunks → only one entry in output."""
    comp = _make_comp("ABC123")
    chunk_results = [([comp], []), ([comp], [])]
    merged, warnings = _merge_component_results(chunk_results)
    assert len(merged) == 1
    assert merged[0].Part_Number == "ABC123"


def test_merge_fills_null_from_later_chunk():
    """A null field in the first chunk is filled from a later chunk."""
    comp1 = _make_comp("ABC123", Voltage_Rating=None)
    comp2 = _make_comp("ABC123", Voltage_Rating="3.3 V")
    chunk_results = [([comp1], []), ([comp2], [])]
    merged, _ = _merge_component_results(chunk_results)
    assert merged[0].Voltage_Rating == "3.3 V"


def test_merge_keeps_first_non_null_ignores_conflict():
    """When both chunks have a non-null value for the same field, the first wins."""
    comp1 = _make_comp("ABC123", Voltage_Rating="5 V")
    comp2 = _make_comp("ABC123", Voltage_Rating="3.3 V")
    chunk_results = [([comp1], []), ([comp2], [])]
    merged, _ = _merge_component_results(chunk_results)
    assert merged[0].Voltage_Rating == "5 V"


# ---------------------------------------------------------------------------
# extract_components_from_text_chunked tests (3)
# ---------------------------------------------------------------------------

def test_chunked_extraction_calls_base_n_times():
    """For text that requires N chunks, the base extractor is called N times."""
    comp = _make_comp("PART1")
    # 3 chunks: chunk_size=10, overlap=0, stride=10, 30-char text → 3 chunks
    text = "D" * 30
    with (
        patch("services.ai_extractor._MAX_CHUNK_CHARS", 10),
        patch("services.ai_extractor._CHUNK_OVERLAP", 0),
        patch("services.ai_extractor._MAX_CHUNKS", 5),
        patch("services.ai_extractor.extract_components_from_text", return_value=([comp], [])) as mock_extract,
    ):
        rows, warnings = extract_components_from_text_chunked(text)

    assert mock_extract.call_count == 3
    assert len(rows) == 1  # deduplicated
    assert rows[0].Part_Number == "PART1"


def test_chunked_extraction_fast_path_small_text():
    """Text that fits in one chunk → base extractor called exactly once, no cap warning."""
    comp = _make_comp("SMALL1")
    text = "S" * 50
    with (
        patch("services.ai_extractor._MAX_CHUNK_CHARS", 100),
        patch("services.ai_extractor.extract_components_from_text", return_value=([comp], [])) as mock_extract,
    ):
        rows, warnings = extract_components_from_text_chunked(text)

    mock_extract.assert_called_once_with(text)
    assert not any("cap" in w.lower() for w in warnings)


def test_chunked_extraction_cap_warning_emitted():
    """When the document exceeds MAX_CHUNKS, a cap warning is included in the output."""
    comp = _make_comp("BIG1")
    # 10-char chunks, no overlap, 6 chunks needed for 60-char text; cap at 3
    text = "B" * 60
    with (
        patch("services.ai_extractor._MAX_CHUNK_CHARS", 10),
        patch("services.ai_extractor._CHUNK_OVERLAP", 0),
        patch("services.ai_extractor._MAX_CHUNKS", 3),
        patch("services.ai_extractor.extract_components_from_text", return_value=([comp], [])),
    ):
        rows, warnings = extract_components_from_text_chunked(text)

    assert any("cap" in w.lower() for w in warnings), f"Expected cap warning, got: {warnings}"
