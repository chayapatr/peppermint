# Peppermint Language Reference (LLM Guide)

Peppermint is a pipe-first DSL for data and ML work, running on Python. This document is a complete, self-contained reference for generating correct Peppermint code.

---

## Core syntax

```
x = 42
name = "alice"
flag = true
nothing = none
```

Comments start with `#`. Assignments are immutable — names cannot be rebound.

String interpolation with `{expr}`:

```
label = "{it.name} ({it.region})"
print("age {it.age}, score {it.score}")
print("in 10 years: {age + 10}")
```

---

## Pipes

Data flows left to right through `|>`. Every pipe step prints a live summary automatically.

```
load("data.csv")
  |> filter(it.age > 18)
  |> add(score: it.income / it.age)
  |> sort(by: "score", dir: "desc")
  |> print()
```

A pipe always produces a `Context` — a value carrying `.data`, `.errors`, and any artifacts written by ML steps. Assign the result to access these fields:

```
posts = load("data.csv") |> ml.kmeans(k: 3, on: "embedding", out: "cluster")

posts.data      # the rows (list of dicts)
posts.errors    # rows that failed any step
posts.kmeans    # { model, k } — written by ml.kmeans
posts.umap      # { model }   — written by ml.umap
posts.viz       # { plot }    — written by viz.*
```

To pipe data back out of a Context:

```
posts.data |> filter(it.cluster == 0) |> print()
```

Suppress per-step output:

```
|> filter(it.age > 18) quiet
```

---

## `it` and `col`

`it` is the current row inside a pipe step:

```
|> filter(it.age > 18)
|> add(ratio: it.income / it.age)
```

`col.field` is a column reference across all rows — used inside aggregation functions and `collapse`. It names a column but does not compute anything on its own:

```
|> collapse(avg: mean(col.salary))
|> add(dept_avg: mean(col.salary, by: "dept"))
|> add(rank: rank(col.salary, dir: "desc"))
```

---

## `match`

The only branching construct. Always returns a value. Arms are checked in order:

```
match(it.income,
  > 50000: "high",
  > 20000: "medium",
  _:       "low"
)
```

Patterns: `>`, `<`, `>=`, `<=`, `==`, `!=`, bare literal (shorthand for `==`), `_` (wildcard):

```
match(n, 0: "zero", 1: "one", _: "many")
match(it.label, == none: "missing", _: it.label)
```

Handle `Result`:

```
match(result,
  Ok(data): data |> print(),
  Err(msg):  print(msg)
)
```

---

## Functions

```
double = x -> x * 2

clean = data -> (
  data
    |> filter(it.age > 18)
    |> filter(it.income > 0)
)
```

`( )` creates a local scope — assignments inside don't leak out. The last expression is the return value. Semicolons work as separators inside `( )`.

Recursive:

```
fact = n -> match(n, 0: 1, _: n * fact(n - 1))
```

Curried:

```
add = x -> y -> x + y
add(1)(2)   # 3
mul = x -> y -> x * y
double = mul(2)
```

---

## Collections

```
[1, 2, 3]                          # list
{ name: "alice", age: 25 }         # object
{ ...existing, score: 42 }         # spread
{ name, age }                      # shorthand: { name: name, age: age }
1..10                              # range
```

A list of objects is a table — same type as `load()`:

```
[{ name: "alice", age: 25 }, { name: "bob", age: 17 }]
  |> filter(it.age >= 18)
```

Indexing and slicing:

```
lst[0]       # element at index
lst[1..3]    # slice, inclusive end
```

Dynamic field access:

```
field = "name"
row[field]   # "alice"
data |> map(it[field])
```

Cross-table lookup:

```
stats = load("cluster_stats.csv")
load("data.csv")
  |> add(cluster_n: find(stats, "cluster", it.cluster).n)
```

`find(table, col, value)` returns the first row where `col == value`, or `none` if not found. `list[i]` is always positional index.

---

## Operators

