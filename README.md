# Peppermint

A pipe-first language for data and ML work, running on top of Python. Every operation is a pipeline step and errors propagate automatically. The Python ecosystem (pandas, scikit-learn, or your own code) is accessible from within the language.

## Install

```sh
pip install peppermint-lang
```

## Run

```sh
pep file.pep  # run a file
pep           # interactive REPL
```

## Examples

### Transform

```
load("employees.csv")
  |> filter(it.age > 18)
  |> add(tax: it.salary * 0.2)
  |> sort(by: "salary", dir: "desc")
  |> print()
```

Each step prints a live summary:

```
|> filter    → List  843 rows × 5 cols  (157 dropped)
|> add       → List  843 rows × 6 cols  (+tax)
|> sort      → List  843 rows × 6 cols
```

### Aggregate

```
load("sales.csv")
  |> collapse(by: "region",
      avg: mean(col.revenue),
      n:   count()
  )
  |> sort(by: "avg", dir: "desc")
  |> print()
```

### Top N per group

```
load("sales.csv")
  |> each(by: "region",
      |> add(rank: rank(col.revenue, dir: "desc"))
      |> filter(it.rank <= 3)
      |> drop("rank")
  )
  |> print()
```

### ML pipeline

```
use ml
use viz
use env

load("data.csv")
  |> add(embedding: ml.embed(it.text,
      source: "deepinfra", model: "Qwen/Qwen3-Embedding-4B",
      apikey: env.get("DEEPINFRA_TOKEN")),
    concurrent: 10)
  |> ml.kmeans(k: 2..8, on: "embedding", out: "cluster")
  |> ml.umap(dims: 2, on: "embedding", out: "umap")
  |> viz.scatter(x: "umap_1", y: "umap_2", color: "cluster", label: "text", display: ["labels", "legend"])
```

### Error handling

```
result = load("data.csv")
  |> filter(it.score > 0.5)

match(result,
  Ok(data): data |> print(),
  Err(msg):  print(msg)
)
```

---

See [docs/language.md](docs/language.md) for the full reference and [examples/](examples/) for more.
