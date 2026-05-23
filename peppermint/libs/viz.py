"""
Peppermint viz stdlib — uses bridge for type conversion.
"""
from __future__ import annotations
from ..bridge import ok, err, get_rows, to_python


def _to_df(data):
    import pandas as pd
    return pd.DataFrame(get_rows(data))


def scatter(data, x=None, y=None, color=None, label=None, _interp=None, _env=None, **_):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        from ..bridge import to_python as _ev
        x = _ev(x) if not isinstance(x, str) else x
        y = _ev(y) if not isinstance(y, str) else y
        color = _ev(color) if color is not None and not isinstance(color, str) else color

        df = _to_df(data)
        fig, ax = plt.subplots()
        if color and color in df.columns:
            for name, group in df.groupby(color):
                ax.scatter(group[x], group[y], label=str(name), alpha=0.7)
            ax.legend()
        else:
            ax.scatter(df[x], df[y], alpha=0.7)
        ax.set_xlabel(x)
        ax.set_ylabel(y)
        plt.tight_layout()
        plt.show()
        plt.close(fig)
        return ok(data)
    except Exception as e:
        return err(str(e))


def histogram(data, col=None, **_):
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
        plt.show()
        plt.close(fig)
        return ok(data)
    except Exception as e:
        return err(str(e))


def heatmap(data, **_):
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
        plt.show()
        plt.close(fig)
        return ok(data)
    except Exception as e:
        return err(str(e))


def plot(data, **_):
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


def grid(*datasets, **_):
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
        plt.show()
        plt.close(fig)
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
