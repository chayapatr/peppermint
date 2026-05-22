# Peppermint Type System

## Value Types

```
Type = Scalar
     | List<Type>
     | Object<{ label: Type, ... }>
     | Tuple<Type...>
     | Result<Type>
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

Monadic bind. Each step receives the unwrapped value from the previous step and returns a new `Result`:

```
bind(Ok(a),  f) = f(a)     -- unwrap and continue
bind(Err(e), f) = Err(e)   -- skip, propagate error
```

A pipeline is a chain of binds:

```
load("data.csv")        -- Result<List<Object>>
  |> filter(it.age > 18)  -- Result<List<Object>>
  |> add(score: ...)       -- Result<List<Object>>
```

If any step returns `Err`, all downstream steps are skipped automatically.

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

## match

```
match : a → (Pattern<a> → b)... → b
```

Evaluates the subject against each arm in order, returns the first match. Always an expression — never a statement. All arms must return the same type.

Patterns:

```
> n   < n   >= n   <= n   == n   != n    -- comparison (Scalar)
Ok(x)   Err(x)                           -- Result destructure
(p, p, ...)                              -- Tuple destructure
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
fact = n -> match(n, == 0: 1, _: n * fact(n - 1))
```

### Sequencing

Inside `( )`, `;` or newlines separate multiple expressions. The last one is returned:

```
f = x -> (print(x); f(x - 1))
```

Type:
```
Block : Expr... → a    -- evaluates each, returns last
```

---

## Type Classes

### Functor

```
map : List<a> → (a → b) → List<b>
```

Output type follows the return value of the transform — `Object` in gives `List<Object>` out, `Scalar` in gives `List<Scalar>` out.

### Filterable

```
filter : List<a> → (a → Bool) → List<a>
```

Works on any list. Preserves element type.

### Foldable

```
reduce : List<a> → b → ((b, a) → b) → b
```

`fn` takes two explicit args — accumulator first, current element second.

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
group  : List<Object<S>> → by → (List<Object<S>> → List<Object<T>>) → List<Object<T>>
```

Passing a non-object list to these raises a type error.

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

Every pipe step returns a `Result`. Handle with `match`:

```
match(result,
  Ok(data): data |> print(),
  Err(msg): print(msg)
)
```

---

## ML Functions

Operate on `List<Object<S>>`, add columns, return `List<Object<S'>>`:

```
ml.embed(col)  : List<Object<S>> → List<Object<S ∪ {embedding: List<Float>}>>
ml.kmeans(k)   : List<Object<S>> → List<Object<S ∪ {cluster: Int}>>
ml.umap(dims)  : List<Object<S>> → List<Object<S ∪ {umap1: Float, umap2: Float, ...}>>
```
