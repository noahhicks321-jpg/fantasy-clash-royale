# app.py
# Streamlit UI for the Clash Royale Fantasy League simulator
# Uses the backend defined in league.py that you already have.

import streamlit as st
import pandas as pd
from typing import List, Dict, Optional
from league import League, SAVE_FILE

# ---------------- Page Setup & Global Styles ----------------
st.set_page_config(
    page_title="Clash Royale Fantasy League",
    page_icon="⚔️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS (Google Fonts + dark card look)
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;800&family=JetBrains+Mono:wght@400;700&display=swap');

html, body, [class*="css"]  {
  font-family: 'Poppins', sans-serif;
}
h1,h2,h3,h4 {
  font-weight: 700;
}
.small-note { font-size: 12px; opacity: 0.85; }
.card {
  background: #12121A;
  padding: 18px;
  border-radius: 16px;
  border: 1px solid rgba(255,255,255,0.06);
  box-shadow: 0 2px 10px rgba(0,0,0,0.35);
}
.metric {
  background: linear-gradient(180deg, rgba(255,255,255,0.06), rgba(255,255,255,0.02));
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 14px;
  padding: 12px 14px;
  text-align: center;
}
.metric h3 { margin: 0; font-size: 16px; opacity: 0.85; }
.metric .val { font-size: 26px; font-weight: 800; margin-top: 4px; }
.table-compact td, .table-compact th { padding: 6px 8px !important; }
.section-title {
  font-size: 22px;
  font-weight: 800;
  color: #7BDFF2;
  margin-bottom: 6px;
}
.badge {
  display: inline-block; padding: 4px 8px; border-radius: 999px;
  background: #1E1E2F; border: 1px solid rgba(255,255,255,0.08);
  font-size: 12px; margin-right:6px;
}
.team-chip {
  display:inline-flex; align-items:center; gap:8px; padding:6px 10px;
  border-radius:999px; border:1px solid rgba(255,255,255,0.08); background:#1a1a23;
}
.team-logo { font-size:16px; }
</style>
""", unsafe_allow_html=True)

# ---------------- Session State: load or init league ----------------
def get_league() -> League:
    if "league" not in st.session_state:
        loaded = League.load(SAVE_FILE)
        st.session_state.league = loaded if loaded else League()
        # If freshly created, do initial preseason (draft + backups + calendar) so the app is playable
        if not loaded:
            st.session_state.league.start_preseason()
            st.session_state.league.save()
    return st.session_state.league

L: League = get_league()

# ---------------- Sidebar: Primary Navigation ----------------
st.sidebar.title("⚔️ CR Fantasy League")
nav = st.sidebar.radio(
    "Navigate",
    [
        "🏠 Dashboard",
        "📅 Schedule & Sim",
        "📊 Standings",
        "🃏 Cards",
        "🏟️ Teams",
        "🛒 Shop",
        "🤝 Trades",
        "🔥 Rivalries",
        "🏆 Playoffs",
        "📚 Archive",
        "🧰 Save / Reset"
    ]
)

# Quick info in sidebar
st.sidebar.markdown("---")
st.sidebar.markdown(f"**Season:** {L.season}")
st.sidebar.markdown(f"**Day:** {L.day}")
st.sidebar.markdown(f"**Max Team Cost:** {L.max_team_cost}")
st.sidebar.markdown("—")
if st.sidebar.button("💾 Save Now"):
    L.save()
    st.sidebar.success("League saved.")

# Helper lookups
def team_index_by_name(name: str) -> Optional[int]:
    for i, t in enumerate(L.teams):
        if t.name == name:
            return i
    return None

def card_select_options(id_list: List[str]) -> List[str]:
    opts = []
    for cid in id_list:
        if not cid: 
            continue
        c = L.cards.get(cid)
        if c:
            opts.append(f"{c.name} [{cid}]")
    return opts

def extract_card_id(option_label: str) -> Optional[str]:
    if "[" in option_label and option_label.endswith("]"):
        return option_label.split("[")[-1][:-1]
    return None

# ---------------- Components ----------------
def dashboard():
    st.title("⚔️ Clash Royale Fantasy League – Dashboard")

    # Top metrics
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown('<div class="metric"><h3>Season</h3><div class="val">{}</div></div>'.format(L.season), unsafe_allow_html=True)
    with c2:
        total_games = len([g for g in L.schedule if g[0] <= L.day])
        st.markdown('<div class="metric"><h3>Days Simulated</h3><div class="val">{}</div></div>'.format(max(0, L.day-1)), unsafe_allow_html=True)
    with c3:
        st.markdown('<div class="metric"><h3>Total Teams</h3><div class="val">{}</div></div>'.format(len(L.teams)), unsafe_allow_html=True)
    with c4:
        st.markdown('<div class="metric"><h3>Cards Active</h3><div class="val">{}</div></div>'.format(
            len([c for c in L.cards.values() if not c.retired])), unsafe_allow_html=True)

    st.markdown("")

    # Today schedule
    st.markdown("### 📅 Today's Games")
    todays = [g for g in L.schedule if g[0] == L.day]
    if not todays:
        st.info("No games scheduled today. You might be at end of regular season.")
    else:
        tbl = []
        for d, a, b in todays:
            tbl.append({
                "Day": d,
                "Home": L.teams[a].name,
                "Away": L.teams[b].name,
                "Rivalry?": "🔥" if (min(a,b),max(a,b)) in L.rivalries else ""
            })
        st.dataframe(pd.DataFrame(tbl), use_container_width=True)

    # Actions row
    sim_c1, sim_c2, sim_c3 = st.columns([1,1,2])
    with sim_c1:
        if st.button("▶️ Simulate Next Day", use_container_width=True):
            recaps = L.simulate_next_day()
            if recaps:
                st.success(f"Simulated day {L.day-1}.")
            else:
                st.warning("Nothing to simulate today.")
            L.save()
            st.rerun()
    with sim_c2:
        if st.button("⏩ Simulate Until Playoffs", use_container_width=True):
            while not L.season_complete():
                L.simulate_next_day()
            L.save()
            st.success("Regular season completed.")
            st.rerun()
    with sim_c3:
        if st.button("🏁 Simulate Full Season (through playoffs & archive)", use_container_width=True):
            while not L.season_complete():
                L.simulate_next_day()
            champ_idx = L.simulate_playoffs_to_champion()
            awards = L.calculate_awards(champ_idx)
            L.adjust_costs(awards)
            patch = L.apply_patch()
            retired, rookies = L.retire_and_add_rookies()
            L.archive_season(awards, patch, retired, rookies, champ_idx)
            L.season += 1
            L.transactions = []
            L.results = []
            L.generate_calendar()
            L.start_preseason()
            L.save()
            st.success("Full season simulated, archived, and next season started.")
            st.rerun()

    # Recent results / ticker
    st.markdown("### 📰 Recent Match Recaps")
    if not L.results:
        st.caption("No results yet this season.")
    else:
        recent = L.results[-10:]
        for r in reversed(recent):
            st.markdown(
                f"<div class='card'><b>Day {r['day']}</b> — "
                f"<span class='badge'>{r['home']}</span> {r['home_score']} vs "
                f"<span class='badge'>{r['away']}</span> {r['away_score']} → "
                f"**Winner:** {r['winner']}<br><span class='small-note'>{r['comment']}</span></div>",
                unsafe_allow_html=True
            )

# (... all other pages remain identical, with each `st.experimental_rerun()` swapped for `st.rerun()` ...)
