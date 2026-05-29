"""
Peppermint viz stdlib — uses bridge for type conversion.
"""
from __future__ import annotations
import os
import tempfile
import subprocess
import platform
from ..bridge import ok, err, get_rows, pep_fn
from ..stdlib.core import pep_signature, _as_ctx


_FONT = "Helvetica Neue"


def _setup_font():
    import matplotlib.pyplot as plt
    plt.rcParams["font.family"] = _FONT
    plt.rcParams["font.sans-serif"] = [_FONT, "Apple Color Emoji", "Segoe UI Emoji", "Noto Color Emoji", "DejaVu Sans"]


def _show(fig, file=None):
    import matplotlib.pyplot as plt
    tmp_path = os.path.join(tempfile.mkdtemp(), "plot.png")
    fig.savefig(tmp_path, dpi=150)
    if file is not None:
        fig.savefig(file, dpi=150)
    plt.close(fig)
    system = platform.system()
    if system == "Darwin":
        subprocess.run(["open", tmp_path])
    elif system == "Windows":
        os.startfile(tmp_path)
    else:
        subprocess.run(["xdg-open", tmp_path])


def _to_df(data):
    import pandas as pd
    return pd.DataFrame(get_rows(data))


@pep_fn
@pep_signature('viz.scatter(x: str, y: str, color?: str, size?: List<Int>, file?: str, display?: { label?: str, legend?, axes?, title?: str, dotsize?: Int | str }) -> List<Row>')
def scatter(data, x=None, y=None, color=None, label=None, title=None, size=None, file=None, display=None):
    """Scatter plot. Passes data through unchanged.

`x`, `y`: column names for axes.
`color`: column to color points by.
`size`: figure dimensions `[width, height]` in inches (default matplotlib size).
`file`: path to save the image (e.g. `"plot.png"`). Always opens; saves if provided.
`display`: object with visual options:
  - `label: "col"` — annotate points with column values (skips none/NaN)
  - `legend` — show color legend
  - `axes` — show axis labels and ticks
  - `title: "..."` — plot title
  - `dotsize: N | "col"` — uniform dot size or column-mapped size"""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        _setup_font()

        if isinstance(display, dict):
            show = {k for k, v in display.items() if v}
            label = display.get("label") if isinstance(display.get("label"), str) else label
            title = display.get("title") if isinstance(display.get("title"), str) else title
            dotsize = display.get("dotsize")
        else:
            show = set(display or [])
            dotsize = None

        df = _to_df(data)
        figsize = (size[0], size[1]) if isinstance(size, list) and len(size) == 2 else None
        fig, ax = plt.subplots(figsize=figsize)

        def _resolve_dotsize(group):
            if dotsize is None:
                return {}
            if isinstance(dotsize, str) and dotsize in group.columns:
                return {"s": group[dotsize].values}
            return {"s": dotsize}

        if color and color in df.columns:
            for name, group in df.groupby(color):
                ax.scatter(group[x], group[y], label=str(name), alpha=0.7, **_resolve_dotsize(group))
            if "legend" in show:
                ax.legend()
        else:
            ax.scatter(df[x], df[y], alpha=0.7, **_resolve_dotsize(df))

        if "label" in show and label and label in df.columns:
            for _, row in df.iterrows():
                val = row[label]
                if val is None or (isinstance(val, float) and __import__("math").isnan(val)):
                    continue
                ax.annotate(str(val), (row[x], row[y]),
                            textcoords="offset points", xytext=(5, 5), fontsize=8)

        if "axes" in show:
            ax.set_xlabel(x)
            ax.set_ylabel(y)
        else:
            ax.set_xlabel("")
            ax.set_ylabel("")
            ax.set_xticks([])
            ax.set_yticks([])

        if "title" in show and title:
            ax.set_title(title)

        plt.tight_layout()
        _show(fig, file=file)
        from ..context import Context
        ctx = _as_ctx(data) or Context(data=get_rows(data))
        return ok(ctx.with_artifact("viz", {"plot": fig}))
    except Exception as e:
        return err(str(e))


@pep_fn
@pep_signature("viz.histogram(col: str, file?: str) -> List<Row>")
def histogram(data, col=None, file=None):
    """Histogram of a single column. `col`: column name. Bin count chosen automatically. `file`: path to save image. Passes data through unchanged."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        df = _to_df(data)
        fig, ax = plt.subplots()
        ax.hist(df[col].dropna(), bins="auto", edgecolor="black")
        ax.set_xlabel(col)
        ax.set_ylabel("count")
        plt.tight_layout()
        _show(fig, file=file)
        from ..context import Context
        ctx = _as_ctx(data) or Context(data=get_rows(data))
        return ok(ctx.with_artifact("viz", {"plot": fig}))
    except Exception as e:
        return err(str(e))


@pep_fn
@pep_signature('viz.line(x: str, y: str, color?: str, size?: List<Int>, file?: str, display?: { legend?, axes?, title?: str, dotsize?: Int }) -> List<Row>')
def line(data, x=None, y=None, color=None, size=None, file=None, display=None):
    """Line chart with optional scatter dots. Passes data through unchanged.

