# Caching

Add `@cache` to any pipe step to cache its result:

```
load("data.csv")
  |> ml.kmeans(k: 5..12, on: "embedding", out: "cluster")
      @cache
  |> add(label: ml.llm(it.text, ...))
      @concurrent(10)
      @retry(3)
      @cache
```

Only steps with `@cache` are cached. Everything else recomputes on every run.

---

## Mental model

The ideal pipeline is a pure function: describe the transformation, run it, get the result. The logic is clean. Rerunning it is safe. Nothing about the outside world leaks in.

Real pipelines are not like this. Some steps are slow — a clustering run takes minutes. Some steps are unreliable — an LLM call fails, times out, or returns garbage. The world is messy. But that messiness should not contaminate how you describe your logic.

`@cache` is how you keep the two concerns separate. You write the pipeline as if it were pure — describe what each step should do, in order, without worrying about reruns or failures. `@cache` handles the world's messiness underneath, without changing what the pipeline means:

```
data              ──f──▶  data'          # what you describe
(data, cache)     ──f──▶  (data', cache')  # what the runtime does
```

`cache` is threaded alongside the data as a silent second value. It carries the record of what the world has already answered. The step checks it before calling out, and updates it after. The logic of `f` does not change — only whether the world needs to be consulted again.

This separates two concerns cleanly:

- **Logic** — described once in the pipeline, unchanged across runs
- **World state** — tracked in `cache`, accumulated across runs

Each run moves `cache'` closer to complete. When everything is cached, the pipeline runs instantly and produces the same result as if it had run fresh.

---

## Strategy

Peppermint uses two cache strategies, chosen automatically based on the shape of the function:

**Step cache** — for whole-dataframe operations (`ml.kmeans`, `ml.umap`, `each` blocks). The entire step output is cached by a hash of the expression plus a fingerprint of the input data. If neither changes on rerun, the step is skipped entirely.

**Row cache** — for per-row operations (`ml.llm`, `ml.embed`). Each row's result is cached independently by hashing the row's input content. On rerun, only rows without a cached result hit the API. Crucially, **failed results are never cached** — a row that returned `none` or threw will be retried on the next run.

The two strategies are independent. Clearing step cache (to force re-clustering) leaves all your LLM/embed results intact.

---

## Step cache

Each `@cache` step is cached by its full expression and input data fingerprint. On rerun, unchanged steps are skipped:

```
|> ml.kmeans    → List  6383 rows × 8 cols  (+cluster)  [cached]
|> ml.umap      → List  6383 rows × 10 cols  (+umap_2, umap_1)  [cached]
```

Steps are invalidated when input data changes. If you edit an earlier step, all downstream `@cache` steps rerun.

The cache key includes the full step expression — two `each` calls with the same input but different blocks are cached independently.

---

## Row cache

`ml.embed` and `ml.llm` on a `@cache` step store per-row results by content hash. On rerun:

- Rows that succeeded previously: served from cache, no API call
- Rows that failed previously: **not cached**, retried for real

This means you can append new rows and rerun — existing rows are free, only new ones get processed. And failed rows always get a fresh attempt on the next run, making reruns the natural retry mechanism:

```
# Run 1: row 3 fails → not cached
# Run 2: rows 1, 2 → cache hit; row 3 → fresh API call
|> add(label: ml.llm(it.text, ...))
    @retry(3)
    @until(it.label != none, max: 5)
    @cache
```

Row cache is stored in `.peppermint/row_cache/`.

---

## Cache directory

By default, cache lives in `.peppermint/` next to the `.pep` file. Override with frontmatter:

```
---
cache_dir: ".cache"
---
```

Or pass `--cache-dir PATH` on the CLI.

---

## When to clear the cache

The cache is content-addressed — stale entries are never used, just unused. The directory grows over time but never causes incorrect results.

Clear manually when:

- You changed a Python library a step calls (the cache can't detect this)
- You want to force a full rerun

```sh
rm -rf .peppermint/
```

To clear only step results and keep LLM/embed row cache:

```sh
rm -rf .peppermint/cache/
```
