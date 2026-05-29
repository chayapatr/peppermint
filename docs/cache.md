# Caching

Pass `--cache` to enable caching:

```sh
pep pipeline.pep --cache
```

Or enable it per-file in the frontmatter:

```
---
cache: true
---
```

Both can be combined. CLI flag takes precedence.

---

## Strategy

Peppermint uses two separate caches with different granularities:

**Step cache** — coarse, per-step. Each pipe step is cached by a hash of its expression (including kwargs and block) plus a fingerprint of its input data. When the same step runs on the same data again, the result is served from cache without re-executing the step. This is suitable for expensive deterministic computations: clustering, dimensionality reduction, regression.

**Row cache** — fine, per-row. `ml.embed` and `ml.llm` cache each row's result independently by hashing the row's input content. When you append new rows to your data and rerun, only the new rows hit the API. Existing rows are free. This is suitable for I/O-bound, per-row operations where you want incremental reprocessing without re-paying for already-computed rows.

The two caches are independent. You can clear the step cache (forcing re-clustering, re-umap) while preserving all your embed/LLM calls, or vice versa.

---

## Step cache

Each pipe step is cached by its expression and input data. On rerun, unchanged steps are skipped and the cached result is restored. The step output shows `[cached]` for skipped steps:

```
|> ml.kmeans    → List  6383 rows × 8 cols  (+cluster)  [cached]
|> ml.umap      → List  6383 rows × 10 cols  (+umap_1, umap_2)  [cached]
```

Steps are invalidated automatically when the input data changes. If you edit an earlier step in the pipeline, all downstream steps rerun.

The cache key includes the full step expression — two `each` calls with the same input but different blocks (e.g. one runs `ml.kmeans`, one runs `sort/take`) are cached independently.

Cache is stored in `.peppermint/cache/` next to the `.pep` file. To reset, delete the directory.

---

## Row cache

`ml.embed` and `ml.llm` cache per-row results separately. Each row's embedding or LLM response is stored by a hash of its input content. On rerun, only rows that haven't been seen before hit the API — rows with existing results are served from cache instantly.

This means you can append new rows to your data and rerun: existing rows are free, only new ones get billed.

Row cache is stored in `.peppermint/row_cache/`.

---

## Cache directory

By default, cache lives in `.peppermint/` next to the `.pep` file. To change it:

```
---
cache: true
cache_dir: ".cache"
---
```

Or pass `--cache-dir PATH` on the CLI.

---

## When to clear the cache

The cache is content-addressed — if your data or step expression changes, the old entry is simply unused and a new one is written. The cache directory grows over time but stale entries never cause incorrect results.

You should clear the cache manually if:
- You changed a Python library that a step calls (the cache can't detect this)
- You want to force a full rerun

```sh
rm -rf .peppermint/
```

To clear only step results and keep row-level LLM/embed cache:

```sh
rm -rf .peppermint/cache/
```
