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

Comments start with `#`. Assignments are immutable — you can't rebind a name once set.

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

Pipes are railway-oriented — if any step fails, all downstream steps are skipped and the error propagates to the end. Each step prints a summary automatically:

```
|> filter    → List  843 rows × 8 cols  (157 dropped)
|> add       → List  843 rows × 9 cols  (+score)
```

Suppress with `quiet`:

```
|> filter(it.age > 18) quiet
```

---

## Context

Every table pipe produces a **Context** — a value that carries data, artifacts, and errors together. You access them by dotting into the named result:

```
posts = load("data.csv")
  |> filter(it.age > 18)
  |> ml.kmeans(k: 3, on: "embedding", out: "cluster")

posts.data      # the rows — list of dicts
posts.errors    # rows that failed any step
posts.kmeans    # artifacts written by ml.kmeans: { model, k }
```

`.data` and `.errors` are always available. Artifact fields (`.kmeans`, `.umap`, `.viz`) are set by specific steps.

Passing a Context into another pipe starts fresh — artifacts don't carry over:

```
posts.data |> filter(it.cluster == 0) |> print()
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

`col.field` refers to a field across all rows. Used in aggregation and column-level functions:

```
|> collapse(avg: mean(col.salary))
|> add(dept_avg: mean(col.salary, by: "dept"))
|> add(rank: rank(col.salary, dir: "desc"))
```

`col` is a reference, not a computation. Functions (`mean`, `rank`, `rolling`) act on it.

---

## String interpolation

Strings support `{expr}` interpolation. The expression is evaluated in the current scope — `it` is available inside pipe steps:

```
name = "alice"
age = 30
print("{name} is {age} years old")

load("data.csv")
  |> add(label: "{it.name} ({it.region})")
  |> add(summary: "age {it.age}, score {it.score}")
```

Any expression works inside `{}`:

```
print("in 10 years: {age + 10}")
print("items: {len(xs)}")
```

---

## `match`

The only branching construct. Always returns a value:

```
match(it.income,
  > 50000: "high",
  > 20000: "medium",
  _:       "low"
)
```

Patterns: `>`, `<`, `>=`, `<=`, `==`, `!=`, `_` (wildcard). Bare literals match by equality:

```
match(n, 0: "zero", 1: "one", _: "many")
```

Use inside a pipe step:

```
|> add(tier: match(it.income, > 80000: "high", _: "low"))
```

---

## Functions

Functions are assignments with `->`:

```
double = x -> x * 2

clean = data -> (
  data
    |> filter(it.age > 18)
    |> filter(it.income > 0)
)
```

Parentheses let the body span multiple lines. Assignments inside `( )` are local — they don't leak to outer scope. The last expression is the return value.

Functions can call themselves recursively:

```
fact = n -> match(n, 0: 1, _: n * fact(n - 1))
```

### Curried functions

```
add = x -> y -> x + y
add(1)(2)    # 3

mul = x -> y -> x * y
double = mul(2)
double(5)    # 10
```

---

## Result and error handling

Every pipe returns `Ok(value)` or `Err(message)`. Handle with `match`:

```
result = load("data.csv")
  |> filter(it.age > 18)

match(result,
  Ok(data): print(data),
  Err(msg):  print(msg)
)
```

Any exception inside a pipe step becomes `Err` — the pipe never crashes mid-run.

---

## Namespaces

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

Import stdlib or external files with `use`:

```
use ml
use math
use viz
use env
use "./transforms.pep" as t
use "./my_utils.py" as u
```

Python files are loaded via the bridge. Every public function is wrapped automatically — no decorators needed. Functions receive plain Python values, return values are converted back, exceptions become `Err`.

---

## Environment variables

```
use env

key = env.OPENAI_API_KEY    # errors if not set
val = env.get("KEY")        # returns Err if not set (safe for optional vars)
```

`env.KEY` is the preferred form for static keys. `env.get("KEY")` is useful when the key name is computed at runtime.

---

## Collections

```
[1, 2, 3]                          # list
{ name: "alice", age: 25 }         # object
{ ...existing, score: 42 }         # object spread
{ name, age }                      # shorthand — same as { name: name, age: age }
1..10                              # range
```

A list of objects becomes a table — the same type returned by `load()`:

```
[{ name: "alice", age: 25 }, { name: "bob", age: 17 }]
  |> filter(it.age >= 18)
  |> print()
```

### Indexing and slicing

```
lst[0]          # element at index
lst[1..3]       # slice from 1 to 3 (inclusive)
```

### Cross-table lookup

`find(table, col, value)` returns the first row where `col` equals `value`. Returns `none` if not found:

```
stats = load("cluster_stats.csv")

