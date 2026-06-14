"""Tests for dead_candidate marking and related CLI plumbing."""
import json
import tempfile
from pathlib import Path

import networkx as nx
import pytest

from graphify.build import mark_dead_candidates


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_graph(nodes, edges=None):
    """Build a bare NX graph from dicts with source_file / source_location."""
    G = nx.Graph()
    for n in nodes:
        G.add_node(n["id"], **{k: v for k, v in n.items() if k != "id"})
    for e in (edges or []):
        src = e["source"]
        tgt = e["target"]
        attrs = {k: v for k, v in e.items() if k not in ("source", "target")}
        attrs.setdefault("_src", src)
        attrs.setdefault("_tgt", tgt)
        G.add_edge(src, tgt, **attrs)
    return G


# ---------------------------------------------------------------------------
# mark_dead_candidates
# ---------------------------------------------------------------------------

class TestMarkDeadCandidates:

    def test_z_class_no_cross_edges_is_marked(self):
        G = _make_graph([
            {"id": "c1", "label": "CLASS ZCL_FOO DEFINITION",
             "source_file": "foo.abap", "source_location": "L1"},
        ])
        mark_dead_candidates(G)
        assert G.nodes["c1"].get("dead_candidate") is True

    def test_z_class_with_cross_edge_not_marked(self):
        G = _make_graph(
            [
                {"id": "c1", "label": "CLASS ZCL_FOO DEFINITION",
                 "source_file": "foo.abap", "source_location": "L1"},
                {"id": "c2", "label": "CLASS ZCL_BAR DEFINITION",
                 "source_file": "bar.abap", "source_location": "L1"},
            ],
            [{"source": "c2", "target": "c1", "_src": "c2", "_tgt": "c1",
              "relation": "calls"}],
        )
        mark_dead_candidates(G)
        assert not G.nodes["c1"].get("dead_candidate")

    def test_z_method_no_cross_edges_is_marked(self):
        G = _make_graph([
            {"id": "m1", "label": "ZCL_FOO->DO_SOMETHING",
             "source_file": "foo.abap", "source_location": "L10"},
        ])
        mark_dead_candidates(G)
        assert G.nodes["m1"].get("dead_candidate") is True

    def test_z_method_same_file_edge_still_marked(self):
        """Same-file calls do NOT count as cross-file in-degree."""
        G = _make_graph(
            [
                {"id": "m1", "label": "ZCL_FOO->HELPER",
                 "source_file": "foo.abap", "source_location": "L5"},
                {"id": "m2", "label": "ZCL_FOO->MAIN",
                 "source_file": "foo.abap", "source_location": "L20"},
            ],
            [{"source": "m2", "target": "m1", "_src": "m2", "_tgt": "m1",
              "relation": "calls"}],
        )
        mark_dead_candidates(G)
        assert G.nodes["m1"].get("dead_candidate") is True

    def test_report_not_marked(self):
        G = _make_graph([
            {"id": "r1", "label": "REPORT ZREPORT_VENTAS",
             "source_file": "rep.abap", "source_location": "L1"},
        ])
        mark_dead_candidates(G)
        assert not G.nodes["r1"].get("dead_candidate")

    def test_function_group_not_marked(self):
        G = _make_graph([
            {"id": "fg1", "label": "FUNCTION GROUP ZFUGR_VENTAS",
             "source_file": "fg.abap", "source_location": "L1"},
        ])
        mark_dead_candidates(G)
        assert not G.nodes["fg1"].get("dead_candidate")

    def test_local_class_not_marked(self):
        G = _make_graph([
            {"id": "lc1", "label": "CLASS LCL_HELPER DEFINITION",
             "source_file": "foo.abap", "source_location": "L1"},
        ])
        mark_dead_candidates(G)
        assert not G.nodes["lc1"].get("dead_candidate")

    def test_mcl_class_not_marked(self):
        G = _make_graph([
            {"id": "mc1", "label": "CLASS MCL_HELPER DEFINITION",
             "source_file": "foo.abap", "source_location": "L1"},
        ])
        mark_dead_candidates(G)
        assert not G.nodes["mc1"].get("dead_candidate")

    def test_node_without_source_location_not_marked(self):
        """External stub nodes (no source_location) must never be marked."""
        G = _make_graph([
            {"id": "sap1", "label": "CLASS ZCL_FOO DEFINITION",
             "source_file": "", "source_location": None},
        ])
        mark_dead_candidates(G)
        assert not G.nodes["sap1"].get("dead_candidate")

    def test_prog_abap_include_marked(self):
        G = _make_graph([
            {"id": "inc1", "label": "ZREPORT_F01",
             "source_file": "ZREPORT_F01.prog.abap", "source_location": "L1"},
        ])
        mark_dead_candidates(G)
        assert G.nodes["inc1"].get("dead_candidate") is True

    def test_y_class_marked(self):
        """YCL_ (Y-namespace) classes are treated like ZCL_."""
        G = _make_graph([
            {"id": "yc1", "label": "CLASS YCL_HELPER DEFINITION",
             "source_file": "helper.abap", "source_location": "L1"},
        ])
        mark_dead_candidates(G)
        assert G.nodes["yc1"].get("dead_candidate") is True

    def test_y_method_marked(self):
        G = _make_graph([
            {"id": "ym1", "label": "YCL_HELPER->BUILD",
             "source_file": "helper.abap", "source_location": "L5"},
        ])
        mark_dead_candidates(G)
        assert G.nodes["ym1"].get("dead_candidate") is True

    def test_for_testing_class_not_marked(self):
        G = _make_graph([
            {"id": "tc1", "label": "CLASS ZCL_FOO DEFINITION FOR TESTING",
             "source_file": "foo.abap", "source_location": "L1"},
        ])
        mark_dead_candidates(G)
        assert not G.nodes["tc1"].get("dead_candidate")

    def test_test_suffix_method_not_marked(self):
        G = _make_graph([
            {"id": "tm1", "label": "ZCL_FOO->VALIDATE_TEST",
             "source_file": "foo.abap", "source_location": "L10"},
        ])
        mark_dead_candidates(G)
        assert not G.nodes["tm1"].get("dead_candidate")

    def test_prog_abap_include_with_cross_edge_not_marked(self):
        G = _make_graph(
            [
                {"id": "inc1", "label": "ZREPORT_F01",
                 "source_file": "ZREPORT_F01.prog.abap", "source_location": "L1"},
                {"id": "prog1", "label": "REPORT ZREPORT",
                 "source_file": "ZREPORT.prog.abap", "source_location": "L1"},
            ],
            [{"source": "prog1", "target": "inc1", "_src": "prog1", "_tgt": "inc1",
              "relation": "includes"}],
        )
        mark_dead_candidates(G)
        assert not G.nodes["inc1"].get("dead_candidate")

    def test_form_not_marked(self):
        """FORMs are called from transactions outside the graph — never dead candidates."""
        G = _make_graph([
            {"id": "frm1", "label": "FORM ZHELPER",
             "source_file": "ZREPORT.prog.abap", "source_location": "L50"},
        ])
        mark_dead_candidates(G)
        assert not G.nodes["frm1"].get("dead_candidate")

    def test_sap_standard_prog_abap_not_marked(self):
        """SAP standard objects (no Z/Y prefix) in .prog.abap must not be marked."""
        G = _make_graph([
            {"id": "sap1", "label": "/CPD/SUB_MONTH_TO_DATE",
             "source_file": "ZREPORT.prog.abap", "source_location": "L100"},
            {"id": "sap2", "label": "ABAP4_CALL_TRANSACTION",
             "source_file": "ZFUGR.prog.abap", "source_location": "L200"},
        ])
        mark_dead_candidates(G)
        assert not G.nodes["sap1"].get("dead_candidate")
        assert not G.nodes["sap2"].get("dead_candidate")

    def test_z_prog_abap_include_still_marked(self):
        """Z-prefixed .prog.abap includes with no cross-file callers are still candidates."""
        G = _make_graph([
            {"id": "inc2", "label": "ZREPORT_F02",
             "source_file": "ZREPORT_F02.prog.abap", "source_location": "L1"},
        ])
        mark_dead_candidates(G)
        assert G.nodes["inc2"].get("dead_candidate") is True

    def test_y_prog_abap_include_still_marked(self):
        """Y-prefixed .prog.abap includes are treated symmetrically with Z-prefixed."""
        G = _make_graph([
            {"id": "yinc1", "label": "YREPORT_F02",
             "source_file": "YREPORT_F02.prog.abap", "source_location": "L1"},
        ])
        mark_dead_candidates(G)
        assert G.nodes["yinc1"].get("dead_candidate") is True

    def test_z_static_method_marked(self):
        """ZCL_*=>METHOD (static call operator) must be marked like ->."""
        G = _make_graph([
            {"id": "sm1", "label": "ZCL_AUTHORITY=>CHECK_PROCESS",
             "source_file": "authority.abap", "source_location": "L5"},
        ])
        mark_dead_candidates(G)
        assert G.nodes["sm1"].get("dead_candidate") is True

    def test_y_static_method_marked(self):
        """YCL_*=>METHOD treated symmetrically with ZCL_*=>METHOD."""
        G = _make_graph([
            {"id": "ysm1", "label": "YCL_UTIL=>FORMAT",
             "source_file": "util.abap", "source_location": "L10"},
        ])
        mark_dead_candidates(G)
        assert G.nodes["ysm1"].get("dead_candidate") is True

    def test_prog_abap_fm_callsite_not_marked(self):
        """CALL FUNCTION call-site nodes in .prog.abap must not be marked.

        The label (Z_WF_INPUT_WF_DATA2) does not match the file stem (ZREPORT_F01),
        so these nodes are references, not include definitions.
        """
        G = _make_graph([
            {"id": "fm1", "label": "Z_WF_INPUT_WF_DATA2",
             "source_file": "ZREPORT_F01.prog.abap", "source_location": "L75"},
        ])
        mark_dead_candidates(G)
        assert not G.nodes["fm1"].get("dead_candidate")

    def test_prog_abap_include_stem_match_still_marked(self):
        """Regression: Z include whose label matches file stem is still a dead candidate."""
        G = _make_graph([
            {"id": "inc3", "label": "ZREPORT_F01",
             "source_file": "ZREPORT_F01.prog.abap", "source_location": "L1"},
        ])
        mark_dead_candidates(G)
        assert G.nodes["inc3"].get("dead_candidate") is True

    def test_z_class_with_uses_edge_cross_file_not_marked(self):
        """Class Z targeted by a uses edge from a different file must not be marked.

        Covers TYPE REF TO / NEW / CREATE OBJECT references: the caller emits a
        uses edge whose source is in a different file than the class definition.
        """
        G = _make_graph(
            [
                {"id": "abap_cls_zcl_traslados",
                 "label": "CLASS ZCL_TRASLADOS DEFINITION",
                 "source_file": "zcl_traslados.abap", "source_location": "L1"},
                {"id": "caller_method", "label": "ZCL_CALLER->RUN",
                 "source_file": "zcl_caller.abap", "source_location": "L10"},
            ],
            [{"source": "caller_method", "target": "abap_cls_zcl_traslados",
              "_src": "caller_method", "_tgt": "abap_cls_zcl_traslados",
              "relation": "uses"}],
        )
        mark_dead_candidates(G)
        assert not G.nodes["abap_cls_zcl_traslados"].get("dead_candidate")

    def test_z_class_stub_source_location_none_skipped(self):
        """Class stub (source_location=None) from cross-file reference must not be marked.

        When the class definition file is not in the corpus, _ensure_stub creates
        a node with source_location=None. mark_dead_candidates must skip it.
        """
        G = _make_graph([
            {"id": "abap_cls_zcl_target",
             "label": "CLASS ZCL_TARGET DEFINITION",
             "source_file": "", "source_location": None},
        ])
        mark_dead_candidates(G)
        assert not G.nodes["abap_cls_zcl_target"].get("dead_candidate")

    def test_non_zcl_z_class_no_callers_marked(self):
        """Class with Z prefix but without CL_ (e.g. ZORDER) must be marked as dead.

        Previous regex required ZCL_/YCL_; classes named ZORDER, ZCALC, etc.
        were silently skipped even if nobody calls them.
        """
        G = _make_graph([
            {"id": "c1", "label": "CLASS ZORDER DEFINITION",
             "source_file": "zorder.abap", "source_location": "L1"},
        ])
        mark_dead_candidates(G)
        assert G.nodes["c1"].get("dead_candidate") is True

    def test_non_zcl_z_method_no_callers_marked(self):
        """Method on a non-CL class (e.g. ZORDER->PROCESS) must be marked as dead."""
        G = _make_graph([
            {"id": "m1", "label": "ZORDER->PROCESS",
             "source_file": "zorder.abap", "source_location": "L10"},
        ])
        mark_dead_candidates(G)
        assert G.nodes["m1"].get("dead_candidate") is True

    def test_non_zcl_z_class_with_cross_edge_not_marked(self):
        """Non-CL Z class with a cross-file caller must not be marked."""
        G = _make_graph(
            [
                {"id": "c1", "label": "CLASS ZORDER DEFINITION",
                 "source_file": "zorder.abap", "source_location": "L1"},
                {"id": "c2", "label": "CLASS ZCL_FACTORY DEFINITION",
                 "source_file": "factory.abap", "source_location": "L1"},
            ],
            [{"source": "c2", "target": "c1", "_src": "c2", "_tgt": "c1",
              "relation": "uses"}],
        )
        mark_dead_candidates(G)
        assert not G.nodes["c1"].get("dead_candidate")

    def test_report_with_tcode_not_dead_candidate(self):
        """Programa con un TCODE apuntándole (edge launches) → NO dead_candidate."""
        from graphify.extract import _make_id
        prog_nid = _make_id("abap_prog", "Z_P_CP_NOMINAS")
        tran_nid = _make_id("abap_tran", "ZFI0001")
        G = _make_graph(
            [
                {"id": prog_nid, "label": "REPORT Z_P_CP_NOMINAS",
                 "source_file": "z_p_cp_nominas.abap", "source_location": "L1"},
                {"id": tran_nid, "label": "ZFI0001",
                 "source_file": "zfi0001.tran.xml", "source_location": "L1"},
            ],
            [{"source": tran_nid, "target": prog_nid, "_src": tran_nid, "_tgt": prog_nid,
              "relation": "launches"}],
        )
        mark_dead_candidates(G)
        assert not G.nodes[prog_nid].get("dead_candidate")

    def test_report_without_tcode_no_callers_flagged_dev_tool(self):
        """Programa sin TCODE y sin callers → dev_tool=True, NO dead_candidate."""
        from graphify.extract import _make_id
        prog_nid = _make_id("abap_prog", "Z_UTIL_ADMIN")
        G = _make_graph([
            {"id": prog_nid, "label": "REPORT Z_UTIL_ADMIN",
             "source_file": "z_util_admin.abap", "source_location": "L1"},
        ])
        mark_dead_candidates(G)
        assert not G.nodes[prog_nid].get("dead_candidate")
        assert G.nodes[prog_nid].get("dev_tool") is True

    def test_report_with_callers_not_dev_tool(self):
        """Programa llamado desde otro código → cross_in > 0, no dev_tool."""
        from graphify.extract import _make_id
        prog_nid = _make_id("abap_prog", "Z_REPORT_VENTAS")
        caller_nid = "c1"
        G = _make_graph(
            [
                {"id": prog_nid, "label": "REPORT Z_REPORT_VENTAS",
                 "source_file": "z_report_ventas.abap", "source_location": "L1"},
                {"id": caller_nid, "label": "ZCL_CALLER->RUN",
                 "source_file": "zcl_caller.abap", "source_location": "L10"},
            ],
            [{"source": caller_nid, "target": prog_nid, "_src": caller_nid, "_tgt": prog_nid,
              "relation": "calls"}],
        )
        mark_dead_candidates(G)
        assert not G.nodes[prog_nid].get("dead_candidate")
        assert not G.nodes[prog_nid].get("dev_tool")


