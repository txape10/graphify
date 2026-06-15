# Architecture

graphify is a Claude Code skill backed by a Python library. The skill orchestrates the library; the library can be used standalone.

## Pipeline

```
detect()  →  extract()  →  build_graph()  →  cluster()  →  analyze()  →  report()  →  export()
```

Each stage is a single function in its own module. They communicate through plain Python dicts and NetworkX graphs - no shared state, no side effects outside `graphify-out/`.

## Module responsibilities

| Module | Function | Input → Output |
|--------|----------|----------------|
| `detect.py` | `collect_files(root)` | directory → `[Path]` filtered list |
| `extract.py` | `extract(path)` | file path → `{nodes, edges}` dict |
| `build.py` | `build_graph(extractions)` | list of extraction dicts → `nx.Graph` |
| `cluster.py` | `cluster(G)` | graph → graph with `community` attr on each node |
| `analyze.py` | `analyze(G)` | graph → analysis dict (god nodes, surprises, questions) |
| `report.py` | `render_report(G, analysis)` | graph + analysis → GRAPH_REPORT.md string |
| `export.py` | `export(G, out_dir, ...)` | graph → Obsidian vault, graph.json, graph.html, graph.svg |
| `callflow_html.py` | `write_callflow_html(...)` | graphify-out files → Mermaid architecture/call-flow HTML |
| `ingest.py` | `ingest(url, ...)` | URL → file saved to corpus dir |
| `cache.py` | `check_semantic_cache / save_semantic_cache` | files → (cached, uncached) split |
| `security.py` | validation helpers | URL / path / label → validated or raises |
| `validate.py` | `validate_extraction(data)` | extraction dict → raises on schema errors |
| `serve.py` | `start_server(graph_path)` | graph file path → MCP stdio server |
| `watch.py` | `watch(root, flag_path)` | directory → writes flag file on change |
| `benchmark.py` | `run_benchmark(graph_path)` | graph file → corpus vs subgraph token comparison |

## Extraction output schema

Every extractor returns:

```json
{
  "nodes": [
    {"id": "unique_string", "label": "human name", "source_file": "path", "source_location": "L42"}
  ],
  "edges": [
    {"source": "id_a", "target": "id_b", "relation": "calls|imports|uses|...", "confidence": "EXTRACTED|INFERRED|AMBIGUOUS"}
  ]
}
```

`validate.py` enforces this schema before `build_graph()` consumes it.

## Confidence labels

| Label | Meaning |
|-------|---------|
| `EXTRACTED` | Relationship is explicitly stated in the source (e.g., an import statement, a direct call) |
| `INFERRED` | Relationship is a reasonable deduction (e.g., call-graph second pass, co-occurrence in context) |
| `AMBIGUOUS` | Relationship is uncertain; flagged for human review in GRAPH_REPORT.md |

## Adding a new language extractor

1. Add a `extract_<lang>(path: Path) -> dict` function in `extract.py` following the existing pattern (tree-sitter parse → walk nodes → collect `nodes` and `edges` → call-graph second pass for INFERRED `calls` edges).
2. Register the file suffix in `extract()` dispatch and `collect_files()`.
3. Add the suffix to `CODE_EXTENSIONS` in `detect.py` and `_WATCHED_EXTENSIONS` in `watch.py`.
4. Add the tree-sitter package to `pyproject.toml` dependencies.
5. Add a fixture file to `tests/fixtures/` and tests to `tests/test_languages.py`.

## ABAP extraction details

### extract_abap()

Parses `.abap` files using tree-sitter-abap (local fork at `../8 - tree-sitter-abap`).

**Nodes extracted:**

| Label pattern | ID scheme | Source construct |
|---|---|---|
| `CLASS <name> DEFINITION` | `abap_cls_*` | `class_definition` AST node |
| `CLASS <name>` | `abap_cls_*` | `class_implementation` AST node (same ID as DEFINITION) |
| `<class>-><method>` | `<stem>_<cls>_<meth>` | `method_implementation` inside class impl |
| `INTERFACE <name>` | `abap_intf_*` | `interface_definition` AST node |
| `FUNCTION GROUP <name>` | `abap_fg_*` | `function_pool_statement` in TOP include |
| `FUNCTION <name>` | `abap_fn_*` | `function_definition` AST node |
| `REPORT <name>` | `abap_prog_*` | `report_statement` AST node |
| `FORM <name>` | `<stem>_<name>` | `form_definition` AST node (file-scoped) |
| `EVENT <name>` | `abap_event_*` | `events_declaration` / `class_events_declaration` |
| `TRANSACTION <tcode>` | `abap_tran_*` | `extract_tran()` from `.tran.xml` |
| `BADI-><method>` | `abap_badi_method_*` | `call_badi_statement` (runtime stub) |

**Edges extracted:**

| Relation | Confidence | Trigger |
|---|---|---|
| `contains` | `EXTRACTED` | file→class, class→method/event, file→FM/FG/interface/form |
| `calls` | `EXTRACTED` | `CALL FUNCTION "..."`, `call_badi_statement` |
| `calls` | `INFERRED` | method `->` / `=>` call, `PERFORM`, `CALL METHOD` |
| `submits` | `EXTRACTED` | `SUBMIT <prog>` (static, Z/Y only; dynamic skipped) |
| `uses` | `INFERRED` | `TYPE REF TO`, `NEW`, `CREATE OBJECT`, `GET BADI TYPE`, `SET HANDLER me->` |
| `raises` | `EXTRACTED` | `RAISE EVENT <name>` |
| `launches` | `EXTRACTED` | `.tran.xml` TCODE → program (Z/Y only) |

