# Standard Library

## Core — always available

| Function | Description |
|---|---|
| `load(path)` | Load CSV or JSON as a Context |
| `save(data, path)` | Write rows to CSV or JSON |
| `filter(pred)` | Keep rows matching condition — `it` is current row |
| `map(expr)` | Transform every element — `it` is current element |
| `mapi(expr)` | Map with index — `it` is `{ idx, val }` |
| `reduce(init, fn)` | Fold list into a single value |
| `add(field: expr)` | Add a new field to every row |
| `drop(field)` | Remove a field |
| `select(fields...)` | Keep only specified fields |
| `rename(old: new)` | Rename a field |
| `sort(by, dir?)` | Sort rows — `dir:` `"asc"` (default) or `"desc"` |
| `take(n)` | Keep first n rows |
| `unique(by?)` | Deduplicate rows — `by:` deduplicates on a single field |
| `each(by:, \|> ...)` | Run a sub-pipe per group, concatenate results. Accepts block or lambda form |
| `collapse(by:, ...)` | Aggregate rows, optionally grouped. Values can be agg fns or a lambda receiving the group |
| `join(other, on)` | Inner join on a shared key |
| `recover(field: expr)` | Move error rows back into data with a fallback value — use after a step that may fail |
| `sum(col.field)` | Sum — use in `collapse` or `add`. Handles vector columns element-wise |
| `mean(col.field)` | Mean — use in `collapse` or `add`. Handles vector columns element-wise |
| `count()` | Row count — use in `collapse` |
| `min(col.field)` | Minimum — use in `collapse` or `add` |
| `max(col.field)` | Maximum — use in `collapse` or `add` |
| `rank(col.field, by?, dir?)` | Rank rows by a column — use in `add` |
| `rolling(col.field, window, fn, by?)` | Rolling window aggregation — use in `add` |
| `len(list)` | Number of elements |
| `concat(a, b, ...)` | Concatenate lists |
| `slice(list, start, end)` | Slice a list (inclusive end) |
| `get(list, i)` | Get element at index — always positional |
| `find(table, col, value)` | Find first row where `col` equals `value` — returns `none` if not found |
| `cross(field, values)` | Duplicate every row once per value in `values`, adding `field` as a new column |
| `flatten(field)` | Explode a list-valued column into one row per element — dict items spread as columns |
| `first(list)` | First element of a list — `none` if empty |
| `last(list)` | Last element of a list — `none` if empty |
| `print(value)` | Print and pass through |
| `halt(message?)` | Stop execution immediately with exit code 1 |
| `str(value)` | Convert to string |
| `int(value)` | Convert to integer |
| `float(value)` | Convert to float |

### Annotations

Use annotations instead of kwargs for execution behavior:

| Annotation | Description |
|---|---|
| `@concurrent(n)` | Run the step over each row using n threads. Works on any step or declaration |
| `@retry(n)` | Retry the step up to n times on exception |
| `@cache` | Cache the whole step by input fingerprint — skips the step on rerun if input is unchanged. Use for deterministic whole-dataframe steps (`ml.kmeans`, `ml.umap`) |
| `@row_cache` | Cache each row's result independently by content hash. On rerun, only uncached rows are recomputed. Failed rows are never cached. Use with `ml.llm`, `ml.embed` |
| `@progress` | Show a live progress bar on stderr as rows complete. Works alongside `@concurrent` and `@row_cache` |

```
# Per-row embed with row-level caching
|> add(embedding: ml.embed(...))
    @concurrent(50)
    @row_cache

# LLM with retry and row-level caching — failures retry on next run
|> add(label: ml.llm(...))
    @concurrent(10)
    @retry(3)
    @row_cache

# Live progress bar while running
|> add(label: ml.llm(...))
    @concurrent(10)
    @row_cache
    @progress

# Cache a deterministic whole-dataframe step
|> ml.kmeans(k: 5..12, on: "embedding", out: "cluster")
    @cache

# On a declaration — applies every time it's used
gpt = ml.llm("classify: {it.title}", source: "openai", model: "gpt-4o", apikey: env.OPENAI_API_KEY)
  @concurrent(10)
  @retry(3)
```

