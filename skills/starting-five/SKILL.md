---
name: starting-five
description: NBA Collect Starting 5 Contest. Picks the highest expected Topps "Scoring 2026" player at PG, SG, SF, PF and C for the current NBA slate, using live injuries, headline checks, matchups, pace, blowout and back-to-back minutes. Logs the model's picks and back-tunes on results. Use for /starting-five or "starting five picks".
---

# NBA Collect Starting 5 Contest (/starting-five)

Pick one player per position (PG, SG, SF, PF, C) from teams on the slate, maximizing expected Topps "Scoring 2026" points after all games finish. This skill works in any agent that can read files, browse the web, and run Python (Claude Code, Claude.ai, ChatGPT). Wherever a step names a tool, use whatever equivalent your platform has.

## Source of truth
The GitHub repo **mmc7676/starting-five** is the single source of truth. Everything in `skills/starting-five/` is canonical:

| Path | Contents | Changes |
|---|---|---|
| `data/SCWPOS.json` | Eligible players: Topps NBA Collect 26 Base Tier 1 cards, player -> {pos, team}. Empty team/position slots have no card. | When cards are added or players are traded |
| `data/prior.json`, `data/raw/` | Last season's (2025-26) per-game Topps baseline per player | Once per season |
| `data/games.json` | One row per player-game: {player, pos, date, team, opp, score} | After every night's games |
| `data/pace.json` | {date: {team: possessions}}. Also used to detect back-to-backs | After every night's games |
| `data/picks/YYYY-MM-DD.json` | The MODEL's picks for that day, with full inputs. Write-once. | Daily |
| `data/results/YYYY-MM-DD.json` | Actual Topps scores of the model's picks vs. the best possible lineup | Morning after |
| `data/params.json` | Tuned parameters, written only by `scripts/tune.py` | When tuning improves the model |
| `scripts/starting_five.py` | Picker | Versioned releases |
| `scripts/score_results.py` | Scores a pick record against actual results | Versioned releases |
| `scripts/tune.py` | Back-tunes parameters on the model's picks vs. results | Versioned releases |

Pulled live every run and never stored, except as a snapshot inside that day's pick record: the schedule and win probabilities, box scores, injury reports, breaking headlines, and anything the user reports directly.

**Only the model's picks are ever logged.** If the user plays a different lineup, do not record it anywhere. Back-tuning uses the model's own picks and the actual results only.

## Slate rule (no date argument)
1. Get the current time and convert it to America/Los_Angeles.
2. At 11:00 PM PT or later, slate = tomorrow's games. Otherwise slate = today's games.
3. Refuse any other date and state this rule. If the time is unavailable, use today's date and say so.

## Step 0: load the repo
Use the first of these that works, and say which one you used:
1. `git clone https://github.com/mmc7676/starting-five` (or `git pull` in an existing clone), then work in `skills/starting-five/`.
2. Read each file over the web from `https://raw.githubusercontent.com/mmc7676/starting-five/main/skills/starting-five/<path>`. List the `data/picks` and `data/results` folders through the GitHub contents API: `https://api.github.com/repos/mmc7676/starting-five/contents/skills/starting-five/data/picks`.
3. The copy of this skill folder you were installed with, which may be older. Say so.
If none of these is available, stop and ask the user to attach the skill folder. Never rebuild the player list from memory.

## Scoring rubric (matches Topps card totals exactly: Caleb Wilson 66, Walker Kessler 47, Brook Lopez 49)
+6 per 2PM, -1 per missed 2PA, +10 per 3PM, -1 per missed 3PA, +2 per FTM, -2 per missed FT, +2 per OREB, +2 per DREB, +4 per AST, +6 per STL, +6 per BLK, -2 per TO, -2 per PF.

## Procedure
1. **Slate.** Get tonight's NBA games: a sports-data tool if you have one, otherwise the ESPN or NBA.com scoreboard. Keep games starting on the slate date in PT. Write `slate.json` as `[[home, away, p_home_win], ...]`, where p_home_win is the home team's win probability (0 to 1) from the feed or a betting line. Use null when there isn't one.
2. **Update history.** For every completed game after the last date in `data/games.json`, get the box score:
   - Score EVERY player who appears in `data/SCWPOS.json` with the rubric and append rows `{player, pos, date, team, opp, score}` to `data/games.json`.
   - Add both teams' possessions to `data/pace.json`.
   - List box-score players who aren't in SCWPOS. Never guess a position.
   - Box scores from some feeds omit players. A missing player is not proof he didn't play.
3. **Score yesterday's model picks.** For each `data/picks/DAY.json` with no matching `data/results/DAY.json` whose games are now in `games.json`, run:
   `python3 scripts/score_results.py data/SCWPOS.json data/games.json data/picks/DAY.json data/results/DAY.json`
