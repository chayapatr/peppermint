# each_lambda.pep — both forms of each: block and lambda

# Block form — multi-step, reads like a loop body
load("examples/people.csv")
  |> each(by: "region",
      |> sort(by: "income", dir: "desc")
      |> take(2)
  )
  |> print()

# Lambda form — single expression, consistent with map/filter
load("examples/people.csv")
  |> each(by: "region", grp -> grp |> sort(by: "income", dir: "desc") |> take(2))
  |> print()
