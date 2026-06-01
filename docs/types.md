# Peppermint Type System

## Value Types

```
Type = Scalar
     | List<Type>
     | Object<{ label: Type, ... }>
     | Result<Type>
     | ColRef<label>
     | Fn<Type... → Type>
     | None

Scalar = Int | Float | Str | Bool
```

`Object` is a record with named fields — what `{ name: "alice", age: 25 }` produces and what each row from `load()` is. `List<Object<...>>` is the primary data structure for tabular data.

---

## Pipe `|>`

```
(|>) : Result<a> → (a → Result<b>) → Result<b>
```

Monadic bind over `Result`. Steps can return a plain value `b` (implicitly `Ok(b)`), an explicit `Err`, or throw an exception (caught and converted to `Err`). The pipe unwraps, applies, and re-wraps:

```
bind(Ok(a),  f) = f(a)    -- f returns Ok(b) or Err(e)
bind(Err(e), f) = Err(e)  -- skip, propagate error
```

Step authors write plain functions returning plain values — `Ok` wrapping is implicit. Only IO functions (`load`, `save`) return `Result` explicitly.

The source is always lifted into `Ok` on entry:

```
[1, 2, 3]               -- plain List, lifted to Ok(List) by pipe
  |> map(it * 2)          -- receives List, returns List, pipe wraps Ok
  |> filter(it > 2)       -- same
```

```
load("data.csv")        -- Ok(List) | Err — IO can fail
  |> filter(it.age > 18)  -- pure, pipe wraps result
  |> add(score: ...)       -- pure, pipe wraps result
```

Any exception thrown inside a pipe step is caught and becomes `Err`. Outside a pipe, exceptions propagate normally.

`match` is the only way to switch from the error track back to the happy track — errors cannot be silently ignored.

Bare name in a pipe step is called as a zero-arg function with the piped value:

```
data |> print      -- same as data |> print()
data |> clean      -- same as data |> clean()
```

---

## `it`

`it` is the implicit element variable, bound per-step to the element type of the list being operated on:

```
List<Object<S>>  →  it : Object<S>
List<Int>        →  it : Int
List<Str>        →  it : Str
```

`it` is syntactic sugar for a lambda with one implicit parameter. These are equivalent:

```
filter(it.age > 18)
filter(row -> row.age > 18)
```

---

## `col.field`

`col.field` produces a `ColRef<label>` — a reference to a column across all rows. It is passive: it names a column but does not compute anything. Functions act on it.

```
col.salary   : ColRef<"salary">
col.amount   : ColRef<"amount">
```

`ColRef` is only meaningful inside column-level functions (`mean`, `sum`, `rank`, `rolling`, etc.) and inside `collapse`. Using it elsewhere has no effect.

---

## match

```
match : a → (Pattern<a> → b)... → b
```

Evaluates the subject against each arm in order, returns the first match. Always an expression — never a statement. All arms must return the same type.

Patterns:

```
> n   < n   >= n   <= n   == n   != n    -- comparison (Scalar)
7   "x"   true   false   none           -- bare literal, shorthand for == value
Ok(x)   Err(x)                           -- Result destructure
_                                        -- wildcard, always matches
```

### Arithmetic operators

```
+  -  *  /  %
```

`%` is modulo, same precedence as `*` and `/`.

---

## Function Application

```
f(a, b, key: c)
```

Positional args are passed in order. Keyword args are named. A function defined as:

```
add = (x, y) -> x + y
```

Can be called as `add(1, 2)`. Stdlib functions also accept keyword args: `sort(by: "age", dir: "desc")`.

### Recursion

Functions can reference themselves. The binding is updated after assignment so the closure sees the function's own name:

```
fact = n -> match(n, 0: 1, _: n * fact(n - 1))
```

### Local bindings

Inside `( )`, assignments are local — they don't leak into the outer scope. The last expression is the return value:

```
next_cell = (grid, x, y) -> (
  cell = grid[y * w + x]   -- local to this block
  n    = neighbors(grid, x, y)
  match(cell, ...)
)
```

Semicolons also work as statement separators:

```
f = x -> (print(x); f(x - 1))
```

Type:
```
Block : Expr... → a    -- evaluates each in a local scope, returns last
```

---

## Type Classes

### Functor

```
map  : List<a> → (a → b) → List<b>
mapi : List<a> → ({idx: Int, value: a} → b) → List<b>
```

`mapi` passes `{idx, value}` as `it` — useful when you need the index alongside the element.

### Filterable

```
filter : List<a> → (a → Bool) → List<a>
take   : List<a> → Int        → List<a>
```

### Foldable

```
reduce : List<a> → b → ((b, a) → b) → b
```

`fn` takes two explicit args — accumulator first, current element second.

---

## List Operations

```
len    : List<a> → Int
get    : List<a> → Int → a           -- prefer lst[i] syntax
concat : List<a>... → List<a>
```

Indexing and slicing syntax:

```
lst[i]      ≡  get(lst, i)
lst[a..b]   ≡  slice(lst, a, b)     -- inclusive end, dynamic expressions ok
```

---

## Object Operations

Only valid on `List<Object<S>>`. Schema-aware — not general list operations.

