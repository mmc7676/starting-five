#!/usr/bin/env python3
"""NBA Collect Starting 5 Contest picker, v2 with matchup adjustments.

Usage: starting_five.py SCWPOS.json games.json slate.json injuries.json pace.json
  pace.json     : {date: {team: possessions}}  from box-score team_stats
  games.json    : [{"player","pos","date","team","opp","score"}, ...]  Topps rubric score per game
  slate.json    : [["HOME","AWAY"], ...] games on the slate
  injuries.json : {"Player": {"status": "Out|Day-To-Day", "comment": "..."}}

For every eligible player in every slate game:
  EV = P(self plays) x base x DvP x opp_matchup x usage x pace
  pace        = expected game possessions / possessions in the games that produced base;
                team pace shrunk toward league pace with K_PACE pseudo-games
  base        = player's mean Topps score
  DvP         = points the opponent allows to this position vs league average,
                shrunk toward 1.0 with K_DVP pseudo-games
  opp_matchup = expectation over whether the opponent's best player at the SAME
                position plays: P_j x (1 - ALPHA x (s_j - 1)) + (1 - P_j) x 1,
                s_j = that defender's avg / league avg at the position
  usage       = 1 + BETA x sum over teammates of (1 - P_k) x avg_k / team-avg total
ALPHA is fitted on history once there are at least FIT_MIN rows; until then the prior is used.
"""
import json, sys, re
from collections import defaultdict

K_DVP, ALPHA_PRIOR, BETA, FIT_MIN, K_PACE = 10, 0.10, 0.15, 150, 5
pos_f, games_f, slate_f, inj_f, pace_f = sys.argv[1:6]
PACE = json.load(open(pace_f))
P = json.load(open(pos_f))['players']
G = json.load(open(games_f))
slate = [tuple(g) for g in json.load(open(slate_f))]
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
avg = {n: sum(s) / len(s) for n, s in by_p.items()}
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
    mates = [(n, avg[n]) for n, v in P.items() if v['team'] == team and n in avg and n != me]
    tot = sum(a for _, a in mates) + avg.get(me, 0)
    if tot <= 0: return 1.0
    return 1 + BETA * sum((1 - p_play(n)[0]) * a for n, a in mates) / tot

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
    hp = sum(hist_pace[n]) / len(hist_pace[n])
    return ((team_pace(t) + team_pace(o)) / 2) / hp

alpha, alpha_src = fit_alpha()
opp_of = {}
for h, a in slate: opp_of[h], opp_of[a] = a, h
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
    ev = ps * avg[n] * dv * of * us * pf
    rows[v['pos']].append((round(ev, 1), n, t, o, round(avg[n], 1), len(by_p[n]), ps, why,
                           round(dv, 3), dn, round(of, 3), odesc, round(us, 3), round(pf, 3)))
print(f'ALPHA={alpha} ({alpha_src}); BETA={BETA} prior; K_DVP={K_DVP}; K_PACE={K_PACE}; league pace={lg_pace:.1f}')
pick = {}
for pos in ['PG', 'SG', 'SF', 'PF', 'C']:
    r = sorted(rows.get(pos, []), key=lambda x: (-x[0], x[1]))
    pick[pos] = r[0][1] if r else None
    print(f'\n{pos}:')
    for e, n, t, o, a, g, ps, why, dv, dn, of, od, us, pf in r[:3]:
        print(f'  {n} ({t} vs {o}) EV {e} | avg {a}/{g}g x P {ps} [{why}] x DvP {dv} (n={dn}) '
              f'x opp {of} [{od}] x usage {us} x pace {pf}')
print('\nPICKS', json.dumps(pick))
