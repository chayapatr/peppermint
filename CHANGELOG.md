# Changelog

## 0.2.3 — 2026-05-25

### Language

- `col.field` — column reference syntax for use in aggregation and column-level functions
- `collapse(by:, ...)` — replaces `group`+`agg`; `by:` is optional (omit for a single-row summary)
- `take(n)` — keep first n elements

### Standard library

- `mean`, `sum`, `min`, `max`, `count` now take `col.field` as argument and accept `by:` for group-scoped broadcasting inside `add`
- `rank(col.field, by:, dir:)` — rank rows by a column, optionally within groups
- `rolling(col.field, window, fn, by:)` — rolling window aggregation, optionally within groups
- `add` detects column-level expressions (`mean`, `rank`, `rolling`, etc.) and broadcasts them back onto rows automatically
- `use env` — new lib for reading environment variables; `env.get("KEY")` returns the value or `Err`
- `ml.embed` — `col:` renamed to `on:`, added `out:` and `apikey:` (all now required, no defaults)
- `ml.kmeans` — `on:` and `out:` now required
- `ml.umap` — `out:` now required; `out: "prefix"` produces `prefix1`, `prefix2`; `out: ["x", "y"]` names columns explicitly
- `ml.ols` — `target:` renamed to `on:`, added `out:` (required); always adds `residual` column; prints R² and coefficients to stderr
- `ml.silhouette` — `on:` now required (cluster column name)

### Removed

- `group(by) { }` — replaced by `collapse(by:, ...)` and (upcoming) `each(by:, |> ...)`
- `agg(...)` — replaced by `collapse(...)`
- `ml.embed` default source auto-detection removed — `source:` and `model:` must be explicit

## 0.2.2 — 2026-05-23

- `obj[key]` dynamic field access — `row[field]` where `field` is a variable now does dict lookup
- `ListValue` removed — lists are plain Python `list`; runtime is `int | float | str | bool | None | list | dict | Ok | Err`
- `match(result, Ok(data): ...)` now works on stored variables, not just inline expressions
- Curried lambdas — `f = x -> y -> x + y` and `f(x)(y)` call syntax
- `reduce` evaluates its data argument eagerly, fixing nested calls like `reduce(mapi(lst, ...), ...)` inside lambda bodies

## 0.2.1 — 2026-05-23

- Multi-line `|>` continuation inside lambda bodies (no parens needed)
- `none` as bare literal match pattern (`none:` shorthand for `== none:`)

### Language

- `lst[i]` list subscript and `lst[a..b]` slice syntax
- `and`, `or`, `not` boolean operators
- Bare literal match shorthand — `0:` instead of `== 0:`, `true:` instead of `== true:`
- Multi-line binary expression continuation — operator at end of line continues on next
- Bare pipe step — `|> print` without parens

### Standard library

- `len` replaces `length` (breaking change)
- `concat(a, b, ...)` added
- `slice(lst, a, b)` added (inclusive end)

## 0.1.1 — 2026-05-23

- Local scoping in `( )` blocks — assignments are local to the block
- `mapi` index field renamed from `index` to `idx`
- Assignments inside paren blocks parsed correctly alongside expressions

## 0.1.0 — 2026-05-23

- Initial release: pipes, match, lambdas, objects, `load`/`save`, `filter`/`map`/`reduce`/`agg`/`group`
- stdlib: `str`, `math`, `ml`, `viz`
- Python bridge via `use "./file.py"`
- Miette-style error messages
