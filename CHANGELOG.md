# Changelog

## 0.2.1 — 2026-05-23

- Multi-line `|>` continuation inside lambda bodies (no parens needed)
- `none` as bare literal match pattern (`none:` shorthand for `== none:`)

## 0.2.0 — 2026-05-23

### Language
- Local scoping in `( )` blocks — assignments don't leak to outer scope
- `lst[i]` subscript and `lst[a..b]` slice syntax
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
