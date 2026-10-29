# /starting-five — NBA Collect Daily Starting 5 Contest Lineup Tool

A universal agent skill (Claude Code plugin, Claude.ai skill, ChatGPT skill) that picks one player per position (PG, SG, SF, PF, C) for the current NBA slate, choosing the player with the highest expected **Topps NBA Collect "Scoring 2026"** points.

## What it does
1. **Picks the slate automatically.** From 11:00 PM Pacific it uses the next day's games; otherwise it uses today's. It takes no date input and won't run other dates.
2. **Updates history.** Scores every eligible player from new box scores and records team possessions.
3. **Pulls live injuries** from ESPN, then runs a **breaking-headline check** on the picks and runners-up.
4. **Projects every player in every game** (blowout and back-to-back minutes included):
   `EV = P(plays) × (this season blended with last season's per-game Topps score) × defense-vs-position × opponent same-position matchup × one-ball teammate usage × pace × expected minutes (blowout risk from win probability, back-to-backs)`
5. **Runs the picker twice** and requires identical output.
6. **Logs the model's picks** (never the user's) to `data/picks/`, scores them the next day into `data/results/`, and back-tunes parameters (`scripts/tune.py`, after 7+ scored days) on actual lineup totals.

## Scoring rubric
The rubric matches the totals on Topps cards exactly.

| Stat | Points |
|---|---|
| 2PM | +6 |
| Missed 2PA | −1 |
| 3PM | +10 |
| Missed 3PA | −1 |
| FTM | +2 |
| Missed FT | −2 |
| OREB / DREB | +2 each |
| AST | +4 |
| STL / BLK | +6 each |
| TO | −2 |
| PF | −2 |

## Install
**Claude Code (plugin):**
```
/plugin marketplace add mmc7676/starting-five
/plugin install starting-five@human0-marketplace
```
Then run `/starting-five`.

**ChatGPT (Skills, Business/Enterprise/Edu):** download `starting-five-skill.zip` (the `skills/starting-five/` folder zipped), then Plugins > Skills > Create > Upload from your computer. Ask: "run starting-five".

**Claude.ai:** Settings > Capabilities > Skills > upload the same zip.

## Source of truth
This repo is canonical. Fetched live each run: slate/odds, box scores, injuries, headlines.

| Path | Contents |
|---|---|
| `data/SCWPOS.json` | Eligible players by position (Base Tier 1 cards) |
| `data/prior.json`, `data/raw/` | 2025-26 per-game Topps baseline |
| `data/games.json`, `data/pace.json` | 2026-27 per-game scores and team possessions |
| `data/picks/DATE.json` | Model picks with inputs snapshot (write-once) |
| `data/results/DATE.json` | Model picks vs. actual best lineup |
| `data/params.json` | Tuned parameters (absent = priors) |
| `scripts/` | `starting_five.py`, `score_results.py`, `tune.py` |

## Limitations
- Player eligibility is the standard Topps NBA Collect 26 Base Series 1 (Base Tier 1) card set. Team/position slots with no card stay empty.
- Projections rest on thin early-season samples, and the matchup weights are priors until enough history exists to fit them.
- Not affiliated with or endorsed by Topps, Fanatics, the NBA or ESPN.

## License
MIT
