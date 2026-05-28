# 08_railway.pep — railway-oriented error handling

# Happy track — all steps run
result = load("examples/people.csv")
  |> filter(it.age > 18)
  |> add(ratio: it.income / it.age)
  |> sort(by: "ratio", dir: "desc")

match(result,
  Ok(data): print(data),
  Err(msg):  print(msg)
)

# Broken track — load fails, all downstream steps skipped automatically
bad = load("examples/missing.csv")
  |> filter(it.age > 18)
  |> add(ratio: it.income / it.age)

match(bad,
  Ok(data): print(data),
  Err(msg):  print(msg)
)

# Error inside a pipe step — caught and becomes Err
risky = load("examples/people.csv")
  |> add(inverse: 1 / it.income)   # Err if any income is 0

match(risky,
  Ok(data): data |> print(),
  Err(msg):  print(msg)
)

# Sub-pipe errors propagate to the outer pipe
grouped = load("examples/people.csv")
  |> collapse(by: "region", avg: mean(col.income), n: count())

match(grouped,
  Ok(data): data |> print(),
  Err(msg):  print(msg)
)
