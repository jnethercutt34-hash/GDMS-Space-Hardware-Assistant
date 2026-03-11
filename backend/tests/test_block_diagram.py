"""Tests for Phase 4: Block Diagram Builder — models, store, generator, export, router."""
import json
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from main import app
from models.block_diagram import (
    Block, BlockCategory, BlockDiagram, Connection, Port, PortDirection,
    BlockDiagramGenerationResult,
)

client = TestClient(app)

# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

_SAMPLE_PORT_IN = Port(id="p_in_01", label="DDR_DQ", direction=PortDirection.BIDIR, bus_width=16, interface_type="DDR4")
_SAMPLE_PORT_OUT = Port(id="p_out_01", label="VCC_1V0", direction=PortDirection.OUT, bus_width=1, interface_type="Power")
_SAMPLE_BLOCK_FPGA = Block(
    id="blk_fpga", label="XCVU9P", part_number="XCVU9P-2FLGA2104I",
    category=BlockCategory.FPGA, x=100, y=100,
    ports=[_SAMPLE_PORT_IN, Port(id="p_pwr_01", label="VCCINT", direction=PortDirection.IN, interface_type="Power")],
)
_SAMPLE_BLOCK_MEM = Block(
    id="blk_mem", label="MT40A512M16", part_number="MT40A512M16LY-075",
    category=BlockCategory.Memory, x=400, y=100,
    ports=[Port(id="p_dq_01", label="DQ", direction=PortDirection.BIDIR, bus_width=16, interface_type="DDR4")],
)
_SAMPLE_BLOCK_PMU = Block(
    id="blk_pmu", label="LTC3888", part_number="LTC3888-2",
    category=BlockCategory.Power, x=100, y=300,
    ports=[_SAMPLE_PORT_OUT],
)
_SAMPLE_CONN = Connection(
    id="conn_01", source_block_id="blk_fpga", source_port_id="p_in_01",
    target_block_id="blk_mem", target_port_id="p_dq_01",
    signal_name="DDR4_DQ[15:0]", net_class="DDR4",
)
_SAMPLE_DIAGRAM = BlockDiagram(
    id="diag_01", name="Test Board", description="Unit test diagram",
    blocks=[_SAMPLE_BLOCK_FPGA, _SAMPLE_BLOCK_MEM, _SAMPLE_BLOCK_PMU],
    connections=[_SAMPLE_CONN],
)


def _make_openai_mock(json_payload: dict) -> MagicMock:
    mock_message = MagicMock()
    mock_message.content = json.dumps(json_payload)
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_response
    return mock_client


# ===========================================================================
# Model validation tests
# ===========================================================================

class TestBlockDiagramModels:
    def test_port_defaults(self):
        p = Port(label="CLK")
        assert p.direction == PortDirection.BIDIR
        assert p.bus_width == 1
        assert p.interface_type is None
        assert len(p.id) == 8

    def test_block_defaults(self):
        b = Block(label="U1")
        assert b.category == BlockCategory.Custom
        assert b.x == 0.0
        assert b.ports == []

    def test_block_with_ports(self):
        assert len(_SAMPLE_BLOCK_FPGA.ports) == 2
        assert _SAMPLE_BLOCK_FPGA.ports[0].bus_width == 16

    def test_connection(self):
        assert _SAMPLE_CONN.signal_name == "DDR4_DQ[15:0]"
        assert _SAMPLE_CONN.net_class == "DDR4"

    def test_diagram_full(self):
        assert _SAMPLE_DIAGRAM.name == "Test Board"
        assert len(_SAMPLE_DIAGRAM.blocks) == 3
        assert len(_SAMPLE_DIAGRAM.connections) == 1

    def test_diagram_roundtrip(self):
        d = _SAMPLE_DIAGRAM.model_dump()
        restored = BlockDiagram.model_validate(d)
        assert restored.id == _SAMPLE_DIAGRAM.id
        assert len(restored.blocks) == 3

    def test_category_enum(self):
        for cat in ["FPGA", "Memory", "Power", "Connector", "Processor", "Optics", "Custom"]:
            b = Block(label="X", category=cat)
            assert b.category == cat

    def test_invalid_category(self):
        with pytest.raises(Exception):
            Block(label="X", category="InvalidCat")

    def test_generation_result_wrapper(self):
        result = BlockDiagramGenerationResult(diagram=_SAMPLE_DIAGRAM)
        assert result.diagram.name == "Test Board"

    def test_port_direction_enum(self):
        for d in ["IN", "OUT", "BIDIR"]:
            p = Port(label="X", direction=d)
            assert p.direction == d


