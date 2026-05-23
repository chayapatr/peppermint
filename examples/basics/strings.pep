# 09_strings.pep — string operations with use str

use str

# String functions work best inside a pipe
"hello"   |> str.upper()   |> print()
"WORLD"   |> str.lower()   |> print()
"  hi  "  |> str.trim()    |> print()

# Use inside a data pipe — it.field passes through str functions
load("examples/people.csv")
  |> add(name_upper: str.upper(it.name))
  |> add(region_short: str.slice(it.region, 0, 2))
  |> select("name")
  |> print()
