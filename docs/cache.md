# Caching

Two annotations, two granularities:

```
load("data.csv")
  |> ml.kmeans(k: 5..12, on: "embedding", out: "cluster")
      @cache                          # whole step — skip entirely if input unchanged

  |> add(label: ml.llm(it.text, ...))
      @concurrent(10)
      @retry(3)
      @row_cache                      # per row — only rerun rows that aren't cached yet
```

---

## Mental model

The ideal pipeline is a pure function: describe the transformation, run it, get the result. The logic is clean. Rerunning is safe. Nothing about the outside world leaks in.

Real pipelines are not like this. Some steps are slow — a clustering run takes minutes. Some steps are unreliable — an LLM call fails, times out, or returns garbage. The world is messy. But that messiness should not contaminate how you describe your logic.

`@cache` and `@row_cache` are how you keep the two concerns separate. You write the pipeline as if it were pure. The annotations handle the world's messiness underneath, without changing what the pipeline means:

```
data              ──f──▶  data'            # what you describe
(data, cache)     ──f──▶  (data', cache')  # what the runtime does
```

`cache` is threaded alongside the data as a silent second value. It carries the record of what the world has already answered. Each run moves `cache'` closer to complete. When everything is cached, the pipeline runs instantly and produces the same result as if it had run fresh.

---

## Two annotations

### `@cache` — step cache

The entire step output is cached by a hash of the step expression and a fingerprint of the input data. On rerun, if neither has changed, the step is skipped entirely:

```
|> ml.kmeans    → List  6383 rows × 8 cols  (+cluster)  [cached]
|> ml.umap      → List  6383 rows × 10 cols  (+umap_2, umap_1)  [cached]
```

Use for whole-dataframe operations that are deterministic and expensive: `ml.kmeans`, `ml.umap`, `each` blocks, any step where the output is a pure function of the input.

Step cache is written only when the step completes with **zero errors**. If any row failed, the step is not cached — it must rerun on the next run to retry the failures.

### `@row_cache` — row cache

Each row is cached independently by a hash of its content and the step name. On rerun, the step processes rows one at a time:

- Cache hit → return stored result, no function call
- Cache miss → call the function, write result to cache

```
|> add(transcript: sim.simulate(...))  → List  1000 rows × 5 cols  [row_cache | 200 run, 800 cached]
```

Use for per-row API calls that are expensive or unreliable: LLM calls, embeddings, external APIs, slow bridge functions.

**Failed rows are never cached.** A row that raises or produces `_error` is always retried on the next run. This means reruns are the natural retry mechanism — no special logic needed.

When all rows complete successfully, `@row_cache` also writes a step cache entry. The next rerun hits that step cache and skips the row loop entirely:

```
run 1:  [row_cache | 1000 run, 0 cached]    # all rows computed, row + step cache written
run 2:  [cached]                             # step cache hit, instant
```

---

## Rerun behavior

```
rerun
  → step cache hit?     → skip everything, instant           (@cache or @row_cache)
  → step cache miss?
      → row cache hit?  → return stored row, no call         (@row_cache only)
      → row cache miss? → call the function                  (always)
```

---

## Crash recovery

The value of `@row_cache` over `@cache` is partial progress. With `@cache`, a crash mid-batch means losing everything — the step either completes or it doesn't. With `@row_cache`, every completed row is safe:

```
# 10,000 scenarios, crash after 6,000
run 1:  [row_cache | 10000 run, 0 cached]     # crashes at row 6,000
run 2:  [row_cache | 4000 run, 6000 cached]   # resumes from row 6,001
run 3:  [cached]                              # all done, step cache hit
```

Adding new rows to the input also works — existing rows hit the row cache, only the new ones run.

---

## When to use which

| Situation | Annotation |
|---|---|
| Expensive whole-dataframe step (`ml.kmeans`, `ml.umap`) | `@cache` |
| Per-row API call (`ml.llm`, `ml.embed`, bridge function) | `@row_cache` |
| Step that can partially fail and needs crash recovery | `@row_cache` |
| Deterministic step you want to skip on rerun | `@cache` |

---

## Cache directory

By default, cache lives in `.peppermint/` next to the `.pep` file:

```
.peppermint/
  cache/       # step cache entries
  row_cache/   # row cache entries
```

Override with frontmatter:

```
---
cache_dir: ".cache"
---
```

The two stores are independent. Clearing step cache forces steps to rerun through the row cache loop. Clearing row cache forces all rows to recompute.

```sh
rm -rf .peppermint/          # clear everything
rm -rf .peppermint/cache/    # clear step cache only, keep row cache
rm -rf .peppermint/row_cache/ # clear row cache only, keep step cache
```

---

## When to clear

The cache is content-addressed — stale entries are never used, just unused. The directory grows over time but never causes incorrect results.

Clear when:

- You changed a Python bridge function the step calls (the cache can't detect code changes, only data changes)
- You want to force a full rerun from scratch
