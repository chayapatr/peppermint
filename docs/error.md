# Error Handling

Peppermint has two distinct error layers: **whole-pipe errors** that stop execution, and **row-level errors** that accumulate without stopping the pipe.

---

## Whole-pipe errors

If a pipe step fails completely — wrong type, undefined variable, file not found — it becomes `Err` and all downstream steps are skipped. The pipe short-circuits:

```
result = load("data.csv")
  |> filter(it.age > 18)     # skipped if load fails
  |> add(score: it.income)   # skipped if filter fails
```

This is the "railway" model. A step either runs on the Ok track or the whole pipe bails to Err.

Check the result with `match`:

```
result = load("data.csv")
  |> filter(it.age > 18)

match(result,
  Ok(data): data |> print(),
  Err(msg):  print(msg)
)
```

---

## Row-level errors

When `add(field: expr)` fails on a specific row — the expression throws, or returns `Err` — that row is moved to `.errors`. The other rows continue through the pipe unaffected.

```
load("posts.csv")
  |> add(label: ml.llm(it.text, ...))
```

If the LLM call fails on row 3, row 3 goes to `.errors`. Rows 1, 2, 4... continue normally. The step output shows `(N errors)` in yellow so you can see it happening.

Error rows carry two metadata fields:
- `_error` — the error message
- `_step` — which step produced the failure (e.g. `"add(label)"`)

---

## Recovering error rows

`recover(field: fallback)` pulls rows back from `.errors` into `.data`, applying a fallback value:

```
load("posts.csv")
  |> add(label: ml.llm(it.text, ...))
  |> recover(label: "unknown")         # literal fallback
```

The fallback can be an expression — `it` refers to the error row:

```
  |> recover(label: it.title)          # use another field as fallback
```

After `recover`, `.errors` is cleared for those rows. If the fallback itself fails, the row stays in `.errors`.

---

## Combining `@retry` with `recover`

`@retry` retries on exception before giving up, sending persistent failures to `.errors`. Use `recover` to pull them back with a fallback:

```
load("posts.csv")
  |> add(label: ml.llm(it.text, source: "openai", model: "gpt-4o", apikey: env.OPENAI_API_KEY, format: "json"))
      @concurrent(10)
      @retry(3)
  |> recover(label: none)
```

What each annotation does:
- `@concurrent(10)` — run across 10 threads; each row is independent
- `@retry(3)` — on exception, retry the row up to 3 times before marking it failed
- `recover(label: none)` — pull the failed rows back into data with `label: none`

---

## Inspecting errors

Access `.errors` by dotting into the named result:

```
result = load("posts.csv")
  |> add(label: ml.llm(...))
      @retry(3)

result.errors |> print()
```

Save them to a file:

```
save(result.errors, "data/failed.csv")
```

Errors from multiple pipelines can be concatenated:

```
save(concat(labels.errors, sub_labels.errors), "data/failed.csv")
```

---

## Summary

| Situation | What happens |
|---|---|
| `load` fails | Whole pipe becomes `Err`, all steps skipped |
| Step throws unexpectedly | Whole pipe becomes `Err` |
| `add(field: expr)` fails on a row | Row moves to `.errors`, other rows continue |
| `select(..., field: expr)` fails on a row | Same — row moves to `.errors` |
| `recover(field: fallback)` | Error rows return to `.data` with fallback applied |

Use `match(result, Ok(data): ..., Err(msg): ...)` to handle whole-pipe failures. Use `recover` to handle per-row failures.
