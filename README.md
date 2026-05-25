# Peppermint

A pipe-first language for data and ML work, running on top of Python. Every operation is a pipeline step and errors propagate automatically.

## Install

```sh
pip install peppermint-lang
pip install peppermint-lang[lsp]   # + language server
pip install peppermint-lang[ml]    # + scikit-learn, umap, openai
pip install peppermint-lang[all]   # everything
```

Or from source:

```sh
git clone https://github.com/chayapatr/peppermint
cd peppermint
pip install -e ".[all]"
```

## Run

```sh
pep file.pep  # run a file
pep           # interactive REPL
pep lsp       # start language server (stdio)
```

## Examples

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

<details>
<summary>Aggregate</summary>

```
load("sales.csv")
  |> collapse(by: "region",
      avg: mean(col.revenue),
      n:   count()
  )
  |> sort(by: "avg", dir: "desc")
  |> print()
```

</details>

<details>
<summary>Top N per group</summary>

```
load("sales.csv")
  |> each(by: "region",
      |> add(rank: rank(col.revenue, dir: "desc"))
      |> filter(it.rank <= 3)
      |> drop("rank")
  )
  |> print()
```

</details>

<details>
<summary>Error handling</summary>

```
result = load("data.csv")
  |> filter(it.score > 0.5)

match(result,
  Ok(data): data |> print(),
  Err(msg):  print(msg)
)
```

</details>

<details>
<summary>Python bridge</summary>

```
use "./transforms.py" as t

load("data.csv")
  |> t.clean()
  |> print()
```

Python functions receive and return plain Python types. Conversion is automatic.

</details>

---

## Editor support

The LSP server (`pep lsp`) provides diagnostics, hover docs, completions, and go-to-definition for any LSP-capable editor.

**VSCode** — install the extension from `ecosystem/vscode-peppermint/`. It auto-discovers `pep` via mise, pyenv, or Homebrew — no PATH setup needed.

**Neovim**:

```lua
vim.lsp.start({ name = "peppermint", cmd = { "pep", "lsp" }, root_dir = vim.fn.getcwd() })
```

**Helix** (`~/.config/helix/languages.toml`):

```toml
[language-server.peppermint-lsp]
command = "pep"
args = ["lsp"]
```

See [docs/ecosystem.md](docs/ecosystem.md) for full editor setup and [docs/language.md](docs/language.md) for the complete language reference.
