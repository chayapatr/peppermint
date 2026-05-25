"""
Peppermint ml stdlib — uses bridge for type conversion.
Python functions receive plain list[dict], return plain list[dict].
"""
from __future__ import annotations
from ..bridge import ok, err, get_rows, pep_fn
from ..stdlib.core import pep_signature


def _to_df(data):
    import pandas as pd
    return pd.DataFrame(get_rows(data))


def _from_df(df):
    return df.to_dict(orient="records")


def _numeric_cols(df):
    import numpy as np
    return df.select_dtypes(include=[np.number]).columns.tolist()


@pep_fn
@pep_signature("ml.kmeans(k: Int | Range, on: str, out: str) -> List<Row>")
def kmeans(data, k=None, on=None, out=None):
    """K-means clustering. `k` accepts a range for auto-selection by silhouette score."""
    import numpy as np
    from sklearn.cluster import KMeans
    from sklearn.metrics import silhouette_score
    from ..interpreter import PmRange
    import sys

    if k is None:
        return err("kmeans: k is required")
    if out is None:
        return err("kmeans: out is required")

    df = _to_df(data)

    if on is not None:
        X = np.stack(df[on].tolist())
        idx = df.index
    else:
        num_cols = _numeric_cols(df)
        sub = df[num_cols].dropna()
        X = sub.values
        idx = sub.index

    if isinstance(k, PmRange):
        best_k, best_score, best_labels = None, -1, None
        for ki in range(k.start, k.end + 1):
            model = KMeans(n_clusters=ki, random_state=42, n_init="auto")
            labels = model.fit_predict(X)
            if len(set(labels)) > 1:
                s = silhouette_score(X, labels)
                if s > best_score:
                    best_k, best_score, best_labels = ki, s, labels
        labels = best_labels
        print(f"kmeans: best k={best_k}, silhouette={best_score:.3f}", file=sys.stderr)
    else:
        model = KMeans(n_clusters=int(k), random_state=42, n_init="auto")
        labels = model.fit_predict(X)

    df = df.copy()
    df.loc[idx, out] = labels.astype(int)
    return ok(_from_df(df))


@pep_fn
@pep_signature("ml.ols(on: str, out: str) -> List<Row>")
def ols(data, on=None, out=None):
    """OLS regression. Adds predicted and residual columns. Prints R² to stderr."""
    from sklearn.linear_model import LinearRegression
    import sys

    if on is None:
        return err("ols: on is required (target column)")
    if out is None:
        return err("ols: out is required")

    df = _to_df(data)
    num_cols = [c for c in _numeric_cols(df) if c != on]
    X = df[num_cols].dropna()
    y = df.loc[X.index, on]

    model = LinearRegression()
    model.fit(X, y)
    predicted = model.predict(X)
    r2 = model.score(X, y)
    coeffs = dict(zip(num_cols, model.coef_))
    print(f"ols: R²={r2:.4f}  intercept={model.intercept_:.4f}", file=sys.stderr)
    for col, coef in coeffs.items():
        print(f"     {col}: {coef:.4f}", file=sys.stderr)
    df = df.copy()
    df.loc[X.index, out] = predicted
    df.loc[X.index, "residual"] = y.values - predicted
    return ok(_from_df(df))


@pep_fn
@pep_signature("ml.umap(dims: Int, on: str, out: str | List<str>) -> List<Row>")
def umap(data, dims=2, on=None, out=None):
    """Dimensionality reduction. `out: \"umap\"` adds `umap_1`, `umap_2`, ... columns. `out: [\"x\", \"y\"]` uses explicit names (length must match `dims`)."""
    import numpy as np
    import umap as umap_lib

    dims = int(dims)

    if out is None:
        return err("umap: out is required")

    df = _to_df(data)

    if on is not None:
        X   = np.stack(df[on].tolist())
        idx = df.index
    else:
        num_cols = _numeric_cols(df)
        sub = df[num_cols].dropna()
        X   = sub.values
        idx = sub.index

    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        reducer = umap_lib.UMAP(n_components=dims, random_state=42)
        embedding = reducer.fit_transform(X)

    df = df.copy()
    if isinstance(out, list):
        if len(out) != dims:
            return err(f"umap: out has {len(out)} names but dims={dims}")
        for i, col in enumerate(out):
            df.loc[idx, col] = embedding[:, i]
    else:
        for i in range(dims):
            df.loc[idx, f"{out}_{i+1}"] = embedding[:, i]
    return ok(_from_df(df))


@pep_fn
@pep_signature("ml.embed(text: str, source: str, model: str, apikey: str) -> List<Num>")
def embed(text, source=None, model=None, apikey=None):
    """Embed a single text string. Use inside `add`: `add(embedding: ml.embed(it.name, ...))`."""
    if source is None:
        return err("embed: source is required (e.g. source: \"deepinfra\" or source: \"local\")")
    if model is None:
        return err("embed: model is required")

    if source == "deepinfra":
        if apikey is None:
            return err("embed: apikey is required for source 'deepinfra'")
        from openai import OpenAI
        client = OpenAI(api_key=apikey, base_url="https://api.deepinfra.com/v1/openai")
        resp = client.embeddings.create(model=model, input=[text], encoding_format="float")
        return resp.data[0].embedding
    elif source == "local":
        from sentence_transformers import SentenceTransformer
        return SentenceTransformer(model).encode([text])[0].tolist()
    else:
        return err(f"embed: unknown source '{source}' (use 'deepinfra' or 'local')")


@pep_fn
@pep_signature("ml.silhouette(on: str) -> List<Row>")
def silhouette(data, on=None):
    """Score current clustering. Prints silhouette score to stderr."""
    from sklearn.metrics import silhouette_score
    import sys

    if on is None:
        return err("silhouette: on is required (cluster column)")

    df = _to_df(data)
    num_cols = [c for c in _numeric_cols(df) if c != on]
    X = df[num_cols].dropna()
    labels = df.loc[X.index, on]
    score = silhouette_score(X, labels)
    print(f"silhouette score: {score:.4f}", file=sys.stderr)
    return ok(data)


def build_ml_env() -> dict:
    return {
        "kmeans":     kmeans,
        "ols":        ols,
        "umap":       umap,
        "embed":      embed,
        "silhouette": silhouette,
    }
