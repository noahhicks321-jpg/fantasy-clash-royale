
# league.py
# Clash Royale Fantasy League backend
# -----------------------------------------------------------------------------
# This file contains a self-contained simulation engine that the Streamlit UI
# (app.py) can import. It was designed to satisfy every feature the app expects
# while remaining readable and extensible.
#
# You will find:
#   • Data classes for Card and Team
#   • League class handling: initialization, preseason (draft/backups),
#     schedule generation, day-by-day simulation, fatigue management,
#     backup-substitution rules, trades, salary-cap shop, awards,
#     playoffs (16 teams: BO3, BO5, BO5, BO7), patches, retirements,
#     rookies, league history archive, HOF probability tracking, etc.
#
# Notes on philosophy:
#   - This is a *toy* simulator that focuses on UX and "league worldbuilding"
#     over deep esports accuracy. We model sensible formulas (documented below),
#     but keep computations lightweight to ensure Streamlit stays snappy.
#   - Nearly every top-level method returns simple Python types so that the UI
#     can render with minimal fuss (dicts/lists/strings — no Pandas requirement).
#
# -----------------------------------------------------------------------------
from __future__ import annotations

import json
import math
import random
import statistics
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

SAVE_FILE = "league_state.json"
RNG_SEED = 1337

# =============================================================================
# Utility helpers
# =============================================================================

def clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))

def weighted_choice(items: List[Tuple[Any, float]]) -> Any:
    total = sum(w for _, w in items)
    r = random.uniform(0, total) if total > 0 else 0
    upto = 0
    for item, w in items:
        if upto + w >= r:
            return item
        upto += w
    return items[-1][0] if items else None

def uid(prefix: str, n: int = 6) -> str:
    import string, random
    return f"{prefix}_{''.join(random.choices(string.ascii_uppercase+string.digits, k=n))}"

# =============================================================================
# Core data structures
# =============================================================================

ARCHETYPES = ["Tank", "DPS", "Control", "Support", "Hybrid"]
ATTACK_TYPES = ["Melee", "Ranged", "Splash", "Magic"]

# -- Synergy matrix: additive bonus/penalty (±5 typical), returns a /100 bonus.
SYNERGY_MATRIX: Dict[Tuple[str, str], float] = {}
def _build_synergy():
    # symmetric entries for clarity
    pairs = {
        ("Tank","Support"): +5, ("Tank","DPS"): +2, ("Tank","Control"): -2, ("Tank","Hybrid"): +1,
        ("DPS","Support"): +1, ("DPS","Control"): +2, ("DPS","Hybrid"): +1,
        ("Control","Support"): +3, ("Control","Hybrid"): +1,
        ("Support","Hybrid"): +2,
        ("Tank","Tank"): -3, ("DPS","DPS"): -2, ("Control","Control"): -1, ("Support","Support"): 0, ("Hybrid","Hybrid"): 0,
    }
    for a in ARCHETYPES:
        for b in ARCHETYPES:
            if (a,b) in pairs:
                SYNERGY_MATRIX[(a,b)] = pairs[(a,b)]
                SYNERGY_MATRIX[(b,a)] = pairs[(a,b)]
            elif (b,a) in pairs:
                SYNERGY_MATRIX[(a,b)] = pairs[(b,a)]
            else:
                SYNERGY_MATRIX[(a,b)] = 0.0

_build_synergy()

def synergy_bonus(a: str, b: str) -> float:
    return SYNERGY_MATRIX.get((a,b), 0.0)

# -----------------------------------------------------------------------------

@dataclass
class Card:
    """Represents a single card (a 'player' in this fantasy league).

    All primary stats are /100 except cost (salary points) and age/lifespan.
    """
    id: str
    name: str
    archetype: str
    attack_type: str

    # Primary stats (0–100)
    attack: int
    defense: int
    speed: int
    hit_speed: int              # card-specific tempo; higher = more hits
    atk_type_score: int         # meta bonus for attack_type
    synergy_score: int          # innate team-friendliness

    # Derived & meta
    total_power: int            # /100 average of core stats + synergy bonuses
    grade: str                  # S/A/B/C/D
    cost: float                 # salary points (<= 20 per team)
    base_cost: float
    age: int                    # seasons played so far
    lifespan: int               # total seasons before forced retirement (3–8)
    retired: bool = False
    awards: List[str] = field(default_factory=list)
    history: List[Dict[str, Any]] = field(default_factory=list)  # per-season snapshots
    hof_prob: float = 0.0       # 0–100 tracker

    # Usage & contribution tracking (reset each season)
    games_played: int = 0
    contribution_sum: float = 0.0   # cumulative % contribution
    avg_pct_contributed: float = 0.0
    pick_rate: float = 0.0          # pick % (drafted frequency)
    fatigue: float = 100.0          # 0–100 (backup used if starter fatigue < threshold)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return d

# -----------------------------------------------------------------------------

