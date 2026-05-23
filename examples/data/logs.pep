# 06_logs.pep — log analysis: filter errors, classify latency

load("examples/logs.csv")
  |> filter(it.status != 200)
  |> add(severity: match(it.latency_ms, > 500: "critical", > 200: "slow", _: "normal"))
  |> sort(by: "latency_ms", dir: "desc")
  |> print()