```
+  -  *  /  %        # arithmetic
>  <  >=  <=  ==  != # comparison
and  or  not         # boolean
|>                   # pipe
->                   # lambda
...                  # spread
lst[i]               # index
lst[a..b]            # slice
```

---

## Namespaces

```
ns transforms {
  clean = data -> data |> filter(it.age > 18)
}

load("data.csv") |> transforms.clean() |> print()
```

Import stdlib or external files:

```
use ml
use math
use viz
use env
use text
use "./transforms.pep" as t
use "./my_utils.py" as u
```

Python files are bridged automatically — every public function is wrapped, arguments are converted, exceptions become `Err`.

---

## Environment variables

```
use env

key = env.OPENAI_API_KEY    # errors if not set (preferred)
val = env.get("KEY")        # returns Err if not set
```

---

## Core functions

| Function                         | Description                                        |
| -------------------------------- | -------------------------------------------------- |
| `load(path)`                     | Load CSV or JSON as a Context                      |
| `save(data, path)`               | Write rows to CSV or JSON — pass-through           |
| `filter(pred)`                   | Keep rows matching condition                       |
| `map(expr)`                      | Transform every element                            |
| `mapi(expr)`                     | Map with index — `it` is `{ idx, val }`            |
| `reduce(init, fn)`               | Fold list into a single value                      |
| `add(field: expr, ...)`          | Add one or more fields to every row                |
| `drop("a", "b")`                 | Remove fields                                      |
| `select("a", b: expr)`           | Keep fields; keyword args compute or rename inline |
| `rename(old: new)`               | Rename a field                                     |
| `sort(by, dir?)`                 | Sort rows — `dir:` `"asc"` or `"desc"`             |
| `take(n)`                        | Keep first n rows                                  |
| `unique(by?)`                    | Deduplicate                                        |
| `each(by:, \|> ...)`             | Sub-pipe per group, concatenate results            |
| `collapse(by:, ...)`             | Aggregate rows, optionally grouped                 |
| `join(other, on)`                | Inner join on shared key                           |
| `recover(field: expr)`           | Move error rows back into data with fallback       |
| `find(table, col, value)`        | First row where col == value, or none              |
| `len(list)`                      | Number of elements                                 |
| `concat(a, b, ...)`              | Concatenate lists                                  |
| `slice(list, start, end)`        | Slice (inclusive end)                              |
| `get(list, i)`                   | Element at index                                   |
| `print(value)`                   | Print and pass through                             |
| `halt(message?)`                 | Stop with exit code 1                              |
| `str(v)` / `int(v)` / `float(v)` | Type cast — `int` returns `none` for NaN           |

---

## Aggregation

```
load("sales.csv")
  |> collapse(by: "region",
      total: sum(col.amount),
      avg:   mean(col.amount),
      n:     count()
  )
```

Omit `by:` for a single-row summary. Agg functions: `sum`, `mean`, `count`, `min`, `max`.

Custom per-group logic with a lambda:

```
|> collapse(by: "region",
    top: rows -> rows |> sort(by: "income", dir: "desc") |> take(1)
)
```

Broadcast group stats back onto rows using `by:` inside `add`:

```
|> add(dept_avg:   mean(col.salary, by: "dept"))
|> add(above_avg:  it.salary > mean(col.salary, by: "dept"))
|> add(rank:       rank(col.salary, by: "dept", dir: "desc"))
|> add(rolling_7:  rolling(col.amount, 7, mean))
```

### `each` — sub-pipe per group

```
load("data.csv")
  |> each(by: "region",
      |> filter(it.score > 0)
      |> add(rank: rank(col.score))
      |> take(10)
  )
```

Lambda form:

```
|> each(by: "region", grp -> grp |> filter(it.score > 0) |> take(10))
```

If the sub-pipe produces a table, results are concatenated. If it's a side effect, the original table is returned unchanged.

---

## Annotations

Annotations attach execution behavior to a step without changing its logic. They follow the step on the next line:

