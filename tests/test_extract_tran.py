"""Tests for extract_tran — SAP transaction extractor (.tran.xml)."""
from pathlib import Path
import tempfile

import pytest

from graphify.extract import extract_tran, _make_id, _get_extractor

FIXTURES = Path(__file__).parent / "fixtures"
SAMPLE = FIXTURES / "zfi0001.tran.xml"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _node_by_id(result: dict, nid: str) -> dict | None:
    return next((n for n in result["nodes"] if n["id"] == nid), None)


def _node_by_label(result: dict, label: str) -> dict | None:
    return next((n for n in result["nodes"] if label.upper() in n["label"].upper()), None)


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

def test_tran_xml_routed_to_extract_tran():
    assert _get_extractor(Path("ZFI0001.tran.xml")) is extract_tran


# ---------------------------------------------------------------------------
# Node extraction
# ---------------------------------------------------------------------------

def test_extract_tran_returns_nodes_and_edges():
    result = extract_tran(SAMPLE)
    assert "nodes" in result
    assert "edges" in result
    assert len(result["nodes"]) >= 1


def test_extract_tran_transaction_node_exists():
    result = extract_tran(SAMPLE)
    tran_nid = _make_id("abap_tran", "ZFI0001")
    node = _node_by_id(result, tran_nid)
    assert node is not None


def test_extract_tran_transaction_node_attributes():
    result = extract_tran(SAMPLE)
    tran_nid = _make_id("abap_tran", "ZFI0001")
    node = _node_by_id(result, tran_nid)
    assert node["label"] == "ZFI0001"
    assert node["tcode"] == "ZFI0001"
    assert node["pgmna"] == "Z_P_CP_NOMINAS"
    assert node["dypno"] == "1000"
    assert "Nómina" in node["ttext"] or "Nomina" in node["ttext"]
    assert node["kind"] == "z_custom"
    assert node["source_location"] == "L1"
    assert node["file_type"] == "code"


def test_extract_tran_program_stub_exists():
    result = extract_tran(SAMPLE)
    prog_nid = _make_id("abap_prog", "Z_P_CP_NOMINAS")
    stub = _node_by_id(result, prog_nid)
    assert stub is not None


def test_extract_tran_program_stub_has_no_source_location():
    """Stub must have source_location=None so mark_dead_candidates skips it."""
    result = extract_tran(SAMPLE)
    prog_nid = _make_id("abap_prog", "Z_P_CP_NOMINAS")
    stub = _node_by_id(result, prog_nid)
    assert stub["source_location"] is None


def test_extract_tran_program_stub_label():
    result = extract_tran(SAMPLE)
    prog_nid = _make_id("abap_prog", "Z_P_CP_NOMINAS")
    stub = _node_by_id(result, prog_nid)
    assert stub["label"] == "REPORT Z_P_CP_NOMINAS"


# ---------------------------------------------------------------------------
# Edge extraction
# ---------------------------------------------------------------------------

def test_extract_tran_launches_edge_exists():
    result = extract_tran(SAMPLE)
    launches = [e for e in result["edges"] if e["relation"] == "launches"]
    assert len(launches) == 1


def test_extract_tran_launches_edge_direction():
    result = extract_tran(SAMPLE)
    tran_nid = _make_id("abap_tran", "ZFI0001")
    prog_nid = _make_id("abap_prog", "Z_P_CP_NOMINAS")
    edge = result["edges"][0]
    assert edge["source"] == tran_nid
    assert edge["target"] == prog_nid


def test_extract_tran_launches_edge_confidence():
    result = extract_tran(SAMPLE)
    edge = result["edges"][0]
    assert edge["confidence"] == "EXTRACTED"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_extract_tran_empty_pgmna_no_edge():
    """Transacción sin PGMNA (tipo parámetro) → sin edge launches."""
    xml = "<TSTC><TCODE>ZPM0001</TCODE><PGMNA></PGMNA><DYPNO></DYPNO></TSTC>"
    with tempfile.NamedTemporaryFile(suffix=".tran.xml", mode="w", encoding="utf-8", delete=False) as f:
        f.write(xml)
        tmp = Path(f.name)
    try:
        result = extract_tran(tmp)
        assert len(result["edges"]) == 0
        assert len(result["nodes"]) == 1  # solo el nodo transacción
    finally:
        tmp.unlink()


def test_extract_tran_sap_standard_pgmna_no_edge():
    """PGMNA que no empieza por Z/Y → sin edge (objeto SAP estándar)."""
    xml = "<TSTC><TCODE>ZPM0002</TCODE><PGMNA>SAPMV45A</PGMNA><DYPNO>4001</DYPNO></TSTC>"
    with tempfile.NamedTemporaryFile(suffix=".tran.xml", mode="w", encoding="utf-8", delete=False) as f:
        f.write(xml)
        tmp = Path(f.name)
    try:
        result = extract_tran(tmp)
        assert len(result["edges"]) == 0
    finally:
        tmp.unlink()


def test_extract_tran_malformed_xml_returns_empty():
    """XML roto → devuelve nodos/edges vacíos sin crash."""
    with tempfile.NamedTemporaryFile(suffix=".tran.xml", mode="w", encoding="utf-8", delete=False) as f:
        f.write("<TSTC><TCODE>ZFI0001<broken")
        tmp = Path(f.name)
    try:
        result = extract_tran(tmp)
        assert result["nodes"] == []
        assert result["edges"] == []
        assert "error" in result
    finally:
        tmp.unlink()


def test_extract_tran_deterministic_ids():
    """Re-extraer el mismo fichero produce IDs idénticos."""
    r1 = extract_tran(SAMPLE)
    r2 = extract_tran(SAMPLE)
    ids1 = {n["id"] for n in r1["nodes"]}
    ids2 = {n["id"] for n in r2["nodes"]}
    assert ids1 == ids2


# ---------------------------------------------------------------------------
# Formato abapGit real (asx: namespace + <?xml?> declaration)
# ---------------------------------------------------------------------------

FULL_SAMPLE = FIXTURES / "zfi0002.tran.xml"


def test_extract_tran_full_format_transaction_node():
    """Formato abapGit real con <?xml?> y namespace asx: debe extraer el nodo."""
    result = extract_tran(FULL_SAMPLE)
    tran_nid = _make_id("abap_tran", "ZFI0002")
    node = _node_by_id(result, tran_nid)
    assert node is not None, "Nodo transacción no encontrado en formato abapGit real"


def test_extract_tran_full_format_attributes():
    result = extract_tran(FULL_SAMPLE)
    tran_nid = _make_id("abap_tran", "ZFI0002")
    node = _node_by_id(result, tran_nid)
    assert node["tcode"] == "ZFI0002"
    assert node["pgmna"] == "Z_P_FACTURAS"
    assert node["dypno"] == "0100"
    assert "Facturas" in node["ttext"]
    assert node["kind"] == "z_custom"


def test_extract_tran_full_format_launches_edge():
    result = extract_tran(FULL_SAMPLE)
    launches = [e for e in result["edges"] if e["relation"] == "launches"]
    assert len(launches) == 1
    assert launches[0]["target"] == _make_id("abap_prog", "Z_P_FACTURAS")
    assert launches[0]["confidence"] == "EXTRACTED"
