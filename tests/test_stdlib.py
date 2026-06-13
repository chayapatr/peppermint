"""Interpreter-level tests for stdlib functions that had zero coverage,
plus behavioral tests for language features only exercised by grammar tests.
"""

import pytest
from peppermint.parser import parse
from peppermint.interpreter import Interpreter, Ok, Err
from peppermint.stdlib import build_global_env


def run(src: str):
    env = build_global_env()
    return Interpreter(env, quiet=True).run(parse(src))


def val(src: str):
    result = run(src)
    return result.value if isinstance(result, Ok) else result


def unwrap(src: str):
    from peppermint.context import Context
    result = run(src)
    if isinstance(result, Ok):
        v = result.value
        return v.data if isinstance(v, Context) else v
    return result


# ---------------------------------------------------------------------------
# sort
# ---------------------------------------------------------------------------

def test_sort_asc():
    result = unwrap('[{ v: 3 }, { v: 1 }, { v: 2 }] |> sort(by: "v")')
    assert [r["v"] for r in result] == [1, 2, 3]

def test_sort_desc():
    result = unwrap('[{ v: 3 }, { v: 1 }, { v: 2 }] |> sort(by: "v", dir: "desc")')
    assert [r["v"] for r in result] == [3, 2, 1]

def test_sort_stable_preserves_other_fields():
    result = unwrap('[{ v: 2, name: "b" }, { v: 1, name: "a" }] |> sort(by: "v")')
    assert result[0]["name"] == "a"
    assert result[1]["name"] == "b"


# ---------------------------------------------------------------------------
# select
# ---------------------------------------------------------------------------

def test_select_keeps_named_fields():
    result = unwrap('[{ a: 1, b: 2, c: 3 }] |> select("a", "b")')
    assert result == [{"a": 1, "b": 2}]

def test_select_missing_field_skipped():
    result = unwrap('[{ a: 1 }] |> select("a", "z")')
    assert result == [{"a": 1}]

def test_select_computed_field():
    result = unwrap('[{ a: 1, b: 2 }] |> select("a", doubled: it.b * 2)')
    assert result == [{"a": 1, "doubled": 4}]

def test_select_only_computed():
    result = unwrap('[{ x: 5 }] |> select(y: it.x + 10)')
    assert result == [{"y": 15}]


# ---------------------------------------------------------------------------
# rename
# ---------------------------------------------------------------------------

def test_rename_field():
    result = unwrap('[{ x: 42 }] |> rename(x: "y")')
    assert result == [{"y": 42}]

def test_rename_preserves_other_fields():
    result = unwrap('[{ a: 1, b: 2 }] |> rename(a: "x")')
    assert result[0] == {"x": 1, "b": 2}

def test_rename_multiple_rows():
    result = unwrap('[{ v: 1 }, { v: 2 }] |> rename(v: "value")')
    assert [r["value"] for r in result] == [1, 2]
    assert all("v" not in r for r in result)


# ---------------------------------------------------------------------------
# concat
# ---------------------------------------------------------------------------

def test_concat_two_lists():
    result = val('[1, 2] |> concat([3, 4])')
    assert result == [1, 2, 3, 4]

def test_concat_tables():
    result = val('[{ v: 1 }] |> concat([{ v: 2 }])')
    assert isinstance(result, list)
    assert len(result) == 2
    assert result[0]["v"] == 1
    assert result[1]["v"] == 2

def test_concat_with_empty():
    result = val('[1, 2, 3] |> concat([])')
    assert result == [1, 2, 3]


# ---------------------------------------------------------------------------
# unique
# ---------------------------------------------------------------------------

def test_unique_by_field_keeps_first():
    result = unwrap('[{ k: "a", v: 1 }, { k: "a", v: 2 }, { k: "b", v: 3 }] |> unique(by: "k")')
    assert len(result) == 2
    assert result[0] == {"k": "a", "v": 1}
    assert result[1]["k"] == "b"

def test_unique_no_by_deduplicates_rows():
    result = unwrap('[{ v: 1 }, { v: 1 }, { v: 2 }] |> unique()')
    assert result == [{"v": 1}, {"v": 2}]

def test_unique_all_distinct():
    result = unwrap('[{ v: 1 }, { v: 2 }, { v: 3 }] |> unique(by: "v")')
    assert len(result) == 3


# ---------------------------------------------------------------------------
# first / last
# ---------------------------------------------------------------------------

def test_first_returns_first_element():
    assert val('[10, 20, 30] |> first()') == 10

def test_first_empty_returns_none():
    assert val('[] |> first()') is None

def test_last_returns_last_element():
    assert val('[10, 20, 30] |> last()') == 30

def test_last_empty_returns_none():
    assert val('[] |> last()') is None

def test_first_single_element():
    assert val('[42] |> first()') == 42

def test_first_on_table():
    result = val('[{ v: 1 }, { v: 2 }] |> first()')
    assert result == {"v": 1}


# ---------------------------------------------------------------------------
# cross
# ---------------------------------------------------------------------------

def test_cross_expands_rows():
    result = unwrap('[{ model: "m1" }] |> cross("seed", [1, 2, 3])')
    assert len(result) == 3
    assert all(r["model"] == "m1" for r in result)
    assert [r["seed"] for r in result] == [1, 2, 3]

def test_cross_multiple_base_rows():
    result = unwrap('[{ x: 1 }, { x: 2 }] |> cross("y", ["a", "b"])')
    assert len(result) == 4

