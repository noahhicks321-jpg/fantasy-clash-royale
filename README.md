
# Clash Royale Fantasy League (Streamlit + Python)

A complete, single-folder project that simulates a fantasy-style Clash Royale league with 30 teams and 160–170 cards.

**Highlights**

- 3 starters + 1 backup per team (backup auto-subs when fatigue < 25).
- 20-week regular season (40 games per team), rivalries, and live standings.
- Salary cap (20 pts), Shop (temporary boosts, fatigue reset).
- Trade Finder (one card trade per season; cap-safe only).
- Playoffs (Top 16: BO3/BO5/BO5/BO7), champion, awards (MVP, DPOY, 6MOY, ROTY, Finals MVP).
- Patch notes (buffs/nerfs), retirements (3), rookies (4), league archive (history per season).
- HOF probability tracker for cards.

## Run

```bash
pip install -r requirements.txt
streamlit run app.py
```

If you deploy on Streamlit Cloud, just push these files to a GitHub repo and set the main file to `app.py`.

## Files

- `app.py` – Streamlit UI.
- `league.py` – Simulation engine and persistence.
- `requirements.txt` – small dep list.
- `league_state.json` – generated save file.

## Save/Reset

The UI sidebar has buttons to save or reset the league. Resetting wipes the world and recreates it fresh (Season 1).

## Customization

Open `league.py` and tweak:
- `ARCHETYPES`, `ATTACK_TYPES`, `SYNERGY_MATRIX`
- Schedule / games per team in `generate_calendar()`
- Award formulas in `calculate_awards()`
- Shop items in `self.shop_catalog`
- Patch nickname pool in `apply_patch()`
