# 03_error_handling.pep — Result type and match for error handling

result = load("examples/people.csv")
  |> filter(it.age > 18)
  |> add(ratio: it.income / it.age)

match(result,
  Ok(data): print(data),
  Err(msg):  print(msg)
)

# also works with a missing file
bad = load("examples/does_not_exist.csv")

match(bad,
  Ok(data): print(data),
  Err(msg):  print(msg)
)
