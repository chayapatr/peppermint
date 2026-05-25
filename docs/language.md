# Peppermint

A pipe-first language for data work. Run files with `pep file.pep`, or just `pep` for the REPL.

---

## Basics

```
x = 42
name = "alice"
flag = true
nothing = none
```

Comments start with `#`.

---

## Pipes

The core of the language. Data flows left to right through `|>`:

```
load("data.csv")
  |> filter(it.age > 18)
  |> add(score: it.income / it.age)
  |> sort(by: "score", dir: "desc")
  |> print()
```

Pipes are railway-oriented — every pipe produces `Ok(value)` or `Err(message)`. If any step fails, all downstream steps are skipped automatically and the error propagates to the end.

Each step prints a summary automatically:

```
|> filter    → List  843 rows × 8 cols  (157 dropped)
|> add       → List  843 rows × 9 cols  (+score)
```

Suppress with `quiet`:

```
|> filter(it.age > 18) quiet
```

---

## `it`

Inside any pipe step, `it` refers to the current row:

```
|> filter(it.age > 18)
|> add(ratio: it.income / it.age)
```

---

## `col.field`

`col.field` refers to a field across all rows as a column. Used in aggregation and column-level functions:

```
|> collapse(avg: mean(col.salary))
|> add(dept_avg: mean(col.salary, by: "dept"))
|> add(rank: rank(col.salary, dir: "desc"))
```

`col` is passive — it is a reference, not a computation. Functions (`mean`, `rank`, `rolling`) act on it.

---

## match

The only branching construct. Always returns a value:

```
match(it.income,
  > 50000: "high",
  > 20000: "medium",
  _:       "low"
)
```

Patterns: `>`, `<`, `>=`, `<=`, `==`, `!=`, `_` (wildcard). Bare literals match by equality — `7` is shorthand for `== 7`, `true` for `== true`, `"x"` for `== "x"`:

```
match(n,
  0: "zero",
  1: "one",
  _: "many"
)
```

Use inside a pipe step:

```
|> add(tier: match(it.income, > 80000: "high", _: "low"))
```

---

## Functions

Functions are just assignments with `->`:

```
double = x -> x * 2

clean = data -> (
  data
    |> filter(it.age > 18)
    |> filter(it.income > 0)
)
```

Parentheses let the body span multiple lines. Assignments inside `( )` are local — they don't leak into the outer scope:

```
next_cell = (grid, x, y) -> (
  cell = grid[y * w + x]
  n    = neighbors(grid, x, y)
  match(cell,
    1: match(n, 2: 1, 3: 1, _: 0),
    _: match(n, 3: 1, _: 0)
  )
)
```

The last expression is the return value. Semicolons also work as statement separators:

```
f = x -> (print(x); f(x - 1))
```

Functions can call themselves recursively:

```
fact = n -> match(n, 0: 1, _: n * fact(n - 1))
```

### Curried functions

A lambda body can itself be a lambda, giving you curried functions:

```
add = x -> y -> x + y
add(1)(2)    # 3

mul = x -> y -> x * y
double = mul(2)
double(5)    # 10
```

Call them like any built-in:

```
load("data.csv")
  |> clean()
  |> print()
```

---

## Result and error handling

Every pipe returns `Ok(value)` or `Err(message)`. Pure functions inside the pipe return plain values — the pipe wraps them in `Ok`. Only IO functions (`load`, `save`) produce `Ok`/`Err` directly.

Any exception inside a pipe step becomes `Err` automatically — you never get a crash mid-pipe.

Handle the result with `match`:

```
result = load("data.csv")
  |> filter(it.age > 18)

match(result,
  Ok(data): print(data),
  Err(msg):  print(msg)
)
```

This works whether `result` is assigned from a pipe or computed inline. `match` is the only way back to the happy track — errors can't be silently ignored.

---

## Namespaces

Group related functions with `ns`:

```
ns transforms {
  clean = data -> (
    data
      |> filter(it.age > 18)
      |> filter(it.income > 0)
  )
}

load("data.csv")
  |> transforms.clean()
  |> print()
```

Import stdlib libs or external files with `use`:

```
use ml
use math
use viz
use env
use "./transforms.pep" as t
use "./my_utils.py" as u     # plain Python file
```

Python files are loaded via the bridge — functions receive and return plain Python types, conversion is automatic.

---

## Collections

```
[1, 2, 3]                          # list
{ name: "alice", age: 25 }         # object
{ ...existing, score: 42 }         # object spread
{ name, age }                      # object shorthand — same as { name: name, age: age }
1..10                              # range
```

A list of objects (`[{ ... }, { ... }]`) automatically becomes a typed `List<Object>`, the same type returned by `load()`. This means you can construct inline datasets and pass them directly to any list operation:

```
[{ name: "alice", age: 25 }, { name: "bob", age: 17 }]
  |> filter(it.age >= 18)
  |> print()
```

### Indexing and slicing

```
lst[0]       # get element at index
lst[1..3]    # slice from index 1 to 3 (inclusive)
lst[mid..len(lst)-1]  # dynamic expressions work too
```

### Dynamic field access

Use a variable as the key to access object fields:

```
row = { name: "alice", age: 25 }
field = "name"
row[field]    # "alice"
```

Useful when the field name is determined at runtime:

```
data |> map(it[field])
```

---

## Operators

```
+  -  *  /  %        # arithmetic
>  <  >=  <=  ==  != # comparison
|>                   # pipe
->                   # lambda
...                  # spread
lst[i]               # index
lst[a..b]            # slice (inclusive)
```

