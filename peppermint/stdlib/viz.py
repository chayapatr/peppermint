from __future__ import annotations
import matplotlib
matplotlib.use("Agg")  # non-interactive by default; override with MPLBACKEND env var
import matplotlib.pyplot as plt
import pandas as pd
from ..interpreter import Ok, Err, ListValue


def _to_df(data: ListValue) -> pd.DataFrame:
    return pd.DataFrame(data.rows)


def scatter(data: ListValue, x: str, y: str, color: str = None, **_) -> Ok | Err:
    try:
        df = _to_df(data)
        fig, ax = plt.subplots()
        if color and color in df.columns:
            groups = df.groupby(color)
            for name, group in groups:
                ax.scatter(group[x], group[y], label=str(name), alpha=0.7)
            ax.legend()
        else:
            ax.scatter(df[x], df[y], alpha=0.7)
        ax.set_xlabel(x)
        ax.set_ylabel(y)
        plt.tight_layout()
        plt.show()
        plt.close(fig)
        return Ok(data)
    except Exception as e:
        return Err(str(e))


def histogram(data: ListValue, col: str, **_) -> Ok | Err:
    try:
        df = _to_df(data)
        fig, ax = plt.subplots()
        ax.hist(df[col].dropna(), bins="auto", edgecolor="black")
        ax.set_xlabel(col)
        ax.set_ylabel("count")
        plt.tight_layout()
        plt.show()
        plt.close(fig)
        return Ok(data)
    except Exception as e:
        return Err(str(e))


def heatmap(data: ListValue, **_) -> Ok | Err:
    try:
        import seaborn as sns
        df = _to_df(data)
        num_df = df.select_dtypes(include="number")
        fig, ax = plt.subplots(figsize=(10, 8))
        sns.heatmap(num_df.corr(), annot=True, fmt=".2f", ax=ax)
        plt.tight_layout()
        plt.show()
        plt.close(fig)
        return Ok(data)
    except Exception as e:
        return Err(str(e))


def plot(data: ListValue, **_) -> Ok | Err:
    try:
        df = _to_df(data)
        num_cols = df.select_dtypes(include="number").columns.tolist()
        if len(num_cols) >= 2:
            return scatter(data, x=num_cols[0], y=num_cols[1])
        elif len(num_cols) == 1:
            return histogram(data, col=num_cols[0])
        else:
            return Err("plot(): no numeric columns to visualize")
    except Exception as e:
        return Err(str(e))


def grid(*datasets, **_) -> Ok | Err:
    try:
        n = len(datasets)
        if n == 0:
            return Err("grid() requires at least one dataset")
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
        return Ok(datasets[0] if datasets else None)
    except Exception as e:
        return Err(str(e))


def build_viz_env() -> dict:
    return {
        "scatter":   scatter,
        "histogram": histogram,
        "heatmap":   heatmap,
        "plot":      plot,
        "grid":      grid,
    }
