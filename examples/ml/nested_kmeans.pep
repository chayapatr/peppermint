use viz
use env
use ml
use text

result = load("examples/data.csv")
  # run text embedding
  |> add(embedding:
        ml.embed(
          it.name,
          source: "deepinfra",
          model: "Qwen/Qwen3-Embedding-4B",
          apikey: env.DEEPINFRA_TOKEN))
      @concurrent(10)

  # run top-level k-means
  |> ml.kmeans(k: 2..6, on: "embedding", out: "cluster")

  # run top level scatter plot
  |> ml.umap(
        dims: 2,
        on: "embedding",
        out: "umap")
  |> viz.scatter(
      x: "umap_1", y: "umap_2", color: "cluster",
      display: { label: "name" })

  # run nested kmeans + viz
  |> each(by: "cluster",
    |> ml.kmeans(
        k: 2..6,
        on: "embedding",
        out: "innercluster")
    |> ml.umap(
        dims: 2,
        on: "embedding",
        out: "innerumap")
    |> viz.scatter(
      x: "innerumap_1", y: "innerumap_2", color: "innercluster",
      display: { label: "name" })
    )

match(result,
  Ok(data): print("DONE!"),
  Err(msg): print(text.join(["error: ", msg]))
)
