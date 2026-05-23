# 05_sales_analysis.pep — multi-step sales pipeline with derived metrics

load("examples/sales.csv")
  |> add(revenue_per_unit: it.revenue / it.units)
  |> add(performance: match(it.revenue, > 12000: "strong", > 7000: "moderate", _: "weak"))
  |> sort(by: "revenue", dir: "desc")
  |> print()
