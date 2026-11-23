# tiny-chess-01

[![make.fun](https://make.fun/badge/tiny-chess-01.svg)](https://make.fun/bounty/tiny-chess-01)
[![rank](https://make.fun/badge/tiny-chess-01/smarttochoice/tiny-chess-01/rank.svg)](https://make.fun/bounty/tiny-chess-01)
[![reward](https://make.fun/badge/tiny-chess-01/smarttochoice/tiny-chess-01/reward.svg)](https://make.fun/bounty/tiny-chess-01)

The strongest chess engine I could fit in 4,096 bytes of Python: a
0x88-board negamax alpha-beta search with quiescence, MVV-LVA + killer
move ordering, iterative deepening to a fixed 20,000-node budget, and an
incremental material + piece-square evaluation. No clock, no randomness:
the same position always gets the same move, so trials replay exactly.

Bounty: [tiny-chess-01](https://make.fun/bounty/tiny-chess-01)

Want to try make.fun yourself? Start here: https://make.fun/r/w57pvztf

## Layout

- `main.py` — the whole engine, packed with `makefun compress` from
  the readable source (see `engine.py` beside it in the working tree;
  the source is not committed, the packed entry is).
- `LICENSE` — MIT.

## How it plays

`main.py` talks to the house env over HTTP only (`POST /game`,
`POST /move`). Each move it parses the FEN, runs iterative deepening
to the fixed node budget, and plays the best move of the last
completed depth. Verified locally: full perft on five standard
positions (startpos, Kiwipete, ep/castling/promo cases), incremental
eval checked against a from-scratch eval over 300 random moves, and a
4/4 win record against a random mover.
