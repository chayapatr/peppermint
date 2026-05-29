# collapse_lambda.pep — custom aggregation with lambdas in collapse

# Built-in aggregations
load("examples/people.csv")
  |> collapse(by: "region",
      n:          count(),
      avg_income: mean(col.income),
      top_earner: rows -> rows |> sort(by: "income", dir: "desc") |> get(0)
  )
  |> print()

# Collapse without by — summarize the whole table
load("examples/people.csv")
  |> collapse(
      n:     count(),
      names: rows -> rows |> map(it.name)
  )
  |> print()
