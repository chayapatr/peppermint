# Changelog

## 0.4.0a1 — 2026-05-28

### Language (breaking)

- `add(field: expr, concurrent: N)` and `add(field: expr, retry: N)` kwargs removed — use `@concurrent(N)` and `@retry(N)` annotations instead
- `map(expr, concurrent: N)` and `mapi(expr, concurrent: N)` kwargs removed — use `@concurrent(N)` annotation
- `table[key]` keyed lookup removed — use `find(table, col, value)` instead (old syntax was ambiguous between positional and keyed access)

### Language

- **String interpolation** — `"{it.title} in {it.cluster}"` — any expression inside `{}` is evaluated in the current scope; `it` works inside pipe steps; per-expression fallback to literal if expression fails to parse
- **`env.KEY`** — bare field access on `env` reads environment variables directly; `env.OPENAI_API_KEY` preferred over `env.get("OPENAI_API_KEY")`
- **`@concurrent(n)`** — annotation on any pipe step or declaration; runs the step over each row in a thread pool with n workers. Replaces `concurrent:` kwarg
- **`@retry(n)`** — annotation; retries the step on exception up to n times
- **`@until(cond, max: n)`** — annotation on a step or `( )` block; retries rows where condition is false up to max rounds; failures go to `.errors`
- **`each` lambda form** — `|> each(by: "col", grp -> grp |> ...)` equivalent to block form

### Runtime

- **Context** — every table pipe now produces a `Context` carrying `.data`, `.errors`, and `.artifacts`. Access via dotted field: `posts.data`, `posts.errors`, `posts.kmeans`, `posts.umap`, `posts.viz`
- **Row-level errors** — when `add(field: expr)` or `select(..., field: expr)` fails on a row, that row moves to `ctx.errors` (with `_error` and `_step` metadata) instead of silently setting `None`. Pipe output shows `(N errors)` in yellow. Use `recover()` to pull failed rows back
- **`--cache` flag** — pass `pep file.pep --cache` to enable step caching. Results stored in `.peppermint/cache/` next to the file; unchanged steps are skipped on rerun. Cache key includes full step expression — steps with same name but different kwargs/block are cached independently
- **Row-level cache** — `ml.embed` and `ml.llm` cache per-row results in `.peppermint/row_cache/`; only new rows hit the API on rerun

### Standard library

- **`find(table, col, value)`** — find the first row where `col` equals `value`; returns `none` if not found. Replaces `table[key]` for cross-table lookup
- **`add(a: expr, b: expr)`** — accepts multiple fields in one call; each is evaluated against the original row independently
- **`drop("a", "b", "c")`** — accepts multiple field names
- **`select("a", b: it.x + 1)`** — keyword args compute or rename fields inline
- **`recover(field: expr)`** — move error rows back into data with a fallback value or expression; use after a step that may fail
- **`int(value)`** — returns `none` for `NaN` and `pandas.NA` instead of raising
- **`ml.llm(format: "json")`** — returns `none` on JSON parse failure (instead of raising), allowing `@until` to retry
- **`ml.kmeans`** — writes `{ model, k }` to `ctx.artifacts["kmeans"]`
- **`ml.umap`** — writes `{ model }` to `ctx.artifacts["umap"]`
- **`ml.ols`** — writes `{ model, r2, coefficients }` to `ctx.artifacts["ols"]`
- **`viz.scatter`, `viz.line`, `viz.histogram`, `viz.heatmap`** — write `{ plot }` to `ctx.artifacts["viz"]`

### LSP / VSCode

- String interpolation `{expr}` highlighted inside strings — `{` and `}` delimiters colored distinctly; full syntax highlighting inside expressions
- Annotation names (`concurrent`, `retry`, `until`, `stable`) no longer flagged as undefined references
- `InterpolatedStr` nodes walked for undefined reference checking

---

## 0.3.4 — 2026-05-27

### Interpreter (breaking fix)

