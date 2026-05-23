# Peppermint

A pipe-first DSL for data and ML work. Designed to be lightweight and readable, where every operation is a pipeline step, errors propagate automatically, and the heavy lifting happens internally so you don't have to worry about it.

## Install

```sh
pip install -e .
```

## Run

```sh
pep file.pep  # run a file
pep           # interactive REPL
```

## Example

```
load("survey.csv")
  |> filter(it.age > 18)
  |> add(score: it.income / it.age)
  |> sort(by: "score", dir: "desc")
  |> print()
```

```
load("survey.csv")
  |> group(by: "region") {
      |> agg(avg_score: mean(it.score), n: count())
  }
  |> sort(by: "avg_score", dir: "desc")
  |> print()
```

Each step prints a summary as it runs:

```
|> filter    → List  843 rows × 5 cols  (157 dropped)
|> add       → List  843 rows × 6 cols  (+score)
|> sort      → List  843 rows × 6 cols
```

See [docs/language.md](docs/language.md) for the full language reference and [examples/](examples/) for more.
