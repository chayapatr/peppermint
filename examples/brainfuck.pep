use str

# find matching ] for [ at position ip (scan forward)
find_close = (prog, ip, depth) -> match(depth,
  == 0: ip,
  _: match(str.at(prog, ip),
    == "[": find_close(prog, ip + 1, depth + 1),
    == "]": find_close(prog, ip + 1, depth - 1),
    _: find_close(prog, ip + 1, depth)
  )
)

# find matching [ for ] at position ip (scan backward)
find_open = (prog, ip, depth) -> match(depth,
  == 0: ip,
  _: match(str.at(prog, ip),
    == "]": find_open(prog, ip - 1, depth + 1),
    == "[": find_open(prog, ip - 1, depth - 1),
    _: find_open(prog, ip - 1, depth)
  )
)

# helper to build next state
next = (state, tape, ptr, ip) -> {tape: tape, ptr: ptr, ip: ip, prog: state.prog, output: state.output}

# one brainfuck step
step = state -> match(str.at(state.prog, state.ip),
  == "+": next(state, set(state.tape, state.ptr, get(state.tape, state.ptr) + 1), state.ptr, state.ip + 1),
  == "-": next(state, set(state.tape, state.ptr, get(state.tape, state.ptr) - 1), state.ptr, state.ip + 1),
  == ">": next(state, state.tape, state.ptr + 1, state.ip + 1),
  == "<": next(state, state.tape, state.ptr - 1, state.ip + 1),
  == ".": {tape: state.tape, ptr: state.ptr, ip: state.ip + 1, prog: state.prog, output: str.join([state.output, str.char(get(state.tape, state.ptr))], "")},
  == "[": next(state, state.tape, state.ptr, match(get(state.tape, state.ptr), == 0: find_close(state.prog, state.ip + 1, 1), _: state.ip + 1)),
  == "]": next(state, state.tape, state.ptr, match(get(state.tape, state.ptr), == 0: state.ip + 1, _: find_open(state.prog, state.ip - 1, 1))),
  _: next(state, state.tape, state.ptr, state.ip + 1)
)

# run until ip reaches end of program
run = (state, len) -> match(state.ip,
  == len: state,
  _: run(step(state), len)
)

# Hello World
prog = "++++++++[>++++[>++>+++>+++>+<<<<-]>+>+>->>+[<]<-]>>.>---.+++++++..+++.>>.<-.<.+++.------.--------.>>+.>++."
init = {tape: [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], ptr: 0, ip: 0, prog: prog, output: ""}
result = run(init, str.length(prog))
print(result.output)
