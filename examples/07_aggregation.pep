# 07_aggregation.pep — agg, group, and aggregation functions

# Basic aggregation — collapse a list into a single summary row
load("examples/people.csv")
  |> agg(
      total_income: sum(it.income),
      avg_income:   mean(it.income),
      min_age:      min(it.age),
      max_age:      max(it.age),
      n:            count()
  )
  |> print()

# Group by region, summarize each group
load("examples/people.csv")
  |> group(by: "region") {
      |> agg(
          avg_income: mean(it.income),
          n:          count()
      )
  }
  |> sort(by: "avg_income", dir: "desc")
  |> print()

# Inline list — no file needed
[
  { category: "A", value: 10 },
  { category: "A", value: 20 },
  { category: "B", value: 5  },
  { category: "B", value: 15 }
]
  |> group(by: "category") {
      |> agg(total: sum(it.value), n: count())
  }
  |> print()
