# CLAUDE.md — Repo 6: Parser ABAP + integración en Graphify (la herramienta)

Ruta: `C:\Users\rchapado\Proyectos Claude\6 - Parser ABAP + integración en Graphify\`

Léelo entero antes de actuar.

## Principios Karpathy (marco general, aplica a TODO el trabajo)

Los cuatro principios de Andrej Karpathy para coding con IA. Rigen por encima de las reglas
específicas de este repo; las reglas de proyecto concretan estos principios, no los sustituyen.

1. **Think Before Coding** — No asumir. No ocultar dudas. Exponer tradeoffs. Si hay ambigüedad,
   preguntar en vez de adivinar; presentar interpretaciones posibles; discrepar si hay un enfoque
   más simple; parar y nombrar lo que no está claro.
2. **Simplicity First** — Código mínimo que resuelve el problema, nada especulativo. Sin features no
   pedidas, sin abstracciones de un solo uso, sin "flexibilidad" no solicitada. Si 200 líneas pueden
   ser 50, reescribir.
3. **Surgical Changes** — Tocar solo lo imprescindible; limpiar solo lo que tú ensucias. No mejorar
   código/comentarios/formato adyacentes; respetar el estilo existente; código muerto ajeno se
   menciona, no se borra. Cada línea cambiada debe trazar a lo pedido.
4. **Goal-Driven Execution** — Definir criterios de éxito verificables y hacer loop hasta cumplirlos.
   Convertir órdenes en metas comprobables; para tareas multipaso, enunciar plan breve con
   verificación por paso.

Equilibrio: cautela sobre velocidad. Tareas triviales (typos, one-liners) → usar juicio.

---

## Estructura física del conjunto (tres repos, sin ambigüedad)

```
C:\Users\rchapado\Proyectos Claude\
  6 - Parser ABAP + integración en Graphify\   ← ESTE repo. ES tu fork de graphify (su .git aquí).
  7 - ZCode+grafos\                             ← datos y grafos (git local privado). Repo hermano.
  8 - tree-sitter-abap\                         ← tu fork del parser ABAP (su .git aquí).
