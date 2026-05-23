# Peppermint

A pipe-first DSL for data and ML work. Designed to be lightweight and readable, where every operation is a pipeline step, errors propagate automatically, and the heavy lifting happens internally so you don't have to worry about it.

## Install

```sh
pip install -e .
```

## Run

```sh
pep run file.pep
```

## Example

```
load("data.csv")
  |> filter(it.age > 18)
  |> add(score: it.income / it.age)
  |> sort(by: "score", dir: "desc")
  |> print()
```

Each step prints a summary as it runs:

```
|> filter    → List  843 rows × 8 cols  (157 dropped)
|> add       → List  843 rows × 9 cols  (+score)
|> sort      → List  843 rows × 9 cols
```

See [docs/language.md](docs/language.md) for the full language reference and [examples/](examples/) for more.
