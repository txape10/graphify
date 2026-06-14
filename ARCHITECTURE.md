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

| Label pattern | Source construct |
|---|---|
| `CLASS <name> DEFINITION` | `CLASS ... DEFINITION` block |
| `CLASS <name> IMPLEMENTATION` | `CLASS ... IMPLEMENTATION` block |
| `<class>-><method>` / `<class>=><method>` | `METHOD` inside implementation |
| `INTERFACE <name>` | `INTERFACE` block |
| `FUNCTION GROUP <name>` | from filename of `*.fugr.abap` |
| `FUNCTION <name>` | `FUNCTION` block inside a function group |
| `REPORT <name>` | derived from filename of `*.prog.abap` |
| `FORM <name>` | `FORM` block (legacy subroutine) |

**Edges extracted:**

| Relation | Confidence | Trigger |
|---|---|---|
| `calls` | `EXTRACTED` | `CALL FUNCTION "..."` |
| `calls` | `INFERRED` | method `->` / `=>` call, `PERFORM`, second-pass call-graph |
| `uses` | `INFERRED` | `DATA ... TYPE REF TO <class>`, `NEW <class>( )`, `CREATE OBJECT ... TYPE <class>` |
| `contains` | `EXTRACTED` | file→class, class→method, file→interface, file→form |

**Node attributes (ABAP-specific):**

- `kind`: `"z_custom"` for objects starting with `Z` or `Y`; `"sap_standard"` for all others. Enables `--hide-dead` and graph filters to separate customer code from SAP dependencies.
- `dead_candidate`: set by `build.mark_dead_candidates(G)` — see below.

**ID strategy:**

- Classes: `_make_id("abap_cls", name)` — global, file-independent. Same ID whether the node comes from the definition file or a reference stub.
- Interfaces: `_make_id("abap_intf", name)` — same rationale.
- Methods: `_make_id("abap_cls", class_name, method_name)`.
- Function modules: `_make_id("abap_fn", name)` — global.
- FORMs / reports: file-scoped via `_make_id(_file_stem(path), name)`.

**Stub nodes:** when a `TYPE REF TO`, `NEW`, or `CREATE OBJECT` reference targets a class not in the corpus, `_ensure_stub()` creates a lightweight placeholder node with `source_file=""` and `source_location=None`. If the definition file is later processed, `G.add_node()` overwrites the stub with real values. `source_location=None` prevents `mark_dead_candidates` from flagging stubs.

### Dead code detection (ABAP)

`build.mark_dead_candidates(G)` runs after `build_graph()` and sets `dead_candidate: true` on Z/Y custom objects that have zero cross-file in-degree (no callers from other files).

**Marked:** `CLASS Z*/Y* DEFINITION`, `ZCL_*/YCL_*-><method>`, `ZCL_*/YCL_*=><method>`, and `.prog.abap` include nodes whose label matches the file stem.

**Never marked:** FORMs (called from transactions outside the graph), function modules, function groups, local classes (`LCL_`/`MCL_`), test classes (`FOR TESTING`), test methods (`*_TEST`), SAP-standard objects (no Z/Y prefix), and stub nodes (`source_location=None`).

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
