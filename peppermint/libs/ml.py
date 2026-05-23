"""
Peppermint ml stdlib — uses bridge for type conversion.
Python functions receive plain list[dict], return plain list[dict].
"""
from __future__ import annotations
from ..bridge import ok, err, get_rows, make_list, from_python, to_python


def _to_df(data):
    import pandas as pd
    return pd.DataFrame(get_rows(data))


def _from_df(df):
    import pandas as pd
    rows = df.to_dict(orient="records")
    return make_list(rows)


def _numeric_cols(df):
    import numpy as np
    return df.select_dtypes(include=[np.number]).columns.tolist()


def _eval_arg(arg, interp, env):
    from ..interpreter import PmRange
    if interp and arg is not None and not isinstance(arg, (int, float, str, bool, PmRange)):
        try:
            return interp.eval(arg, env)
        except Exception:
            return arg
    return arg


def kmeans(data, k=5, _interp=None, _env=None, **_):
    try:
        from sklearn.cluster import KMeans
        from sklearn.metrics import silhouette_score
        from ..interpreter import PmRange
        import sys

        k = _eval_arg(k, _interp, _env)
        df = _to_df(data)
        num_cols = _numeric_cols(df)
        X = df[num_cols].dropna()

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
        df.loc[X.index, "cluster"] = labels.astype(int)
        return ok(_from_df(df))
    except Exception as e:
        return err(str(e))


def ols(data, target=None, _interp=None, _env=None, **_):
    try:
        from sklearn.linear_model import LinearRegression

        target = _eval_arg(target, _interp, _env)
        df = _to_df(data)
        num_cols = [c for c in _numeric_cols(df) if c != target]
        X = df[num_cols].dropna()
        y = df.loc[X.index, target]

        model = LinearRegression()
        model.fit(X, y)
        df = df.copy()
        df.loc[X.index, "predicted"] = model.predict(X)
        return ok(_from_df(df))
    except Exception as e:
        return err(str(e))


def umap(data, dims=2, _interp=None, _env=None, **_):
    try:
        import umap as umap_lib

        dims = int(_eval_arg(dims, _interp, _env))
        df = _to_df(data)
        num_cols = _numeric_cols(df)
        X = df[num_cols].dropna()

        reducer = umap_lib.UMAP(n_components=dims, random_state=42)
        embedding = reducer.fit_transform(X)

        df = df.copy()
        for i in range(dims):
            df.loc[X.index, f"umap{i+1}"] = embedding[:, i]
        return ok(_from_df(df))
    except Exception as e:
        return err(str(e))


def embed(data, col=None, model="all-MiniLM-L6-v2", _interp=None, _env=None, **_):
    try:
        from sentence_transformers import SentenceTransformer

        col = _eval_arg(col, _interp, _env)
        df = _to_df(data)
        texts = df[col].tolist()
        m = SentenceTransformer(model)
        embeddings = m.encode(texts)

        df = df.copy()
        df["embedding"] = list(embeddings)
        return ok(_from_df(df))
    except Exception as e:
        return err(str(e))


def silhouette(data, **_):
    try:
        from sklearn.metrics import silhouette_score
        import sys

        df = _to_df(data)
        if "cluster" not in df.columns:
            return err("silhouette() requires a 'cluster' column — run kmeans first")
        num_cols = [c for c in _numeric_cols(df) if c != "cluster"]
        X = df[num_cols].dropna()
        labels = df.loc[X.index, "cluster"]
        score = silhouette_score(X, labels)
        print(f"silhouette score: {score:.4f}", file=sys.stderr)
        return ok(data)
    except Exception as e:
        return err(str(e))


def build_ml_env() -> dict:
    return {
        "kmeans":     kmeans,
        "ols":        ols,
        "umap":       umap,
        "embed":      embed,
        "silhouette": silhouette,
    }
