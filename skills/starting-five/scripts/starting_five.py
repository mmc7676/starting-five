#!/usr/bin/env python3
"""NBA Collect Starting 5 Contest picker, v2 with matchup adjustments.

Usage: starting_five.py SCWPOS.json games.json slate.json injuries.json pace.json [prior.json]
                        [--out=picks/YYYY-MM-DD.json --date=YYYY-MM-DD --version=X.Y.Z --params=params.json]
  prior.json    : {player: {season, g, topps_pg}}  last season's per-game Topps baseline (optional)
  pace.json     : {date: {team: possessions}}  from box-score team_stats
  games.json    : [{"player","pos","date","team","opp","score"}, ...]  Topps rubric score per game
  slate.json    : [["HOME","AWAY",p_home_win], ...] games on the slate (p_home_win optional, 0-1)
  injuries.json : {"Player": {"status": "Out|Day-To-Day", "comment": "..."}}

For every eligible player in every slate game:
  EV = P(self plays) x base x DvP x opp_matchup x usage x pace x minutes
  minutes     = blowout x back-to-back expected-minutes ratio
                blowout: P(blowout) = 0.05 + 0.60 x ((p_fav - 0.5) / 0.5), p_fav = favorite's win prob;
                in a blowout starters keep BLOWOUT_MIN_RATIO of their minutes (26/36)
                back-to-back: team also played the previous date in pace.json -> x B2B_RATIO
  pace        = expected game possessions / possessions in the games that produced base;
                team pace shrunk toward league pace with K_PACE pseudo-games
  base        = blend of this season's mean and last season's per-game Topps score:
                (n x current + w x prior) / (n + w), w = K_PRIOR x min(1, prior games / 20);
                players without a prior regress toward the position mean of last-season priors with K_PRIOR/2 pseudo-games
  DvP         = points the opponent allows to this position vs league average,
                shrunk toward 1.0 with K_DVP pseudo-games
  opp_matchup = expectation over whether the opponent's best player at the SAME
                position plays: P_j x (1 - ALPHA x (s_j - 1)) + (1 - P_j) x 1,
                s_j = that defender's avg / league avg at the position
  usage       = zero-sum one-ball redistribution: 1 + BETA x vacated x (my share of active team production) / my avg
  lineup      = top EV per position; teammates are NOT penalized (one player's scoring feeds another's assists)
ALPHA is fitted on history once there are at least FIT_MIN rows; until then the prior is used.
"""
import json, sys, re
from collections import defaultdict

K_DVP, ALPHA_PRIOR, BETA, FIT_MIN, K_PACE = 10, 0.10, 0.15, 150, 5
BLOWOUT_MIN_RATIO, B2B_RATIO = 26 / 36, 0.95
K_PRIOR = 8  # pseudo-games of last-season record
_args = [a for a in sys.argv[1:] if not a.startswith('--')]
_opts = dict(a[2:].split('=', 1) for a in sys.argv[1:] if a.startswith('--') and '=' in a)
pos_f, games_f, slate_f, inj_f, pace_f = _args[0:5]
PRIOR = json.load(open(_args[5])) if len(_args) > 5 else {}
TUNABLE = {'ALPHA_PRIOR', 'BETA', 'K_DVP', 'K_PACE', 'K_PRIOR', 'BLOWOUT_MIN_RATIO', 'B2B_RATIO'}
if 'params' in _opts:  # tuned parameters (params.json written by tune.py) override the priors
    for k, v in json.load(open(_opts['params'])).items():
        if k in TUNABLE: globals()[k] = v
PACE = json.load(open(pace_f))
P = json.load(open(pos_f))['players']
G = json.load(open(games_f))
slate = [tuple(g) for g in json.load(open(slate_f))]
from datetime import date, timedelta
INJ = json.load(open(inj_f))

def p_play(name):
    i = INJ.get(name)
    if not i: return 0.97, 'not listed'
    st, c = i['status'].lower(), i.get('comment', '').lower()
    if st == 'out': return 0.0, 'Out'
    if re.search(r'probable|practiced in full|fully participated', c): return 0.9, 'DTD-probable'
    if 'questionable' in c: return 0.5, 'DTD-questionable'
    if 'doubtful' in c: return 0.25, 'DTD-doubtful'
    if re.search(r'ruled out|did not return', c): return 0.35, 'DTD-ruled out last game'
    return 0.6, 'DTD'

