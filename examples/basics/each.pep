load("examples/sales.csv")

# Top 2 products by revenue per region
  |> each(by: "region",
      |> add(rank: rank(col.revenue, dir: "desc"))
      |> filter(it.rank <= 2)
      |> drop("rank")
  )
  |> sort(by: "region")
  |> print
