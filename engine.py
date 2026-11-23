# tiny-chess-01: 0x88 negamax alpha-beta + quiescence, MVV-LVA + killer
# ordering, iterative deepening to a fixed node budget (deterministic:
# no clock, no randomness), incremental material + piece-square eval.
# Talks to the make.fun env over HTTP only. Standard library only.
import json, os, sys, urllib.request, urllib.error

# piece codes: 1 pawn, 2 knight, 3 bishop, 4 rook, 5 queen, 6 king.
# Sign is colour: white +, black -.
V = [0, 100, 320, 330, 500, 900, 20000]
KN = (-33, -31, -18, -14, 14, 18, 31, 33)
KG = (-17, -16, -15, -1, 1, 15, 16, 17)
BD = (-17, -15, 15, 17)
RD = (-16, -1, 1, 16)
INF = 1000000
MATE = 100000
CAP = 30000          # fixed node budget per move
MAXD = 9             # iterative-deepening ceiling

# Piece-square tables, rows rank 1 -> rank 8, my own values.
PST = [
 [0,0,0,0,0,0,0,0, 5,10,10,-20,-20,10,10,5, 5,-5,-10,0,0,-10,-5,5,
  0,0,0,20,20,0,0,0, 5,5,10,25,25,10,5,5, 10,10,20,30,30,20,10,10,
  50,50,50,50,50,50,50,50, 0,0,0,0,0,0,0,0],
 [-50,-40,-30,-30,-30,-30,-40,-50, -40,-20,0,0,0,0,-20,-40,
  -30,0,10,15,15,10,0,-30, -30,5,15,20,20,15,5,-30,
  -30,5,15,20,20,15,5,-30, -30,0,10,15,15,10,0,-30,
  -40,-20,0,0,0,0,-20,-40, -50,-40,-30,-30,-30,-30,-40,-50],
 [-20,-10,-10,-10,-10,-10,-10,-20, -10,0,0,0,0,0,0,-10,
  -10,0,5,10,10,5,0,-10, -10,5,5,10,10,5,5,-10,
  -10,0,10,10,10,10,0,-10, -10,10,10,10,10,10,10,-10,
  -10,5,0,0,0,0,5,-10, -20,-10,-10,-10,-10,-10,-10,-20],
 [0,0,0,0,0,0,0,0, 5,10,10,10,10,10,10,5,
  -5,0,0,0,0,0,0,-5, -5,0,0,0,0,0,0,-5,
  -5,0,0,0,0,0,0,-5, -5,0,0,0,0,0,0,-5,
  -5,0,0,0,0,0,0,-5, 0,0,0,5,5,0,0,0],
 [-20,-10,-10,-5,-5,-10,-10,-20, -10,0,0,0,0,0,0,-10,
  -10,0,5,5,5,5,0,-10, -5,0,5,5,5,5,0,-5,
  0,0,5,5,5,5,0,-5, -10,5,5,5,5,5,0,-10,
  -10,0,5,0,0,0,0,-10, -20,-10,-10,-5,-5,-10,-10,-20],
 [20,30,10,0,0,10,30,20, 20,20,0,0,0,0,20,20,
  -10,-20,-20,-20,-20,-20,-20,-10, -20,-30,-30,-40,-40,-30,-30,-20,
  -30,-40,-40,-50,-50,-40,-40,-30, -30,-40,-40,-50,-50,-40,-40,-30,
  -30,-40,-40,-50,-50,-40,-40,-30, -30,-40,-40,-50,-50,-40,-40,-30],
]

b = [0] * 128          # 0x88 board
s = 1                  # side to move: 1 white, -1 black
cr = 0                 # castling rights: 1 K, 2 Q, 4 k, 8 q
ep = -1                # en-passant square or -1
wk = bk = 4            # king squares
sc = 0                 # eval from White's view (material + PST)
N = 0                  # nodes searched this move
K1 = [[0, 0] for _ in range(64)]   # killer moves per ply