# ===========================================================================
# Store tests (with temp file)
# ===========================================================================

class TestBlockDiagramStore:
    def _patch_store(self, tmp_path):
        store_file = os.path.join(str(tmp_path), "diagrams.json")
        return patch("services.block_diagram_store._STORE_PATH", store_file)

    def test_create_and_list(self, tmp_path):
        with self._patch_store(tmp_path):
            from services.block_diagram_store import create, list_all
            d = _SAMPLE_DIAGRAM.model_dump()
            create(d)
            all_d = list_all()
            assert len(all_d) == 1
            assert all_d[0]["name"] == "Test Board"

    def test_get_by_id(self, tmp_path):
        with self._patch_store(tmp_path):
            from services.block_diagram_store import create, get_by_id
            d = _SAMPLE_DIAGRAM.model_dump()
            create(d)
            found = get_by_id("diag_01")
            assert found is not None
            assert found["name"] == "Test Board"

    def test_get_missing(self, tmp_path):
        with self._patch_store(tmp_path):
            from services.block_diagram_store import get_by_id
            assert get_by_id("nonexistent") is None

    def test_update(self, tmp_path):
        with self._patch_store(tmp_path):
            from services.block_diagram_store import create, update, get_by_id
            d = _SAMPLE_DIAGRAM.model_dump()
            create(d)
            d["name"] = "Updated Board"
            update("diag_01", d)
            found = get_by_id("diag_01")
            assert found["name"] == "Updated Board"

    def test_update_missing(self, tmp_path):
        with self._patch_store(tmp_path):
            from services.block_diagram_store import update
            assert update("nonexistent", {}) is None

    def test_delete(self, tmp_path):
        with self._patch_store(tmp_path):
            from services.block_diagram_store import create, delete, list_all
            create(_SAMPLE_DIAGRAM.model_dump())
            assert delete("diag_01") is True
            assert len(list_all()) == 0

    def test_delete_missing(self, tmp_path):
        with self._patch_store(tmp_path):
            from services.block_diagram_store import delete
            assert delete("nonexistent") is False


# ===========================================================================
# AI generator tests (mocked)
# ===========================================================================

class TestBlockDiagramGenerator:
    def test_generate_from_parts(self):
        diagram_data = _SAMPLE_DIAGRAM.model_dump()
        ai_response = {"diagram": diagram_data}
        mock_client = _make_openai_mock(ai_response)

        with patch("services.block_diagram_generator._get_client", return_value=mock_client):
            from services.block_diagram_generator import generate_from_parts
            result = generate_from_parts([{"Part_Number": "XCVU9P"}])

        assert result.name == "Test Board"
        assert len(result.blocks) == 3

    def test_generate_from_text(self):
        diagram_data = _SAMPLE_DIAGRAM.model_dump()
        ai_response = {"diagram": diagram_data}
        mock_client = _make_openai_mock(ai_response)

        with patch("services.block_diagram_generator._get_client", return_value=mock_client):
            from services.block_diagram_generator import generate_from_text
            result = generate_from_text("FPGA connected to DDR4 memory")

        assert len(result.connections) == 1

    def test_generate_bad_json(self):
        mock_message = MagicMock()
        mock_message.content = "not json"
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response

        with patch("services.block_diagram_generator._get_client", return_value=mock_client):
            from services.block_diagram_generator import generate_from_parts
            with pytest.raises(ValueError, match="non-JSON"):
                generate_from_parts([])

    def test_generate_no_api_key(self):
        with patch("services.block_diagram_generator._get_client", side_effect=RuntimeError("INTERNAL_API_KEY is not set")):
            from services.block_diagram_generator import generate_from_parts
            with pytest.raises(RuntimeError, match="INTERNAL_API_KEY"):
                generate_from_parts([])


