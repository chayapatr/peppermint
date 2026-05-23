use str
use math

get2d = (grid, x, y) -> grid[y * 8 + x]

safe = (grid, x, y) -> match(x,
  < 0: 0, > 7: 0,
  _: match(y, < 0: 0, > 7: 0, _: get2d(grid, x, y))
)

nb_top = (grid, x, y) -> safe(grid, x-1, y-1) + safe(grid, x, y-1) + safe(grid, x+1, y-1)
nb_mid = (grid, x, y) -> safe(grid, x-1, y) + safe(grid, x+1, y)
nb_bot = (grid, x, y) -> safe(grid, x-1, y+1) + safe(grid, x, y+1) + safe(grid, x+1, y+1)
neighbors = (grid, x, y) -> nb_top(grid, x, y) + nb_mid(grid, x, y) + nb_bot(grid, x, y)

next_cell = (grid, x, y) -> (
  cell = get2d(grid, x, y)
  n = neighbors(grid, x, y)
  match(cell,
    1: match(n, 2: 1, 3: 1, _: 0),
    _: match(n, 3: 1, _: 0)
  )
)

next_gen = grid -> mapi(grid, next_cell(grid, it.idx % 8, math.floor(it.idx / 8)))

cell_char = (grid, i) -> match(grid[i], 1: "#", _: ".")
sep = i -> match(i % 8, 0: "\n", _: "")
render = grid -> str.join(mapi(grid, str.join([sep(it.idx), cell_char(grid, it.idx)], "")), "")

run = (grid, n) -> match(n, 0: grid, _: run(next_gen(grid), n - 1))

glider = [
  0, 1, 0, 0, 0, 0, 0, 0,
  0, 0, 1, 0, 0, 0, 0, 0,
  1, 1, 1, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 0, 0
]


f = x -> (
  run(glider, x) |> render |> print
  match(x, < 20: f(x+1), _: 0)
)

f(0)