use ml

load("examples/sales.csv")
  |> ml.kmeans(k: 2..6, out: "segment")
  |> ml.silhouette(on: "segment")
  |> print