# player averages and league averages by position
by_p = defaultdict(list)
for r in G: by_p[r['player']].append(r['score'])
cur = {n: sum(s) / len(s) for n, s in by_p.items()}
_ps = defaultdict(list)
for r in G: _ps[r['pos']].append(r['score'])
lg_raw = {p: sum(v) / len(v) for p, v in _ps.items()}
_pp = defaultdict(list)
for n, pr in PRIOR.items():
    if n in P: _pp[P[n]['pos']].append(pr['topps_pg'])
if _pp: lg_raw = {p: sum(v) / len(v) for p, v in _pp.items()}  # unbiased: all rotation players with a prior
def blended(n):
    c, k = cur.get(n), len(by_p.get(n, []))
    pr = PRIOR.get(n)
    if not pr:  # no last-season record (rookie/new): regress toward the position's league mean
        pos = P.get(n, {}).get('pos'); m = lg_raw.get(pos)
        if c is None or m is None: return c
        w = K_PRIOR / 2
        return (k * c + w * m) / (k + w)
    w = K_PRIOR * min(1.0, pr['g'] / 20)
    if c is None: return pr['topps_pg']
    return (k * c + w * pr['topps_pg']) / (k + w)
avg = {n: blended(n) for n in set(cur) | set(PRIOR)}
by_p.update({n: [] for n in PRIOR if n not in by_p})
pos_scores = defaultdict(list)
for r in G: pos_scores[r['pos']].append(r['score'])
lg = {p: sum(s) / len(s) for p, s in pos_scores.items()}

# defense vs position: average score allowed by opponent O to position p, per player-game
allowed = defaultdict(list)
for r in G: allowed[(r['opp'], r['pos'])].append(r['score'])
def dvp(opp, pos):
    s = allowed.get((opp, pos), [])
    if not s or pos not in lg: return 1.0, 0
    raw = (sum(s) / len(s)) / lg[pos]
    return (len(s) * raw + K_DVP) / (len(s) + K_DVP), len(s)

def best_defender(team, pos):
    c = [(avg[n], n) for n, v in P.items() if v['team'] == team and v['pos'] == pos and n in avg]
    return max(c) if c else None

def opp_factor(opp, pos, alpha):
    d = best_defender(opp, pos)
    if not d: return 1.0, None
    a, n = d
    s = min(max(a / lg[pos], 0.0), 2.0)
    pj, _ = p_play(n)
    return pj * (1 - alpha * (s - 1)) + (1 - pj), f'{n} s={s:.2f} P={pj}'

def usage(team, me):
    """One ball: vacated production is redistributed zero-sum, in proportion to each active
    teammate's own production. Total redistributed = BETA x vacated, never more."""
    roster = [(n, avg[n], p_play(n)[0]) for n, v in P.items() if v['team'] == team and n in avg]
    vacated = sum((1 - p) * a for n, a, p in roster if n != me)
    active = sum(p * a for n, a, p in roster)
    if active <= 0 or me not in avg: return 1.0
    my_share = p_play(me)[0] * avg[me] / active
    return 1 + BETA * vacated * my_share / avg[me]

def fit_alpha():
    """Grid-search ALPHA on history: predict each game from the player's other games."""
    if len(G) < FIT_MIN: return ALPHA_PRIOR, f'prior (only {len(G)} rows < {FIT_MIN})'
    best = None
    for a10 in range(0, 31):
        a, err, n = a10 / 100, 0.0, 0
        for r in G:
            others = [x['score'] for x in G if x['player'] == r['player'] and x is not r]
            if not others: continue
            d = best_defender(r['opp'], r['pos'])
            f = 1.0 if not d else 1 - a * (min(max(d[0] / lg[r['pos']], 0), 2) - 1)
            err += (sum(others) / len(others) * f - r['score']) ** 2; n += 1
        if n and (best is None or err / n < best[1]): best = (a, err / n)
    return best[0], f'fitted on {len(G)} rows'

# pace
tp = defaultdict(list)
for d, tm in PACE.items():
    for t, v in tm.items(): tp[t].append(v)
lg_pace = sum(sum(v) for v in tp.values()) / sum(len(v) for v in tp.values())
def team_pace(t):
    v = tp.get(t, [])
    return (sum(v) + K_PACE * lg_pace) / (len(v) + K_PACE)
def game_pace(d, a, b):
    g = PACE.get(d, {})
    return (g[a] + g[b]) / 2 if a in g and b in g else lg_pace
