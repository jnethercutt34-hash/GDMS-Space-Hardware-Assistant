"""Unit tests for ai_extractor._enrich_from_text() regex fallback patterns.

Each test supplies a component dict with one field missing and a text string
containing the pattern, then asserts the field was filled correctly.
"""
import pytest

from services.ai_extractor import _enrich_from_text


# ---------------------------------------------------------------------------
# Pin Count
# ---------------------------------------------------------------------------

class TestPinCount:
    def test_n_pin_pattern(self):
        comp = {}
        _enrich_from_text(comp, "This is a 28-pin HTSSOP package")
        assert comp["Pin_Count"] == "28"

    def test_n_Pin_capitalized(self):
        comp = {}
        _enrich_from_text(comp, "Available in 100-Pin QFP")
        assert comp["Pin_Count"] == "100"

    def test_ball_bga_not_matched(self):
        """'100-ball BGA' does not match the N-pin regex — verify no false match."""
        comp = {}
        _enrich_from_text(comp, "100-ball BGA package")
        assert comp.get("Pin_Count") is None

    def test_skipped_when_already_set(self):
        comp = {"Pin_Count": "64"}
        _enrich_from_text(comp, "This is a 28-pin package")
        assert comp["Pin_Count"] == "64"  # not overwritten


# ---------------------------------------------------------------------------
# Operating Temperature Range
# ---------------------------------------------------------------------------

class TestTemperatureRange:
    def test_military_minus55_to_plus125(self):
        comp = {}
        _enrich_from_text(comp, "Operating temperature: -55 °C to +125 °C")
        assert comp["Operating_Temperature_Range"] == "-55 to +125 C"

    def test_industrial_minus40_to_plus85(self):
        comp = {}
        _enrich_from_text(comp, "Operating range: -40 °C to +85 °C")
        assert comp["Operating_Temperature_Range"] == "-40 to +85 C"

    def test_en_dash_minus55(self):
        """En-dash (–55) instead of hyphen (-55)."""
        comp = {}
        _enrich_from_text(comp, "Temperature: –55 C to 125 C")
        assert comp["Operating_Temperature_Range"] == "-55 to +125 C"

    def test_no_match_other_range(self):
        comp = {}
        _enrich_from_text(comp, "Storage temperature: -65 C to +150 C")
        assert comp.get("Operating_Temperature_Range") is None

    def test_skipped_when_already_set(self):
        comp = {"Operating_Temperature_Range": "-40 to +105 C"}
        _enrich_from_text(comp, "Operating temperature: -55 °C to +125 °C")
        assert comp["Operating_Temperature_Range"] == "-40 to +105 C"


# ---------------------------------------------------------------------------
# Radiation TID
# ---------------------------------------------------------------------------

class TestRadiationTID:
    def test_krad_si(self):
        comp = {}
        _enrich_from_text(comp, "Total ionizing dose: 100 krad(Si)")
        assert comp["Radiation_TID"] == "100 krad(Si)"

    def test_krad_si_no_parens(self):
        comp = {}
        _enrich_from_text(comp, "TID tested to 300 krad Si minimum")
        assert comp["Radiation_TID"] == "300 krad(Si)"

    def test_skipped_when_already_set(self):
        comp = {"Radiation_TID": "50 krad(Si)"}
        _enrich_from_text(comp, "Rated for 100 krad(Si)")
        assert comp["Radiation_TID"] == "50 krad(Si)"


# ---------------------------------------------------------------------------
# SEL Threshold
# ---------------------------------------------------------------------------

