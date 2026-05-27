"""
Peppermint viz stdlib — uses bridge for type conversion.
"""
from __future__ import annotations
import os
import tempfile
import subprocess
import platform
from ..bridge import ok, err, get_rows, pep_fn
from ..stdlib.core import pep_signature


_FONT = "Helvetica Neue"


def _setup_font():
    import matplotlib.pyplot as plt
    plt.rcParams["font.family"] = _FONT
    plt.rcParams["font.sans-serif"] = [_FONT, "Apple Color Emoji", "Segoe UI Emoji", "Noto Color Emoji", "DejaVu Sans"]


def _show(fig):
    import matplotlib.pyplot as plt
    path = os.path.join(tempfile.mkdtemp(), "plot.png")
    fig.savefig(path, dpi=150)
    plt.close(fig)
    system = platform.system()
    if system == "Darwin":
        subprocess.run(["open", path])
    elif system == "Windows":
        os.startfile(path)
    else:
        subprocess.run(["xdg-open", path])


def _to_df(data):
    import pandas as pd
    return pd.DataFrame(get_rows(data))


@pep_fn
@pep_signature('viz.scatter(x: str, y: str, color?: str, size?: List<Int>, display?: { label?: str, legend?, axes?, title?: str, dotsize?: Int | str }) -> List<Row>')
def scatter(data, x=None, y=None, color=None, label=None, title=None, size=None, display=None):
    """Scatter plot. Passes data through unchanged.

`x`, `y`: column names for axes.
`color`: column to color points by.
`size`: figure dimensions `[width, height]` in inches (default matplotlib size).
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
        _show(fig)
        return ok(data)
    except Exception as e:
        return err(str(e))


@pep_fn
@pep_signature("viz.histogram(col: str) -> List<Row>")
def histogram(data, col=None):
    """Histogram of a single column. `col`: column name. Bin count chosen automatically. Passes data through unchanged."""
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
        _show(fig)
        return ok(data)
    except Exception as e:
        return err(str(e))


@pep_signature("viz.heatmap() -> List<Row>")
def heatmap(data, **_):
    """Correlation heatmap of all numeric columns. No parameters needed. Passes data through unchanged."""
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
        _show(fig)
        return ok(data)
    except Exception as e:
        return err(str(e))


@pep_signature("viz.plot() -> List<Row>")
def plot(data, **_):
    """Auto-plot based on data shape: scatter if 2+ numeric columns, histogram if 1. Passes data through unchanged."""
    try:
        df = _to_df(data)
        num_cols = df.select_dtypes(include="number").columns.tolist()
        if len(num_cols) >= 2:
            return scatter(data, x=num_cols[0], y=num_cols[1])
        elif len(num_cols) == 1:
            return histogram(data, col=num_cols[0])
        else:
            return err("plot(): no numeric columns to visualize")
    except Exception as e:
        return err(str(e))


@pep_signature("viz.grid(...) -> List<Row>")
def grid(*datasets, **_):
    """Multiple scatter plots side by side. Pass datasets as positional args: `viz.grid(data1, data2)`. Each panel auto-picks the first two numeric columns. Returns the first dataset unchanged."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

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
        _show(fig)
        return ok(datasets[0] if datasets else None)
    except Exception as e:
        return err(str(e))


def build_viz_env() -> dict:
    return {
        "scatter":   scatter,
        "histogram": histogram,
        "heatmap":   heatmap,
        "plot":      plot,
        "grid":      grid,
    }
