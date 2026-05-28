# Ecosystem

## LSP server (`peppermint/lsp/`)

A Language Server Protocol server that provides diagnostics, hover docs, completions, and go-to-definition for `.pep` files. Works with any editor that supports LSP.

### Install

```sh
pip install peppermint-lang[lsp]
```

### Start manually

```sh
pep lsp
```

The server communicates over stdio. Most editors handle this automatically via their LSP client configuration.

### Neovim (via `nvim-lspconfig`)

Add to your config:

```lua
vim.api.nvim_create_autocmd("FileType", {
  pattern = "peppermint",
  callback = function()
    vim.lsp.start({
      name = "peppermint",
      cmd = { "pep", "lsp" },
      root_dir = vim.fn.getcwd(),
    })
  end,
})
```

Add filetype detection for `.pep` files if needed:

```lua
vim.filetype.add({ extension = { pep = "peppermint" } })
```

### Helix

Add to `~/.config/helix/languages.toml`:

```toml
[[language]]
name = "peppermint"
scope = "source.pep"
file-types = ["pep"]
language-servers = ["peppermint-lsp"]

[language-server.peppermint-lsp]
command = "pep"
args = ["lsp"]
```

### Emacs (via `eglot`)

```elisp
(add-to-list 'eglot-server-programs
             '(peppermint-mode . ("pep" "lsp")))
```

---

## VSCode extension (`ecosystem/vscode-peppermint/`)

Syntax highlighting plus LSP integration (hover, completions, diagnostics, go-to-definition) for VSCode.

### Requirements

- `peppermint-lang[lsp]` installed in the active Python environment (`pip install peppermint-lang[lsp]`)
- Node.js (to build from source)

### Install from source

```sh
cd ecosystem/vscode-peppermint
npm install
npx @vscode/vsce package
code --install-extension vscode-peppermint-*.vsix
```

Or use **Extensions: Install from VSIX** in the VSCode command palette and select the generated `.vsix` file.

### How it works

On activation, the extension locates the `pep` binary by scanning common version manager install paths (mise, pyenv, Homebrew) and falls back to `python3 -m peppermint lsp`. It then spawns the server as a child process and connects over stdio using `vscode-languageclient`. No PATH configuration is required.