def test_cross_preserves_all_fields():
    result = unwrap('[{ a: 1, b: 2 }] |> cross("c", ["x", "y"])')
    assert all("a" in r and "b" in r and "c" in r for r in result)


# ---------------------------------------------------------------------------
# flatten
# ---------------------------------------------------------------------------

def test_flatten_scalar_items():
    result = unwrap('[{ id: 1, tags: ["a", "b"] }, { id: 2, tags: ["c"] }] |> flatten("tags")')
    assert len(result) == 3
    assert result[0] == {"id": 1, "value": "a"}
    assert result[1] == {"id": 1, "value": "b"}
    assert result[2] == {"id": 2, "value": "c"}

def test_flatten_dict_items():
    result = unwrap('[{ items: [{ v: 10 }, { v: 20 }] }] |> flatten("items")')
    assert len(result) == 2
    assert result[0]["v"] == 10
    assert result[1]["v"] == 20

def test_flatten_empty_list_skips_row():
    result = unwrap('[{ id: 1, xs: [] }, { id: 2, xs: [9] }] |> flatten("xs")')
    assert len(result) == 1
    assert result[0]["id"] == 2


# ---------------------------------------------------------------------------
# save
# ---------------------------------------------------------------------------

def test_save_csv(tmp_path):
    import csv
    out = str(tmp_path / "out.csv")
    run(f'[{{ a: 1, b: 2 }}, {{ a: 3, b: 4 }}] |> save("{out}")')
    with open(out) as f:
        rows = list(csv.DictReader(f))
    assert rows[0]["a"] == "1"
    assert rows[1]["b"] == "4"

def test_save_json(tmp_path):
    import json
    out = str(tmp_path / "out.json")
    run(f'[{{ x: 10 }}, {{ x: 20 }}] |> save("{out}")')
    with open(out) as f:
        data = json.load(f)
    assert len(data) == 2
    assert data[0]["x"] == 10

def test_save_returns_original_data(tmp_path):
    out = str(tmp_path / "out.csv")
    result = run(f'[{{ v: 7 }}] |> save("{out}")')
    assert isinstance(result, Ok)


# ---------------------------------------------------------------------------
# to_str / to_float / to_int
# ---------------------------------------------------------------------------

def test_to_str_int():
    assert val('str(42)') == "42"

def test_to_str_float():
    assert val('str(3.14)') == "3.14"

def test_to_str_in_add():
    result = unwrap('[{ n: 5 }] |> add(label: str(it.n))')
    assert result[0]["label"] == "5"

def test_to_float_string():
    assert val('float("3.14")') == pytest.approx(3.14)

def test_to_float_int():
    assert val('float(5)') == pytest.approx(5.0)

def test_to_int_float():
    assert val('int(3.9)') == 3

def test_to_int_string():
    assert val('int("42")') == 42

def test_to_int_none_returns_none():
    assert val('int(none)') is None


# ---------------------------------------------------------------------------
# slice
# ---------------------------------------------------------------------------

def test_slice_middle():
    result = val('[10, 20, 30, 40, 50] |> slice(1, 3)')
    assert result == [20, 30, 40]  # inclusive end

def test_slice_from_start():
    result = val('[1, 2, 3, 4] |> slice(0, 1)')
    assert result == [1, 2]

def test_slice_single_element():
    result = val('[10, 20, 30] |> slice(2, 2)')
    assert result == [30]


# ---------------------------------------------------------------------------
# len
# ---------------------------------------------------------------------------

def test_len_list():
    assert val('len([1, 2, 3])') == 3

def test_len_empty():
    assert val('len([])') == 0

def test_len_string_list():
    assert val('len(["a", "b"])') == 2


# ---------------------------------------------------------------------------
# Boolean operators: and / or / not
# ---------------------------------------------------------------------------

def test_and_both_true():
    assert val('true and true') is True

def test_and_short_circuits_on_false():
    assert val('false and true') is False

def test_or_first_true():
    assert val('true or false') is True

def test_or_both_false():
    assert val('false or false') is False

def test_not_true():
    assert val('not true') is False

def test_not_false():
    assert val('not false') is True

def test_and_with_comparisons():
    assert val('(1 < 2) and (3 < 4)') is True

def test_or_with_comparisons():
    assert val('(1 > 2) or (3 < 4)') is True

def test_and_in_filter():
    result = unwrap('[{ a: 1, b: 2 }, { a: 3, b: 4 }, { a: 1, b: 5 }] |> filter(it.a == 1 and it.b > 3)')
    assert len(result) == 1
    assert result[0] == {"a": 1, "b": 5}

def test_or_in_filter():
    result = unwrap('[{ v: 1 }, { v: 5 }, { v: 10 }] |> filter(it.v == 1 or it.v == 10)')
    assert len(result) == 2
    assert [r["v"] for r in result] == [1, 10]


# ---------------------------------------------------------------------------
# ns declaration
# ---------------------------------------------------------------------------

def test_ns_field_access():
    assert val("""
ns math {
  pi = 3.14159
}
math.pi
""") == pytest.approx(3.14159)

def test_ns_function_call():
    assert val("""
ns utils {
  double = x -> x * 2
}
utils.double(5)
""") == 10

def test_ns_multiple_members():
    result = val("""
ns cfg {
  threshold = 18
  label = "adult"
}
cfg.threshold
""")
    assert result == 18

def test_ns_function_uses_ns_constant():
    result = val("""
ns rules {
  limit = 100
  over = x -> x > 100
}
rules.over(150)
""")
    assert result is True