load("data.csv")
  |> add(cluster_n: find(stats, "cluster", it.cluster).n)
```

`list[i]` is always positional index -- `rows[0]` is the first row.

### Dynamic field access

```
row = { name: "alice", age: 25 }
field = "name"
row[field]    # "alice"

data |> map(it[field])
```

---

## Operators

```
+  -  *  /  %        # arithmetic
>  <  >=  <=  ==  != # comparison
and  or  not         # boolean
|>                   # pipe
->                   # lambda
...                  # spread
lst[i]               # index / keyed lookup
lst[a..b]            # slice (inclusive)
```

---

## Aggregation

`collapse` reduces a table to a summary:

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
```

### Custom aggregation with a lambda

Pass a lambda to `collapse` for custom per-group logic:

```
load("data.csv")
  |> collapse(by: "region",
      n:          count(),
      top_earner: rows -> rows |> sort(by: "income", dir: "desc") |> take(1)
  )
```

### Broadcasting back onto rows

Use `mean`, `sum`, etc. inside `add` with `by:` to annotate each row with its group statistic:

```
load("employees.csv")
  |> add(dept_avg: mean(col.salary, by: "dept"))
  |> add(above_avg: it.salary > mean(col.salary, by: "dept"))
```

### Rank within group

```
load("employees.csv")
  |> add(rank: rank(col.salary, by: "dept", dir: "desc"))
  |> filter(it.rank <= 2)
  |> drop("rank")
```

### `each` — sub-pipe per group

Run an arbitrary pipe on each group. Two equivalent forms:

```
# Block form
load("data.csv")
  |> each(by: "region",
      |> filter(it.score > 0)
      |> add(rank: rank(col.score))
      |> take(10)
  )

# Lambda form
load("data.csv")
  |> each(by: "region", grp -> grp |> filter(it.score > 0) |> take(10))
```

If the sub-pipe produces a table, `each` concatenates results across groups. If it's a side effect (`print`, `viz`), `each` returns the original table unchanged.

### Rolling window

```
load("sales.csv")
  |> sort(by: "date")
  |> add(rolling_avg: rolling(col.amount, 7, mean))
  |> add(rolling_by_region: rolling(col.amount, 7, mean, by: "region"))
```

---

## Cross-table enrichment

Use `find(table, col, value)` for single-row lookups:

```
labels = load("cluster_labels.csv")
load("data.csv")
  |> add(label: find(labels, "cluster", it.cluster).title)
```

For full inner joins:

```
people |> join(scores, on: "id")
```

---

## Annotations

Annotations attach execution behavior to a pipe step or declaration without changing its logic.

### `@concurrent(n)`

Run the step over each row in a thread pool with `n` workers. Preserves row order:

```
load("posts.csv")
  |> add(embedding: ml.embed(it.text, source: "deepinfra", model: "..."))
      @concurrent(50)
```

On a declaration, applies every time it's used in a pipe:

```
use env
gpt = ml.llm("classify: {it.title}", source: "openai", model: "gpt-4o", apikey: env.OPENAI_API_KEY)
  @concurrent(10)

load("posts.csv")
  |> add(label: gpt)
```

### `@retry(n)`

Retry the step up to `n` times on exception before writing `none`:

```
|> add(label: ml.llm(...))
    @retry(3)
```

### `@until(cond, max: n)`

Retry the step (or block) on rows where `cond` is false, up to `max` rounds. Rows that pass are frozen; rows still failing after `max` rounds go to `.errors`:

```
# Single step
|> add(label: ml.llm(...))
    @until(it.label != none, max: 5)

# Multi-step block
(
  |> add(label: ml.llm(...))
  |> add(label: match(it.label, == none: none, _: it.label))
) @until(it.label != none, max: 5)
```

Combine with `@retry`:

```
|> add(label: ml.llm(...))
    @retry(3)
    @until(it.label != none, max: 5)
```

---

## Caching

Pass `--cache` to enable step caching. Results are stored in `.peppermint/cache/` next to the `.pep` file. On rerun, unchanged steps are skipped:

```
pep pipeline.pep --cache
```

`ml.embed` and `ml.llm` use row-level caching — each row's result is cached independently, so adding new rows only processes the new ones.

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

## Standard library

See [stdlib.md](stdlib.md) for the full reference — core functions, `math`, `ml`, `viz`, `text`, and `env`.

See [error.md](error.md) for how errors are handled at both the pipe and row level.

See [cache.md](cache.md) for step and row caching.
