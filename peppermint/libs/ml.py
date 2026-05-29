"""
Peppermint ml stdlib — uses bridge for type conversion.
Python functions receive plain list[dict], return plain list[dict].
"""
from __future__ import annotations
from ..bridge import ok, err, get_rows, pep_fn_lazy
from ..stdlib.core import pep_signature, _as_ctx


def _to_df(data):
    import pandas as pd
    return pd.DataFrame(get_rows(data))


def _from_df(df):
    return df.to_dict(orient="records")


def _numeric_cols(df):
    import numpy as np
    return df.select_dtypes(include=[np.number]).columns.tolist()


def _save_model(model, path):
    import pickle, sys
    with open(path, "wb") as f:
        pickle.dump(model, f)
    print(f"model saved to {path}", file=sys.stderr)


def _load_model(path):
    import pickle
    with open(path, "rb") as f:
        return pickle.load(f)


def _resolve_model(model, save_model, load_model):
    """Return (path_to_load_or_None, path_to_save_or_None).
    `model` shorthand: load if file exists, else fit and save."""
    import os
    if model is not None:
        if os.path.exists(model):
            return model, None
        return None, model
    return load_model, save_model


@pep_fn_lazy
@pep_signature('ml.kmeans(k: Int | Range, on: str, out: str, model?: str, method?: "silhouette" | "elbow", save_model?: str, load_model?: str) -> List<Row>')
def kmeans(data, k=None, on=None, out=None, model=None, method="silhouette", save_model=None, load_model=None):
    """K-means clustering.

`on`: vector column name (omit to use all numeric cols).
`k`: number of clusters, or a range (e.g. `2..8`) for auto-selection.
`out`: name for the cluster label column.
`method`: auto-selection strategy when `k` is a range — `"silhouette"` (default) maximizes cohesion; `"elbow"` picks the knee in inertia curve.
`model`: load if file exists, else fit and save (shorthand for `save_model`/`load_model`)."""
    import numpy as np
    from sklearn.cluster import KMeans
    from sklearn.metrics import silhouette_score
    from ..interpreter import PmRange
    import sys

    if out is None:
        return err("kmeans: out is required")

    load_path, save_path = _resolve_model(model, save_model, load_model)

    df = _to_df(data)

    if on is not None:
        X = np.stack(df[on].tolist())
        idx = df.index
    else:
        num_cols = _numeric_cols(df)
        sub = df[num_cols].dropna()
        X = sub.values
        idx = sub.index

    if load_path is not None:
        fitted = _load_model(load_path)
        labels = fitted.predict(X)
    else:
        if k is None:
            return err("kmeans: k is required")
        if isinstance(k, PmRange):
            ks = range(k.start, k.end + 1)
            models = {}
            for ki in ks:
                m = KMeans(n_clusters=ki, random_state=42, n_init="auto")
                m.fit(X)
                models[ki] = m

            if method == "elbow":
                inertias = {ki: m.inertia_ for ki, m in models.items()}
                ks_list = sorted(inertias)
                diffs = [inertias[ks_list[i]] - inertias[ks_list[i+1]] for i in range(len(ks_list)-1)]
                diffs2 = [diffs[i] - diffs[i+1] for i in range(len(diffs)-1)]
                best_k = ks_list[diffs2.index(max(diffs2)) + 1]
                print(f"kmeans: elbow k={best_k}, inertia={inertias[best_k]:.1f}", file=sys.stderr)
            else:
                best_k, best_score = None, -1
                for ki, m in models.items():
                    lbls = m.labels_
                    if len(set(lbls)) > 1:
                        s = silhouette_score(X, lbls)
                        if s > best_score:
                            best_k, best_score = ki, s
                print(f"kmeans: best k={best_k}, silhouette={best_score:.3f}", file=sys.stderr)

            fitted = models[best_k]
            labels = fitted.labels_
        else:
            fitted = KMeans(n_clusters=int(k), random_state=42, n_init="auto")
            labels = fitted.fit_predict(X)

        if save_path is not None:
            _save_model(fitted, save_path)

    from ..context import Context
    df = df.copy()
    df.loc[idx, out] = labels.astype(int)
    ctx = _as_ctx(data) or Context(data=[])
    final_k = best_k if isinstance(k, PmRange) else (int(k) if k is not None else None)
    return ok(ctx.with_data(_from_df(df)).with_artifact("kmeans", {"model": fitted, "k": final_k}))