def pv(p, sq):
    a = abs(p)
    r = sq >> 4
    i = r * 8 + (sq & 7) if p > 0 else (7 - r) * 8 + (sq & 7)
    v = V[a] + PST[a - 1][i]
    return v if p > 0 else -v


def full():
    global sc
    sc = 0
    for i, p in enumerate(b):
        if p and not i & 0x88:
            sc += pv(p, i)


def parse(fen):
    global s, cr, ep, wk, bk
    parts = fen.split()
    b[:] = [0] * 128
    r = 7
    f = 0
    for ch in parts[0]:
        if ch == "/":
            r -= 1
            f = 0
        elif ch.isdigit():
            f += int(ch)
        else:
            p = "PNBRQK".index(ch.upper()) + 1
            if ch.islower():
                p = -p
            sq = r * 16 + f
            b[sq] = p
            if abs(p) == 6:
                if p > 0:
                    wk = sq
                else:
                    bk = sq
            f += 1
    s = 1 if parts[1] == "w" else -1
    cr = 0
    if len(parts) > 2:
        for ch in parts[2]:
            cr |= {"K": 1, "Q": 2, "k": 4, "q": 8}.get(ch, 0)
    ep = -1
    if len(parts) > 3 and parts[3] != "-":
        ep = (ord(parts[3][0]) - 97) + (int(parts[3][1]) - 1) * 16
    full()


def attacked(sq, by):
    t = sq - 15 * by
    if not t & 0x88 and b[t] == by:
        return True
    t = sq - 17 * by
    if not t & 0x88 and b[t] == by:
        return True
    for d in KN:
        t = sq + d
        if not t & 0x88 and b[t] == 2 * by:
            return True
    for d in KG:
        t = sq + d
        if not t & 0x88 and b[t] == 6 * by:
            return True
    for d in BD:
        t = sq + d
        while not t & 0x88:
            q = b[t]
            if q:
                if q == 3 * by or q == 5 * by:
                    return True
                break
            t += d
    for d in RD:
        t = sq + d
        while not t & 0x88:
            q = b[t]
            if q:
                if q == 4 * by or q == 5 * by:
                    return True
                break
            t += d
    return False


def gen(caps=False):
    """Pseudo-legal moves for side s as ints f | t<<7 | promo<<14.
    caps=True keeps captures (and promotions) only."""
    global ep
    ms = []
    ap = ms.append
    for i, p in enumerate(b):
        if not p or p * s <= 0 or i & 0x88:
            continue
        a = abs(p)
        if a == 1:
            d = 16 * s
            t = i + d
            if not t & 0x88 and b[t] == 0:
                if (t >> 4) in (0, 7):
                    if not caps:
                        for pr in (5, 4, 3, 2):
                            ap(i | t << 7 | pr << 14)
                    else:
                        for pr in (5, 4, 3, 2):
                            ap(i | t << 7 | pr << 14)
                elif not caps:
                    ap(i | t << 7)
                    if (i >> 4) == (1 if s > 0 else 6) and b[i + 2 * d] == 0:
                        ap(i | (i + 2 * d) << 7)
            for dd in (d - 1, d + 1):
                t = i + dd
                if t & 0x88:
                    continue
                q = b[t]
                if q and q * s < 0:
                    if (t >> 4) in (0, 7):
                        for pr in (5, 4, 3, 2):
                            ap(i | t << 7 | pr << 14)
                    else:
                        ap(i | t << 7)
                elif t == ep and q == 0:
                    ap(i | t << 7)
        elif a == 2 or a == 6:
            for d in KN if a == 2 else KG:
                t = i + d
                if t & 0x88:
                    continue
                q = b[t]
                if q == 0:
                    if not caps:
                        ap(i | t << 7)
                elif q * s < 0:
                    ap(i | t << 7)
        else:
            for d in BD if a == 3 else RD if a == 4 else BD + RD:
                t = i + d
                while not t & 0x88:
                    q = b[t]
                    if q == 0:
                        if not caps:
                            ap(i | t << 7)
                    else:
                        if q * s < 0:
                            ap(i | t << 7)
                        break
                    t += d
    if not caps:
        if s > 0:
            if cr & 1 and b[5] == 0 and b[6] == 0 and b[7] == 4 and b[4] == 6 \
                    and not attacked(4, -1) and not attacked(5, -1) and not attacked(6, -1):
                ap(4 | 6 << 7)
            if cr & 2 and b[3] == 0 and b[2] == 0 and b[1] == 0 and b[0] == 4 and b[4] == 6 \
                    and not attacked(4, -1) and not attacked(3, -1) and not attacked(2, -1):
                ap(4 | 2 << 7)
        else:
            if cr & 4 and b[117] == 0 and b[118] == 0 and b[119] == -4 and b[116] == -6 \
                    and not attacked(116, 1) and not attacked(117, 1) and not attacked(118, 1):
                ap(116 | 118 << 7)
            if cr & 8 and b[115] == 0 and b[114] == 0 and b[113] == 0 and b[112] == -4 and b[116] == -6 \
                    and not attacked(116, 1) and not attacked(115, 1) and not attacked(114, 1):
                ap(116 | 114 << 7)
    return ms