```
|> add(label: ml.llm(...))
    @concurrent(10)
    @retry(3)
    @until(it.label != none, max: 5)
    @cache
```

| Annotation             | Description                                                                    |
| ---------------------- | ------------------------------------------------------------------------------ |
| `@concurrent(n)`       | Run over each row using n threads, preserving order                            |
| `@retry(n)`            | Retry the step on exception up to n times                                      |
| `@until(cond, max: n)` | Retry rows where cond is false, up to max rounds; failing rows go to `.errors` |
| `@cache`               | Cache this step's result across runs                                           |

Annotations on a declaration apply every time it's used in a pipe:

```
gpt = ml.llm("classify: {it.title}", source: "openai", model: "gpt-4o", apikey: env.OPENAI_API_KEY)
  @concurrent(10)
  @retry(3)
  @cache
```

`@until` can wrap a multi-step block:

```
(
  |> add(label: ml.llm(...))
  |> add(label: match(it.label, == none: none, _: it.label))
) @until(it.label != none, max: 5)
```

---

## Error handling

### Whole-pipe errors

If a pipe step fails completely, it becomes `Err` and all downstream steps are skipped:

```
result = load("data.csv") |> filter(it.age > 18)

match(result,
  Ok(data): data |> print(),
  Err(msg):  print(msg)
)
```

### Row-level errors

When `add(field: expr)` fails on a row, that row moves to `.errors`. The rest continue. Error rows carry `_error` (message) and `_step` (which step failed).

`recover(field: fallback)` pulls rows from `.errors` back into `.data`:

```
|> add(label: ml.llm(...))
|> recover(label: "unknown")         # literal fallback
|> recover(label: it.title)          # expression using error row
```

Inspect and save errors:

```
result.errors |> print()
save(result.errors, "data/failed.csv")
save(concat(a.errors, b.errors), "data/all_failed.csv")
```

### Enforcement pattern

Use `halt` to abort if any rows failed:

```
match(len(result.errors),
  == 0: result.data |> save("output.csv"),
  _:    halt("rerun to retry {len(result.errors)} failed rows")
)
```

---

## Caching

Add `@cache` to any step to persist its result across runs. Steps without `@cache` always recompute.

```
load("data.csv")
  |> ml.kmeans(k: 5..12, on: "embedding", out: "cluster")
      @cache
  |> add(label: ml.llm(it.text, source: "openai", model: "gpt-4o", apikey: env.OPENAI_API_KEY, format: "json"))
      @concurrent(10)
      @retry(3)
      @until(it.label != none, max: 5)
      @cache
```

- **Whole-dataframe steps** (`ml.kmeans`, `ml.umap`): caches full output by input fingerprint
- **Per-row steps** (`ml.llm`, `ml.embed`): caches each row independently by content hash; failed rows are never cached and are retried on the next run

Cache directory defaults to `.peppermint/` next to the `.pep` file. Override with frontmatter:

```
---
cache_dir: ".cache"
---
```

---

## ML library

`pip install peppermint-lang[ml]`

```
use ml
use env
```

| Function                                                            | Description                                                               |
| ------------------------------------------------------------------- | ------------------------------------------------------------------------- |
| `ml.embed(text, source:, model:, apikey?)`                          | Embed a string — use inside `add` with `@concurrent`                      |
| `ml.llm(prompt, source:, model:, apikey?, format?)`                 | Single LLM call — use inside `add`; `source:` `"openai"`, `"anthropic"`, or `"deepinfra"`; `format: "json"` parses response |
| `ml.kmeans(k:, on:, out:, method?, model?)`                         | K-means — `k:` accepts a range for auto-select; writes `.kmeans` artifact |
| `ml.umap(dims:, on:, out:, neighbors?, min_dist?, metric?, model?)` | UMAP — writes `.umap` artifact                                            |
| `ml.ols(on:, out:, model?)`                                         | OLS regression — writes `.ols` artifact                                   |
| `ml.dist(a, b, metric?)`                                            | Distance between two vectors — use inside `add`                           |
| `ml.silhouette(on:)`                                                | Print silhouette score — pass-through                                     |