---

## Standard library

### Core — always available

| Function | Description |
|---|---|
| `load(path)` | Load CSV or JSON as list of rows |
| `save(path)` | Write list to CSV or JSON file |
| `filter(pred)` | Keep elements matching condition |
| `map(expr)` | Transform every element |
| `reduce(init, fn)` | Fold list into a single value |
| `add(field: expr)` | Add a new field to every row |
| `drop(field)` | Remove a field |
| `select(fields...)` | Keep only specified fields |
| `rename(old: new)` | Rename a field |
| `sort(by, dir)` | Sort rows |
| `take(n)` | Keep first n rows |
| `join(other, on)` | Inner join on a shared key field |
| `collapse(by:, ...)` | Aggregate rows, optionally grouped |
| `sum(col.field)` | Sum of a column — use in `collapse` or `add` |
| `mean(col.field)` | Mean of a column — use in `collapse` or `add` |
| `count()` | Row count — use in `collapse` |
| `min(col.field)` | Minimum — use in `collapse` or `add` |
| `max(col.field)` | Maximum — use in `collapse` or `add` |
| `rank(col.field, by:, dir:)` | Rank rows by a column — use in `add` |
| `rolling(col.field, window, fn, by:)` | Rolling window — use in `add` |
| `len(list)` | Number of elements |
| `get(list, i)` | Element at index (prefer `list[i]`) |
| `concat(a, b, ...)` | Concatenate lists |
| `print(value)` | Print and pass through |

### `use env`

| Function | Description |
|---|---|
| `env.get("KEY")` | Read environment variable — returns value or `Err` |

### `use math`

| Function | Description |
|---|---|
| `math.log(x)` | Natural log |
| `math.mean(list)` | Mean |
| `math.std(list)` | Standard deviation |
| `math.sqrt(x)` | Square root |
| `math.round(x)` | Round |

### `use ml`

All ml functions require `on:` (input column) and `out:` (output column) to be explicit.

| Function | Description |
|---|---|
| `ml.embed(on:, out:, source:, model:, apikey:)` | Text embedding — adds embedding column |
| `ml.kmeans(k:, on:, out:)` | K-means clustering — adds cluster column; `k:` accepts a range for auto-select |
| `ml.umap(dims:, on:, out:)` | Dimensionality reduction — `out: "umap"` adds `umap1`, `umap2`; `out: ["x","y"]` names explicitly |
| `ml.ols(on:, out:)` | OLS regression — adds predicted and residual columns; prints R² to stderr |
| `ml.silhouette(on:)` | Score current clustering — prints score to stderr |

### `use viz`

| Function | Description |
|---|---|
| `viz.scatter(x:, y:, color:, label:, display:)` | Scatter plot — `display:` list controls what's shown: `"axes"`, `"labels"`, `"legend"`, `"title"` |
| `viz.histogram(col:)` | Histogram |
| `viz.heatmap()` | Correlation heatmap |
| `viz.plot()` | Auto-plot based on data shape |
| `viz.grid(...)` | Multiple plots side by side |

### `use str`

| Function | Description |
|---|---|
| `str.trim(s)` | Strip whitespace |
| `str.lower(s)` | Lowercase |
| `str.upper(s)` | Uppercase |
| `str.replace(s, old, new)` | Replace substring |
| `str.split(s, sep)` | Split into list |
| `str.join(parts, sep)` | Join list into string |
| `str.contains(s, sub)` | True if substring present |
| `str.starts_with(s, prefix)` | True if starts with prefix |
| `str.ends_with(s, suffix)` | True if ends with suffix |
| `str.length(s)` | String length |
| `str.match(s, pattern)` | True if regex matches |
| `str.slice(s, start, end?)` | Substring by index |

---

## Aggregation

`collapse` reduces a list to a summary. Pass any combination of `sum`, `mean`, `count`, `min`, `max` with `col.field`:

```
load("sales.csv")
  |> collapse(total: sum(col.amount), avg: mean(col.amount), n: count())
  |> print()
```

Add `by:` to aggregate per group:

```
load("sales.csv")
  |> collapse(by: "region", total: sum(col.amount), n: count())
  |> sort(by: "total", dir: "desc")
  |> print()
```

### Broadcasting back onto rows

Use `mean`, `sum`, etc. inside `add` with `by:` to annotate each row with its group statistic:

```
load("employees.csv")
  |> add(dept_avg: mean(col.salary, by: "dept"))
  |> add(normalized: (it.salary - mean(col.salary, by: "dept")) / std(col.salary, by: "dept"))
```

### Rank within group

```
load("employees.csv")
  |> add(rank: rank(col.salary, by: "dept", dir: "desc"))
  |> filter(it.rank <= 2)
  |> drop(rank)
```

### Rolling window

```
load("sales.csv")
  |> sort(by: "date")
  |> add(rolling_avg: rolling(col.amount, 7, mean))
  |> add(rolling_avg_by_region: rolling(col.amount, 7, mean, by: "region"))
```

---

## Working with `none`

`none` is a first-class value. Filter it out explicitly:

```
|> filter(it.income != none)
```

Or use `match` to handle it per-row:

```
|> add(income: match(it.income, == none: 0, _: it.income))
```

---

## Joining datasets

```
people = load("people.csv")
scores = load("scores.csv")

people
  |> join(scores, on: "id")
  |> filter(it.score > 0.8)
  |> print()
```

`join` does an inner join — rows with no match in `other` are dropped.
