#!/usr/bin/env python3
"""Statistical treatment of the trips_btc.jsonl setup claims (stdlib only).

1. Loss-cut asymmetry: per-trader one-sided Mann-Whitney U (loss holds < win
   holds), exact sign test across traders, Stouffer combination, and a
   cluster bootstrap CI (resampling traders) for the median hold ratio.
2. Win-rate contrasts (fade vs chase, big-move vs quiet, adds vs single):
   Cochran-Mantel-Haenszel test stratified BY TRADER, so pooled Simpson
   effects from the two hyperactive accounts can't drive the result.
3. Robustness: repeat 1 excluding scratch trips (|price ret| < 0.05%).
"""
import json
import math
import random
from collections import defaultdict

trips = [json.loads(l) for l in open('/home/smoltz/claude/crypto_whales/data/trips_btc.jsonl')]
by = defaultdict(list)
for t in trips:
    by[t['addr']].append(t)


def phi(z):
    return 0.5 * math.erfc(-z / math.sqrt(2))


def mwu_one_sided(xs, ys):
    """P(rank(xs) < rank(ys)) test: one-sided p for xs stochastically smaller.
    Normal approximation with tie correction. Returns (z, p)."""
    n1, n2 = len(xs), len(ys)
    allv = [(v, 0) for v in xs] + [(v, 1) for v in ys]
    allv.sort()
    ranks = {}
    i = 0
    tie_term = 0.0
    rank_sum_x = 0.0
    while i < len(allv):
        j = i
        while j < len(allv) and allv[j][0] == allv[i][0]:
            j += 1
        avg_rank = (i + j + 1) / 2.0     # ranks are 1-based
        t = j - i
        tie_term += t**3 - t
        for k in range(i, j):
            if allv[k][1] == 0:
                rank_sum_x += avg_rank
        i = j
    u1 = rank_sum_x - n1 * (n1 + 1) / 2.0
    n = n1 + n2
    mean = n1 * n2 / 2.0
    var = n1 * n2 / 12.0 * ((n + 1) - tie_term / (n * (n - 1)))
    if var <= 0:
        return 0.0, 0.5
    z = (u1 - mean) / math.sqrt(var)
    return z, phi(z)          # one-sided: small u1 (xs smaller) -> p small


def median(xs):
    s = sorted(xs)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def hold_test(trip_filter=lambda t: True, label=""):
    print(f"\n=== 1. 負け保有 < 勝ち保有 {label} ===")
    print(f"{'addr':<12} {'nW':>3} {'nL':>3} {'ratio':>6} {'z':>6} {'p(one-sided)':>12}")
    zs, ratios, n_shorter = [], [], 0
    n_traders = 0
    for a, ts in by.items():
        ts = [t for t in ts if trip_filter(t)]
        w = [t['hold_h'] for t in ts if t['pnl'] > 0]
        l = [t['hold_h'] for t in ts if t['pnl'] <= 0]
        if len(w) < 3 or len(l) < 3:
            continue
        n_traders += 1
        z, p = mwu_one_sided(l, w)
        r = median(l) / median(w) if median(w) else float('inf')
        ratios.append(r)
        zs.append(z)
        if r < 1:
            n_shorter += 1
        print(f"{a[:10] + '..':<12} {len(w):>3} {len(l):>3} {r:>6.2f} {z:>+6.2f} {p:>12.4g}")
    if not zs:
        print("  (no traders with >= 3 wins and >= 3 losses — nothing to test)")
        return
    # sign test (exact binomial, one-sided: P(X >= n_shorter | p=0.5))
    n = n_traders
    p_sign = sum(math.comb(n, i) for i in range(n_shorter, n + 1)) / 2**n
    # Stouffer
    z_st = sum(zs) / math.sqrt(len(zs))
    p_st = phi(z_st)
    # cluster bootstrap over traders for the median ratio
    rng = random.Random(42)
    boots = []
    for _ in range(10000):
        sample = [ratios[rng.randrange(len(ratios))] for _ in range(len(ratios))]
        boots.append(median(sample))
    boots.sort()
    lo, hi = boots[249], boots[9749]
    print(f"\n  ratio<1 のトレーダー: {n_shorter}/{n}  符号検定 p = {p_sign:.3g}")
    print(f"  Stouffer合成 z = {z_st:+.2f}, p = {p_st:.3g}")
    print(f"  中央値ratio {median(ratios):.2f}, クラスタブートストラップ95%CI "
          f"[{lo:.2f}, {hi:.2f}] (トレーダー単位リサンプル, n={n})")


