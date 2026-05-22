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

Functions are just assignments with `=>`:

```
double = x => x * 2

clean = data => (
  data
    |> filter(it.age > 18)
    |> filter(it.income > 0)
)
```

Parentheses let the body span multiple lines — newlines inside `( )` are ignored.

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
  clean = data => (
    data
      |> filter(it.age > 18)
      |> filter(it.income > 0)
  )
}

load("data.csv")
  |> transforms.clean()
  |> print()
```

Import external files or stdlib namespaces with `use`:

```
use ml
use "./transforms" as t
```

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
+  -  *  /          # arithmetic
>  <  >=  <=  ==  != # comparison
|>                   # pipe
=>                   # lambda
...                  # spread
```

---

## Standard library

| Function | Description |
|---|---|
| `load(path)` | Load CSV as list of rows |
| `filter(pred)` | Keep rows matching condition |
| `map(expr)` | Transform every row |
| `add(field: expr)` | Add a new field to every row |
| `drop(field)` | Remove a field |
| `sort(by, dir)` | Sort rows |
| `print(value)` | Print and pass through |
| `math.log(x)` | Natural log |
| `math.mean(list)` | Mean |
| `math.std(list)` | Standard deviation |
| `math.sqrt(x)` | Square root |
| `math.round(x)` | Round |