@pep_fn_lazy
@pep_signature("ml.ols(on: str, out: str, model?: str, save_model?: str, load_model?: str) -> List<Row>")
def ols(data, on=None, out=None, model=None, save_model=None, load_model=None):
    """OLS regression.

`on`: target column. Uses all other numeric columns as features.
`out`: name for the predicted values column. Also adds a `residual` column.
Prints R² and per-feature coefficients to stderr.
`model`: load if file exists, else fit and save."""
    from sklearn.linear_model import LinearRegression
    import sys

    if on is None:
        return err("ols: on is required (target column)")
    if out is None:
        return err("ols: out is required")

    load_path, save_path = _resolve_model(model, save_model, load_model)

    df = _to_df(data)
    num_cols = [c for c in _numeric_cols(df) if c != on]
    X = df[num_cols].dropna()

    if load_path is not None:
        fitted = _load_model(load_path)
    else:
        y = df.loc[X.index, on]
        fitted = LinearRegression()
        fitted.fit(X, y)
        r2 = fitted.score(X, y)
        coeffs = dict(zip(num_cols, fitted.coef_))
        print(f"ols: R²={r2:.4f}  intercept={fitted.intercept_:.4f}", file=sys.stderr)
        for col, coef in coeffs.items():
            print(f"     {col}: {coef:.4f}", file=sys.stderr)
        if save_path is not None:
            _save_model(fitted, save_path)

    from ..context import Context
    predicted = fitted.predict(X)
    df = df.copy()
    df.loc[X.index, out] = predicted
    if load_path is None:
        y = df.loc[X.index, on]
        df.loc[X.index, "residual"] = y.values - predicted
    ctx = _as_ctx(data) or Context(data=[])
    artifact = {"model": fitted}
    if load_path is None:
        artifact["r2"] = fitted.score(X, df.loc[X.index, on])
        artifact["coefficients"] = dict(zip(num_cols, fitted.coef_))
    return ok(ctx.with_data(_from_df(df)).with_artifact("ols", artifact))


@pep_fn_lazy
@pep_signature("ml.umap(dims: Int, on: str, out: str | List<str>, neighbors?: Int, min_dist?: Num, metric?: str, model?: str, save_model?: str, load_model?: str) -> List<Row>")
def umap(data, dims=2, on=None, out=None, neighbors=15, min_dist=0.1, metric="euclidean", model=None, save_model=None, load_model=None):
    """Dimensionality reduction via UMAP.

`dims`: output dimensions (default: 2).
`on`: vector column (omit to use all numeric cols).
`out`: column name prefix (e.g. `"umap"` → `umap_1`, `umap_2`) or list of exact names.
`neighbors`: local vs global structure (default: 15).
`min_dist`: point spread (default: 0.1).
`metric`: distance metric (default: `"euclidean"`).
`model`: load if file exists, else fit and save."""
    import numpy as np
    import umap as umap_lib

    dims     = int(dims)
    neighbors = int(neighbors)
    min_dist  = float(min_dist)

    if out is None:
        return err("umap: out is required")

    load_path, save_path = _resolve_model(model, save_model, load_model)

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
        if load_path is not None:
            reducer = _load_model(load_path)
            embedding = reducer.transform(X)
        else:
            reducer = umap_lib.UMAP(
                n_components=dims,
                n_neighbors=neighbors,
                min_dist=min_dist,
                metric=metric,
                random_state=42,
            )
            embedding = reducer.fit_transform(X)
            if save_path is not None:
                _save_model(reducer, save_path)

    from ..context import Context
    df = df.copy()
    if isinstance(out, list):
        if len(out) != dims:
            return err(f"umap: out has {len(out)} names but dims={dims}")
        for i, col in enumerate(out):
            df.loc[idx, col] = embedding[:, i]
    else:
        for i in range(dims):
            df.loc[idx, f"{out}_{i+1}"] = embedding[:, i]
    ctx = _as_ctx(data) or Context(data=[])
    return ok(ctx.with_data(_from_df(df)).with_artifact("umap", {"model": reducer}))


_client_cache: dict = {}