def mk(m):
    global s, cr, ep, wk, bk, sc
    f = m & 127
    t = (m >> 7) & 127
    pr = (m >> 14) & 7
    p = b[f]
    c = b[t]
    cs = -1
    if abs(p) == 1 and t == ep and c == 0:   # en passant capture
        cs = t - 16 * s
        c = b[cs]
    u = (c, cs, cr, ep, p)
    sc -= pv(p, f)
    if c:
        sc -= pv(c, cs if cs >= 0 else t)
    b[f] = 0
    np = pr * s if pr else p
    b[t] = np
    sc += pv(np, t)
    if abs(p) == 6:                           # king move: castle + track
        if p > 0:
            wk = t
        else:
            bk = t
        if t - f == 2:
            b[t - 1] = b[t + 1]
            b[t + 1] = 0
            sc -= pv(b[t - 1], t + 1)
            sc += pv(b[t - 1], t - 1)
        elif f - t == 2:
            b[t + 1] = b[t - 2]
            b[t - 2] = 0
            sc -= pv(b[t + 1], t - 2)
            sc += pv(b[t + 1], t + 1)
    if cs >= 0:
        b[cs] = 0
    if f == 4 or t == 4:
        cr &= ~3
    if f == 0 or t == 0:
        cr &= ~2
    if f == 7 or t == 7:
        cr &= ~1
    if f == 116 or t == 116:
        cr &= ~12
    if f == 112 or t == 112:
        cr &= ~8
    if f == 119 or t == 119:
        cr &= ~4
    ep = (f + t) // 2 if abs(p) == 1 and abs(t - f) == 32 else -1
    s = -s
    return u


def un(m, u):
    global s, cr, ep, wk, bk, sc
    f = m & 127
    t = (m >> 7) & 127
    pr = (m >> 14) & 7
    c, cs, ocr, oep, p = u
    s = -s
    np = b[t]
    sc -= pv(np, t)
    if c:
        sc += pv(c, cs if cs >= 0 else t)
    b[t] = c if cs < 0 else 0   # normal capture: victim back on t; ep: t stays empty
    if cs >= 0:
        b[cs] = c
    if abs(p) == 6:
        if t - f == 2:
            b[t + 1] = b[t - 1]
            b[t - 1] = 0
            sc += pv(b[t + 1], t + 1)
            sc -= pv(b[t + 1], t - 1)
        elif f - t == 2:
            b[t - 2] = b[t + 1]
            b[t + 1] = 0
            sc += pv(b[t - 2], t - 2)
            sc -= pv(b[t - 2], t + 1)
        if p > 0:
            wk = f
        else:
            bk = f
    b[f] = p
    sc += pv(p, f)
    cr = ocr
    ep = oep


