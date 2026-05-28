# context.pep — accessing Context fields after a pipe

use ml

# After a pipe, the result is a Context with .data and .errors
result = load("examples/people.csv")
  |> filter(it.age > 18)
  |> add(income_k: it.income / 1000)

# .data — the rows
result.data |> print()

# .errors — rows that failed any step (empty here)
print(result.errors)

# Dot into a named assignment to get specific fields
summary = result.data
  |> collapse(n: count(), avg_income: mean(col.income_k))

print("rows: {summary.data[0].n}, avg income: {summary.data[0].avg_income}")
