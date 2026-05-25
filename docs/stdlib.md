# Standard Library

## Core — always available

| Function | Description |
|---|---|
| `load(path)` | Load CSV or JSON as list of rows |
| `save(path)` | Write list to CSV or JSON file |
| `filter(pred)` | Keep elements matching condition |
| `map(expr, concurrent?)` | Transform every element |
| `mapi(expr, concurrent?)` | Map with index — `it` is `{ idx, value }` |
| `reduce(init, fn)` | Fold list into a single value |
| `add(field: expr, concurrent?)` | Add a new field to every row |
| `drop(field)` | Remove a field |
| `select(fields...)` | Keep only specified fields |
| `rename(old: new)` | Rename a field |
| `sort(by, dir)` | Sort rows |
| `take(n)` | Keep first n rows |
| `join(other, on)` | Inner join on a shared key field |
| `each(by:, \|> ...)` | Run a sub-pipe per group, concatenate results |
| `collapse(by:, ...)` | Aggregate rows, optionally grouped |
| `sum(col.field)` | Sum of a column — use in `collapse` or `add` |
| `mean(col.field)` | Mean of a column — use in `collapse` or `add` |
| `count()` | Row count — use in `collapse` |
| `min(col.field)` | Minimum — use in `collapse` or `add` |
| `max(col.field)` | Maximum — use in `collapse` or `add` |
| `rank(col.field, by:, dir:)` | Rank rows by a column — use in `add` |
| `rolling(col.field, window, fn, by:)` | Rolling window — use in `add` |
| `len(list)` | Number of elements |
| `concat(a, b, ...)` | Concatenate lists |
| `print(value)` | Print and pass through |

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
| `ml.embed(text, source:, model:, apikey?)` | Embed a single string — use inside `add` |
| `ml.kmeans(k:, on:, out:)` | K-means clustering; `k:` accepts a range for auto-select by silhouette score |
| `ml.umap(dims:, on:, out:)` | Dimensionality reduction — `out: "umap"` adds `umap_1`, `umap_2`, ...; `out: ["x","y"]` names explicitly |
| `ml.ols(on:, out:)` | OLS regression — adds predicted and residual columns; prints R² to stderr |
| `ml.silhouette(on:)` | Score current clustering — prints silhouette score to stderr |

---

## `use viz`

`pip install peppermint-lang[viz]`

| Function | Description |
|---|---|
| `viz.scatter(x:, y:, color?, label?, display?)` | Scatter plot — `display:` controls what's shown: `"axes"`, `"labels"`, `"legend"`, `"title"` |
| `viz.histogram(col:)` | Histogram |
| `viz.heatmap()` | Correlation heatmap of all numeric columns |
| `viz.plot()` | Auto-plot based on data shape |
| `viz.grid(...)` | Multiple plots side by side |

---

## `use str`

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
