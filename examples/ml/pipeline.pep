use ml
use viz
use env

load("examples/data.csv")
  |> ml.embed(
      on: "name", out: "embedding",
      source: "deepinfra",
      model: "Qwen/Qwen3-Embedding-4B",
      apikey: env.get("DEEPINFRA_TOKEN"))
  |> ml.kmeans(k: 2, on: "embedding", out: "cluster")
  |> ml.umap(dims: 2, on: "embedding", out: "umap")
  |> viz.scatter(
    x: "umap1", y: "umap2", color: "cluster",
    label: "name", display: ["labels"]
)