hold_test()

# robustness: exclude scratches
hold_test(lambda t: abs(t.get('ret_trip', 0.0)) >= 0.0005,
          label="(スクラッチ除外: |値幅| >= 0.05%)")


def aligned(t):
    r = t.get('ret_prior')
    if r is None or r == 0.0:
        return None
    return (r > 0) == (t['side'] == 'L')


def cmh(strata, label, exposed_name, unexposed_name):
    """strata: list of (a,b,c,d) = (win&exp, win&unexp, loss&exp, loss&unexp).
    CMH test + Mantel-Haenszel odds ratio."""
    num = den = 0.0
    or_num = or_den = 0.0
    used = 0
    n_exp = n_unexp = w_exp = w_unexp = 0
    for a, b, c, d in strata:
        n = a + b + c + d
        if n < 2 or (a + c) == 0 or (b + d) == 0 or (a + b) == 0 or (c + d) == 0:
            # stratum with an empty margin contributes nothing
            if n:
                n_exp += a + c; n_unexp += b + d; w_exp += a; w_unexp += b
            continue
        used += 1
        n_exp += a + c; n_unexp += b + d; w_exp += a; w_unexp += b
        num += a - (a + b) * (a + c) / n
        den += (a + b) * (c + d) * (a + c) * (b + d) / (n * n * (n - 1))
        or_num += a * d / n
        or_den += b * c / n
    z = num / math.sqrt(den) if den > 0 else 0.0
    p = 2 * (1 - phi(abs(z)))
    orr = or_num / or_den if or_den else float('inf')
    print(f"\n  {label}")
    print(f"    {exposed_name}: WR {w_exp}/{n_exp} ({w_exp / n_exp:.0%})   "
          f"{unexposed_name}: WR {w_unexp}/{n_unexp} ({w_unexp / n_unexp:.0%})")
    print(f"    CMH(トレーダー層別, {used}層有効): OR_MH = {orr:.2f}, "
          f"z = {z:+.2f}, p(two-sided) = {p:.3g}")


print("\n=== 2. 勝率コントラスト（トレーダー層別CMH; プーリングの錯覚を排除） ===")

def strata_for(pred):
    out = []
    for a, ts in by.items():
        grp = [(t, pred(t)) for t in ts]
        grp = [(t, e) for t, e in grp if e is not None]
        a11 = sum(1 for t, e in grp if e and t['pnl'] > 0)
        b = sum(1 for t, e in grp if not e and t['pnl'] > 0)
        c = sum(1 for t, e in grp if e and t['pnl'] <= 0)
        d = sum(1 for t, e in grp if not e and t['pnl'] <= 0)
        out.append((a11, b, c, d))
    return out

cmh(strata_for(lambda t: (lambda al: None if al is None else not al)(aligned(t))),
    "逆張りエントリー（直前4hと逆方向） vs 順張り", "逆張り", "順張り")
cmh(strata_for(lambda t: None if t.get('ret_prior') is None
               else abs(t['ret_prior']) >= 0.01),
    "大変動後 (|4h|>=1%) vs 静かな時間帯のエントリー", "大変動後", "静穏時")
cmh(strata_for(lambda t: t['n_adds'] > 0),
    "積み増しあり vs 一発エントリー", "積み増し", "一発")
