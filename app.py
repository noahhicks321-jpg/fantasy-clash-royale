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
    # Return human-friendly "CardName (ID)" entries
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
            st.experimental_rerun()
    with sim_c2:
        if st.button("⏩ Simulate Until Playoffs", use_container_width=True):
            while not L.season_complete():
                L.simulate_next_day()
            L.save()
            st.success("Regular season completed.")
            st.experimental_rerun()
    with sim_c3:
        if st.button("🏁 Simulate Full Season (through playoffs & archive)", use_container_width=True):
            # Finish regular season if needed, then playoffs, awards, archive, next preseason
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
            st.experimental_rerun()

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

def schedule_and_sim():
    st.title("📅 Schedule & Simulation")

    todays = [g for g in L.schedule if g[0] == L.day]
    st.markdown("#### Today")
    if todays:
        df = pd.DataFrame([
            {"Day": d, "Home": L.teams[a].name, "Away": L.teams[b].name,
             "Rivalry?": "🔥" if (min(a,b),max(a,b)) in L.rivalries else ""}
            for d,a,b in todays
        ])
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No games today.")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("▶️ Simulate Next Day"):
            L.simulate_next_day()
            L.save()
            st.experimental_rerun()
    with c2:
        if st.button("⏭️ Simulate 7 Days"):
            for _ in range(7):
                if L.season_complete():
                    break
                L.simulate_next_day()
            L.save()
            st.experimental_rerun()

    st.markdown("#### All Results (This Season)")
    if L.results:
        st.dataframe(pd.DataFrame(L.results), use_container_width=True)
    else:
        st.caption("No results yet.")

def standings():
    st.title("📊 Standings")
    table = L.standings_table()
    df = pd.DataFrame(table)
    st.dataframe(df, use_container_width=True)

    st.markdown("### Longest Streaks (live)")
    longest_win = sorted(L.teams, key=lambda t: t.streak, reverse=True)[:5]
    longest_lose = sorted(L.teams, key=lambda t: t.streak)[:5]
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Winning Streaks**")
        st.table(pd.DataFrame([{"Team": t.name, "Streak": t.streak} for t in longest_win if t.streak > 0]))
    with c2:
        st.markdown("**Losing Streaks**")
        st.table(pd.DataFrame([{"Team": t.name, "Streak": t.streak} for t in longest_lose if t.streak < 0]))

