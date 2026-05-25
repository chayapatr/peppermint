# Changelog

# 0.3.1 — 2026-05-25

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