@dataclass
class Team:
    id: str
    name: str
    logo: str
    color: str
    gm_personality: str

    roster: List[str]      # 3 starters -> list of Card IDs
    backup: Optional[str]  # backup Card ID
    wins: int = 0
    losses: int = 0
    streak: int = 0
    cost_spent: float = 0.0
    shop_points_left: float = 0.0
    boosts: List[Dict[str, Any]] = field(default_factory=list)

    # One card trade + one pick trade per season (can be combined in one)
    trade_card_used: bool = False
    trade_pick_used: bool = False

    # GM Career tracking (meta progression)
    career_titles: int = 0
    career_trades_won: int = 0
    career_trades_lost: int = 0
    career_seasons: int = 0

    # Chemistry system (0–100 per card pair)
    chemistry: Dict[Tuple[str, str], float] = field(default_factory=dict)

# =============================================================================
# League
# =============================================================================

class League:
    """Top-level simulation container.

    Public attributes the UI depends on:
      - teams: List[Team]
      - cards: Dict[card_id, Card]
      - schedule: List[(day, home_idx, away_idx)]
      - rivalries: Dict[(team_i, team_j), {games,a_wins,b_wins}]
      - transactions: List[str]
      - results: List[Dict]  (game recaps)
      - playoffs: Dict with 'bracket', 'results', 'champion'
      - past_seasons: Dict[season_num, {...}]
      - shop_catalog: List[Dict] items for UI

    Methods the UI calls are documented inline below.
    """
    def __init__(self, n_teams: int = 30, rng_seed: int = RNG_SEED):
        random.seed(rng_seed)
        self.rng_seed = rng_seed
        self.season: int = 1
        self.day: int = 1
        self.max_team_cost: float = 20.0
        self.cards: Dict[str, Card] = {}
        self.teams: List[Team] = []
        self.schedule: List[Tuple[int, int, int]] = []  # (day, home_i, away_i)
        self.rivalries: Dict[Tuple[int, int], Dict[str, int]] = {}
        self.transactions: List[str] = []
        self.results: List[Dict[str, Any]] = []
        self.playoffs: Dict[str, Any] = {}
        self.past_seasons: Dict[int, Dict[str, Any]] = {}
        self.records: Dict[str, Any] = {
            "worst_record": None,
            "best_record": None,
            "biggest_upset": None,
            "most_awards_one_season": None,
        }

        # Shop items
        self.shop_catalog: List[Dict[str, Any]] = [
            {"key": "boost_atk_+3_2g", "label": "Attack +3 (2 games)", "pts": 1.5, "stat": "attack", "amount": 3, "games": 2, "teamwide": False},
            {"key": "boost_def_+3_2g", "label": "Defense +3 (2 games)", "pts": 1.5, "stat": "defense", "amount": 3, "games": 2, "teamwide": False},
            {"key": "boost_spd_+3_2g", "label": "Speed +3 (2 games)", "pts": 1.5, "stat": "speed", "amount": 3, "games": 2, "teamwide": False},
            {"key": "team_all_+2_2g", "label": "Team All +2 (2 games)", "pts": 3.0, "stat": "all", "amount": 2, "games": 2, "teamwide": True},
            {"key": "stamina_reset", "label": "Reset Fatigue (single)", "pts": 0.75, "stat": "stamina_reset", "amount": 100, "games": 0, "teamwide": False},
        ]

        # Build world
        self._generate_card_pool(min_cards=160, cap=170)
        self._generate_teams(n_teams)
        self.start_preseason()      # draft starters & backups, set chemistry, set budgets
        self.generate_calendar()    # 20 weeks → 40 games per team
        # Ready to play!

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    @classmethod
    def load(cls, path: str) -> Optional["League"]:
        p = Path(path)
        if not p.exists():
            return None
        data = json.loads(p.read_text())
        L = cls.__new__(cls)  # bypass __init__
        # Basic
        L.rng_seed = data["rng_seed"]
        random.seed(L.rng_seed)
        L.season = data["season"]
        L.day = data["day"]
        L.max_team_cost = data["max_team_cost"]
        L.schedule = [tuple(x) for x in data["schedule"]]
        L.rivalries = {(int(k.split(",")[0]), int(k.split(",")[1])): v for k, v in data["rivalries"].items()}
        L.transactions = data["transactions"]
        L.results = data["results"]
        L.playoffs = data["playoffs"]
        L.past_seasons = {int(k): v for k, v in data["past_seasons"].items()}
        L.records = data.get("records", {})
        L.shop_catalog = data["shop_catalog"]

        # Cards
        L.cards = {}
        for cid, cd in data["cards"].items():
            L.cards[cid] = Card(**cd)

        # Teams
        L.teams = []
        for td in data["teams"]:
            T = Team(**td)
            # Ensure tuple keys for chemistry
            T.chemistry = {tuple(eval(k)) if isinstance(k,str) else tuple(k): v for k,v in T.chemistry.items()}
            L.teams.append(T)

        return L

    def save(self, path: str = SAVE_FILE) -> None:
        data = dict(
            rng_seed=self.rng_seed,
            season=self.season,
            day=self.day,
            max_team_cost=self.max_team_cost,
            cards={cid: c.to_dict() for cid, c in self.cards.items()},
            teams=[asdict(t) for t in self.teams],
            schedule=self.schedule,
            rivalries={f"{a},{b}": v for (a,b), v in self.rivalries.items()},
            transactions=self.transactions,
            results=self.results,
            playoffs=self.playoffs,
            past_seasons=self.past_seasons,
            records=self.records,
            shop_catalog=self.shop_catalog,
        )
        Path(path).write_text(json.dumps(data, indent=2))

    # ------------------------------------------------------------------
    # World generation
    # ------------------------------------------------------------------

    def _generate_card_pool(self, min_cards: int = 160, cap: int = 170) -> None:
        """Create a card pool with names, stats, costs, and lifespans.

        Ensures at least `min_cards` exist, and never above `cap` at once.
        """
        n_cards = random.randint(min_cards, min(min_cards+8, cap))
        for i in range(n_cards):
            cid = uid("C")
            ar = random.choice(ARCHETYPES)
            at = random.choice(ATTACK_TYPES)
            atk = random.randint(50, 95)
            dfn = random.randint(50, 95)
            spd = random.randint(50, 95)
            hsp = random.randint(40, 95)
            typ = random.randint(40, 95)
            syn = random.randint(40, 95)
            # Total power = avg + synergy baseline + small randomness
            raw_avg = (atk + dfn + spd + hsp + typ + syn) / 6.0
            total = clamp(raw_avg + 0.25 * (syn - 50.0))
            grade = "S" if total >= 90 else "A" if total >= 80 else "B" if total >= 70 else "C" if total >= 60 else "D"
            base_cost = round(max(0.5, (total - 50) / 12.0), 2)  # 0.5–~4.2
            cost = base_cost
            life = random.randint(3, 8)
            name = self._generate_card_name(i)
            self.cards[cid] = Card(
                id=cid, name=name, archetype=ar, attack_type=at,
                attack=atk, defense=dfn, speed=spd, hit_speed=hsp,
                atk_type_score=typ, synergy_score=syn,
                total_power=int(round(total)), grade=grade,
                cost=cost, base_cost=base_cost, age=0, lifespan=life,
            )

    def _generate_card_name(self, i: int) -> str:
        # Semi-flavorful names
        pool1 = ["Miner","Ice Wizard","Mega Knight","Giant Skeleton","Electro Spirit","Goblin Gang","Royal Ghost",
                 "Dart Goblin","Battle Healer","Cannon Cart","Magic Archer","Inferno Dragon","Electro Wizard","Bandit",
                 "Lumberjack","Skeleton King","Archer Queen","Golden Knight","Monk","Phoenix","Goblin Drill","Ram Rider"]
        return random.choice(pool1) + f" #{i+1}"

    def _generate_teams(self, n_teams: int) -> None:
        names = [f"Team {chr(65+i)}" for i in range(n_teams)]
        logos = ["🛡️","🐉","🦅","🦈","🦂","🐺","🦁","🐯","🐼","🦊","🐸","🐻","🦄","🐙","🐗","🦅","🐲","🐧","🦉","🦕","🐍","🦬","🦒","🦓","🦌","🦭","🐬","🦢","🦩","🦚"]
        colors = ["#%06x" % random.randint(0, 0xFFFFFF) for _ in range(n_teams)]
        gm_styles = ["Analyst","Trader","Culture","Risk-Taker","Balanced"]
        for i in range(n_teams):
            self.teams.append(Team(
                id=uid("T"), name=names[i], logo=random.choice(logos), color=colors[i],
                gm_personality=random.choice(gm_styles),
                roster=[], backup=None, wins=0, losses=0, streak=0, cost_spent=0.0, shop_points_left=0.0,
            ))

    # ------------------------------------------------------------------
    # Preseason: fantasy draft + backups + chemistry init
    # ------------------------------------------------------------------

    def start_preseason(self) -> None:
        """Fantasy draft from scratch for all teams every season.

        - Each team drafts 3 starters + 1 backup.
        - Enforce salary cap 20 points.
        - Initialize chemistry and shop points (remaining cap).
        """
        # reset per-team season flags
        for T in self.teams:
            T.wins = T.losses = 0
            T.streak = 0
            T.roster = []
            T.backup = None
            T.cost_spent = 0.0
            T.shop_points_left = 0.0
            T.boosts.clear()
            T.trade_card_used = False
            T.trade_pick_used = False
            T.chemistry.clear()

        # reset per-card season stats
        for c in self.cards.values():
            c.games_played = 0
            c.contribution_sum = 0.0
            c.avg_pct_contributed = 0.0
            c.pick_rate = 0.0
            c.fatigue = 100.0

        # Wipe pick counts
        pick_counts = {cid: 0 for cid in self.cards}

        # Simple snake draft order
        order = list(range(len(self.teams)))
        rounds = 4  # 3 starters + 1 backup
        forward = True
        for r in range(rounds):
            picks = order if forward else list(reversed(order))
            for ti in picks:
                self._draft_one_card(ti, pick_counts, is_backup=(r == 3))
            forward = not forward

        # Assign pick rates
        total_picks = sum(pick_counts.values()) or 1
        for cid, count in pick_counts.items():
            self.cards[cid].pick_rate = round(100.0 * count / total_picks, 2)

        # Set shop points from remaining cap
        for T in self.teams:
            T.shop_points_left = max(0.0, self.max_team_cost - T.cost_spent)

        # Initialize starting chemistry for trios
        for T in self.teams:
            for i in range(len(T.roster)):
                for j in range(i+1, len(T.roster)):
                    a, b = T.roster[i], T.roster[j]
                    base = 50.0 + synergy_bonus(self.cards[a].archetype, self.cards[b].archetype)
                    T.chemistry[(a,b)] = clamp(base, 0, 100)

    def _draft_one_card(self, ti: int, pick_counts: Dict[str, int], is_backup: bool=False) -> None:
        T = self.teams[ti]
        # Consider affordable cards, prefer higher total_power
        candidates = [(cid, c) for cid, c in self.cards.items() if not c.retired and
                      cid not in T.roster and cid != T.backup and (T.cost_spent + c.cost) <= self.max_team_cost]
        if not candidates:
            # allow over-cap last pick if needed (rare)
            candidates = [(cid, c) for cid, c in self.cards.items() if not c.retired and cid not in T.roster and cid != T.backup]
        candidates.sort(key=lambda x: (x[1].total_power, x[1].grade), reverse=True)
        pick_cid = candidates[0][0] if candidates else None
        if not pick_cid:
            return
        if is_backup and T.backup is None:
            T.backup = pick_cid
        else:
            if len(T.roster) < 3:
                T.roster.append(pick_cid)
        T.cost_spent += self.cards[pick_cid].cost
        pick_counts[pick_cid] += 1
        self.transactions.append(f"Draft: {T.name} selected {self.cards[pick_cid].name} ({'Backup' if is_backup else 'Starter'})")

    # ------------------------------------------------------------------
    # Schedule
    # ------------------------------------------------------------------

    def generate_calendar(self) -> None:
        """20 weeks, 40 games per team ⇒ (teams * 40)/2 total games.

        We spread games across sequential 'days'. Rivalries increment when teams
        meet; UI uses rivalries to show 🔥.
        """
        self.schedule = []
        n = len(self.teams)
        games_per_team = 40
        # Track remaining games per team
        remain = [games_per_team for _ in range(n)]
        day = 1
        # Simple pairing heuristic
        while sum(remain) > 0:
            used = set()
            # attempt to schedule as many pairs as possible in a day
            for a in range(n):
                if a in used or remain[a] <= 0:
                    continue
                # find opponent with remaining games and not used
                ops = [b for b in range(n) if b != a and b not in used and remain[b] > 0]
                if not ops:
                    continue
                b = random.choice(ops)
                home, away = (a, b) if random.random() < 0.5 else (b, a)
                self.schedule.append((day, home, away))
                used.add(a); used.add(b)
                remain[a] -= 1; remain[b] -= 1
                # rivalry bookkeeping
                key = (min(a,b), max(a,b))
                if key not in self.rivalries:
                    self.rivalries[key] = {"games": 0, "a_wins": 0, "b_wins": 0}
                self.rivalries[key]["games"] += 1
            day += 1
        # reset day to 1 for season start
        self.day = 1

    # ------------------------------------------------------------------
    # Simulation
    # ------------------------------------------------------------------

    def season_complete(self) -> bool:
        # All scheduled days completed when last day > max day in schedule
        if not self.schedule:
            return True
        return self.day > max(d for d,_,_ in self.schedule)

    def simulate_next_day(self) -> List[Dict[str, Any]]:
        """Simulate all games whose day matches self.day.

        Backup rule: If any starter fatigue < 25, auto-sub with backup for that slot.
        Fatigue reduces by 8–15 for those who played; +12–20 recovery if they rested.
        Contribution % is computed per-card within the team based on power formula.
        """
        todays = [x for x in self.schedule if x[0] == self.day]
        recaps: List[Dict[str,Any]] = []
        if not todays:
            return recaps

        for day, home_i, away_i in todays:
            h_score, a_score, detail = self._simulate_game(home_i, away_i)
            winner = self.teams[home_i].name if h_score > a_score else self.teams[away_i].name
            self.results.append({
                "day": day, "home": self.teams[home_i].name, "away": self.teams[away_i].name,
                "home_score": h_score, "away_score": a_score, "winner": winner,
                "comment": detail
            })
            recaps.append(self.results[-1])
        self.day += 1
        return recaps

    def _effective_card_power(self, card: Card, boosts: List[Dict[str, Any]]) -> float:
        atk = card.attack
        dfn = card.defense
        spd = card.speed
        hsp = card.hit_speed
        typ = card.atk_type_score
        syn = card.synergy_score
        # apply active boosts
        for b in list(boosts):
            if b.get("games_left", 0) == 0 and b["stat"] != "stamina_reset":
                continue
            if b["teamwide"] or b.get("target") == card.id:
                if b["stat"] == "attack":
                    atk += b["amount"]
                elif b["stat"] == "defense":
                    dfn += b["amount"]
                elif b["stat"] == "speed":
                    spd += b["amount"]
                elif b["stat"] == "all":
                    atk += b["amount"]; dfn += b["amount"]; spd += b["amount"]
        # fatigue penalty
        fatigue_factor = 0.5 + 0.5 * (card.fatigue/100.0)  # 0.5–1.0
        base = (atk*0.28 + dfn*0.24 + spd*0.22 + hsp*0.10 + typ*0.06 + syn*0.10)
        return base * fatigue_factor

    def _chemistry_pair_bonus(self, T: Team) -> float:
        # average chemistry over pairs (0–100 → 0.95–1.05 multiplier)
        if len(T.roster) < 3:
            return 1.0
        pairs = []
        for i in range(3):
            for j in range(i+1, 3):
                key = (T.roster[i], T.roster[j])
                val = T.chemistry.get(key, 50.0)
                pairs.append(val)
        avg = statistics.mean(pairs) if pairs else 50.0
        return 0.95 + 0.001 * (avg - 50.0)  # 50 → 0.95; 100 → 1.0

    def _maybe_use_backup(self, T: Team) -> Tuple[List[str], List[str]]:
        # Returns (active_ids, benched_ids) for starters w/ backup subs if fatigue < 25
        active = T.roster.copy()
        benched = []
        if T.backup:
            for i, cid in enumerate(T.roster):
                if self.cards[cid].fatigue < 25.0:
                    active[i] = T.backup
                    benched.append(cid)
        return active, benched

    def _simulate_game(self, home_i: int, away_i: int) -> Tuple[int, int, str]:
        H = self.teams[home_i]
        A = self.teams[away_i]

        # apply backup rule
        h_active, h_bench = self._maybe_use_backup(H)
        a_active, a_bench = self._maybe_use_backup(A)

        # compute per-card powers
        def team_power(T: Team, active_ids: List[str]) -> Tuple[float, Dict[str,float]]:
            pmap = {}
            for cid in active_ids:
                c = self.cards[cid]
                pmap[cid] = self._effective_card_power(c, T.boosts)
            # synergy multiplier based on archetype pairings
            mult = self._chemistry_pair_bonus(T)
            total = sum(pmap.values()) * mult
            return total, pmap

        home_total, h_map = team_power(H, h_active)
        away_total, a_map = team_power(A, a_active)

        # random noise + tiny home advantage
        home_total *= 1.03
        noise_h = random.uniform(0.95, 1.05)
        noise_a = random.uniform(0.95, 1.05)
        h_score = int(round(home_total * noise_h / 10.0))
        a_score = int(round(away_total * noise_a / 10.0))
        if h_score == a_score:
            # tiebreak
            if random.random() < 0.5:
                h_score += 1
            else:
                a_score += 1

        # update W/L records
        if h_score > a_score:
            H.wins += 1; A.losses += 1
            H.streak = H.streak + 1 if H.streak >= 0 else 1
            A.streak = A.streak - 1 if A.streak <= 0 else -1
            # rivalry bookkeeping
            key = (min(home_i, away_i), max(home_i, away_i))
            if home_i < away_i:
                self.rivalries[key]["a_wins"] += 1
            else:
                self.rivalries[key]["b_wins"] += 1
        else:
            A.wins += 1; H.losses += 1
            A.streak = A.streak + 1 if A.streak >= 0 else 1
            H.streak = H.streak - 1 if H.streak <= 0 else -1
            key = (min(home_i, away_i), max(home_i, away_i))
            if away_i < home_i:
                self.rivalries[key]["a_wins"] += 1
            else:
                self.rivalries[key]["b_wins"] += 1

        # contributions -> normalize to %
        def apply_contrib(T: Team, active_ids: List[str], pmap: Dict[str,float], bench_ids: List[str]):
            total = sum(pmap.values()) or 1.0
            for cid, val in pmap.items():
                c = self.cards[cid]
                c.games_played += 1
                pct = 100.0 * (val / total)
                c.contribution_sum += pct
            # benchers recover fatigue more
            for cid in bench_ids:
                self.cards[cid].fatigue = clamp(self.cards[cid].fatigue + random.uniform(10, 18))

        apply_contrib(H, h_active, h_map, h_bench)
        apply_contrib(A, a_active, a_map, a_bench)

        # fatigue decay for players who played
        def decay_fatigue(active_ids: List[str]):
            for cid in active_ids:
                c = self.cards[cid]
                c.fatigue = clamp(c.fatigue - random.uniform(8, 15))

        decay_fatigue(h_active)
        decay_fatigue(a_active)

        # decrement boost durations
        def tick_boosts(T: Team):
            nxt = []
            for b in T.boosts:
                if b["stat"] == "stamina_reset":
                    continue
                g = b.get("games_left", 0)
                if g > 1:
                    b["games_left"] = g - 1
                    nxt.append(b)
            T.boosts = nxt

        tick_boosts(H); tick_boosts(A)

        detail = f"{self.teams[home_i].name} vs {self.teams[away_i].name} — active subs: {len(h_bench)+len(a_bench)}"
        return h_score, a_score, detail

    # ------------------------------------------------------------------
    # Standings / Tables
    # ------------------------------------------------------------------

    def standings_table(self) -> List[Dict[str, Any]]:
        tbl = []
        for i, T in enumerate(self.teams):
            tbl.append({"Rank": i+1, "Team": T.name, "W": T.wins, "L": T.losses, "Streak": T.streak})
        tbl.sort(key=lambda x: (x["W"], -x["L"]), reverse=True)
        for i, r in enumerate(tbl):
            r["Rank"] = i+1
        return tbl

    # ------------------------------------------------------------------
    # Shop
    # ------------------------------------------------------------------

    def purchase_boost(self, team_idx: int, key: str, target_card: Optional[str]=None) -> Tuple[bool, str]:
        T = self.teams[team_idx]
        item = next((x for x in self.shop_catalog if x["key"] == key), None)
        if not item:
            return False, "Item not found."
        if T.shop_points_left < item["pts"]:
            return False, "Not enough shop points."
        if not item["teamwide"] and item["stat"] != "stamina_reset" and not target_card:
            return False, "This item needs a target card."
        entry = dict(item)
        entry["games_left"] = item["games"]
        if not item["teamwide"]:
            entry["target"] = target_card
        # stamina reset is immediate
        if item["stat"] == "stamina_reset" and target_card:
            self.cards[target_card].fatigue = 100.0
            T.shop_points_left -= item["pts"]
            self.transactions.append(f"Shop: {T.name} reset fatigue for {self.cards[target_card].name}")
            return True, "Fatigue reset applied."
        T.boosts.append(entry)
        T.shop_points_left -= item["pts"]
        self.transactions.append(f"Shop: {T.name} purchased {item['label']}")
        return True, "Boost added."

    # ------------------------------------------------------------------
    # Trades
    # ------------------------------------------------------------------

    def trade_finder_offers(self, your_idx: int, your_card: str) -> List[Dict[str, Any]]:
        offers = []
        yourT = self.teams[your_idx]
        yc = self.cards[your_card]
        for ti, T in enumerate(self.teams):
            if ti == your_idx:
                continue
            for cid in T.roster + ([T.backup] if T.backup else []):
                if not cid:
                    continue
                c = self.cards[cid]
                # simple heuristic: offer if total_power within ±8 and cap remains valid
                if abs(c.total_power - yc.total_power) <= 8:
                    new_cost_you = yourT.cost_spent - yc.cost + c.cost
                    new_cost_them = T.cost_spent - c.cost + yc.cost
                    if new_cost_you <= self.max_team_cost and new_cost_them <= self.max_team_cost:
                        offers.append({
                            "team_idx": ti, "team_name": T.name,
                            "their_card": cid, "their_card_name": c.name, "their_cost": c.cost
                        })
        return offers

    def execute_trade(self, your_idx: int, your_card: str, other_idx: int, their_card: str) -> Tuple[bool, str]:
        A = self.teams[your_idx]; B = self.teams[other_idx]
        if A.trade_card_used:
            return False, "You have already used your card-trade slot this season."
        # swap if appears in roster or backup
        def swap(T: Team, out_id: str, in_id: str):
            if out_id in T.roster:
                i = T.roster.index(out_id)
                T.roster[i] = in_id
            elif T.backup == out_id:
                T.backup = in_id

        if your_card not in A.roster + ([A.backup] if A.backup else []):
            return False, "Your card not on your team."
        if their_card not in B.roster + ([B.backup] if B.backup else []):
            return False, "Other card not on their team."

        yc = self.cards[your_card]; oc = self.cards[their_card]
        new_cost_A = A.cost_spent - yc.cost + oc.cost
        new_cost_B = B.cost_spent - oc.cost + yc.cost
        if new_cost_A > self.max_team_cost or new_cost_B > self.max_team_cost:
            return False, "Trade violates salary cap."

        swap(A, your_card, their_card)
        swap(B, their_card, your_card)
        A.cost_spent = new_cost_A; B.cost_spent = new_cost_B
        A.trade_card_used = True
        self.transactions.append(f"Trade: {A.name} traded {yc.name} ⇄ {oc.name} with {B.name}")
        return True, "Trade completed."

    # ------------------------------------------------------------------
    # Playoffs
    # ------------------------------------------------------------------

    def start_playoffs(self) -> None:
        """Seed top 16 by record. Series lengths: 3/5/5/7. Bracket pairs are (1,16),(2,15),..."""
        tbl = self.standings_table()
        order = [next(i for i,T in enumerate(self.teams) if T.name == row["Team"]) for row in tbl]
        seeds = order[:16]
        pairs = []
        for i in range(8):
            pairs.append((seeds[i], seeds[15-i]))
        self.playoffs = {"bracket": pairs, "results": [], "champion": None}

    def _simulate_series(self, a: int, b: int, best_of: int) -> int:
        wins_needed = best_of//2 + 1
        aw = bw = 0
        while aw < wins_needed and bw < wins_needed:
            hs, as_, _ = self._simulate_game(a, b)
            if hs > as_:
                aw += 1
            else:
                bw += 1
        return a if aw > bw else b

    def simulate_playoffs_to_champion(self) -> int:
        if not self.playoffs or not self.playoffs.get("bracket"):
            self.start_playoffs()
        pairs = self.playoffs["bracket"]
        rounds = [3,5,5,7]
        winners = []
        rnd_results = []
        current = pairs
        for rnd, bo in enumerate(rounds, start=1):
            winners = []
            for a,b in current:
                w = self._simulate_series(a,b,bo)
                winners.append(w)
                rnd_results.append({"round": rnd, "A": self.teams[a].name, "B": self.teams[b].name, "best_of": bo, "winner": self.teams[w].name})
            # next round pairing
            current = [(winners[i], winners[i+1]) for i in range(0, len(winners), 2)]

        champ = winners[0]
        self.playoffs["champion"] = self.teams[champ].name
        self.playoffs["results"] = rnd_results

        # increment GM title
        self.teams[champ].career_titles += 1
        return champ

    # ------------------------------------------------------------------
    # Awards & Patches & Retirements
    # ------------------------------------------------------------------

    def calculate_awards(self, champion_idx: int) -> Dict[str, Any]:
        """Compute MVP, DPOY, 6MOY, ROTY, Finals MVP (simple proxy)."""
        # Calculate per-card averages
        for c in self.cards.values():
            c.avg_pct_contributed = (c.contribution_sum / c.games_played) if c.games_played else 0.0

        # MVP: highest avg_pct_contributed (minimum games filter)
        candidates = [c for c in self.cards.values() if c.games_played >= 10 and not c.retired]
        mvp = max(candidates, key=lambda c: c.avg_pct_contributed, default=None)

        # DPOY: composite of DEF + (contribution weighted by DEF share)
        def d_def_score(c: Card) -> float:
            base = c.defense
            return base * (0.6 + 0.4 * (c.avg_pct_contributed/100.0))

        dpoy = max(candidates, key=d_def_score, default=None)

        # Sixth Man: best backup contribution (played many games as backup)
        # Heuristic: card whose fatigue stayed high (not over-used) but high contribution; or those flagged as backups on many teams
        sixth = max(candidates, key=lambda c: (c.avg_pct_contributed * (1.0 if c.pick_rate < 1.5 else 0.9)), default=None)

        # Rookie: lowest age (0) with strong avg contribution
        rookies = [c for c in self.cards.values() if c.age == 0 and not c.retired]
        roty = max(rookies, key=lambda c: c.avg_pct_contributed, default=None)

        # Finals MVP: pick among champion team's roster with highest contribution average
        champ_team = self.teams[champion_idx]
        finals_pool = [self.cards[cid] for cid in champ_team.roster if cid in self.cards]
        finals_mvp = max(finals_pool, key=lambda c: c.avg_pct_contributed, default=(finals_pool[0] if finals_pool else None))

        awards = {
            "MVP": mvp.name if mvp else None,
            "DPOY": dpoy.name if dpoy else None,
            "Sixth Man": sixth.name if sixth else None,
            "ROTY": roty.name if roty else None,
            "Finals MVP": finals_mvp.name if finals_mvp else None,
        }
        # Attach to cards
        for k, name in awards.items():
            if not name:
                continue
            card = next((c for c in self.cards.values() if c.name == name), None)
            if card:
                card.awards.append(f"{k} S{self.season}")

        return awards

    def adjust_costs(self, awards: Dict[str, Any]) -> None:
        # Small adjustments: MVP +0.5, DPOY +0.3, Finals MVP +0.3, ROTY +0.2, Sixth +0.2
        bumps = {"MVP": 0.5, "DPOY": 0.3, "Finals MVP": 0.3, "ROTY": 0.2, "Sixth Man": 0.2}
        for k, nm in awards.items():
            if not nm:
                continue
            for c in self.cards.values():
                if c.name == nm:
                    c.cost = round(c.cost + bumps[k], 2)

    def apply_patch(self) -> Dict[str, Any]:
        """Patch notes: random buffs/nerfs; retirements may be tagged as 'patch-related' later."""
        changes = []
        for c in random.sample(list(self.cards.values()), k=min(20, len(self.cards))):
            delta = random.randint(-4, 4)
            if delta == 0:
                continue
            # choose stat
            stat = random.choice(["attack","defense","speed","hit_speed","atk_type_score","synergy_score"])
            old = getattr(c, stat)
            new = int(clamp(old + delta, 30, 99))
            setattr(c, stat, new)
            # recompute total/grade
            raw_avg = (c.attack + c.defense + c.speed + c.hit_speed + c.atk_type_score + c.synergy_score)/6.0
            c.total_power = int(round(clamp(raw_avg + 0.25*(c.synergy_score-50))))
            c.grade = "S" if c.total_power >= 90 else "A" if c.total_power >= 80 else "B" if c.total_power >= 70 else "C" if c.total_power >= 60 else "D"
            changes.append({"card": c.name, "stat": stat, "delta": delta})
        patch = {"season": self.season, "nickname": random.choice(["Tank Nerf Patch","Speed Era Begins","Synergy Shuffle","Meta Mixer","Balance Tuning"]), "changes": changes}
        self.transactions.append(f"Patch {patch['nickname']} applied with {len(changes)} changes.")
        return patch

    def retire_and_add_rookies(self) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Retire 3 cards (or those exceeding lifespan) and add 4 rookies; keep pool <= 170."""
        retired = []
        # forced retirements by age
        force_ids = [cid for cid, c in self.cards.items() if (c.age >= c.lifespan or c.retired)]
        # choose additional retirements
        pool_ids = [cid for cid in self.cards if cid not in force_ids]
        rand_ids = random.sample(pool_ids, k=min(3, len(pool_ids)))
        for cid in set(force_ids + rand_ids):
            c = self.cards[cid]
            c.retired = True
            retired.append({"card": c.name, "reason": "Patch-related" if random.random() < 0.2 else "Age/Lifespan"})
        # age everyone else
        for c in self.cards.values():
            if not c.retired:
                c.age += 1
        # rookies
        rookies = []
        to_add = 4
        # keep pool size under cap by deleting fully retired + not on rosters
        active_ids = {cid for T in self.teams for cid in (T.roster + ([T.backup] if T.backup else []))}
        if len(self.cards) + to_add > 170:
            # prune retired non-rostered cards
            for cid in list(self.cards.keys()):
                if self.cards[cid].retired and cid not in active_ids:
                    del self.cards[cid]
        for i in range(to_add):
            cid = uid("C")
            ar = random.choice(ARCHETYPES)
            at = random.choice(ATTACK_TYPES)
            atk = random.randint(55, 92)
            dfn = random.randint(55, 92)
            spd = random.randint(55, 92)
            hsp = random.randint(45, 92)
            typ = random.randint(45, 92)
            syn = random.randint(45, 92)
            raw_avg = (atk + dfn + spd + hsp + typ + syn) / 6.0
            total = clamp(raw_avg + 0.25 * (syn - 50.0))
            grade = "S" if total >= 90 else "A" if total >= 80 else "B" if total >= 70 else "C" if total >= 60 else "D"
            base_cost = round(max(0.5, (total - 50) / 12.0), 2)
            cost = base_cost
            life = random.randint(3, 8)
            name = "Rookie " + self._generate_card_name(random.randint(1000, 9999))
            self.cards[cid] = Card(
                id=cid, name=name, archetype=ar, attack_type=at,
                attack=atk, defense=dfn, speed=spd, hit_speed=hsp,
                atk_type_score=typ, synergy_score=syn,
                total_power=int(round(total)), grade=grade,
                cost=cost, base_cost=base_cost, age=0, lifespan=life,
            )
            rookies.append({"card": name, "badge": "NEW"})
        return retired, rookies

    # ------------------------------------------------------------------
    # Archive
    # ------------------------------------------------------------------

    def archive_season(self, awards: Dict[str, Any], patch: Dict[str, Any],
                       retired: List[Dict[str, Any]], rookies: List[Dict[str, Any]], champion_idx: int) -> None:
        # standings snapshot
        standings = self.standings_table()
        # store season data
        self.past_seasons[self.season] = {
            "standings": standings,
            "awards": awards,
            "playoffs": {
                "champion": self.teams[champion_idx].name,
                "rounds": self.playoffs.get("results", []),
            },
            "retirements": retired,
            "rookies": rookies,
            "transactions": list(self.transactions),
            "patch_notes": patch,
        }
        # HOF probability update
        self._update_hof_probabilities()
        # reset in-season logs (kept in archive)
        self.transactions.clear()
        self.results.clear()
        self.playoffs = {}

    # ------------------------------------------------------------------
    # HOF Tracker
    # ------------------------------------------------------------------

    def _update_hof_probabilities(self) -> None:
        """Compute a rolling 'HOF probability' for each card based on awards,
        contribution, and longevity. Weighted awards: MVP > Finals MVP > DPOY > ROTY/6MOY.
        """
        for c in self.cards.values():
            score = 0.0
            # awards
            for a in c.awards:
                if "MVP" in a and "Finals" not in a:
                    score += 10
                elif "Finals MVP" in a:
                    score += 6
                elif "DPOY" in a:
                    score += 4
                elif "ROTY" in a or "Sixth Man" in a:
                    score += 2
            # contribution
            score += min(10.0, c.avg_pct_contributed / 10.0)  # up to +10
            # longevity
            score += min(8.0, c.age * 0.75)
            # grade / total
            score += (c.total_power - 60) * 0.2  # S-tier tends to rise
            c.hof_prob = clamp(score, 0, 100)

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def run_full_season_if_needed(self) -> None:
        if not self.season_complete():
            while not self.season_complete():
                self.simulate_next_day()
        champ_idx = self.simulate_playoffs_to_champion()
        awards = self.calculate_awards(champ_idx)
        self.adjust_costs(awards)
        patch = self.apply_patch()
        retired, rookies = self.retire_and_add_rookies()
        self.archive_season(awards, patch, retired, rookies, champ_idx)
        self.season += 1
        self.generate_calendar()
        self.start_preseason()
        self.save()

    def reset_new_league(self) -> None:
        random.seed(self.rng_seed)
        self.__init__(n_teams=len(self.teams), rng_seed=self.rng_seed)
        self.save()
