#!/usr/bin/env python3
"""Score a logged MODEL pick record against what actually happened.

Usage: score_results.py SCWPOS.json games.json picks/YYYY-MM-DD.json results/YYYY-MM-DD.json

Reads the day's actual Topps scores from games.json (rows with that date) and writes:
  - each model pick's actual score vs. its projected EV
  - the actual best (highest-scoring) eligible player per position that night
  - the model lineup total vs. the best possible lineup total ("regret")
This is the data used to back-tune the model's priors. Only model picks are logged and scored.
"""
import json, sys
pos_f, games_f, picks_f, out_f = sys.argv[1:5]
P = json.load(open(pos_f))['players']
G = json.load(open(games_f))
rec = json.load(open(picks_f))
d = rec['date']
day = [r for r in G if r['date'] == d]
if not day:
    sys.exit(f'No scored games for {d} in {games_f}; update history first.')
actual = {r['player']: r['score'] for r in day}
POSL = ['PG', 'SG', 'SF', 'PF', 'C']
res = {'date': d, 'model_version': rec.get('model_version'), 'positions': {}}
model_total = best_total = 0
for p in POSL:
    pk = rec['picks'].get(p)
    name = pk['player'] if pk else None
    a = actual.get(name)  # None = did not play or missing from box score
    cands = sorted(((s, n) for n, s in actual.items() if P.get(n, {}).get('pos') == p), reverse=True)
    best = {'player': cands[0][1], 'score': cands[0][0]} if cands else None
    res['positions'][p] = {'pick': name, 'projected_ev': pk['ev'] if pk else None,
                           'actual': a, 'error': (a - pk['ev']) if (a is not None and pk) else None,
                           'best': best, 'pick_rank': next((i + 1 for i, (_, n) in enumerate(cands) if n == name), None)}
    model_total += a or 0
    best_total += best['score'] if best else 0
res['model_total'] = model_total
res['best_total'] = best_total
res['regret'] = best_total - model_total
json.dump(res, open(out_f, 'w'), indent=1)
print(json.dumps(res, indent=1))