- Fixed pipe-step assignments inside lambda block bodies (`x = data |> f() |> g()`): `x` now holds the final pipe result (after all steps), not the raw source value. Previously, `x = data |> collapse(...)` would bind `x` to `data`, making subsequent references to `x` silently return the wrong value.

### LSP

- Fixed false-positive "Undefined name" for variables assigned inside a lambda block body `( )` via a pipe step (`x = data |> ...`). The block scope scanner now extracts pipe-step assignments when building `block_known`, so later statements in the same block can reference them without a warning.

### Parser

- Fixed `'Parser' object has no attribute '_cur'` crash when `#` comments appeared inside a lambda block body `( )` — `_cur()` was called but never defined; now an alias for `_peek()`

### viz

- `viz.line(x, y, color?, size?, file?, display?)` : line chart with per-group lines; `display.dotsize` adds scatter dots on top of each line; supports `legend`, `axes`, `title`

---

## 0.3.3 — 2026-05-25

### Standard library

- `add(concurrent: N)` : runs field expression in parallel using N threads; preserves row order
- `map(concurrent: N)` : same for `map`
- `mapi(concurrent: N)` : same for `mapi`

### Core (breaking)

- `mapi` row object renamed: `it.value` → `it.val` — shorter and avoids shadowing result type names

- `str(value)`, `int(value)`, `float(value)` type cast functions added to core
- `use str` renamed to `use text` — avoids conflict with `str()` cast; all functions now under `text.*`

### text

- `text.parse(s)` : parse a JSON string back to a value — useful for embedding columns loaded from CSV

### math

- Added `math.min`, `math.max`, `math.sum`, `math.median`, `math.clamp(x, lo, hi)`, `math.pow(x, exp)`

### Bridge

- `@pep_fn` — default decorator for lib functions; auto-evaluates unevaluated kwargs, catches exceptions as `Err`
- `@pep_fn_lazy` — alias for `@pep_fn`, signals intent that kwargs may be expressions
- `@pep_fn_static` — no evaluation step, for functions whose args are always plain literals
- All stdlib libs (`ml`, `viz`, `math`, `str`) migrated from `wrap_lib` to `@pep_fn`
- `wrap_lib` still available for plain Python file imports

### ml

- `ml.embed` now reuses a single HTTP client per `(source, apikey)` — fixes "too many open files" under concurrent usage
- `ml.umap(neighbors?, min_dist?, metric?)` : new optional params for local/global structure tuning and distance metric
- `ml.umap` output columns renamed from `out1`/`out2` to `out_1`/`out_2` for consistency (e.g. `umap_1`, `umap_2`)
- `ml.kmeans`, `ml.ols`, `ml.umap` accept `model?` shorthand — loads if file exists, fits and saves otherwise; also `save_model?`/`load_model?` for explicit control
- `ml.dist(a, b, metric?)` : row-level scalar distance between two vectors; use inside `add`: `add(dist: ml.dist(it.embedding, it.centroid))`

### Standard library

- `mean`, `sum`, `min`, `max` inside `collapse` now handle vector (list) columns — element-wise operation via numpy
- Recommended centroid-distance pattern: `collapse(by, centroid: mean(col.embedding))` + `join` + `add(dist: ml.dist(...))`

### viz (breaking)

- `viz.scatter` `display` parameter now accepts an object: `display: { labels: "col", legend, axes, title: "..." }`
- Bare keys in object literals (`{ legend, axes }`) are treated as `true` — old list form `display: ["legend"]` still accepted
- `viz.scatter(size: [w, h])` : figure dimensions in inches
- `viz.scatter(display: { dotsize: N | "col" })` : uniform dot size or column-mapped variable size
- `viz.scatter`, `viz.histogram`, `viz.heatmap`, `viz.plot`, `viz.grid` all accept `file?: str` — saves image to path while still opening it
- `display: { labels: "col" }` renamed to `display: { label: "col" }` for consistency with top-level `color:` param

### LSP

