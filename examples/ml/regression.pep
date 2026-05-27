use ml
use viz

# OLS regression: predict revenue from all other numeric columns.
# Prints R² and coefficients, then shows residuals vs predicted.

load("examples/sales.csv")
  |> ml.ols(on: "revenue", out: "predicted")
  |> viz.scatter(
    x: "predicted",
    y: "residual",
    display: { axes }
  )
