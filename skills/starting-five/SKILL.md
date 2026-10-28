---
name: "starting-five"
description: "NBA Collect Starting 5 Contest: picks the max-expected Topps-rubric player at PG, SG, SF, PF and C for the current NBA slate, with live injuries and per-matchup adjustments. Use for /starting-five."
---

# NBA Collect Starting 5 Contest (/starting-five)

Pick one player per position (PG, SG, SF, PF, C) from teams on the slate, maximizing expected Topps "Scoring 2026" points after all games finish. 

## Slate rule (no date argument)
1. Get the current time and convert it to America/Los_Angeles.
2. At 11:00 PM PT or later, slate = tomorrow's games. Otherwise slate = today's games.
3. Refuse any other date and state this rule. If the time is unavailable, use today's date and say so.

## Data (bundled in this skill; copy data/*.json and scripts/starting_five.py into the working dir. If a Human0 Project with nba-starting-five/ docs is attached, prefer those newer copies and write updates back there)
- data/SCWPOS.json: player -> {pos, team} for Topps NBA Collect 26 Base Tier 1 cards. The only eligible players; positions a team has no card for stay empty.
- data/games.json: one row per player-game {player, pos, date, team, opp, score}.
- data/pace.json: {date: {team: possessions}}, from box-score team_stats.possessions.
- scripts/starting_five.py: the picker (v3: matchup and pace).

## Scoring rubric (matches Topps card totals exactly: Caleb Wilson 66, Walker Kessler 47, Brook Lopez 49)
+6 per 2PM, -1 per missed 2PA, +10 per 3PM, -1 per missed 3PA, +2 per FTM, -2 per missed FT, +2 per OREB, +2 per DREB, +4 per AST, +6 per STL, +6 per BLK, -2 per TO, -2 per PF.

## Procedure
1. Slate: fetch_sports_data(league nba, scores). Keep games starting on the slate date in PT and write slate.json as [[home, away], ...].
2. Update history first: for every closed game after the last date in games.json, fetch game_stats.
   - Score EVERY player listed in SCWPOS with the rubric and append rows with team and opponent to games.json.
   - Add both teams' possessions to pace.json.
   - Write both files back to the Project.
   - List box-score players missing from SCWPOS instead of guessing their position.
3. Live injuries: WebFetch https://www.espn.com/nba/injuries and write injuries.json as {name: {status, comment}}. Add any injury news Human0 reports in the conversation as Out or Day-To-Day with a comment naming Human0 as the source.
4. Run: python3 starting_five.py SCWPOS.json games.json slate.json injuries.json pace.json
5. Headline check (the ESPN page lags): spawn ONE general-purpose agent to search breaking news since the injury page's last update for the 5 picks and each position's runner-up. Topics: injury, illness, rest, suspension, personal leave, trade, death.
   - Require a table: Player | Status | headline | report date | source URL. No invented URLs; "No news found" when nothing turns up.
   - Cross-check every report against games.json. An injury reported BEFORE a game the player then played in is resolved; ignore it. Beware results from prior seasons (e.g. 2025 stories); check the year.
   - For each confirmed new status, add it to injuries.json and go back to step 4.
6. Run the picker a second time and diff the outputs. They must be identical; report any difference as a failure.

## Model (applied to every player in every slate game)
EV = P(self plays) x base x DvP x opp_matchup x usage x pace
- P(play), from the injury report: not listed 0.97; Out 0; probable / practiced in full 0.9; questionable 0.5; doubtful 0.25; ruled out or did not return last game 0.35; other day-to-day 0.6.
- base: the player's mean Topps score.
- DvP: points the opponent allows to this position divided by the league position average, shrunk toward 1.0 with 10 pseudo-games.
- opp_matchup: blends over whether the opponent's best player at the SAME position plays: P_j x (1 - ALPHA x (s_j - 1)) + (1 - P_j), where s_j = that defender's avg / league avg at the position.
- usage: 1 + 0.15 x the expected-missing share of teammate production.
- pace: expected game possessions / average possessions in the games that produced the player's base.
  - Expected possessions = mean of both teams' paces.
  - Each team's pace is shrunk toward the league pace with 5 pseudo-games.
- ALPHA is fitted on history once games.json has 150 or more rows; until then the prior 0.10 is used. BETA (0.15), K_DVP (10) and K_PACE (5) are priors.

## Output
Table: Position | Pick | Team vs Opp | EV | factor breakdown | injury + headline status, plus the top-3 per position. State plainly:
- picks within about 5 EV of the runner-up are near coin-flips;
- thin samples (1-2 games) and the DvP sample size n;
- headline checks that found nothing confirm nothing;
- injuries can change, so re-run near lock;
- labels: FACT (card, box score, possession, injury and headline data), DERIVED (scores, EV), HYPOTHESIS (P(play) weights and priors).