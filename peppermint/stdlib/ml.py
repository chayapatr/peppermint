from __future__ import annotations
import numpy as np
import pandas as pd
from ..interpreter import Ok, Err, ListValue, PmRange


def _eval(arg, interp, env):
    if interp and arg is not None and not isinstance(arg, (int, float, str, bool, PmRange)):
        try:
            return interp.eval(arg, env)
        except Exception:
            return arg
    return arg


def _to_df(data: ListValue) -> pd.DataFrame:
    return pd.DataFrame(data.rows)


def _from_df(df: pd.DataFrame) -> ListValue:
    rows = df.to_dict(orient="records")
    schema = {k: type(v) for k, v in rows[0].items()} if rows else {}
    return ListValue(rows=rows, schema=schema)


def _numeric_cols(df: pd.DataFrame) -> list[str]:
    return df.select_dtypes(include=[np.number]).columns.tolist()


def kmeans(data: ListValue, k=5, score=None, _interp=None, _env=None, **_) -> Ok | Err:
    try:
        from sklearn.cluster import KMeans
        from sklearn.metrics import silhouette_score

        k = _eval(k, _interp, _env)
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
            import sys
            print(f"kmeans: best k={best_k}, silhouette={best_score:.3f}", file=sys.stderr)
        else:
            model = KMeans(n_clusters=int(k), random_state=42, n_init="auto")
            labels = model.fit_predict(X)

        df = df.copy()
        df.loc[X.index, "cluster"] = labels.astype(int)
        return Ok(_from_df(df))
    except Exception as e:
        return Err(str(e))


def ols(data: ListValue, target=None, _interp=None, _env=None, **_) -> Ok | Err:
    try:
        from sklearn.linear_model import LinearRegression

        target = _eval(target, _interp, _env)
        df = _to_df(data)
        num_cols = [c for c in _numeric_cols(df) if c != target]
        X = df[num_cols].dropna()
        y = df.loc[X.index, target]

        model = LinearRegression()
        model.fit(X, y)
        df = df.copy()
        df.loc[X.index, "predicted"] = model.predict(X)
        return Ok(_from_df(df))
    except Exception as e:
        return Err(str(e))


def umap(data: ListValue, dims=2, _interp=None, _env=None, **_) -> Ok | Err:
    try:
        import umap as umap_lib

        dims = int(_eval(dims, _interp, _env))
        df = _to_df(data)
        num_cols = _numeric_cols(df)
        X = df[num_cols].dropna()

        reducer = umap_lib.UMAP(n_components=dims, random_state=42)
        embedding = reducer.fit_transform(X)

        df = df.copy()
        for i in range(dims):
            df.loc[X.index, f"umap{i+1}"] = embedding[:, i]
        return Ok(_from_df(df))
    except Exception as e:
        return Err(str(e))


def embed(data: ListValue, col: str, model: str = "all-MiniLM-L6-v2", **_) -> Ok | Err:
    try:
        from sentence_transformers import SentenceTransformer

        df = _to_df(data)
        texts = df[col].tolist()
        m = SentenceTransformer(model)
        embeddings = m.encode(texts)

        df = df.copy()
        df["embedding"] = list(embeddings)
        return Ok(_from_df(df))
    except Exception as e:
        return Err(str(e))


def silhouette(data: ListValue, **_) -> Ok | Err:
    try:
        from sklearn.metrics import silhouette_score

        df = _to_df(data)
        if "cluster" not in df.columns:
            return Err("silhouette() requires a 'cluster' column — run kmeans first")
        num_cols = [c for c in _numeric_cols(df) if c != "cluster"]
        X = df[num_cols].dropna()
        labels = df.loc[X.index, "cluster"]
        score = silhouette_score(X, labels)
        import sys
        print(f"silhouette score: {score:.4f}", file=sys.stderr)
        return Ok(data)
    except Exception as e:
        return Err(str(e))


def build_ml_env() -> dict:
    return {
        "kmeans":     kmeans,
        "ols":        ols,
        "umap":       umap,
        "embed":      embed,
        "silhouette": silhouette,
    }