class Stop(Exception):
    pass


def legal(caps=False):
    ms = []
    for m in gen(caps):
        u = mk(m)
        if not attacked(wk if s < 0 else bk, s):
            ms.append(m)
        un(m, u)
    return ms


def oscore(m, pl):
    f = m & 127
    t = (m >> 7) & 127
    pr = (m >> 14) & 7
    c = b[t]
    sc_ = 0
    if c:
        sc_ += V[abs(c)] * 10 - V[abs(b[f])] // 32
    elif abs(b[f]) == 1 and t == ep:
        sc_ += 100
    if pr:
        sc_ += 900 + V[pr]
    if m == K1[pl][0]:
        sc_ += 500
    elif m == K1[pl][1]:
        sc_ += 400
    return sc_


def Q(a, be, pl):
    global N
    N += 1
    if N > CAP:
        raise Stop
    st = sc * s
    if st >= be:
        return be
    if st > a:
        a = st
    for m in sorted(legal(True), key=lambda m: oscore(m, pl), reverse=True):
        u = mk(m)
        v = -Q(-be, -a, pl + 1)
        un(m, u)
        if v >= be:
            return be
        if v > a:
            a = v
    return a


def S(d, a, be, pl):
    global N
    N += 1
    if N > CAP:
        raise Stop
    if d <= 0:
        return Q(a, be, pl)
    ms = legal()
    if not ms:
        return -MATE + pl if attacked(wk if s > 0 else bk, -s) else 0
    ms.sort(key=lambda m: oscore(m, pl), reverse=True)
    for m in ms:
        u = mk(m)
        v = -S(d - 1, -be, -a, pl + 1)
        un(m, u)
        if v >= be:
            if not b[(m >> 7) & 127]:
                if K1[pl][0] != m:
                    K1[pl][1] = K1[pl][0]
                    K1[pl][0] = m
            return be
        if v > a:
            a = v
    return a


def choose():
    global N
    N = 0
    ms = legal()
    if len(ms) == 1:
        return ms[0]
    ms.sort(key=lambda m: oscore(m, 0), reverse=True)
    best = ms[0]
    for d in range(1, MAXD + 1):
        try:
            ba = -INF
            bm = None
            for m in ms:
                u = mk(m)
                v = -S(d - 1, -INF, -ba, 1)
                un(m, u)
                if v > ba:
                    ba = v
                    bm = m
            if bm is not None:
                best = bm
                ms.remove(bm)
                ms.insert(0, bm)
        except Stop:
            break
    return best


def uci(m):
    f = m & 127
    t = (m >> 7) & 127
    pr = (m >> 14) & 7
    r = chr(97 + (f & 7)) + str((f >> 4) + 1) + chr(97 + (t & 7)) + str((t >> 4) + 1)
    if pr:
        r += "nbrq"[pr - 2]
    return r


ENV = os.environ.get("MAKEFUN_ENV_URL")


def post(path, body):
    req = urllib.request.Request(
        ENV + path, data=json.dumps(body).encode(),
        headers={"content-type": "application/json"})
    try:
        with urllib.request.urlopen(req) as res:
            return json.load(res)
    except urllib.error.HTTPError as e:
        sys.exit(f"{path}: HTTP {e.code} {e.read().decode(errors='replace')}")


def main():
    if not ENV:
        sys.exit("MAKEFUN_ENV_URL is not set")
    while True:
        g = post("/game", {})
        if g["status"] == "done":
            break
        while g["status"] == "your_move":
            parse(g["fen"])
            g = post("/move", {"game": g["game"], "move": uci(choose())})
        print(f"game {g['game']}: {g['outcome']} by {g['reason']}", file=sys.stderr)
    print(f"done: {g.get('wins')} won, {g.get('draws')} drawn, {g.get('losses')} lost",
          file=sys.stderr)


if __name__ == "__main__":
    main()
