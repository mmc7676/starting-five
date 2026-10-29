#!/usr/bin/env python3
"""Back-tune the model's priors on its OWN logged picks vs. actual results.

Usage: tune.py REPO_DATA_DIR SCRIPTS_DIR [--min-days=7]
  REPO_DATA_DIR must contain SCWPOS.json games.json pace.json prior.json picks/ results/
For every day with both picks/DAY.json and results/DAY.json it re-runs the picker with each
candidate parameter set, using only history from BEFORE that day plus that day's logged
slate and injuries, and scores the lineup it would have chosen with the day's actual Topps
scores. Objective: maximize the mean actual lineup total (equivalently minimize regret).
Writes params.json only when at least --min-days days exist and a candidate beats the
current parameters; otherwise it reports and changes nothing.
"""
import json, os, sys, subprocess, tempfile, itertools
D, S = sys.argv[1], sys.argv[2]
mind = int(next((a.split('=')[1] for a in sys.argv[3:] if a.startswith('--min-days=')), 7))
days = sorted(f[:-5] for f in os.listdir(os.path.join(D, 'picks'))
              if os.path.exists(os.path.join(D, 'results', f)))
print(f'{len(days)} scored model-pick days available: {days}')
if len(days) < mind:
    sys.exit(f'Not tuning: need at least {mind} scored days. params.json unchanged.')
G = json.load(open(os.path.join(D, 'games.json')))
PACE = json.load(open(os.path.join(D, 'pace.json')))
cur = json.load(open(os.path.join(D, 'params.json'))) if os.path.exists(os.path.join(D, 'params.json')) else {}
grid = {'B2B_RATIO': [0.90, 0.95, 1.0], 'BLOWOUT_MIN_RATIO': [0.65, 26 / 36, 0.80],
        'BETA': [0.10, 0.15, 0.25], 'K_PRIOR': [4, 8, 16]}
tmp = tempfile.mkdtemp()
def run(day, params):
    rec = json.load(open(os.path.join(D, 'picks', day + '.json')))
    g = [r for r in G if r['date'] < day]
    pc = {k: v for k, v in PACE.items() if k < day}
    f = {n: os.path.join(tmp, n) for n in ['g.json', 'pc.json', 's.json', 'i.json', 'p.json', 'o.json']}
    json.dump(g, open(f['g.json'], 'w')); json.dump(pc, open(f['pc.json'], 'w'))
    json.dump(rec['inputs']['slate'], open(f['s.json'], 'w')); json.dump(rec['inputs']['injuries'], open(f['i.json'], 'w'))
    json.dump(params, open(f['p.json'], 'w'))
    subprocess.run([sys.executable, os.path.join(S, 'starting_five.py'), os.path.join(D, 'SCWPOS.json'), f['g.json'],
                    f['s.json'], f['i.json'], f['pc.json'], os.path.join(D, 'prior.json'),
                    f'--out={f["o.json"]}', f'--date={day}', f'--params={f["p.json"]}'],
                   check=True, capture_output=True)
    picks = json.load(open(f['o.json']))['picks']
    actual = {r['player']: r['score'] for r in G if r['date'] == day}
    return sum(actual.get(v['player'], 0) for v in picks.values() if v)
def score(params): return sum(run(d, params) for d in days) / len(days)
base = score(cur)
best = (base, cur)
for combo in itertools.product(*grid.values()):
    pr = dict(zip(grid.keys(), combo))
    sc = score(pr)
    if sc > best[0] + 1e-9: best = (sc, pr)
print(f'current params mean lineup actual: {base:.1f}; best: {best[0]:.1f} with {best[1]}')
if best[1] is not cur:
    json.dump(best[1], open(os.path.join(D, 'params.json'), 'w'), indent=1)
    print('WROTE params.json')
else:
    print('Current params already best. params.json unchanged.')