**Node attributes (ABAP-specific):**

- `kind`: `"z_custom"` for objects starting with `Z` or `Y`; `"sap_standard"` for all others. Enables `--hide-dead` and graph filters to separate customer code from SAP dependencies. Events inside Z/Y classes inherit the class kind (event names don't follow the Z/Y convention).
- `dead_candidate`: set by `build.mark_dead_candidates(G)` — see below.
- `dev_tool`: set on `REPORT` nodes with no cross-file callers — utility programs run directly from SE38, not called from other code.
- `tcode`, `pgmna`, `dypno`, `ttext`: set on transaction nodes from `.tran.xml` exports.

**ID strategy (global IDs enable cross-file reconciliation):**

| Scheme | Objects |
|---|---|
| `abap_cls_*` | Classes — same ID in definition file and in `TYPE REF TO` stubs |
| `abap_intf_*` | Interfaces — same ID in definition and reference |
| `abap_fn_*` | Function modules — same ID in FM definition and `CALL FUNCTION` stub |
| `abap_fg_*` | Function groups |
| `abap_prog_*` | Programs/reports — same ID in `.abap` source and `.tran.xml` stub |
| `abap_event_*` | Events — same ID in declaration and `RAISE EVENT` stub |
| `abap_tran_*` | Transactions (from `.tran.xml`) |
| `abap_badi_method_*` | BADI method stubs (runtime-resolved, not reconciled) |
| `abap_method_*` | Methods — global, `_make_id("abap_method", class, method)` |
| `<stem>_<name>` | FORMs — file-scoped |

**Stub nodes:** cross-file references create lightweight placeholder nodes via `_ensure_stub()` with `source_file=""` and `source_location=None`. When the definition file is processed, `G.add_node()` overwrites the stub with real values. `source_location=None` signals `mark_dead_candidates` to skip stubs.

**ID global vs file-scoped — method IDs:** all method nodes use a global scheme (`abap_method_*`) independent of which file is being processed. This ensures that a stub created by a caller in `zcl_bar.abap` (via `SET HANDLER me->m` or a static `ZCL_FOO=>m` call) shares the same ID as the definition in `zcl_foo.abap`, enabling cross-file in-degree counting in `mark_dead_candidates`. FORMs remain file-scoped (`<stem>_<name>`) because FORM names are not globally unique.

### extract_tran()

Parses abapGit `.tran.xml` exports. These files come in two formats: (1) bare sibling elements `<TSTC>…</TSTC><TSTCT>…</TSTCT>` (older abapGit) and (2) a proper XML document with `<?xml?>` declaration and `<asx:abap>/<asx:values>` root (current abapGit). The extractor handles both: it strips any `<?xml?>` declaration with a non-greedy regex, wraps the remaining content in a synthetic `<root>`, and locates `TSTC`/`TSTCT` via namespace-agnostic XPath (`.//{*}TSTC`) so the `asx:` prefix is transparent. A 512 KB size guard prevents oversized file DoS.

Emits one `abap_tran` node per file plus a `launches EXTRACTED` edge to an `abap_prog` stub when `PGMNA` starts with `Z` or `Y`. The stub ID matches `extract_abap`'s REPORT node ID, so the two nodes merge automatically when the program source is in the corpus.

### Dead code detection (ABAP)

`build.mark_dead_candidates(G)` runs after `build_graph()` and sets `dead_candidate: true` on Z/Y custom objects with zero cross-file in-degree (no callers from other files in the corpus).

**Marked:** `CLASS Z*/Y* DEFINITION` and `Z*/Y*-><method>` / `Z*/Y*=><method>` nodes from `.abap` files; `.prog.abap` include nodes whose label matches the file stem.

**Never marked (and why):**

| Category | Reason |
|---|---|
| Function modules (`FUNCTION *`) | May be called from SAP-standard enhancement frameworks (CMOD/SMOD exits, classic BADIs) outside the corpus |
| Function groups (`FUNCTION GROUP *`) | Containers; zero direct callers is expected |
| FORMs (`FORM *`) | Called via `PERFORM` from programs not always in corpus |
| Reports (`REPORT *`) | Receive `dev_tool: true` if no callers — utility programs run from SE38 |
| Local classes (`LCL_*`, `MCL_*`) | File-local, never cross-file |
| Test classes / test methods | Identified by `FOR TESTING` / `*_TEST` patterns |
| SAP-standard objects (no Z/Y prefix) | Not customer code |
| Stub nodes (`source_location=None`) | No definition in corpus |

## Security

All external input passes through `graphify/security.py` before use:

- URLs → `validate_url()` (http/https only) + `_NoFileRedirectHandler` (blocks file:// redirects)
- Fetched content → `safe_fetch()` / `safe_fetch_text()` (size cap, timeout)
- Graph file paths → `validate_graph_path()` (must resolve inside `graphify-out/`)
- Node labels → `sanitize_label()` (strips control chars, caps 256 chars, HTML-escapes)

See `SECURITY.md` for the full threat model.

## Testing

One test file per module under `tests/`. Run with:

```bash
pytest tests/ -q
```

All tests are pure unit tests - no network calls, no file system side effects outside `tmp_path`.