### `recover`

```
|> add(label: ml.llm(...))
|> recover(label: "unknown")         # literal fallback
|> recover(label: it.title)          # expression fallback
```

Moves all rows currently in `.errors` back into `.data`, applying the fallback expression per row. Clears `.errors` after recovery.

### Context fields

After a pipe, the result is a Context. Access fields by dotting into the named assignment:

```
posts = load("data.csv") |> ml.kmeans(k: 3, out: "cluster")

posts.data      # the rows
posts.errors    # rows that failed any step
posts.kmeans    # { model, k } — written by ml.kmeans
posts.umap      # { model } — written by ml.umap
posts.viz       # { plot } — written by viz.*
```

---

## `use env`

| Function | Description |
|---|---|
| `env.KEY` | Read environment variable — errors if not set (preferred) |
| `env.get("KEY")` | Read environment variable — returns `Err` if not set |

```
use env
key = env.OPENAI_API_KEY
val = env.get("OPTIONAL_KEY")
```

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
| `ml.embed(text, source:, model:, apikey?)` | Embed a single string — use inside `add` with `@concurrent(N)` for batch calls |
| `ml.llm(prompt, source:, model:, apikey?, format?)` | Single LLM call — use inside `add`. `source:` `"openai"`, `"anthropic"`, or `"deepinfra"`. `format: "json"` strips fences and parses response |
| `ml.kmeans(k:, on:, out:, method?, model?)` | K-means — `k:` accepts a range for auto-select; `method:` `"silhouette"` (default) or `"elbow"`; writes `.kmeans` artifact |
| `ml.umap(dims:, on:, out:, neighbors?, min_dist?, metric?, model?)` | Dimensionality reduction — writes `.umap` artifact |
| `ml.ols(on:, out:, model?)` | OLS regression — adds predicted and residual columns; writes `.ols` artifact |
| `ml.dist(a, b, metric?)` | Distance between two vectors — use inside `add`; `metric:` `"cosine"` (default) or `"euclidean"` |
| `ml.silhouette(on:)` | Score current clustering — prints silhouette score to stderr |

`model:` shorthand on `kmeans`/`umap`/`ols`: loads from file if it exists, otherwise fits and saves.

Use `@row_cache` on any `add` step with `ml.embed` or `ml.llm` for per-row caching — only uncached rows hit the API on rerun. Failed rows are never cached and are retried automatically.

---

## `use viz`

`pip install peppermint-lang[viz]`

All viz functions write a `.viz.plot` artifact to the Context and open the plot immediately. Pass `file:` to also save to disk.

| Function | Description |
|---|---|
| `viz.scatter(x:, y:, color?, size?, file?, display?)` | Scatter plot — `display: { label: "col", legend, axes, title: "...", dotsize: N \| "col" }` |
| `viz.line(x:, y:, color?, size?, file?, display?)` | Line chart — `display: { legend, axes, title: "...", dotsize: N }` |
| `viz.histogram(col:, file?)` | Histogram |
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

Plain Python files work out of the box — Peppermint wraps public functions automatically. For more control, use `peppermint.bridge` decorators.

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

Functions receive plain Python values (`list[dict]`, `str`, `int`, etc.). Exceptions become `Err` automatically.

### Using decorators

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

### Decorators

| Decorator | Behavior |
|---|---|
| `@pep_fn` | **Default.** Auto-evaluates unevaluated kwargs. Exceptions become `Err`. |
| `@pep_fn_lazy` | Alias for `@pep_fn`. |
| `@pep_fn_static` | No evaluation step — args pass straight through. |

`@pep_signature("lib.fn(args) -> ReturnType")` attaches the signature shown in LSP hover tooltips.
