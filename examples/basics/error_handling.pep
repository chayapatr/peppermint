# error_handling.pep — row-level errors and recovery

# When add() fails on a row, that row moves to .errors
# Other rows continue through the pipe unaffected

result = load("examples/people.csv")
  |> add(ratio: it.income / it.age)

# .errors holds any rows that failed
print(result.errors)

# recover() pulls failed rows back with a fallback value
result2 = load("examples/people.csv")
  |> add(score_label: match(it.score,
      > 0.8: "high",
      > 0.5: "medium",
      _:     "low"
  ))
  |> recover(score_label: "unknown")

result2.data |> print()

# match on whole-pipe errors (e.g. file not found)
bad = load("examples/missing.csv")

match(bad,
  Ok(data): data |> print(),
  Err(msg):  print(msg)
)
