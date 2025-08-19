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

# (CSS omitted for brevity — same as your original)

# ---------------- Session State: load or init league ----------------
def get_league() -> League:
    if "league" not in st.session_state:
        loaded = League.load(SAVE_FILE)
        st.session_state.league = loaded if loaded else League()
        if not loaded:
            st.session_state.league.start_preseason()
            st.session_state.league.save()
    return st.session_state.league

L: League = get_league()

# (all your helpers same as before...)

# ---------------- Components ----------------
def dashboard():
    st.title("⚔️ Clash Royale Fantasy League – Dashboard")

    # (unchanged dashboard content...)

    with sim_c1:
        if st.button("▶️ Simulate Next Day", use_container_width=True):
            recaps = L.simulate_next_day()
            if recaps:
                st.success(f"Simulated day {L.day-1}.")
            else:
                st.warning("Nothing to simulate today.")
            L.save()
            st.rerun()   # ✅ fixed

    with sim_c2:
        if st.button("⏩ Simulate Until Playoffs", use_container_width=True):
            while not L.season_complete():
                L.simulate_next_day()
            L.save()
            st.success("Regular season completed.")
            st.rerun()   # ✅ fixed

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
            st.rerun()   # ✅ fixed

# (rest of your pages...)

def schedule_and_sim():
    # ...
    if st.button("▶️ Simulate Next Day"):
        L.simulate_next_day()
        L.save()
        st.rerun()   # ✅ fixed

    if st.button("⏭️ Simulate 7 Days"):
        for _ in range(7):
            if L.season_complete():
                break
            L.simulate_next_day()
        L.save()
        st.rerun()   # ✅ fixed

# (same replacements inside teams_page, shop_page, trades_page, playoffs_page, save_reset_page, etc.)