---

## Full examples

### Basic pipeline

```
load("employees.csv")
  |> filter(it.age > 18)
  |> add(tax: it.salary * 0.2)
  |> sort(by: "salary", dir: "desc")
  |> print()
```

### Aggregate

```
load("sales.csv")
  |> collapse(by: "region",
      avg: mean(col.revenue),
      n:   count()
  )
  |> sort(by: "avg", dir: "desc")
  |> print()
```

### Top N per group

```
load("sales.csv")
  |> each(by: "region",
      |> add(rank: rank(col.revenue, dir: "desc"))
      |> filter(it.rank <= 3)
      |> drop("rank")
  )
```

### Embedding + clustering + visualization

```
use ml
use viz
use env

load("data.csv")
  |> add(embedding: ml.embed(it.text,
      source: "deepinfra", model: "Qwen/Qwen3-Embedding-4B",
      apikey: env.DEEPINFRA_TOKEN))
      @concurrent(50)
      @cache
  |> ml.kmeans(k: 2..8, on: "embedding", out: "cluster")
      @cache
  |> ml.umap(dims: 2, on: "embedding", out: "umap")
      @cache
  |> viz.scatter(x: "umap_1", y: "umap_2", color: "cluster",
      display: { label: "text", legend })
```

### LLM enrichment with retry, caching, and enforcement

```
use ml
use env

result = load("posts.csv")
  |> add(label: ml.llm(it.text,
      source: "openai", model: "gpt-4o",
      apikey: env.OPENAI_API_KEY, format: "json"))
      @concurrent(10)
      @retry(3)
      @until(it.label != none, max: 5)
      @cache

match(len(result.errors),
  == 0: result.data |> save("output.csv"),
  _:    halt("rerun to retry {len(result.errors)} failed rows")
)
```

### Hierarchical clustering

```
use ml
use env

gpt = ml.llm("describe this cluster in 5 words: {it.text}", source: "openai", model: "gpt-4o", apikey: env.OPENAI_API_KEY, format: "json")
  @concurrent(10)
  @retry(3)

result = load("data.csv")
  |> ml.kmeans(k: 5..12, on: "embedding", out: "cluster")
      @cache

centroids = result.data
  |> collapse(by: "cluster", centroid: mean(col.embedding))

result.data
  |> each(by: "cluster",
      |> ml.kmeans(k: 2..6, on: "embedding", out: "sub_cluster")
          @cache
      |> add(description: gpt)
          @until(it.description != none, max: 5)
          @cache
  )
  |> add(label: find(centroids, "cluster", it.cluster).centroid)
```

### Python bridge

```
use "./transforms.py" as t

load("data.csv")
  |> t.clean()
  |> print()
```

```python
# transforms.py
def clean(rows):
    return [r for r in rows if r["score"] is not None]
```

---

## Common patterns

**Add a field from a match:**

```
|> add(tier: match(it.income, > 80000: "high", > 40000: "mid", _: "low"))
```

**Handle `none` per-row:**

```
|> add(income: match(it.income, == none: 0, _: it.income))
|> filter(it.income != none)
```

**Group broadcast — annotate each row with its group stat:**

```
|> add(dept_avg: mean(col.salary, by: "dept"))
|> filter(it.salary > it.dept_avg)
```

**Cross-table enrich:**

```
labels = load("labels.csv")
load("data.csv")
  |> add(label: find(labels, "cluster", it.cluster).title)
```

**Recover with fallback after LLM step:**

```
|> add(label: ml.llm(...))
    @retry(3)
    @until(it.label != none, max: 5)
|> recover(label: "unknown")
```

**Save errors for inspection:**

```
save(result.errors, "data/failed.csv")
```

**Enforce no errors before writing output:**

```
match(len(result.errors),
  == 0: result.data |> save("output.csv"),
  _:    halt("{len(result.errors)} rows failed — rerun to retry")
)
```
