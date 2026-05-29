# railway.pep — whole-pipe error handling

# Happy track — all steps run
result = load("examples/people.csv")
  |> filter(it.age > 18)
  |> add(ratio: it.income / it.age)
  |> sort(by: "ratio", dir: "desc")

match(result,
  Ok(data): data |> print(),
  Err(msg):  print(msg)
)

# Broken track — load fails, all downstream steps skipped automatically
bad = load("examples/missing.csv")
  |> filter(it.age > 18)
  |> add(ratio: it.income / it.age)

match(bad,
  Ok(data): data |> print(),
  Err(msg):  print(msg)
)
