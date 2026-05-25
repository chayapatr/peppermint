"""
Peppermint viz stdlib — uses bridge for type conversion.
"""
from __future__ import annotations
import os
import tempfile
import subprocess
import platform
from ..bridge import ok, err, get_rows, to_python
from ..stdlib.core import pep_signature


_FONT = "Helvetica Neue"


def _setup_font():
    import matplotlib.pyplot as plt
    plt.rcParams["font.family"] = _FONT


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


@pep_signature('viz.scatter(x: str, y: str, color?: str, label?: str, display?: List<str>) -> List<Row>')
def scatter(data, x=None, y=None, color=None, label=None, title=None, display=None, _interp=None, _env=None, **_):
    """Scatter plot. `display` controls what's shown: "axes", "labels", "legend", "title"."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        _setup_font()

        from ..bridge import to_python as _ev
        x       = _ev(x)       if not isinstance(x,     str)  else x
        y       = _ev(y)       if not isinstance(y,     str)  else y
        color   = _ev(color)   if color   is not None and not isinstance(color,   str) else color
        label   = _ev(label)   if label   is not None and not isinstance(label,   str) else label
        title   = _ev(title)   if title   is not None and not isinstance(title,   str) else title
        display = _ev(display) if display is not None and not isinstance(display, list) else (display or [])
        show = set(display)

        df = _to_df(data)
        fig, ax = plt.subplots()

        if color and color in df.columns:
            for name, group in df.groupby(color):
                ax.scatter(group[x], group[y], label=str(name), alpha=0.7)
            if "legend" in show:
                ax.legend()
        else:
            ax.scatter(df[x], df[y], alpha=0.7)

        if "labels" in show and label and label in df.columns:
            for _, row in df.iterrows():
                ax.annotate(str(row[label]), (row[x], row[y]),
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


@pep_signature("viz.histogram(col: str) -> List<Row>")
def histogram(data, col=None, **_):
    """Histogram of a column."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        col = to_python(col) if not isinstance(col, str) else col
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
    """Correlation heatmap of all numeric columns."""
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
    """Auto-plot based on data shape."""
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
    """Multiple plots side by side."""
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
