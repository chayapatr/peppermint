use ml
use viz

load("examples/data.csv")
  |> add(embedding: ml.embed(it.name, source: "local", model: "all-MiniLM-L6-v2"))
  |> ml.umap(dims: 2, on: "embedding", out: "umap")
  |> viz.scatter(
    x: "umap_1", y: "umap_2",
    color: "category",
    display: { label: "name", legend }
)
