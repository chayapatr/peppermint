# interpolation.pep — string interpolation with {expr}

name = "alice"
age = 30

# Basic variable interpolation
print("{name} is {age} years old")

# Expression inside interpolation
print("in 10 years: {age + 10}")

# In a data pipe — it.field access
load("examples/people.csv")
  |> add(label: "{it.name} ({it.region})")
  |> add(summary: "age {it.age}, income {it.income}")
  |> select("label", "summary")
  |> print()