```
add    : List<Object<S>> → (label: Object<S> → a) → List<Object<S ∪ {label: a}>>
drop   : List<Object<S>> → label                  → List<Object<S \ {label}>>
select : List<Object<S>> → label...               → List<Object<S ∩ {label...}>>
rename : List<Object<S>> → (old: new)             → List<Object<S[old→new]>>
sort   : List<Object<S>> → by → dir               → List<Object<S>>
join   : List<Object<S>> → List<Object<T>> → on   → List<Object<S ∪ T>>
save   : List<Object<S>> → path                   → List<Object<S>>   -- pass-through
```

Passing a non-object list to these raises a type error.

---

## Aggregation

### `collapse`

```
collapse : List<Object<S>> → (by:?, label: AggFn)... → List<Object<{by?, label: Scalar}>>
```

Collapses rows into a summary. `by:` is optional — omit for a single-row result, provide for one row per unique key value.

```
AggFn = sum(ColRef) | mean(ColRef) | count() | min(ColRef) | max(ColRef)
```

The `AggFn` constructors:

```
sum   : ColRef<f> → AggFn
mean  : ColRef<f> → AggFn
count : ()        → AggFn
min   : ColRef<f> → AggFn
max   : ColRef<f> → AggFn
```

All accept an optional `by:` parameter for use inside `add` — when present, the result is a Series aligned to rows (group broadcast), not a scalar.

### Column functions — for use inside `add`

```
rank    : ColRef<f> → by:? → dir:? → Series<Int>
rolling : ColRef<f> → Int → AggFn → by:? → Series<Float>
```

When `add` receives a `Series` (from `rank`, `rolling`, or a `by:`-scoped agg), it aligns the values back onto rows by position. When it receives a scalar, it broadcasts the same value to all rows.

```
add(label: AggFn)    -- scalar or series, resolved at runtime
```

---

## List Construction

A list literal `[{...}, {...}]` where all elements are objects produces `List<Object>`, the same type as `load()`. A list of scalars produces `List<Scalar>`:

```
[1, 2, 3]                             -- List<Int>
[{ name: "a" }, { name: "b" }]        -- List<Object<{ name: Str }>>
```

---

## Dispatch (Overloading)

`map` and `filter` are overloaded — dispatch on the runtime type of the input:

```
map(expr)
  List<Object<S>>  →  it : Object<S>,  output type follows expr
  List<a>          →  it : a,          output type follows expr

filter(pred)
  List<Object<S>>  →  it : Object<S>
  List<a>          →  it : a
```

---

## Result

```
Result<a> = Ok<a> | Err<Str>
```

Every pipe produces a `Result`. Pure functions inside the pipe return plain values — the pipe wraps them. Only `load` and `save` return `Result` directly (IO can fail).

Handle with `match`:

```
match(result,
  Ok(data): data |> print(),
  Err(msg): print(msg)
)
```

Outside a pipe, expressions are not wrapped — `1 + 1` is `2`, not `Ok(2)`. Errors outside a pipe crash.

---

## Object Shorthand

```
{ x }       ≡   { x: x }
{ x, y }    ≡   { x: x, y: y }
```

Any name inside `{ }` without a `:` is shorthand for `name: name`. Can be mixed with explicit fields:

```
{ x, label: "hello", y }
```

---

## Libraries (`use`)

Loaded on demand. Any `.py` file in `peppermint/libs/` is autodiscovered. User Python files loaded via `use "./file.py"` go through the bridge automatically.

### Env — `use env`

```
env.get(key) : Str → Str | Err
```

Reads an environment variable. Returns `Err` if not set.

### ML — `use ml`

All functions require explicit `on:` (input column) and `out:` (output column):

```
ml.embed(on:, out:, source:, model:, apikey:)
  : List<Object<S>> → List<Object<S ∪ {out: List<Float>}>>

ml.kmeans(k:, on:, out:)
  : List<Object<S>> → List<Object<S ∪ {out: Int}>>

ml.umap(dims:, on:, out:)
  : List<Object<S>> → List<Object<S ∪ {out1: Float, out2: Float, ...}>>

ml.ols(on:, out:)
  : List<Object<S>> → List<Object<S ∪ {out: Float, residual: Float}>>

ml.silhouette(on:)
  : List<Object<S>> → List<Object<S>>   -- pass-through, prints score to stderr
```

### Str — `use str`

Operate on `Str`, return `Str` or `Bool`:

```
str.trim(s)              : Str → Str
str.lower(s)             : Str → Str
str.upper(s)             : Str → Str
str.replace(s, old, new) : Str → Str
str.split(s, sep)        : Str → List<Str>
str.join(parts, sep)     : List<Str> → Str
str.contains(s, sub)     : Str → Bool
str.starts_with(s, pre)  : Str → Bool
str.ends_with(s, suf)    : Str → Bool
str.length(s)            : Str → Int
str.match(s, pattern)    : Str → Bool
str.slice(s, start, end) : Str → Str
```

### Bridge

Python libs loaded via `use` go through `peppermint/bridge.py`:
- `to_python` / `from_python` — convert between Peppermint and Python types
- `get_rows`, `map_rows`, `add_column`, `filter_rows` — row utilities
- `ok(val)`, `err(msg)` — construct results without importing interpreter internals
