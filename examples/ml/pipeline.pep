use ml
use viz
use env

load("examples/data.csv")
  |> add(embedding: ml.embed(it.name,
      source: "deepinfra",
      model: "Qwen/Qwen3-Embedding-4B",
      apikey: env.DEEPINFRA_TOKEN))
      @concurrent(10)
  |> ml.kmeans(k: 2, on: "embedding", out: "cluster")
  |> ml.umap(dims: 2, on: "embedding", out: "umap")
  |> viz.scatter(
    x: "umap_1", y: "umap_2", color: "cluster",
    display: { label: "name", legend }
)
