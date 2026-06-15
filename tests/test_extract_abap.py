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


def test_extract_abap_class_id_is_global():
    """Class and interface node IDs must use global schemes ('abap_cls'/'abap_intf').

    This ensures that reference stubs created by callers in other files share
    the same ID as the real definition node, enabling cross-file in-degree
    counting in mark_dead_candidates.
    """
    result = extract_abap(SAMPLE)
    cls_node = next(
        (n for n in result["nodes"] if "ZCL_GREETER" in n["label"].upper()
         and "DEFINITION" in n["label"].upper()),
        None,
    )
    assert cls_node is not None
    assert cls_node["id"] == _make_id("abap_cls", "ZCL_GREETER")

    intf_node = next(
        (n for n in result["nodes"] if "ZIF_PRINTABLE" in n["label"].upper()),
        None,
    )
    assert intf_node is not None
    assert intf_node["id"] == _make_id("abap_intf", "ZIF_PRINTABLE")


# ---------------------------------------------------------------------------
# Instantiation edges (TYPE REF TO / NEW / CREATE OBJECT)
# ---------------------------------------------------------------------------

INST = FIXTURES / "instantiation.abap"


def test_extract_abap_type_ref_to_emits_uses_edge():
    """DATA lo TYPE REF TO <class> must emit a uses INFERRED edge."""
    result = extract_abap(INST)
    uses_edges = [e for e in result["edges"] if e["relation"] == "uses"]
    assert len(uses_edges) >= 1
    targets = {e["target"] for e in uses_edges}
    assert _make_id("abap_cls", "ZCL_PRODUCT") in targets


def test_extract_abap_uses_edge_confidence_is_inferred():
    """Instantiation uses edges must have confidence INFERRED."""
    result = extract_abap(INST)
    for edge in result["edges"]:
        if edge["relation"] == "uses":
            assert edge["confidence"] == "INFERRED"


def test_extract_abap_uses_edge_deduplication():
    """Three patterns referencing the same class must produce exactly one uses edge."""
    result = extract_abap(INST)
    tgt = _make_id("abap_cls", "ZCL_PRODUCT")
    uses_to_target = [e for e in result["edges"]
                      if e["relation"] == "uses" and e["target"] == tgt]
    assert len(uses_to_target) == 1


def test_extract_abap_instantiation_stub_has_no_source_location():
    """Referenced class stub must have source_location=None so mark_dead_candidates skips it."""
    result = extract_abap(INST)
    tgt_id = _make_id("abap_cls", "ZCL_PRODUCT")
    stub = next((n for n in result["nodes"] if n["id"] == tgt_id), None)
    assert stub is not None, "Stub node for ZCL_PRODUCT must be present"
    assert stub["source_location"] is None


def test_extract_abap_no_dangling_uses_edge_sources():
    """Every uses edge source must reference a known node."""
    result = extract_abap(INST)
    node_ids = _node_ids(result)
    for edge in result["edges"]:
        if edge["relation"] == "uses":
            assert edge["source"] in node_ids, f"Dangling uses source: {edge['source']}"


# ---------------------------------------------------------------------------
# FUNCTION MODULE extraction (function_module.abap)
# ---------------------------------------------------------------------------

FM_FIXTURE = FIXTURES / "function_module.abap"


def test_extract_abap_function_module_node():
    result = extract_abap(FM_FIXTURE)
    labels = _node_labels(result)
    assert any("FUNCTION Z_ADD_NUMBERS" in lbl for lbl in labels)
    assert any("FUNCTION Z_CALLER" in lbl for lbl in labels)


def test_extract_abap_function_module_global_id():
    result = extract_abap(FM_FIXTURE)
    nid = _make_id("abap_fn", "Z_ADD_NUMBERS")
    assert any(n["id"] == nid for n in result["nodes"])


def test_extract_abap_function_module_kind():
    result = extract_abap(FM_FIXTURE)
    node = next(
        (n for n in result["nodes"] if n.get("label") == "FUNCTION Z_ADD_NUMBERS"),
        None,
    )
    assert node is not None
    assert node["kind"] == "z_custom"


def test_extract_abap_function_pool_node():
    result = extract_abap(FM_FIXTURE)
    labels = _node_labels(result)
    assert any("FUNCTION GROUP ZFM_TEST" in lbl for lbl in labels)


def test_extract_abap_function_pool_global_id():
    result = extract_abap(FM_FIXTURE)
    nid = _make_id("abap_fg", "ZFM_TEST")
    assert any(n["id"] == nid for n in result["nodes"])


def test_extract_abap_call_function_targets_fm_node():
    """CALL FUNCTION inside a FM body must emit a calls edge to the FM nid."""
    result = extract_abap(FM_FIXTURE)
    tgt = _make_id("abap_fn", "Z_ADD_NUMBERS")
    call_edges = [e for e in result["edges"]
                  if e["relation"] == "calls" and e["target"] == tgt]
    assert len(call_edges) >= 1
    assert call_edges[0]["confidence"] == "EXTRACTED"


def test_extract_abap_function_module_deterministic_ids():
    r1 = extract_abap(FM_FIXTURE)
    r2 = extract_abap(FM_FIXTURE)
    assert {n["id"] for n in r1["nodes"]} == {n["id"] for n in r2["nodes"]}


# ---------------------------------------------------------------------------
# SUBMIT extraction (submit.abap)
# ---------------------------------------------------------------------------

SUBMIT_FIXTURE = FIXTURES / "submit.abap"


def test_extract_abap_submit_emits_submits_edges():
    result = extract_abap(SUBMIT_FIXTURE)
    sub_edges = [e for e in result["edges"] if e["relation"] == "submits"]
    assert len(sub_edges) >= 1


def test_extract_abap_submit_edge_confidence():
    result = extract_abap(SUBMIT_FIXTURE)
    for edge in result["edges"]:
        if edge["relation"] == "submits":
            assert edge["confidence"] == "EXTRACTED"


def test_extract_abap_submit_only_z_targets():
    """SUBMIT sapmv45a (SAP standard) must not generate a stub or edge."""
    result = extract_abap(SUBMIT_FIXTURE)
    sap_nid = _make_id("abap_prog", "SAPMV45A")
    assert all(e["target"] != sap_nid for e in result["edges"] if e["relation"] == "submits")


def test_extract_abap_submit_stub_has_no_source_location():
    result = extract_abap(SUBMIT_FIXTURE)
    tgt_nid = _make_id("abap_prog", "ZREPORT_SALES")
    stub = next((n for n in result["nodes"] if n["id"] == tgt_nid), None)
    assert stub is not None
    assert stub["source_location"] is None


def test_extract_abap_submit_deterministic_ids():
    r1 = extract_abap(SUBMIT_FIXTURE)
    r2 = extract_abap(SUBMIT_FIXTURE)
    assert {n["id"] for n in r1["nodes"]} == {n["id"] for n in r2["nodes"]}

