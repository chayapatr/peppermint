# Standard Library

## Core — always available

| Function | Description |
|---|---|
| `load(path)` | Load CSV or JSON as list of rows |
| `save(path)` | Write list to CSV or JSON file |
| `filter(pred)` | Keep elements matching condition |
| `map(expr, concurrent?)` | Transform every element |
| `mapi(expr, concurrent?)` | Map with index — `it` is `{ idx, val }` |
| `reduce(init, fn)` | Fold list into a single value |
| `add(field: expr, concurrent?)` | Add a new field to every row |
| `drop(field)` | Remove a field |
| `select(fields...)` | Keep only specified fields |
| `rename(old: new)` | Rename a field |
| `sort(by, dir)` | Sort rows |
| `take(n)` | Keep first n rows |
| `join(other, on)` | Inner join on a shared key field |
| `each(by:, \|> ...)` | Run a sub-pipe per group, concatenate results |
| `collapse(by:, ...)` | Aggregate rows, optionally grouped. Values can be agg fns (`mean`, `count`, etc.) or a lambda receiving the group as a list |
| `sum(col.field)` | Sum of a column — use in `collapse` or `add`. Handles vector (list) columns element-wise |
| `mean(col.field)` | Mean of a column — use in `collapse` or `add`. Handles vector (list) columns element-wise |
| `count()` | Row count — use in `collapse` |
| `min(col.field)` | Minimum — use in `collapse` or `add`. Handles vector (list) columns element-wise |
| `max(col.field)` | Maximum — use in `collapse` or `add`. Handles vector (list) columns element-wise |
| `rank(col.field, by:, dir:)` | Rank rows by a column — use in `add` |
| `rolling(col.field, window, fn, by:)` | Rolling window — use in `add` |
| `len(list)` | Number of elements |
| `concat(a, b, ...)` | Concatenate lists |
| `print(value)` | Print and pass through |
| `str(value)` | Convert to string |
| `int(value)` | Convert to integer |
| `float(value)` | Convert to float |

`concurrent: N` runs the expression in a thread pool with N workers. Useful for I/O-bound expressions like `ml.embed`.

---

## `use env`

| Function | Description |
|---|---|
| `env.get("KEY")` | Read environment variable — returns value or `Err` |

---

## `use math`

| Function | Description |
|---|---|
| `math.log(x)` | Natural log |
| `math.sqrt(x)` | Square root |
| `math.pow(x, exp)` | x raised to exp |
| `math.abs(x)` | Absolute value |
| `math.round(x)` | Round to nearest integer |
| `math.floor(x)` | Floor |
| `math.ceil(x)` | Ceiling |
| `math.clamp(x, lo, hi)` | Clamp x to [lo, hi] |
| `math.mean(list)` | Mean of a list |
| `math.median(list)` | Median of a list |
| `math.std(list)` | Standard deviation |
| `math.min(list)` | Minimum of a list |
| `math.max(list)` | Maximum of a list |
| `math.sum(list)` | Sum of a list |

---

## `use ml`

`pip install peppermint-lang[ml]`

| Function | Description |
|---|---|
| `ml.embed(text, source:, model:, apikey?)` | Embed a single string — use inside `add` with `concurrent: N, retry: N` for batch API calls |
| `ml.llm(prompt, source:, model:, apikey?)` | Single LLM call — use inside `add`. Returns a string |
| `ml.kmeans(k:, on:, out:, model?)` | K-means clustering; `k:` accepts a range for auto-select by silhouette score; `model:` loads if file exists, else fits and saves |
| `ml.umap(dims:, on:, out:, neighbors?, min_dist?, metric?, model?)` | Dimensionality reduction — `neighbors` (default 15), `min_dist` (default 0.1), `metric` (default "euclidean"); `model:` caches fit |
| `ml.ols(on:, out:, model?)` | OLS regression — adds predicted and residual columns; prints R² to stderr |
| `ml.dist(a, b, metric?)` | Distance between two vectors — use inside `add`; `metric:` `"cosine"` (default) or `"euclidean"` |
| `ml.silhouette(on:)` | Score current clustering — prints silhouette score to stderr |