- Block-local names no longer flagged as undefined (e.g. assignments inside `( )` blocks)
- Pattern-bound names (`Ok(data)`, `Err(msg)`) no longer flagged as undefined
- Hover tooltips for keywords: `match`, `use`, `true`, `false`, `none`, `it`, `col`
- Hover tooltips for operators: `|>`, `->`

## 0.3.2 — 2026-05-25

### LSP

- `pep lsp` : Language Server Protocol server over stdio, works with any LSP-capable editor
- Diagnostics : parse errors and undefined name references shown inline
- Hover : function signature and description for all stdlib and lib functions
- Completions : stdlib names, namespace-aware (`ml.`, `math.`, etc.), user-defined variables
- Go-to-definition : jumps to assignment site for user-defined names
- `pip install peppermint-lang[lsp]` to install

### VSCode extension (`ecosystem/vscode-peppermint`)

- Upgraded from syntax-only to full LSP client
- Launches `pep lsp` automatically on `.pep` file open

### ml (breaking)

- `ml.embed` is now a single-row column expression instead of a pipe step: `add(embedding: ml.embed(it.text, source: ..., model: ..., apikey: ...))` — `on:` and `out:` params removed
- `ml.umap` `out:` now accepts a list of explicit column names; length must match `dims`

## 0.3.1 — 2026-05-25

- fix README.md for PyPI

## 0.3.0 — 2026-05-25

### Language

- `col.field` : column reference for use in aggregation and column-level functions
- `collapse(by:, ...)` : replaces `group`+`agg`; `by:` is optional (omit for a single-row summary)
- `each(by:, |> ...)` : run a sub-pipe per group; results are concatenated or original table returned for side effects
- `take(n)` : keep first n elements
- `rank(col.field, by:, dir:)` : rank rows by column, optionally within groups : use in `add`
- `rolling(col.field, window, fn, by:)` : rolling window : use in `add`
- `add` with `col.field` expressions broadcasts group statistics back onto rows automatically

### Standard library

- `use env` : `env.get("KEY")` reads environment variables, returns `Err` if not set
- `ml` : all functions now use explicit `on:` and `out:` params; no defaults inferred from context

### Removed

- `group(by) { }` and `agg(...)` : replaced by `collapse` and `each`

## 0.2.2 — 2026-05-23

- `obj[key]` dynamic field access : `row[field]` where `field` is a variable now does dict lookup
- `ListValue` removed : lists are plain Python `list`; runtime is `int | float | str | bool | None | list | dict | Ok | Err`
- `match(result, Ok(data): ...)` now works on stored variables, not just inline expressions
- Curried lambdas : `f = x -> y -> x + y` and `f(x)(y)` call syntax
- `reduce` evaluates its data argument eagerly, fixing nested calls like `reduce(mapi(lst, ...), ...)` inside lambda bodies

## 0.2.1 — 2026-05-23

- Multi-line `|>` continuation inside lambda bodies (no parens needed)
- `none` as bare literal match pattern (`none:` shorthand for `== none:`)

## 0.2.0 — 2026-05-23

### Language

- `lst[i]` list subscript and `lst[a..b]` slice syntax
- `and`, `or`, `not` boolean operators
- Bare literal match shorthand: `0:` instead of `== 0:`, `true:` instead of `== true:`
- Multi-line binary expression continuation: operator at end of line continues on next
- Bare pipe step: `|> print` without parens

### Standard library

- `len` replaces `length` (breaking change)
- `concat(a, b, ...)` added
- `slice(lst, a, b)` added (inclusive end)

## 0.1.1 — 2026-05-23

- Local scoping in `( )` blocks : assignments are local to the block
- `mapi` index field renamed from `index` to `idx`
- Assignments inside paren blocks parsed correctly alongside expressions

## 0.1.0 — 2026-05-23

- Initial release: pipes, match, lambdas, objects, `load`/`save`, `filter`/`map`/`reduce`/`agg`/`group`
- stdlib: `str`, `math`, `ml`, `viz`
- Python bridge via `use "./file.py"`
- Miette-style error messages