def cards_page():
    st.title("🃏 Cards")

    # Filters
    colf1, colf2, colf3 = st.columns([2,2,2])
    with colf1:
        name_q = st.text_input("Search by name")
    with colf2:
        archetype = st.selectbox("Filter by Archetype", ["All"] + list(set([c.archetype for c in L.cards.values()])))
    with colf3:
        show_only_active = st.checkbox("Only active (not retired)", value=True)

    # Build card rows
    rows = []
    for cid, c in L.cards.items():
        if show_only_active and c.retired:
            continue
        if name_q and name_q.lower() not in c.name.lower():
            continue
        if archetype != "All" and c.archetype != archetype:
            continue
        rows.append({
            "ID": cid,
            "Name": c.name,
            "Archetype": c.archetype,
            "Attack Type": c.attack_type,
            "ATK": c.attack, "DEF": c.defense, "SPD": c.speed, "STA": c.stamina, "SPC": c.special,
            "Cost": c.cost, "Age": c.age, "Life": c.lifespan,
            "Retired": c.retired
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True)

    # Card detail
    st.markdown("---")
    st.subheader("Card Details")
    pick = st.selectbox("Select a card", ["—"] + [f"{L.cards[cid].name} [{cid}]" for cid in L.cards.keys()])
    if pick != "—":
        cid = extract_card_id(pick)
        if cid and cid in L.cards:
            c = L.cards[cid]
            st.markdown(f"**{c.name}**  "
                        f"<span class='badge'>{c.archetype}</span> "
                        f"<span class='badge'>{c.attack_type}</span>",
                        unsafe_allow_html=True)
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("ATK", c.attack)
            c2.metric("DEF", c.defense)
            c3.metric("SPD", c.speed)
            c4.metric("STA", c.stamina)
            c5.metric("SPC", c.special)
            st.caption(f"Cost: **{c.cost}** (base {c.base_cost}) • Age: {c.age}/{c.lifespan} • Retired: {c.retired}")
            if c.awards:
                st.markdown("**Awards:** " + ", ".join(c.awards))
            if c.history:
                st.markdown("**Season-by-Season Snapshot**")
                st.table(pd.DataFrame(c.history))

def teams_page():
    st.title("🏟️ Teams")

    # List teams with quick stats
    data = []
    for i, T in enumerate(L.teams):
        data.append({
            "Team": T.name,
            "GM Style": T.gm_personality,
            "W": T.wins, "L": T.losses, "Streak": T.streak,
            "Cost Spent": round(T.cost_spent, 2),
            "Shop Pts": round(T.shop_points_left, 2),
            "Roster": ", ".join([L.cards[cid].name for cid in T.roster]),
            "Backup": L.cards[T.backup].name if T.backup else ""
        })
    st.dataframe(pd.DataFrame(data), use_container_width=True)

    # Edit a single team (rename, see roster)
    st.markdown("---")
    st.subheader("Team Detail / Edit")
    team_names = [t.name for t in L.teams]
    tsel = st.selectbox("Select Team", team_names)
    ti = team_index_by_name(tsel)
    if ti is not None:
        T = L.teams[ti]
        st.markdown(
            f"<div class='team-chip'><span class='team-logo'>{T.logo}</span>"
            f"<b>{T.name}</b> <span class='badge'>{T.gm_personality}</span></div>",
            unsafe_allow_html=True
        )
        st.caption(f"Roster cost: {round(T.cost_spent,2)} / {L.max_team_cost} • Shop Points: {round(T.shop_points_left,2)}")
        rcols = st.columns(3)
        for idx, cid in enumerate(T.roster):
            with rcols[idx]:
                c = L.cards[cid]
                st.markdown(f"**Starter {idx+1}:** {c.name}")
                st.caption(f"ATK {c.attack} • DEF {c.defense} • SPD {c.speed} • STA {c.stamina} • Cost {c.cost}")
        if T.backup:
            c = L.cards[T.backup]
            st.markdown(f"**Backup:** {c.name} — STA {c.stamina} • Cost {c.cost}")

        # Rename
        new_name = st.text_input("Rename team", value=T.name)
        if new_name and new_name != T.name:
            if st.button("Save Team Name"):
                T.name = new_name
                L.save()
                st.success("Saved.")
                st.experimental_rerun()

def shop_page():
    st.title("🛒 Salary Cap Shop")

    tnames = [t.name for t in L.teams]
    tsel = st.selectbox("Choose Team", tnames)
    ti = team_index_by_name(tsel)
    if ti is None:
        st.stop()
    T = L.teams[ti]

    st.markdown(f"**Shop Points Available:** `{round(T.shop_points_left,2)}`")
    # Active boosts
    st.markdown("**Active Boosts:**")
    if T.boosts:
        st.table(pd.DataFrame([
            {"Key": b["key"], "Stat": b["stat"], "Amount": b["amount"], "Teamwide": b["teamwide"], "Games Left": b.get("games_left",0)}
            for b in T.boosts
        ]))
    else:
        st.caption("No active boosts.")

    st.markdown("### Catalog")
    df = pd.DataFrame(L.shop_catalog)
    df["Label"] = df["label"]
    df = df[["key","Label","pts","stat","games","teamwide"]].rename(columns={"pts":"Cost (pts)","stat":"Stat","games":"Duration","teamwide":"Teamwide"})
    st.dataframe(df, use_container_width=True, hide_index=True)

    item_keys = [i["key"] for i in L.shop_catalog]
    choice = st.selectbox("Select Item", ["—"] + item_keys)
    target = None
    if choice != "—":
        # If item needs a target card (fatigue reset or single-card boost)
        selected_item = next((x for x in L.shop_catalog if x["key"] == choice), None)
        needs_target = selected_item and not selected_item["teamwide"] and selected_item["stat"] in ("attack","defense","speed","all","stamina_reset")
        if needs_target:
            eligible = card_select_options(L.teams[ti].roster + ([T.backup] if T.backup else []))
            card_label = st.selectbox("Target Card", ["—"] + eligible)
            if card_label != "—":
                target = extract_card_id(card_label)
        if st.button("🛒 Purchase"):
            ok, msg = L.purchase_boost(ti, choice, target_card=target)
            if ok:
                L.save()
                st.success(msg)
                st.experimental_rerun()
            else:
                st.error(msg)

def trades_page():
    st.title("🤝 Trade Finder")

    # Pick a team
    tnames = [t.name for t in L.teams]
    tsel = st.selectbox("Your Team", tnames)
    ti = team_index_by_name(tsel)
    if ti is None:
        st.stop()
    T = L.teams[ti]

    # Choose one of your cards to shop
    own_cards = card_select_options(T.roster + ([T.backup] if T.backup else []))
    csel = st.selectbox("Card to Offer", ["—"] + own_cards)
    if csel == "—":
        st.info("Pick a card to get offers.")
        return
    my_card_id = extract_card_id(csel)

    if st.button("🔎 Find Offers"):
        offers = L.trade_finder_offers(ti, my_card_id)
        if not offers:
            st.warning("No valid offers found (cap constraints?).")
        st.session_state.trade_offers = offers

    offers = st.session_state.get("trade_offers", [])
    if offers:
        st.markdown("### Offers")
        for i, o in enumerate(offers):
            with st.expander(f"Offer {i+1}: {o['team_name']} gives {o['their_card_name']} (Cost {o['their_cost']})"):
                if st.button(f"Accept Offer {i+1}"):
                    ok, msg = L.execute_trade(ti, my_card_id, o["team_idx"], o["their_card"])
                    if ok:
                        L.save()
                        st.success("Trade executed.")
                        st.session_state.trade_offers = []
                        st.experimental_rerun()
                    else:
                        st.error(msg)

    # Transactions log
    st.markdown("---")
    st.subheader("Transactions Log (This Season)")
    if L.transactions:
        st.table(pd.DataFrame({"Event": L.transactions}))
    else:
        st.caption("No transactions recorded yet.")

def rivalries_page():
    st.title("🔥 Rivalries")

    if not L.rivalries:
        st.info("Rivalries will appear after schedule is generated.")
        return

    rows = []
    for (a,b), v in L.rivalries.items():
        rows.append({
            "Team A": L.teams[a].name,
            "Team B": L.teams[b].name,
            "Games": v["games"],
            "A Wins": v["a_wins"],
            "B Wins": v["b_wins"]
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True)

def playoffs_page():
    st.title("🏆 Playoffs")

    if st.button("🎬 Start Playoffs (seed top 16)"):
        L.start_playoffs()
        L.save()
        st.success("Playoffs seeded.")
        st.experimental_rerun()

    if L.playoffs:
        st.markdown("### Current Bracket (by names)")
        current_pairs = [{"Match": i+1, "A": L.teams[a].name, "B": L.teams[b].name}
                         for i, (a,b) in enumerate(L.playoffs.get("bracket", []))]
        if current_pairs:
            st.table(pd.DataFrame(current_pairs))
        else:
            st.caption("No active bracket pairs (maybe already simulated).")

        if st.button("🏁 Simulate to Champion"):
            champ_idx = L.simulate_playoffs_to_champion()
            st.success(f"Champion: {L.teams[champ_idx].name}")
            st.markdown("### Generating Awards, Costs, Patch, Retirements, Archive, and Next Season…")
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
            st.success("Postseason complete. New season started.")
            st.experimental_rerun()

        # Show historical results if present
        if "results" in L.playoffs and L.playoffs["results"]:
            st.markdown("### Series Results (this postseason)")
            st.table(pd.DataFrame(L.playoffs["results"]))
        if "champion" in L.playoffs:
            st.markdown(f"**Champion:** {L.playoffs['champion']}")

    else:
        st.info("Playoffs have not started. Finish regular season or click 'Start Playoffs'.")

def archive_page():
    st.title("📚 Archive (Yearbook)")

    if not L.past_seasons:
        st.info("No archived seasons yet. Complete a season first.")
        return

    seasons = sorted(L.past_seasons.keys())
    chosen = st.selectbox("Select Season", seasons, index=len(seasons)-1)
    data = L.past_seasons[chosen]

    # Layout
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("#### Standings")
        st.table(pd.DataFrame(data.get("standings", [])))
    with c2:
        st.markdown("#### Awards")
        aw = data.get("awards", {})
        if aw:
            st.json(aw)
        else:
            st.caption("None recorded.")
    with c3:
        st.markdown("#### Playoffs")
        p = data.get("playoffs", {})
        st.caption(f"Champion: **{p.get('champion','N/A')}**")
        st.table(pd.DataFrame(p.get("rounds", [])))

    st.markdown("---")
    c4, c5 = st.columns(2)
    with c4:
        st.markdown("#### Retirements")
        st.table(pd.DataFrame(data.get("retirements", [])))
    with c5:
        st.markdown("#### Transactions")
        st.table(pd.DataFrame({"Event": data.get("transactions", [])}))

    st.markdown("#### Patch Notes")
    st.json(data.get("patch_notes", {}))

def save_reset_page():
    st.title("🧰 Save / Reset")

    st.markdown("**Save File:** `{}`".format(SAVE_FILE))
    c1, c2 = st.columns(2)
    with c1:
        if st.button("💾 Save League"):
            L.save()
            st.success("Saved.")
    with c2:
        if st.button("♻️ Reset League (Start Season 1)"):
            st.warning("This will erase current progress and start a fresh league.", icon="⚠️")
            L.reset_new_league()
            L.save()
            st.success("League reset.")
            st.experimental_rerun()

    st.markdown("---")
    st.subheader("Utilities")
    u1, u2, u3 = st.columns(3)
    with u1:
        if st.button("🧪 Run Full Season (one-click)"):
            L.run_full_season_if_needed()
            L.save()
            st.success("One full season completed and archived.")
            st.experimental_rerun()
    with u2:
        if st.button("📆 Generate New Calendar (keeps season)"):
            L.generate_calendar()
            L.save()
            st.success("Calendar regenerated.")
            st.experimental_rerun()
    with u3:
        if st.button("🛠 Re-Run Preseason (draft, FA)"):
            L.start_preseason()
            L.save()
            st.success("Preseason complete.")
            st.experimental_rerun()

# ---------------- Route ----------------
if nav == "🏠 Dashboard":
    dashboard()
elif nav == "📅 Schedule & Sim":
    schedule_and_sim()
elif nav == "📊 Standings":
    standings()
elif nav == "🃏 Cards":
    cards_page()
elif nav == "🏟️ Teams":
    teams_page()
elif nav == "🛒 Shop":
    shop_page()
elif nav == "🤝 Trades":
    trades_page()
elif nav == "🔥 Rivalries":
    rivalries_page()
elif nav == "🏆 Playoffs":
    playoffs_page()
elif nav == "📚 Archive":
    archive_page()
elif nav == "🧰 Save / Reset":
    save_reset_page()