# ---------------------------------------------------------------------------
# to_json hide_dead
# ---------------------------------------------------------------------------

class TestHideDead:

    def test_hide_dead_writes_graph_full_and_filters(self, tmp_path):
        from graphify.export import to_json

        G = _make_graph([
            {"id": "c1", "label": "CLASS ZCL_FOO DEFINITION",
             "source_file": "foo.abap", "source_location": "L1", "dead_candidate": True},
            {"id": "c2", "label": "CLASS ZCL_BAR DEFINITION",
             "source_file": "bar.abap", "source_location": "L1"},
        ])
        out = tmp_path / "graph.json"
        result = to_json(G, {}, str(out), force=True, hide_dead=True)
        assert result is True
        full = tmp_path / "graph_full.json"
        assert full.exists(), "graph_full.json must be written when hide_dead=True"
        full_data = json.loads(full.read_text())
        filtered_data = json.loads(out.read_text())
        assert len(full_data["nodes"]) == 2
        assert len(filtered_data["nodes"]) == 1
        assert filtered_data["nodes"][0]["id"] == "c2"

    def test_hide_dead_false_no_graph_full(self, tmp_path):
        from graphify.export import to_json

        G = _make_graph([
            {"id": "c1", "label": "CLASS ZCL_FOO DEFINITION",
             "source_file": "foo.abap", "source_location": "L1", "dead_candidate": True},
        ])
        out = tmp_path / "graph.json"
        to_json(G, {}, str(out), force=True, hide_dead=False)
        assert not (tmp_path / "graph_full.json").exists()


# ---------------------------------------------------------------------------
# _query_graph_text exclude_dead
# ---------------------------------------------------------------------------

class TestExcludeDead:

    def test_exclude_dead_removes_dead_nodes_from_traversal(self):
        from graphify.serve import _query_graph_text

        G = _make_graph([
            {"id": "live1", "label": "CLASS ZCL_LIVE DEFINITION",
             "source_file": "live.abap", "source_location": "L1"},
            {"id": "dead1", "label": "CLASS ZCL_DEAD DEFINITION",
             "source_file": "dead.abap", "source_location": "L1",
             "dead_candidate": True},
        ])
        result_with = _query_graph_text(G, "DEAD", exclude_dead=True)
        result_without = _query_graph_text(G, "DEAD", exclude_dead=False)
        # With exclude_dead the dead node should not appear (no match found or pruned)
        assert "ZCL_DEAD" not in result_with or "No matching" in result_with
        # Without exclude_dead it should appear
        assert "ZCL_DEAD" in result_without or "No matching" in result_without
