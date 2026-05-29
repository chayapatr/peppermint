use viz
use env
use ml

result = load("examples/data.csv")
  |> add(embedding:
        ml.embed(
          it.name,
          source: "deepinfra",
          model: "Qwen/Qwen3-Embedding-4B",
          apikey: env.DEEPINFRA_TOKEN))
      @concurrent(10)

  |> ml.kmeans(k: 2..6, on: "embedding", out: "cluster")
  |> ml.umap(dims: 2, on: "embedding", out: "umap")
  |> viz.scatter(
      x: "umap_1", y: "umap_2", color: "cluster",
      display: { label: "name" })

  |> each(by: "cluster",
    |> ml.kmeans(k: 2..6, on: "embedding", out: "sub_cluster")
    |> ml.umap(dims: 2, on: "embedding", out: "sub_umap")
    |> viz.scatter(
      x: "sub_umap_1", y: "sub_umap_2", color: "sub_cluster",
      display: { label: "name" })
    )

print("done — {len(result.data)} rows, {len(result.errors)} errors")
