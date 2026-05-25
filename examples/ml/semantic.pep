use ml
use viz

load("examples/data.csv")
  |> ml.embed(
      on: "name",
      out: "embedding",
      source: "local",
      model: "all-MiniLM-L6-v2")
  |> ml.umap(dims: 2, on: "embedding", out: "umap")
  |> viz.scatter(
    x: "umap1", y: "umap2",
    color: "category", label: "name",
    display: ["labels", "legend"]
)
