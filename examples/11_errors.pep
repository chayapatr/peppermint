# Error showcase — run each block one at a time by commenting the others out

people = [
  { name: "alice", age: 30 },
  { name: "bob",   age: 17 }
]

# 1. Field does not exist
people
  |> filter(it.score > 0)

# 2. Undefined variable
# result = missing_data |> filter(it.age > 18)

# 3. Wrong number of args
# double = x -> x * 2
# double(1, 2)

# 4. Parse error — uncomment to see
# x = foo(bar