---

## `use viz`

`pip install peppermint-lang[viz]`

| Function | Description |
|---|---|
| `viz.scatter(x:, y:, color?, size?, file?, display?)` | Scatter plot — `size: [w, h]` sets figure size; `file: "path.png"` saves image; `display: { label: "col", legend, axes, title: "...", dotsize: N \| "col" }` |
| `viz.histogram(col:, file?)` | Histogram — `file:` saves image |
| `viz.heatmap(file?)` | Correlation heatmap of all numeric columns |
| `viz.plot(file?)` | Auto-plot based on data shape |
| `viz.grid(..., file?)` | Multiple plots side by side |

---

## `use text`

| Function | Description |
|---|---|
| `text.parse(s)` | Parse a JSON string — useful for embedding columns loaded from CSV |
| `text.trim(s)` | Strip whitespace |
| `text.lower(s)` | Lowercase |
| `text.upper(s)` | Uppercase |
| `text.replace(s, old, new)` | Replace substring |
| `text.split(s, sep)` | Split into list |
| `text.join(parts, sep)` | Join list into string |
| `text.contains(s, sub)` | True if substring present |
| `text.starts_with(s, prefix)` | True if starts with prefix |
| `text.ends_with(s, suffix)` | True if ends with suffix |
| `text.length(s)` | String length |
| `text.match(s, pattern)` | True if regex matches |
| `text.slice(s, start, end?)` | Substring by index |

---

## Writing Python libs

Plain Python files work out of the box — just import them and Peppermint wraps the public functions automatically. For more control, use the `peppermint.bridge` decorators.

### Simple case — no decorators needed

```python
# mylib.py
def normalize(rows):
    total = sum(r["value"] for r in rows)
    return [{**r, "pct": r["value"] / total} for r in rows]
```

```
use "./mylib.py" as mylib
load("data.csv") |> mylib.normalize() |> print()
```

Functions receive plain Python values (`list[dict]`, `str`, `int`, etc.) and return plain Python. Exceptions become `Err` automatically.

### Using decorators

Decorators give you hover tooltips in the LSP and handle lazy kwargs (expressions that haven't been evaluated yet when the function is called, like ranges or `env.get(...)`).

```python
from peppermint.bridge import pep_fn
from peppermint.stdlib.core import pep_signature

@pep_fn
@pep_signature("mylib.top(data, n: Int) -> List<Row>")
def top(data, n=10):
    """Return the top n rows by the first numeric column."""
    return sorted(data, key=lambda r: list(r.values())[0], reverse=True)[:n]

def build_mylib_env():
    return {"top": top}
```

`build_mylib_env()` is optional but required if you want Peppermint to discover the lib via `use mylib` (without a path). For path-based imports (`use "./mylib.py"`), it's not needed.

### How `@pep_fn` works

When a Peppermint expression like `mylib.top(data, n: 2..8)` is called, the `n` argument may arrive as an unevaluated AST node — the interpreter hasn't resolved the range yet. `@pep_fn` checks each kwarg: if it's a plain value (`str`, `int`, `bool`, `list`), it passes through unchanged; if it looks like an AST node, it calls `_interp.eval()` to resolve it first. Your function body always receives plain Python.

Without `@pep_fn`, plain imports still work — but any unevaluated expression passed as a kwarg would arrive as an internal AST object rather than its resolved value.

### Decorators

| Decorator | Behavior |
|---|---|
| `@pep_fn` | **Default.** Auto-evaluates unevaluated kwargs before calling the function. Exceptions become `Err`. |
| `@pep_fn_lazy` | Alias for `@pep_fn`. Use to signal explicitly that kwargs may be expressions. |
| `@pep_fn_static` | No evaluation step — args pass straight through. Use when all args are guaranteed plain literals. |

`@pep_signature("lib.fn(args) -> ReturnType")` attaches the signature string shown in LSP hover tooltips.
