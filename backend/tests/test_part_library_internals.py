"""Unit tests for part_library internal helpers: variant consolidation and search text."""
import pytest

from services.part_library import (
    _base_pn,
    _build_search_text,
    _build_variant_entry,
    _ensure_search_text,
    _pick_primary,
    consolidate_variants,
)


# ===========================================================================
# _base_pn
# ===========================================================================

class TestBasePn:
    def test_no_suffix(self):
        assert _base_pn("TPS7H1111") == "TPS7H1111"

    def test_strip_sep(self):
        assert _base_pn("TPS7H1111SEP") == "TPS7H1111"

    def test_strip_mpwpt(self):
        assert _base_pn("TPS7H1111MPWPT") == "TPS7H1111"

    def test_strip_chained_suffixes(self):
        # TPS7H1111MPWPTSEP -> strip SEP -> TPS7H1111MPWPT -> strip MPWPT -> TPS7H1111
        assert _base_pn("TPS7H1111MPWPTSEP") == "TPS7H1111"

    def test_strip_trailing_dash(self):
        assert _base_pn("LTC2983-") == "LTC2983"

    def test_strip_rh(self):
        assert _base_pn("XQRKU060RH") == "XQRKU060"

    def test_preserves_short_names(self):
        assert _base_pn("AD590") == "AD590"


# ===========================================================================
# _pick_primary
# ===========================================================================

class TestPickPrimary:
    def _part(self, pn, **kwargs):
        return {"Part_Number": pn, **kwargs}

    def test_single_part(self):
        p = self._part("TPS7H1111")
        primary, variants = _pick_primary([p])
        assert primary["Part_Number"] == "TPS7H1111"
        assert variants == []

    def test_prefers_shorter_base(self):
        parts = [
            self._part("TPS7H1111MPWPTSEP"),
            self._part("TPS7H1111"),
        ]
        primary, variants = _pick_primary(parts)
        assert primary["Part_Number"] == "TPS7H1111"
        assert len(variants) == 1

    def test_military_pn_deprioritized(self):
        parts = [
            self._part("5962A1234567"),
            self._part("TPS7H1111"),
        ]
        primary, _ = _pick_primary(parts)
        assert primary["Part_Number"] == "TPS7H1111"

    def test_sample_pn_deprioritized(self):
        parts = [
            self._part("TPS7H1111EVM"),
            self._part("TPS7H1111"),
        ]
        primary, _ = _pick_primary(parts)
        assert primary["Part_Number"] == "TPS7H1111"

    def test_all_military_picks_first(self):
        parts = [
            self._part("5962A1111111"),
            self._part("5962B2222222"),
        ]
        primary, variants = _pick_primary(parts)
        assert primary is not None
        assert len(variants) == 1


# ===========================================================================
# _build_variant_entry
# ===========================================================================

class TestBuildVariantEntry:
    def test_includes_differing_fields(self):
        primary = {"Part_Number": "TPS7H1111", "Package_Type": "QFP"}
        variant = {"Part_Number": "TPS7H1111SEP", "Package_Type": "BGA"}
        entry = _build_variant_entry(variant, primary)
        assert entry["Part_Number"] == "TPS7H1111SEP"
        assert entry["Package_Type"] == "BGA"

    def test_excludes_same_fields(self):
        primary = {"Part_Number": "TPS7H1111", "Package_Type": "QFP", "Pin_Count": 48}
        variant = {"Part_Number": "TPS7H1111SEP", "Package_Type": "QFP", "Pin_Count": 48}
        entry = _build_variant_entry(variant, primary)
        assert entry == {"Part_Number": "TPS7H1111SEP"}

    def test_includes_different_summary(self):
        primary = {"Part_Number": "A", "Summary": "Base part"}
        variant = {"Part_Number": "B", "Summary": "Variant part"}
        entry = _build_variant_entry(variant, primary)
        assert entry["Summary"] == "Variant part"

    def test_excludes_same_summary(self):
        primary = {"Part_Number": "A", "Summary": "Same"}
        variant = {"Part_Number": "B", "Summary": "Same"}
        entry = _build_variant_entry(variant, primary)
        assert "Summary" not in entry


# ===========================================================================
# consolidate_variants
# ===========================================================================

class TestConsolidateVariants:
    def test_empty(self):
        assert consolidate_variants([]) == {}

    def test_single_part_no_variants(self):
        result = consolidate_variants([{"Part_Number": "A", "Summary": "Test"}])
        assert result["Part_Number"] == "A"
        assert "variants" not in result

    def test_multiple_parts_creates_variants(self):
        parts = [
            {"Part_Number": "TPS7H1111MPWPTSEP", "Package_Type": "TSSOP"},
            {"Part_Number": "TPS7H1111", "Package_Type": "QFP"},
        ]
        result = consolidate_variants(parts)
        assert result["Part_Number"] == "TPS7H1111"
        assert "variants" in result
        assert len(result["variants"]) == 1
        assert result["variants"][0]["Part_Number"] == "TPS7H1111MPWPTSEP"


# ===========================================================================
# _build_search_text / _ensure_search_text
# ===========================================================================

class TestBuildSearchText:
    def test_includes_string_fields(self):
        part = {"Part_Number": "TPS7H1111", "Summary": "Rad-hard LDO"}
        text = _build_search_text(part)
        assert "tps7h1111" in text
        assert "rad-hard ldo" in text

    def test_excludes_search_text_field(self):
        part = {"Part_Number": "A", "_search_text": "old cached"}
        text = _build_search_text(part)
        assert "old cached" not in text

    def test_excludes_variants_key_includes_variant_content(self):
        part = {
            "Part_Number": "TPS7H1111",
            "variants": [{"Part_Number": "TPS7H1111SEP", "Package_Type": "BGA"}],
        }
        text = _build_search_text(part)
        assert "tps7h1111sep" in text
        assert "bga" in text

    def test_excludes_list_fields(self):
        part = {"Part_Number": "A", "tags": ["fpga", "rad-hard"]}
        text = _build_search_text(part)
        assert "fpga" not in text  # list fields are skipped

    def test_none_values_skipped(self):
        part = {"Part_Number": "A", "Summary": None}
        text = _build_search_text(part)
        assert "none" not in text


class TestEnsureSearchText:
    def test_adds_if_missing(self):
        part = {"Part_Number": "A"}
        _ensure_search_text(part)
        assert "_search_text" in part

    def test_does_not_overwrite(self):
        part = {"Part_Number": "A", "_search_text": "existing"}
        _ensure_search_text(part)
        assert part["_search_text"] == "existing"