# ===========================================================================
# Export tests
# ===========================================================================

class TestBlockDiagramExport:
    def test_csv_export(self):
        from services.block_diagram_export import generate_netlist_csv
        csv = generate_netlist_csv(_SAMPLE_DIAGRAM.model_dump())
        assert "Instance,Part_Number,Pin,Net,Net_Class" in csv
        assert "DDR4_DQ[15:0]" in csv
        assert "XCVU9P" in csv

    def test_csv_export_empty(self):
        from services.block_diagram_export import generate_netlist_csv
        csv = generate_netlist_csv({"blocks": [], "connections": []})
        assert "Instance" in csv  # header only

    def test_script_export(self):
        from services.block_diagram_export import generate_netlist_script
        script = generate_netlist_script(_SAMPLE_DIAGRAM.model_dump())
        assert "GDMS Space Hardware Assistant" in script
        assert "COMPONENTS" in script
        assert "NETS" in script
        assert "XCVU9P" in script
        assert "win32com.client" in script

    def test_script_export_empty(self):
        from services.block_diagram_export import generate_netlist_script
        script = generate_netlist_script({"blocks": [], "connections": []})
        assert "COMPONENTS = []" in script


# ===========================================================================
# Router tests
# ===========================================================================

class TestBlockDiagramRouter:
    def test_create_and_list(self):
        with patch("routers.block_diagram.create", return_value=_SAMPLE_DIAGRAM.model_dump()):
            with patch("routers.block_diagram.list_all", return_value=[_SAMPLE_DIAGRAM.model_dump()]):
                resp = client.get("/api/diagrams")
                assert resp.status_code == 200

    def test_get_found(self):
        with patch("routers.block_diagram.get_by_id", return_value=_SAMPLE_DIAGRAM.model_dump()):
            resp = client.get("/api/diagrams/diag_01")
            assert resp.status_code == 200
            assert resp.json()["name"] == "Test Board"

    def test_get_not_found(self):
        with patch("routers.block_diagram.get_by_id", return_value=None):
            resp = client.get("/api/diagrams/missing")
            assert resp.status_code == 404

    def test_delete_found(self):
        with patch("routers.block_diagram.delete", return_value=True):
            resp = client.delete("/api/diagrams/diag_01")
            assert resp.status_code == 200

    def test_delete_not_found(self):
        with patch("routers.block_diagram.delete", return_value=False):
            resp = client.delete("/api/diagrams/missing")
            assert resp.status_code == 404

    def test_export_netlist_script(self):
        with patch("routers.block_diagram.get_by_id", return_value=_SAMPLE_DIAGRAM.model_dump()):
            resp = client.post("/api/diagrams/diag_01/export-netlist?format=script")
            assert resp.status_code == 200
            assert "text/x-python" in resp.headers["content-type"]
            assert "COMPONENTS" in resp.text

    def test_export_netlist_csv(self):
        with patch("routers.block_diagram.get_by_id", return_value=_SAMPLE_DIAGRAM.model_dump()):
            resp = client.post("/api/diagrams/diag_01/export-netlist?format=csv")
            assert resp.status_code == 200
            assert "text/csv" in resp.headers["content-type"]

    def test_export_not_found(self):
        with patch("routers.block_diagram.get_by_id", return_value=None):
            resp = client.post("/api/diagrams/missing/export-netlist")
            assert resp.status_code == 404
