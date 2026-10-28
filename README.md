# /starting-five — NBA Collect Starting 5 Contest

A Claude skill that picks one player per position (PG, SG, SF, PF, C) for the current NBA slate, choosing the player with the highest expected **Topps NBA Collect "Scoring 2026"** points.

## What it does
1. **Picks the slate automatically.** From 11:00 PM Pacific it uses the next day's games; otherwise it uses today's. It takes no date input and won't run other dates.
2. **Updates history.** Scores every eligible player from new box scores and records team possessions.
3. **Pulls live injuries** from ESPN, then runs a **breaking-headline check** on the picks and runners-up.
4. **Projects every player in every game:**
   `EV = P(plays) × avg Topps score × defense-vs-position × opponent same-position matchup × teammate usage × pace`
5. **Runs the picker twice** and requires identical output.

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
In Claude Code, run:

```
/plugin marketplace add mmc7676/starting-five
/plugin install starting-five@human0-marketplace
```

Then run `/starting-five`.

## Data
`skills/starting-five/data/`:
- `SCWPOS.json`: eligible players by position.
- `games.json`: per-game Topps scores starting Oct 24, 2026.
- `pace.json`: team possessions per game.

## Limitations
- Player eligibility comes from one collector's Base Tier 1 cards, so it is not the full Topps checklist.
- Projections rest on thin early-season samples, and the matchup weights are priors until enough history exists to fit them.
- Not affiliated with or endorsed by Topps, Fanatics, the NBA or ESPN.

## License
MIT