@pep_fn_lazy
@pep_signature("ml.embed(text: str, source: str, model: str, apikey: str) -> List<Num>")
def embed(text, source=None, model=None, apikey=None, _row_cache=None, **_):
    """Embed a single text string. Use inside `add`.

`source`: `"deepinfra"` or `"local"`.
`model`: model name (e.g. `"Qwen/Qwen3-Embedding-4B"` or a local SentenceTransformer name).
`apikey`: required for `"deepinfra"`.

Example: `add(embedding: ml.embed(it.text, source: "deepinfra", model: "...", apikey: env.get("KEY")), concurrent: 50, retry: 3)`"""
    if source is None:
        raise ValueError("embed: source is required (e.g. source: \"deepinfra\" or source: \"local\")")
    if model is None:
        raise ValueError("embed: model is required")

    if _row_cache is not None:
        from ..cache import cache_key_for_row
        rk = cache_key_for_row({"text": text}, f"ml.embed(source={source},model={model})")
        cached = _row_cache.get_row(rk)
        if cached is not None:
            return cached

    if source == "deepinfra":
        if apikey is None:
            raise ValueError("embed: apikey is required for source 'deepinfra'")
        from openai import OpenAI
        ck = ("deepinfra", apikey)
        if ck not in _client_cache:
            _client_cache[ck] = OpenAI(api_key=apikey, base_url="https://api.deepinfra.com/v1/openai")
        resp = _client_cache[ck].embeddings.create(model=model, input=[text], encoding_format="float")
        result = resp.data[0].embedding
    elif source == "local":
        from sentence_transformers import SentenceTransformer
        ck = ("local", model)
        if ck not in _client_cache:
            _client_cache[ck] = SentenceTransformer(model)
        result = _client_cache[ck].encode([text])[0].tolist()
    else:
        raise ValueError(f"embed: unknown source '{source}' (use 'deepinfra' or 'local')")

    if _row_cache is not None:
        _row_cache.set_row(rk, result)
    return result



@pep_fn_lazy
@pep_signature("ml.llm(prompt: str, source: str, model: str, apikey?: str, format?: str) -> str | Any")
def llm(prompt, source=None, model=None, apikey=None, format=None, _row_cache=None, **_):
    """Run a single LLM call. Use inside `add`.

`source`: `"deepinfra"` or `"openai"`.
`model`: model name (e.g. `"meta-llama/Llama-3.3-70B-Instruct"`).
`apikey`: required for `"deepinfra"` and `"openai"`.
`format`: `"json"` — strips markdown fences, parses response as JSON, raises on parse failure."""
    if source is None:
        raise ValueError("llm: source is required (e.g. source: \"deepinfra\" or source: \"openai\")")
    if model is None:
        raise ValueError("llm: model is required")

    if _row_cache is not None:
        from ..cache import cache_key_for_row
        rk = cache_key_for_row({"prompt": prompt}, f"ml.llm(source={source},model={model},format={format})")
        cached = _row_cache.get_row(rk)
        if cached is not None:
            return cached

    if source in ("deepinfra", "openai"):
        if apikey is None and source == "deepinfra":
            raise ValueError("llm: apikey is required for source 'deepinfra'")
        from openai import OpenAI
        if source == "deepinfra":
            cache_key = ("deepinfra_llm", apikey)
            if cache_key not in _client_cache:
                _client_cache[cache_key] = OpenAI(api_key=apikey, base_url="https://api.deepinfra.com/v1/openai")
        else:
            cache_key = ("openai_llm", apikey)
            if cache_key not in _client_cache:
                _client_cache[cache_key] = OpenAI(api_key=apikey)
        client = _client_cache[cache_key]
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
        )
        content = resp.choices[0].message.content

        if format == "json":
            import json, re
            cleaned = re.sub(r"^```json\s*|^```\s*|```$", "", content.strip(), flags=re.MULTILINE).strip()
            try:
                result = json.loads(cleaned)
            except json.JSONDecodeError:
                result = None  # let @until retry
        else:
            result = content
    else:
        raise ValueError(f"llm: unknown source '{source}' (use 'deepinfra' or 'openai')")

    if _row_cache is not None and result is not None:
        _row_cache.set_row(rk, result)
    return result


@pep_signature("ml.dist(a: List<Num>, b: List<Num>, metric?: str) -> Num")
def dist(a, b, metric="cosine", **_):
    """Distance between two vectors. Returns a scalar. Use inside `add`.

`metric`: `"cosine"` (default) or `"euclidean"`.

Example: `add(dist: ml.dist(it.embedding, it.centroid, metric: "cosine"))`"""
    import numpy as np
    A = np.array(a, dtype=float)
    B = np.array(b, dtype=float)
    if metric == "cosine":
        denom = np.linalg.norm(A) * np.linalg.norm(B)
        return float(1.0 - np.dot(A, B) / max(denom, 1e-10))
    elif metric == "euclidean":
        return float(np.linalg.norm(A - B))
    else:
        raise ValueError(f"dist: unknown metric '{metric}' (use 'cosine' or 'euclidean')")


@pep_fn_lazy
@pep_signature("ml.silhouette(on: str) -> List<Row>")
def silhouette(data, on=None):
    """Silhouette score for current clustering.

`on`: cluster label column. Uses all other numeric columns as features.
Prints score to stderr and passes data through unchanged."""
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
        "dist":       dist,
        "llm":        llm,
    }