class TestSELThreshold:
    def test_sel_immune_let_pattern(self):
        comp = {}
        _enrich_from_text(comp, "SEL immune to LET = 75 MeV-cm2/mg")
        assert "75" in comp["Radiation_SEL_Threshold"]
        assert "MeV" in comp["Radiation_SEL_Threshold"]

    def test_sel_free_pattern(self):
        comp = {}
        _enrich_from_text(comp, "Single Event Latchup free to 80 MeV")
        assert "80" in comp["Radiation_SEL_Threshold"]

    def test_bare_let_pattern(self):
        """LET = N MeV without SEL context — still matched as fallback."""
        comp = {}
        _enrich_from_text(comp, "LET threshold: LET = 43 MeV-cm2/mg")
        assert "43" in comp["Radiation_SEL_Threshold"]

    def test_skipped_when_already_set(self):
        comp = {"Radiation_SEL_Threshold": "60 MeV-cm2/mg"}
        _enrich_from_text(comp, "SEL immune to LET = 75 MeV")
        assert comp["Radiation_SEL_Threshold"] == "60 MeV-cm2/mg"


# ---------------------------------------------------------------------------
# Voltage Rating
# ---------------------------------------------------------------------------

class TestVoltageRating:
    def test_input_voltage_range(self):
        comp = {}
        _enrich_from_text(comp, "Input voltage range from 2.25 V to 6.5 V")
        assert comp["Voltage_Rating"] == "2.25 V to 6.5 V"

    def test_input_voltage_no_from(self):
        comp = {}
        _enrich_from_text(comp, "Input voltage 3.0V to 5.5V")
        assert comp["Voltage_Rating"] == "3.0 V to 5.5 V"

    def test_no_match_output_voltage(self):
        """Output voltage should not match the 'Input voltage' pattern."""
        comp = {}
        _enrich_from_text(comp, "Output voltage: 3.3 V typical")
        assert comp.get("Voltage_Rating") is None

    def test_skipped_when_already_set(self):
        comp = {"Voltage_Rating": "1.8 V"}
        _enrich_from_text(comp, "Input voltage range from 2.25 V to 6.5 V")
        assert comp["Voltage_Rating"] == "1.8 V"


# ---------------------------------------------------------------------------
# Thermal Resistance
# ---------------------------------------------------------------------------

class TestThermalResistance:
    def test_theta_ja(self):
        comp = {}
        _enrich_from_text(comp, "θJA = 35.2 °C/W")
        assert comp["Thermal_Resistance"] == "35.2 C/W"

    def test_theta_spelled_out(self):
        comp = {}
        _enrich_from_text(comp, "Theta JA (junction to ambient): 42 C/W")
        assert comp["Thermal_Resistance"] == "42 C/W"

    def test_no_match_theta_jc(self):
        """θJC (junction-to-case) should not match the θJA pattern."""
        comp = {}
        _enrich_from_text(comp, "θJC = 10 C/W")
        assert comp.get("Thermal_Resistance") is None

    def test_skipped_when_already_set(self):
        comp = {"Thermal_Resistance": "20 C/W"}
        _enrich_from_text(comp, "θJA = 35 °C/W")
        assert comp["Thermal_Resistance"] == "20 C/W"


# ---------------------------------------------------------------------------
# Empty / edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_text(self):
        comp = {}
        _enrich_from_text(comp, "")
        assert comp == {}

    def test_none_text_handled(self):
        """If text is None (shouldn't happen but defensive)."""
        comp = {}
        # _enrich_from_text uses `text if text else ""` internally
        _enrich_from_text(comp, None)
        assert comp == {}

    def test_all_fields_filled_skips_all_regex(self):
        comp = {
            "Pin_Count": "28",
            "Operating_Temperature_Range": "-55 to +125 C",
            "Radiation_TID": "100 krad(Si)",
            "Radiation_SEL_Threshold": "75 MeV-cm2/mg",
            "Voltage_Rating": "3.3 V",
            "Thermal_Resistance": "35 C/W",
        }
        original = dict(comp)
        _enrich_from_text(comp, "28-pin, -55 C to +125 C, 100 krad(Si), LET=75 MeV, input voltage 2.25V to 6.5V, θJA 42 C/W")
        assert comp == original  # nothing changed