4. **Tune.** Run `python3 scripts/tune.py data scripts`. It changes `data/params.json` only when at least 7 scored days exist and a candidate setting beats the current one on actual lineup totals. Otherwise it reports and changes nothing.
5. **Live injuries.** Fetch https://www.espn.com/nba/injuries, plus the official NBA injury report if reachable, and write `injuries.json` as `{name: {status, comment}}`. Add anything the user reports in the conversation as Out or Day-To-Day, with a comment naming the user as the source.
6. **Run the picker:**
   `python3 scripts/starting_five.py data/SCWPOS.json data/games.json slate.json injuries.json data/pace.json data/prior.json --params=data/params.json --out=data/picks/DATE.json --date=DATE --version=VERSION`
   Omit `--params` if `data/params.json` doesn't exist.
7. **Headline check** (injury pages lag). Search breaking news from the last 48 hours for the 5 picks and each position's runner-up: injury, illness, rest, suspension, personal leave, trade, death. Use a sub-agent if your platform has one. Tonight's team injury reports count as sources.
   - Produce a table: Player | Status | headline | report date | source URL. Never invent a URL; write "No news found" when nothing turns up.
   - Cross-check every report against `data/games.json`. An injury reported BEFORE a game the player then played in is resolved; ignore it. Results from earlier seasons are a common trap; check the year.
   - Add each confirmed new status to `injuries.json` and repeat step 6.
8. **Determinism check.** Run step 6 a second time to a scratch output and compare. The picks and pick JSON must be identical; report any difference as a failure.
9. **Save to the source of truth.** Commit `data/games.json`, `data/pace.json`, the new `data/picks/DATE.json`, any new `data/results/*.json` and any `data/params.json` change, then push to `mmc7676/starting-five` main. If you can't push from this platform, say so plainly and give the user the changed files to commit. Never fail silently.

## Model (applied to every eligible player in every slate game)
EV = P(plays) x base x DvP x opp_matchup x usage x pace x minutes
- **P(plays)**, from the injury report: not listed 0.97; Out 0; probable / practiced in full 0.9; questionable 0.5; doubtful 0.25; ruled out or did not return last game 0.35; other day-to-day 0.6.
- **base**: this season's mean blended with last season's record: (n x current + w x prior) / (n + w), w = K_PRIOR x min(1, prior games / 20).
  - A player with no current games uses his prior alone.
  - A player with no prior (rookie, missed last season) regresses toward his position's mean of last-season priors with K_PRIOR / 2 pseudo-games.
- **DvP**: points the opponent allows to this position divided by the league position average, shrunk toward 1.0 with K_DVP pseudo-games.
- **opp_matchup**: blends over whether the opponent's best player at the same position plays: P_j x (1 - ALPHA x (s_j - 1)) + (1 - P_j), where s_j = that defender's avg / league avg at the position.
- **usage** (one ball, zero-sum): production that missing teammates are expected to leave behind is redistributed to active teammates in proportion to their own production. The total redistributed is BETA x what was vacated. Teammates are NOT penalized for being picked together: one player's scoring can feed another's assists.
- **pace**: expected game possessions / possessions in the games that produced the player's base. Both teams' paces are shrunk toward league pace with K_PACE pseudo-games.
- **minutes** = blowout x back-to-back:
  - P(blowout) = 0.05 + 0.60 x (p_fav - 0.5) / 0.5, where p_fav is the favorite's win probability.
  - Starters play BLOWOUT_MIN_RATIO of their minutes in a blowout.
  - A team that played the previous date takes x B2B_RATIO.
- **Defaults**: ALPHA 0.10, BETA 0.15, K_DVP 10, K_PACE 5, K_PRIOR 8, BLOWOUT_MIN_RATIO 26/36, B2B_RATIO 0.95. `data/params.json` overrides them once tuning has earned it.

## Known gaps
State these when they bear on a pick:
- Win probability doesn't update when a star is ruled out late.
- Late-tip back-to-back fatigue isn't modeled beyond B2B_RATIO.
- The model works on total score only, not per-stat projections.
- Real minutes data isn't available.
- 66 of 238 players have no prior.

## Output
Table: Position | Pick | Team vs Opp | EV | factor breakdown | injury + headline status, plus the top-3 per position and the lineup EV total. State plainly:
- which Step 0 source was used, and whether step 9 pushed;
- picks within about 5 EV of the runner-up are near coin-flips;
- thin samples, and picks whose base rests on the prior alone or with no prior;
- headline checks that found nothing confirm nothing;
- injuries can change, so re-run near lock;
- labels: FACT (card, box score, possession, odds, last-season, injury and headline data), DERIVED (scores, EV, results), HYPOTHESIS (P(play) weights and untuned priors).
