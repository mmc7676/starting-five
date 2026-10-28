---
name: starting-five
description: NBA Collect Starting 5 Contest: picks the max-expected Topps-rubric player at PG, SG, SF, PF and C for the current NBA slate, with live injuries, matchups, pace and blowout/back-to-back minutes. Use for /starting-five.
---

# NBA Collect Starting 5 Contest (/starting-five)

Pick one player per position (PG, SG, SF, PF, C) from teams on the slate, maximizing expected Topps "Scoring 2026" points after all games finish.

## Slate rule (no date argument)
1. Get the current time and convert it to America/Los_Angeles.
2. At 11:00 PM PT or later, slate = tomorrow's games. Otherwise slate = today's games.
3. Refuse any other date and state this rule. If the time is unavailable, use today's date and say so.

## Step 0: load the data (works in any chat)
Load these four files into a working folder: SCWPOS.json, games.json, pace.json, starting_five.py. Try these sources in order and say which one you used:
1. The data bundled with this skill: data/*.json and scripts/starting_five.py.
2. The public GitHub repo mmc7676/starting-five. Clone it with git or read the files over WebFetch:
   https://raw.githubusercontent.com/mmc7676/starting-five/main/skills/starting-five/data/SCWPOS.json
   https://raw.githubusercontent.com/mmc7676/starting-five/main/skills/starting-five/data/games.json
   https://raw.githubusercontent.com/mmc7676/starting-five/main/skills/starting-five/data/pace.json
   https://raw.githubusercontent.com/mmc7676/starting-five/main/skills/starting-five/scripts/starting_five.py
3. A data pack the user attached (starting-five-datapack.zip).
If none of these works, stop and ask the user to attach the data pack. Never rebuild the player list from memory.
If there is no shell to run Python in, apply the Model below by hand to the top candidates per position and say so.

## Data
- SCWPOS.json: player -> {pos, team} for Topps NBA Collect 26 Base Tier 1 cards. The only eligible players; positions a team has no card for stay empty.
- games.json: one row per player-game {player, pos, date, team, opp, score}.
- pace.json: {date: {team: possessions}}, from box-score team_stats.possessions. Also used to detect back-to-backs.
- starting_five.py: the picker (v4: matchup, pace, minutes).

## Scoring rubric (matches Topps card totals exactly: Caleb Wilson 66, Walker Kessler 47, Brook Lopez 49)
+6 per 2PM, -1 per missed 2PA, +10 per 3PM, -1 per missed 3PA, +2 per FTM, -2 per missed FT, +2 per OREB, +2 per DREB, +4 per AST, +6 per STL, +6 per BLK, -2 per TO, -2 per PF.

## Procedure
1. Slate: fetch_sports_data(league nba, scores). Keep games starting on the slate date in PT. Write slate.json as [[home, away, p_home_win], ...], where p_home_win is the feed's win_probability for the home team / 100. Use null when the feed doesn't give one.
2. Update history first: for every closed game after the last date in games.json, fetch game_stats.
   - Score EVERY player listed in SCWPOS with the rubric and append rows with team and opponent to games.json.
   - Add both teams' possessions to pace.json.
   - If the Human0 Project is attached, write both files back to it.
   - List box-score players missing from SCWPOS instead of guessing their position.
3. Live injuries: WebFetch https://www.espn.com/nba/injuries and write injuries.json as {name: {status, comment}}. Add any injury news the user reports in the conversation as Out or Day-To-Day with a comment naming the user as the source.
4. Run: python3 starting_five.py SCWPOS.json games.json slate.json injuries.json pace.json
5. Headline check (the ESPN page lags): spawn ONE general-purpose agent to search breaking news from the last 48 hours for the 5 picks and each position's runner-up. Use extended search. Topics: injury, illness, rest, suspension, personal leave, trade, death. Team injury reports for tonight's game count as sources.
   - Require a table: Player | Status | headline | report date | source URL. No invented URLs; "No news found" when nothing turns up.
   - Cross-check every report against games.json. An injury reported BEFORE a game the player then played in is resolved; ignore it. Beware results from prior seasons (e.g. 2025 stories); check the year.
   - For each confirmed new status, add it to injuries.json and go back to step 4.
6. Run the picker a second time and diff the outputs. They must be identical; report any difference as a failure.

## Model (applied to every player in every slate game)
EV = P(self plays) x base x DvP x opp_matchup x usage x pace x minutes
- P(play), from the injury report: not listed 0.97; Out 0; probable / practiced in full 0.9; questionable 0.5; doubtful 0.25; ruled out or did not return last game 0.35; other day-to-day 0.6.
- base: the player's mean Topps score.
- DvP: points the opponent allows to this position divided by the league position average, shrunk toward 1.0 with 10 pseudo-games.
- opp_matchup: blends over whether the opponent's best player at the SAME position plays: P_j x (1 - ALPHA x (s_j - 1)) + (1 - P_j), where s_j = that defender's avg / league avg at the position.
- usage (one ball, zero-sum): production that missing teammates are expected to leave behind is redistributed to active teammates in proportion to their own production. The total redistributed is 0.15 x what was vacated.
- Teammates are NOT penalized for being picked together: one player's scoring can feed another's assists.
- pace: expected game possessions / average possessions in the games that produced the player's base.
  - Expected possessions = mean of both teams' paces.
  - Each team's pace is shrunk toward the league pace with 5 pseudo-games.
- minutes = blowout x back-to-back:
  - P(blowout) = 0.05 + 0.60 x (p_fav - 0.5) / 0.5, where p_fav is the favorite's win probability. It applies to both teams.
  - In a blowout, starters play 26/36 of their minutes. Factor = P x 26/36 + (1 - P).
  - Back-to-back (the team played the previous date in pace.json): x 0.95.
- ALPHA is fitted on history once games.json has 150 or more rows; until then the prior 0.10 is used. BETA (0.15), K_DVP (10), K_PACE (5), the blowout curve and the B2B ratio are priors.

## Output
Table: Position | Pick | Team vs Opp | EV | factor breakdown | injury + headline status, plus the top-3 per position and the lineup EV total. State plainly:
- which data source Step 0 used;
- picks within about 5 EV of the runner-up are near coin-flips;
- thin samples (1-2 games) and the DvP sample size n;
- headline checks that found nothing confirm nothing;
- injuries can change, so re-run near lock;
- labels: FACT (card, box score, possession, win-probability, injury and headline data), DERIVED (scores, EV), HYPOTHESIS (P(play) weights and all priors).
