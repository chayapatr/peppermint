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

See [stdlib.md](stdlib.md) for the full reference — core functions, `math`, `ml`, `viz`, `str`, and `env`.

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
  |> drop("rank")
```

### `each` — arbitrary pipe per group

For cases where `by:` on a column function isn't enough — side effects per group, or complex multi-step transforms per partition:

```
load("sales.csv")
  |> each(by: "region", |> viz.scatter(x: "date", y: "amount"))
```

Multi-step sub-pipe:

```
load("data.csv")
  |> each(by: "cohort",
      |> filter(it.score > 0)
      |> add(rank: rank(col.score))
      |> take(10)
  )
```

If the sub-pipe produces a table, `each` concatenates results across groups and the pipe continues. If it's a pure side effect (`save`, `viz`, `print`), `each` returns the original table unchanged. The group key is always present in the result.

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
