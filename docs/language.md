# Peppermint

A pipe-first language for data work. Run files with `pep run file.pep`.

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

## match

The only branching construct. Always returns a value:

```
match(it.income,
  > 50000: "high",
  > 20000: "medium",
  _:       "low"
)
```

Patterns: `>`, `<`, `>=`, `<=`, `==`, `!=`, `_` (wildcard).

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

Parentheses let the body span multiple lines — newlines inside `( )` are ignored. Semicolons work as statement separators inside `( )`:

```
f = x -> (print(x); f(x - 1))
```

Functions can call themselves recursively:

```
fact = n -> match(n, == 0: 1, _: n * fact(n - 1))
```

Call them like any built-in:

```
load("data.csv")
  |> clean()
  |> print()
```

---

## Result and error handling

Every pipe returns `Ok(value)` or `Err(message)`. If a step fails, the rest of the pipe is skipped automatically.

Handle at the end with `match`:

```
result = load("data.csv")
  |> filter(it.age > 18)

match(result,
  Ok(data): print(data),
  Err(msg):  print(msg)
)
```

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
(1, "hello", true)                 # tuple
1..10                              # range
```

---

## Operators

```
+  -  *  /  %        # arithmetic
>  <  >=  <=  ==  != # comparison
|>                   # pipe
->                   # lambda
...                  # spread
```

---

## Standard library

### Core — always available

| Function | Description |
|---|---|
| `load(path)` | Load CSV or JSON as list of rows |
| `filter(pred)` | Keep elements matching condition — any list |
| `map(expr)` | Transform every element — any list |
| `reduce(init, fn)` | Fold list into a single value |
| `add(field: expr)` | Add a new field to every row |
| `drop(field)` | Remove a field |
| `select(fields...)` | Keep only specified fields |
| `rename(old: new)` | Rename a field |
| `sort(by, dir)` | Sort rows |
| `join(other, on)` | Join two lists on a key |
| `group(by) { }` | Group by field, run sub-pipe per group |
| `print(value)` | Print and pass through |

### `use math`

| Function | Description |
|---|---|
| `math.log(x)` | Natural log |
| `math.mean(list)` | Mean |
| `math.std(list)` | Standard deviation |
| `math.sqrt(x)` | Square root |
| `math.round(x)` | Round |

### `use ml`

| Function | Description |
|---|---|
| `ml.kmeans(k)` | K-means clustering — adds `cluster` field |
| `ml.umap(dims)` | Dimensionality reduction — adds `umap1`, `umap2`, ... |
| `ml.ols(target)` | Linear regression — adds `predicted` field |
| `ml.embed(col)` | Text embedding — adds `embedding` field |
| `ml.silhouette()` | Score current clustering |

### `use viz`

| Function | Description |
|---|---|
| `viz.scatter(x, y, color?)` | Scatter plot |
| `viz.histogram(col)` | Histogram |
| `viz.heatmap()` | Correlation heatmap |
| `viz.plot()` | Auto-plot based on data shape |
| `viz.grid(...)` | Multiple plots side by side |