hist_pace = defaultdict(list)
for r in G: hist_pace[r['player']].append(game_pace(r['date'], r['team'], r['opp']))
def pace_factor(n, t, o):
    hp = sum(hist_pace[n]) / len(hist_pace[n]) if hist_pace[n] else lg_pace
    return ((team_pace(t) + team_pace(o)) / 2) / hp

alpha, alpha_src = fit_alpha()
opp_of, pwin = {}, {}
for g in slate:
    h, a = g[0], g[1]
    opp_of[h], opp_of[a] = a, h
    if len(g) > 2 and g[2] is not None: pwin[h], pwin[a] = g[2], 1 - g[2]
YDAY = max(PACE)
def minutes_factor(t):
    pf = max(pwin.get(t, 0.5), 1 - pwin.get(t, 0.5))
    pb = 0.05 + 0.60 * (pf - 0.5) / 0.5
    blow = pb * BLOWOUT_MIN_RATIO + (1 - pb)
    b2b = t in PACE.get(YDAY, {})
    return blow * (B2B_RATIO if b2b else 1.0), pb, b2b
rows = defaultdict(list)
for n, v in P.items():
    t = v['team']
    if t not in opp_of or n not in avg: continue
    ps, why = p_play(n)
    o = opp_of[t]
    dv, dn = dvp(o, v['pos'])
    of, odesc = opp_factor(o, v['pos'], alpha)
    us = usage(t, n)
    pf = pace_factor(n, t, o)
    mf, pb, b2b = minutes_factor(t)
    ev = ps * avg[n] * dv * of * us * pf * mf
    rows[v['pos']].append((round(ev, 1), n, t, o, round(avg[n], 1), len(by_p[n]), ps, why,
                           round(dv, 3), dn, round(of, 3), odesc, round(us, 3), round(pf, 3), round(mf, 3), round(pb, 2), b2b))
print(f'ALPHA={alpha} ({alpha_src}); BETA={BETA} prior; K_DVP={K_DVP}; K_PACE={K_PACE}; league pace={lg_pace:.1f}; B2B = teams that played {YDAY}')
POSL = ['PG', 'SG', 'SF', 'PF', 'C']
top = {pos: sorted(rows.get(pos, []), key=lambda x: (-x[0], x[1]))[:3] for pos in POSL}
for pos in POSL:
    print(f'\n{pos}:')
    for e, n, t, o, a, g, ps, why, dv, dn, of, od, us, pf, mf, pb, b2b in top[pos]:
        print(f'  {n} ({t} vs {o}) EV {e} | avg {a}/{g}g x P {ps} [{why}] x DvP {dv} (n={dn}) '
              f'x opp {of} [{od}] x usage {us} x pace {pf} x minutes {mf} [P(blowout)={pb}{", B2B" if b2b else ""}]')
pick = {p: (top[p][0][1] if top[p] else None) for p in POSL}
print(f"\nLINEUP EV {sum(top[p][0][0] for p in POSL if top[p]):.1f}")
print('PICKS', json.dumps(pick))
if 'out' in _opts:  # write-once model pick record (the model's picks only, never a user's)
    rec = {'date': _opts.get('date'), 'model_version': _opts.get('version'), 'picks': {}, 'top3': {},
           'lineup_ev': round(sum(top[p][0][0] for p in POSL if top[p]), 1),
           'params': {'ALPHA': alpha, 'BETA': BETA, 'K_DVP': K_DVP, 'K_PACE': K_PACE, 'K_PRIOR': K_PRIOR,
                      'BLOWOUT_MIN_RATIO': round(BLOWOUT_MIN_RATIO, 4), 'B2B_RATIO': B2B_RATIO},
           'inputs': {'slate': json.load(open(slate_f)), 'injuries': INJ}}
    keys = ['ev', 'player', 'team', 'opp', 'base', 'games', 'p_play', 'injury', 'dvp', 'dvp_n',
            'opp_matchup', 'opp_defender', 'usage', 'pace', 'minutes', 'p_blowout', 'b2b']
    for p in POSL:
        rows3 = [dict(zip(keys, r)) for r in top[p]]
        rec['top3'][p] = rows3
        rec['picks'][p] = rows3[0] if rows3 else None
    json.dump(rec, open(_opts['out'], 'w'), indent=1)
    print('WROTE', _opts['out'])