```

- **Esta carpeta (6) ES el fork de graphify**, no una carpeta contenedora. Se obtiene clonando tu
  fork de graphify COMO esta carpeta. No se clona graphify "dentro" de aquí.
- **El parser NO vive aquí.** Es el repo 8 (tu fork de `kennyhml/tree-sitter-abap`). Este repo (6)
  **depende** del 8: el `pyproject.toml` de este fork apunta a tu parser local del repo 8 (instalación
  editable), no al paquete de PyPI.
- El repo 8 existe desde el principio porque la Fase 2 probablemente exija extender la gramática para
  tu legacy, y eso requiere un fork propio (no puedes modificar el repo de kennyhml).

## Qué es este repo

Fork de `safishamsi/graphify` (rama base: **v8**) cuyo único objetivo de divergencia es **añadir ABAP
como lenguaje extraíble**, usando el parser del repo 8. Todo lo demás idéntico al upstream para poder
rebasar sin conflictos.

- Upstream: https://github.com/safishamsi/graphify (rama `v8`)
- Parser base (a forkear → repo 8): https://github.com/kennyhml/tree-sitter-abap
- Paquete PyPI de graphify: `graphifyy` (doble "y"). Comando: `graphify`. Dev con **uv**.
- Vive en GitHub (fork público; posible PR de la integración ABAP). **Nunca incluir código ABAP
  propietario aquí** — eso va en el repo 7, privado.

## Alcance estricto: SOLO código

El parser tree-sitter parsea **código** (`.abap`). El DDIC (tablas, estructuras, elementos de datos,
CDS) NO es de este repo — se extrae de los XML de abapGit con otro extractor, en el repo 7. Si una
tarea menciona DDIC/tablas/CDS, no corresponde aquí (salvo la costura código→datos, ver más abajo).

## Reglas específicas de este repo (concretan los principios de arriba)

1. **Verifica antes de escribir** (Think Before Coding aplicado): lee el fichero real
   (`extract.py`, `detect.py`, `watch.py`, `validate.py`, `ARCHITECTURE.md`) y confirma que coincide
   con el plan antes de tocar. Si no coincide, para y dilo.
2. **Toca lo mínimo del upstream** (Surgical Changes): modificar de *graphify* solo `extract.py`
   (función + dispatch), `collect_files()`, `CODE_EXTENSIONS` (`detect.py`), `_WATCHED_EXTENSIONS`
   (`watch.py`), `pyproject.toml`, `tests/`, y por excepción aprobada `dedup.py` (`_is_exact_identity`) y `_rewire_unique_stub_nodes` (guardia `ddic_*`). No refactorizar el pipeline. Scripts propios (p. ej.
   `probe_abap.py`) son código nuevo, viven aparte.
3. **Respeta el esquema de `validate.py`** (no inventar otro):
   ```json
   {"nodes":[{"id":"...","label":"...","source_file":"...","source_location":"L<n>"}],
    "edges":[{"source":"...","target":"...","relation":"calls|imports|uses|...",
              "confidence":"EXTRACTED|INFERRED|AMBIGUOUS"}]}
   ```
4. **Fija versiones**: el parser (repo 8) y graphify deben usar versiones de `tree-sitter` (py)
   compatibles. La API de `Language(...)` difiere entre <0.21 y ≥0.21: escribir para la instalada.
5. **Sigue un `extract_<lang>` existente como plantilla** (Simplicity First): copiar el patrón, no
   inventar uno nuevo.
6. **`id` deterministas**: derivar del nombre del objeto ABAP, no de offsets de línea. El repo 7
   depende de esto para que el grafo global no duplique nodos.
7. **Correcciones directas** (preferencia tuya): corrige y muestra diff conciso; sin explicación larga
   salvo que la pida.

## Patrón de `extract_abap(path: Path) -> dict`

Pipeline: `tree-sitter parse → recorrer árbol → recolectar nodes/edges → 2ª pasada call-graph (calls
INFERRED)`.

**Nodos:** clases (`CLASS ... DEFINITION/IMPLEMENTATION`), métodos, interfaces, grupos de funciones,
módulos de función (`FUNCTION`), reports/programas, rutinas `FORM` (legacy).
**Edges:** `calls` (método `->`/`=>`, `CALL FUNCTION`, `PERFORM`), `imports`/`uses` donde el AST deje.
Empezar por nodos + `calls`.

**Distinción Z vs SAP estándar — DECISIÓN TOMADA:** el grafo incluye dependencias hacia objetos SAP
estándar (tablas como TADIR, funciones como TR_TADIR_INTERFACE), pero **distinguidos** de los objetos Z.
- La marca va en el **nodo**, no en el edge. Atributo `"kind"`: `"z_custom"` (tuyo) vs `"sap_standard"`.
- Regla de derivación por nombre: empieza por `Z` o `Y` → `z_custom`; resto → `sap_standard`.
  Excepción: los **FORM** (locales a su programa) toman el kind del fichero que los contiene (nombre hasta el primer `.`), no del nombre de la rutina.
- Los nodos `sap_standard` se crean como nodos ligeros (solo nombre + kind) al emitir un edge hacia
  ellos; no requieren fichero `.abap`. Así el grafo puede filtrar "solo Z" o "todo" sin perder info.

### Costura código→datos — IMPLEMENTADA (Open SQL → stubs `ddic_tabl_*`)

`extract_abap` emite aristas desde el código hacia las tablas que lee/escribe con Open SQL:

- **Relaciones**: `selects_from` (SELECT/JOIN/subconsultas/`OPEN CURSOR`) y `writes_to`
  (INSERT/UPDATE/MODIFY/DELETE). `selects_from` es la misma relación que usa `extract_ddic` (repo 7)
  para vista→tabla, con el mismo sentido (quien lee → tabla); no colisionan porque los orígenes difieren.
- **Origen**: método, FORM o módulo de función que envuelve la sentencia; en código de nivel superior,
  el nodo fichero (igual que `calls`).
- **Destino**: `ddic_tabl_<nombre_minúsculas>` (mismo formato que `extract_ddic._node_id`). Se crea un
  **nodo stub** (`file_type=code`, `source_location=None`, `kind` z_custom/sap_standard, etiqueta en
  mayúsculas): `build_from_json` descarta aristas cuyo destino no existe (sin nodos fantasma), así que
  sin stub la arista se perdería. Al ejecutar `extract_ddic.py` (repo 7) sobre el mismo id el stub se
  **promueve** a nodo DDIC (`file_type=ddic`, `_origin=ddic_extractor`, `_promoted_from_stub=True`).
  Por eso `dedup.py::_is_exact_identity` excluye de la fusión por similitud de etiqueta los nodos
  `file_type=ddic`, `_origin=ddic_extractor` o con id `ddic_*`: sin ello, un `graphify extract`
  **incremental** (`build_merge` carga el `graph.json` con los DDIC ya inyectados) fundía tablas
  hermanas (`ZTSU_EXPED_LOG_H/_M/_R...`) y redirigía las aristas a la tabla equivocada. Con versiones
  anteriores a este fix no ejecutar `extract` incremental sobre un grafo con nodos DDIC.
  **La condición previa original ("Graphify reconcilia por nombre con nodos de otro extractor") era
  falsa**; la reconciliación se logra por id idéntico + stub.
- **Confianza**: EXTRACTED salvo `MODIFY t FROM wa` y `DELETE t FROM wa` (INFERRED: ambiguos con tablas
  internas; se descartan si `t` está declarado con `DATA` en el fichero o tiene prefijo local
  `[lgmipcer]?_` (`lt_`, `gs_`, `mi_`, `it_`, `cs_`, `es_`, `rt_`...); no se recogen parámetros de método ni `TABLES`). `... FROM TABLE` es EXTRACTED: no existe para tablas internas.
- **INCLUDE**: `INCLUDE x.` emite `includes` (EXTRACTED) hacia `abap_incl_<x>`; el fichero include define ese nodo (etiqueta `INCLUDE X`, no marcado dead) y lo hace padre (`contains`) de sus definiciones de primer nivel además del nodo fichero (REPORT→include→FORM = 2 saltos). Origen: FORM/método/FM envolvente o, a nivel superior, REPORT / `abap_fg_*` / el propio include. Sin stub para includes Z (un stub con `source_file=""` haría que `_disambiguate_colliding_node_ids` renombrase el nodo real); stub `sap_standard` para los estándar. Si el include no está en el corpus la arista se descarta en el build. `_rewire_unique_stub_nodes` ignora stubs `ddic_*` (tabla y transacción homónimas, patrón SM30).
- **Método**: la gramática (repo 8) no tiene reglas de Open SQL, así que se escanea el **texto** por
  sentencias (`_abap_sql_table_refs`), enmascarando comentarios y literales con los mismos offsets que
  el árbol. No se toca la gramática.
- `graphify extract` construye un grafo **no dirigido**: si un método lee y escribe la misma tabla, las
  dos aristas se funden y prevalece `writes_to`. Tras cambiar el extractor hay que
  invalidar la caché: `graphify extract` no tiene `--force`; borrar `<out>/graphify-out/cache/ast`,
  `cache/stat-index.json` y `manifest.json` (este último evita el modo incremental), y después
  ejecutar `extract_ddic.py --full-rebuild` en el repo 7.

**Limitaciones**: SQL dinámico (`FROM (lv_tab)`, `SELECT (lv_fields)`) y `EXEC SQL` no se resuelven;
las formas cortas obsoletas con `TABLES` (`MODIFY t.`, `DELETE t.`) quedan fuera; vistas DDIC y CDS
(`zcds_*`) acaban como `ddic_tabl_<vista>` (no casan con `ddic_view_*`); macros con `&1` y
`IMPORT/EXPORT ... FROM DATABASE` no se analizan; un `FROM` dentro de funciones SQL como
`TRIM( BOTH x FROM col )` puede dar un falso positivo aislado.

## Cobertura legacy

Parser permisivo pero NO cubre todo el ABAP obsoleto y falla en colon-chaining general. Esto es
esperado. Si un fichero da nodos `ERROR`, no toques la gramática por iniciativa propia: reporta % y
construcciones, y se decide (ignorar / extender gramática en repo 8 / preprocesar con ABAP Formatter).

## Comandos

```bash
uv sync --all-extras
uv run graphify --version
uv run pytest tests/ -q
uv run pytest tests/ -q -k abap
```
Windows/PowerShell: `graphify .` (sin barra), `graphify install --platform windows`.

## Definición de "hecho" (Goal-Driven Execution)

- `uv run pytest tests/ -q -k abap` pasa.
- `graphify extract <carpeta-con-.abap>` (sin caché/manifest previos) da nodos modernos **y** legacy con edges `calls`
  moderno→legacy.
- Nada del pipeline modificado fuera de la regla 2.
- `id` deterministas (regla 6): re-extraer no duplica nodos.
- % de nodos ERROR sobre el corpus documentado y aceptable (acordado conmigo).

## Estilo

Python idiomático consistente con upstream; sin dependencias nuevas salvo el parser del repo 8.
Commits: `feat:`/`fix:`/`docs:`. Antes de PR/commit grande: `uv run pytest tests/ -q` en verde.
