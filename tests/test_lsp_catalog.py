from peppermint.lsp.catalog import build_catalog

def test_catalog_has_core_functions():
    cat = build_catalog()
    assert "filter" in cat
    assert "collapse" in cat
    assert cat["filter"]["signature"] is not None
    assert cat["filter"]["doc"] is not None

def test_catalog_has_lib_functions():
    cat = build_catalog()
    assert "env.get" in cat
    assert "math.log" in cat

def test_catalog_ml_prefix():
    cat = build_catalog()
    assert "ml.embed" in cat
    assert cat["ml.embed"]["signature"].startswith("ml.embed(")