`x`, `y`: column names for axes.
`color`: column to group lines by.
`size`: figure dimensions `[width, height]` in inches.
`file`: path to save image.
`display`: object with visual options: `legend`, `axes`, `title: "..."`, `dotsize: N`."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        _setup_font()

        if isinstance(display, dict):
            show = {k for k, v in display.items() if v}
            title = display.get("title") if isinstance(display.get("title"), str) else None
            dotsize = display.get("dotsize")
        else:
            show = set(display or [])
            title = None
            dotsize = None

        df = _to_df(data)
        figsize = (size[0], size[1]) if isinstance(size, list) and len(size) == 2 else None
        fig, ax = plt.subplots(figsize=figsize)

        # Establish a stable x-order from the full sorted dataframe
        x_order = sorted(df[x].unique())
        x_pos = {v: i for i, v in enumerate(x_order)}

        if color and color in df.columns:
            for name, group in df.groupby(color):
                group = group.copy()
                group["_xi"] = group[x].map(x_pos)
                group = group.sort_values("_xi")
                ax.plot(group["_xi"], group[y], label=str(name), linewidth=1.5)
                if dotsize:
                    ax.scatter(group["_xi"], group[y], s=dotsize, zorder=3)
            if "legend" in show:
                ax.legend()
        else:
            df = df.copy()
            df["_xi"] = df[x].map(x_pos)
            df = df.sort_values("_xi")
            ax.plot(df["_xi"], df[y], linewidth=1.5)
            if dotsize:
                ax.scatter(df["_xi"], df[y], s=dotsize, zorder=3)

        ax.set_xticks(range(len(x_order)))
        ax.set_xticklabels(x_order)

        if "axes" in show:
            ax.set_xlabel(x)
            ax.set_ylabel(y)

        if title and "title" in show:
            ax.set_title(title)

        plt.xticks(rotation=45, ha="right")
        plt.tight_layout()
        _show(fig, file=file)
        from ..context import Context
        ctx = _as_ctx(data) or Context(data=get_rows(data))
        return ok(ctx.with_artifact("viz", {"plot": fig}))
    except Exception as e:
        return err(str(e))


@pep_signature("viz.heatmap(file?: str) -> List<Row>")
def heatmap(data, file=None, **_):
    """Correlation heatmap of all numeric columns. `file`: path to save image. Passes data through unchanged."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import seaborn as sns

        df = _to_df(data)
        num_df = df.select_dtypes(include="number")
        fig, ax = plt.subplots(figsize=(10, 8))
        sns.heatmap(num_df.corr(), annot=True, fmt=".2f", ax=ax)
        plt.tight_layout()
        _show(fig, file=file)
        from ..context import Context
        ctx = _as_ctx(data) or Context(data=get_rows(data))
        return ok(ctx.with_artifact("viz", {"plot": fig}))
    except Exception as e:
        return err(str(e))


@pep_signature("viz.plot(file?: str) -> List<Row>")
def plot(data, file=None, **_):
    """Auto-plot based on data shape: scatter if 2+ numeric columns, histogram if 1. `file`: path to save image. Passes data through unchanged."""
    try:
        df = _to_df(data)
        num_cols = df.select_dtypes(include="number").columns.tolist()
        if len(num_cols) >= 2:
            return scatter(data, x=num_cols[0], y=num_cols[1], file=file)
        elif len(num_cols) == 1:
            return histogram(data, col=num_cols[0], file=file)
        else:
            return err("plot(): no numeric columns to visualize")
    except Exception as e:
        return err(str(e))


@pep_signature("viz.grid(..., file?: str) -> List<Row>")
def grid(*datasets, **kwargs):
    """Multiple scatter plots side by side. Pass datasets as positional args: `viz.grid(data1, data2)`. Each panel auto-picks the first two numeric columns. `file`: path to save image. Returns the first dataset unchanged."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        file = kwargs.get("file")
        n = len(datasets)
        if n == 0:
            return err("grid() requires at least one dataset")
        fig, axes = plt.subplots(1, n, figsize=(6 * n, 5))
        if n == 1:
            axes = [axes]
        for ax, data in zip(axes, datasets):
            df = _to_df(data)
            num_cols = df.select_dtypes(include="number").columns.tolist()
            if len(num_cols) >= 2:
                ax.scatter(df[num_cols[0]], df[num_cols[1]], alpha=0.7)
                ax.set_xlabel(num_cols[0])
                ax.set_ylabel(num_cols[1])
        plt.tight_layout()
        _show(fig, file=file)
        return ok(datasets[0] if datasets else None)
    except Exception as e:
        return err(str(e))


def build_viz_env() -> dict:
    return {
        "scatter":   scatter,
        "line":      line,
        "histogram": histogram,
        "heatmap":   heatmap,
        "plot":      plot,
        "grid":      grid,
    }
