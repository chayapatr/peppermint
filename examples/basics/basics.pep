# 01_basics.pep — filtering, adding fields, sorting

result = load("examples/people.csv")
  |> filter(it.age > 18)
  |> add(score_pct: it.score * 100)
  |> add(tier: match(it.income, > 80000: "high", > 40000: "medium", _: "low"))
  |> sort(by: "income", dir: "desc")

print(result)
