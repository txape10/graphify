"""Tests for extract_abap — ABAP extractor integration in graphify."""
from pathlib import Path

import pytest

from graphify.extract import extract_abap, _make_id, _file_stem, _DISPATCH

FIXTURES = Path(__file__).parent / "fixtures"
SAMPLE = FIXTURES / "sample.abap"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _node_labels(result: dict) -> list[str]:
    return [n["label"] for n in result["nodes"]]


def _node_ids(result: dict) -> set[str]:
    return {n["id"] for n in result["nodes"]}


def _edge_relations(result: dict) -> list[str]:
    return [e["relation"] for e in result["edges"]]


# ---------------------------------------------------------------------------
# Dispatch registration
# ---------------------------------------------------------------------------

def test_abap_registered_in_dispatch():
    assert ".abap" in _DISPATCH
    assert _DISPATCH[".abap"] is extract_abap


# ---------------------------------------------------------------------------
# Node extraction
# ---------------------------------------------------------------------------

def test_extract_abap_returns_nodes_and_edges():
    result = extract_abap(SAMPLE)
    assert "nodes" in result
    assert "edges" in result
    assert len(result["nodes"]) > 0


def test_extract_abap_finds_class():
    result = extract_abap(SAMPLE)
    labels = _node_labels(result)
    assert any("ZCL_GREETER" in lbl.upper() for lbl in labels)


def test_extract_abap_finds_methods():
    result = extract_abap(SAMPLE)
    labels = _node_labels(result)
    assert any("GREET" in lbl.upper() for lbl in labels)
    assert any("GET_MESSAGE" in lbl.upper() for lbl in labels)


def test_extract_abap_finds_interface():
    result = extract_abap(SAMPLE)
    labels = _node_labels(result)
    assert any("ZIF_PRINTABLE" in lbl.upper() for lbl in labels)


def test_extract_abap_finds_form():
    result = extract_abap(SAMPLE)
    labels = _node_labels(result)
    assert any("FORMAT_OUTPUT" in lbl.upper() for lbl in labels)


def test_extract_abap_finds_report():
    result = extract_abap(SAMPLE)
    labels = _node_labels(result)
    assert any("ZHELLO_TEST" in lbl.upper() for lbl in labels)


# ---------------------------------------------------------------------------
# kind attribute
# ---------------------------------------------------------------------------

def test_extract_abap_z_class_has_z_custom_kind():
    result = extract_abap(SAMPLE)
    cls_node = next(
        (n for n in result["nodes"] if "ZCL_GREETER" in n["label"].upper()),
        None,
    )
    assert cls_node is not None
    assert cls_node.get("kind") == "z_custom"


def test_extract_abap_z_interface_has_z_custom_kind():
    result = extract_abap(SAMPLE)
    intf_node = next(
        (n for n in result["nodes"] if "ZIF_PRINTABLE" in n["label"].upper()),
        None,
    )
    assert intf_node is not None
    assert intf_node.get("kind") == "z_custom"


# ---------------------------------------------------------------------------
# Edge extraction
# ---------------------------------------------------------------------------

def test_extract_abap_call_function_edge_is_extracted():
    result = extract_abap(SAMPLE)
    call_edges = [
        e for e in result["edges"]
        if e["relation"] == "calls" and e["confidence"] == "EXTRACTED"
    ]
    assert len(call_edges) >= 1
    targets = [e["target"] for e in call_edges]
    expected_tgt = _make_id("abap_fn", "SUSR_USER_CHANGE_PASSWORD_RFC")
    assert expected_tgt in targets


def test_extract_abap_perform_edge_is_inferred():
    result = extract_abap(SAMPLE)
    perform_edges = [
        e for e in result["edges"]
        if e["relation"] == "calls" and e["confidence"] == "INFERRED"
    ]
    assert len(perform_edges) >= 1


def test_extract_abap_contains_edges_are_extracted():
    result = extract_abap(SAMPLE)
    contains = [e for e in result["edges"] if e["relation"] == "contains"]
    assert len(contains) >= 3  # file→class, class→method×2, file→form, file→interface
    for edge in contains:
        assert edge["confidence"] == "EXTRACTED"


def test_extract_abap_no_dangling_edge_sources():
    """Every edge source must reference a known node."""
    result = extract_abap(SAMPLE)
    node_ids = _node_ids(result)
    for edge in result["edges"]:
        assert edge["source"] in node_ids, f"Dangling source: {edge['source']}"


# ---------------------------------------------------------------------------
# Schema correctness
# ---------------------------------------------------------------------------

def test_extract_abap_node_schema():
    result = extract_abap(SAMPLE)
    for node in result["nodes"]:
        assert "id" in node
        assert "label" in node
        assert "file_type" in node
        assert "source_file" in node
        assert node["file_type"] == "code"


def test_extract_abap_edge_schema():
    result = extract_abap(SAMPLE)
    valid_confidences = {"EXTRACTED", "INFERRED", "AMBIGUOUS"}
    for edge in result["edges"]:
        assert "source" in edge
        assert "target" in edge
        assert "relation" in edge
        assert "confidence" in edge
        assert "source_file" in edge
        assert edge["confidence"] in valid_confidences


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

def test_extract_abap_deterministic_ids():
    """Re-extracting the same file produces identical node IDs."""
    result1 = extract_abap(SAMPLE)
    result2 = extract_abap(SAMPLE)
    ids1 = {n["id"] for n in result1["nodes"]}
    ids2 = {n["id"] for n in result2["nodes"]}
    assert ids1 == ids2
