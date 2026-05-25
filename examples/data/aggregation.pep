# aggregation.pep — collapse, each, and column functions

# Basic aggregation — collapse all rows into a single summary
load("examples/people.csv")
  |> collapse(
      avg_income: mean(col.income),
      min_age:    min(col.age),
      max_age:    max(col.age),
      n:          count()
  )
  |> print()

# Group by region using collapse
load("examples/people.csv")
  |> collapse(by: "region",
      avg_income: mean(col.income),
      n:          count()
  )
  |> sort(by: "avg_income", dir: "desc")
  |> print()

# Annotate each row with its group average (broadcast)
load("examples/people.csv")
  |> add(region_avg: mean(col.income, by: "region"))
  |> print()

# Top 1 per region using each
load("examples/people.csv")
  |> each(by: "region",
      |> add(rank: rank(col.income, dir: "desc"))
      |> filter(it.rank == 1)
      |> drop("rank")
  )
  |> print()
