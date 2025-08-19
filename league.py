import json
import os
import random
from typing import List, Dict, Optional, Tuple

SAVE_FILE = "league_save.json"

# ---------------------- Data Classes ----------------------
class Card:
    def __init__(self, cid: str, name: str, archetype: str, attack_type: str,
                 attack: int, defense: int, speed: int, stamina: int, special: int,
                 cost: float, age: int = 0, lifespan: int = 8, retired: bool = False):
        self.id = cid
        self.name = name
        self.archetype = archetype
        self.attack_type = attack_type
        self.attack = attack
        self.defense = defense
        self.speed = speed
        self.stamina = stamina
        self.special = special
        self.base_cost = cost
        self.cost = cost
        self.age = age
        self.lifespan = lifespan
        self.retired = retired
        self.awards: List[str] = []
        self.history: List[Dict] = []

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "archetype": self.archetype,
            "attack_type": self.attack_type,
            "attack": self.attack,
            "defense": self.defense,
            "speed": self.speed,
            "stamina": self.stamina,
            "special": self.special,
            "base_cost": self.base_cost,
            "cost": self.cost,
            "age": self.age,
            "lifespan": self.lifespan,
            "retired": self.retired,
            "awards": self.awards,
            "history": self.history,
        }

    @staticmethod
    def from_dict(d):
        c = Card(
            d["id"], d["name"], d["archetype"], d["attack_type"],
            d["attack"], d["defense"], d["speed"], d["stamina"], d["special"],
            d.get("base_cost", d["cost"]), d.get("age", 0), d.get("lifespan", 8),
            d.get("retired", False)
        )
        c.cost = d.get("cost", c.base_cost)
        c.awards = d.get("awards", [])
        c.history = d.get("history", [])
        return c


class Team:
    def __init__(self, name: str, logo: str, gm_personality: str):
        self.name = name
        self.logo = logo
        self.gm_personality = gm_personality
        self.wins = 0
        self.losses = 0
        self.streak = 0
        self.roster: List[str] = []  # list of card ids
        self.backup: Optional[str] = None
        self.cost_spent = 0.0
        self.shop_points_left = 20.0
        self.boosts: List[Dict] = []

    def to_dict(self):
        return {
            "name": self.name,
            "logo": self.logo,
            "gm_personality": self.gm_personality,
            "wins": self.wins,
            "losses": self.losses,
            "streak": self.streak,
            "roster": self.roster,
            "backup": self.backup,
            "cost_spent": self.cost_spent,
            "shop_points_left": self.shop_points_left,
            "boosts": self.boosts,
        }

    @staticmethod
    def from_dict(d):
        t = Team(d["name"], d["logo"], d["gm_personality"])
        t.wins = d.get("wins", 0)
        t.losses = d.get("losses", 0)
        t.streak = d.get("streak", 0)
        t.roster = d.get("roster", [])
        t.backup = d.get("backup", None)
        t.cost_spent = d.get("cost_spent", 0.0)
        t.shop_points_left = d.get("shop_points_left", 20.0)
        t.boosts = d.get("boosts", [])
        return t


# ---------------------- League ----------------------
class League:
    def __init__(self):
        self.season = 1
        self.day = 1
        self.max_team_cost = 100.0
        self.teams: List[Team] = []
        self.cards: Dict[str, Card] = {}
        self.schedule: List[Tuple[int, int, int]] = []  # (day, home_idx, away_idx)
        self.results: List[Dict] = []
        self.transactions: List[str] = []
        self.rivalries: Dict[Tuple[int, int], Dict] = {}
        self.playoffs: Dict = {}
        self.past_seasons: Dict[int, Dict] = {}
        self.shop_catalog: List[Dict] = self.default_shop_catalog()
        self.rng_seed = random.randint(1, 1_000_000)
        random.seed(self.rng_seed)

    # ---------------------- Save / Load ----------------------
    def save(self, path: str = SAVE_FILE):
        data = {
            "season": self.season,
            "day": self.day,
            "max_team_cost": self.max_team_cost,
            "teams": [t.to_dict() for t in self.teams],
            "cards": {cid: c.to_dict() for cid, c in self.cards.items()},
            "schedule": self.schedule,
            "results": self.results,
            "transactions": self.transactions,
            "rivalries": self.rivalries,
            "playoffs": self.playoffs,
            "past_seasons": self.past_seasons,
            "shop_catalog": self.shop_catalog,
            "rng_seed": self.rng_seed,
        }
        with open(path, "w") as f:
            json.dump(data, f)

    @staticmethod
    def load(path: str) -> Optional["League"]:
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r") as f:
                data = json.load(f)
            L = League()
            L.season = data.get("season", 1)
            L.day = data.get("day", 1)
            L.max_team_cost = data.get("max_team_cost", 100.0)
            L.teams = [Team.from_dict(td) for td in data.get("teams", [])]
            L.cards = {cid: Card.from_dict(cd) for cid, cd in data.get("cards", {}).items()}
            L.schedule = data.get("schedule", [])
            L.results = data.get("results", [])
            L.transactions = data.get("transactions", [])
            L.rivalries = data.get("rivalries", {})
            L.playoffs = data.get("playoffs", {})
            L.past_seasons = data.get("past_seasons", {})
            L.shop_catalog = data.get("shop_catalog", [])
            L.rng_seed = data.get("rng_seed", random.randint(1, 1_000_000))
            random.seed(L.rng_seed)
            return L
        except Exception as e:
            print("Error loading league:", e)
            return None

    # ---------------------- Shop ----------------------
    def default_shop_catalog(self):
        return [
            {"key": "atk_boost", "label": "+2 ATK for 3 games", "pts": 5, "stat": "attack", "amount": 2, "games": 3, "teamwide": False},
            {"key": "def_boost", "label": "+2 DEF for 3 games", "pts": 5, "stat": "defense", "amount": 2, "games": 3, "teamwide": False},
            {"key": "spd_boost", "label": "+1 SPD for 3 games", "pts": 5, "stat": "speed", "amount": 1, "games": 3, "teamwide": False},
            {"key": "team_boost", "label": "+1 ATK to all starters for 2 games", "pts": 8, "stat": "attack", "amount": 1, "games": 2, "teamwide": True},
            {"key": "stamina_reset", "label": "Reset fatigue for one card", "pts": 3, "stat": "stamina_reset", "amount": 0, "games": 0, "teamwide": False},
        ]

    def purchase_boost(self, team_idx: int, item_key: str, target_card: Optional[str] = None):
        team = self.teams[team_idx]
        item = next((x for x in self.shop_catalog if x["key"] == item_key), None)
        if not item:
            return False, "Item not found."
        if team.shop_points_left < item["pts"]:
            return False, "Not enough shop points."
        if not item["teamwide"] and not target_card:
            return False, "Must specify a card."
        team.shop_points_left -= item["pts"]
        boost = {"key": item["key"], "stat": item["stat"], "amount": item["amount"], "teamwide": item["teamwide"], "games_left": item["games"]}
        if target_card:
            boost["target"] = target_card
        team.boosts.append(boost)
        self.transactions.append(f"{team.name} purchased {item['label']}")
        return True, f"{team.name} purchased {item['label']}"

    # ---------------------- Simulation ----------------------
    def simulate_next_day(self):
        games = [g for g in self.schedule if g[0] == self.day]
        if not games:
            self.day += 1
            return []

        recaps = []
        for d, a, b in games:
            home = self.teams[a]
            away = self.teams[b]
            home_score, away_score = self.simulate_match(home, away)
            if home_score > away_score:
                home.wins += 1
                home.streak = max(1, home.streak + 1)
                away.losses += 1
                away.streak = min(-1, away.streak - 1)
                winner = home.name
            else:
                away.wins += 1
                away.streak = max(1, away.streak + 1)
                home.losses += 1
                home.streak = min(-1, home.streak - 1)
                winner = away.name
            recap = {"day": self.day, "home": home.name, "away": away.name, "home_score": home_score, "away_score": away_score, "winner": winner, "comment": "GGs!"}
            self.results.append(recap)
            recaps.append(recap)
        self.day += 1
        return recaps

    def simulate_match(self, home: Team, away: Team) -> Tuple[int, int]:
        def team_strength(team: Team):
            strength = 0
            for cid in team.roster:
                if cid not in self.cards:
                    continue
                c = self.cards[cid]
                strength += c.attack + c.defense + c.speed + c.stamina + c.special
            # apply boosts
            for b in team.boosts:
                if b.get("games_left", 0) > 0:
                    if b["teamwide"]:
                        strength += b["amount"] * len(team.roster)
                    else:
                        strength += b["amount"]
                    b["games_left"] -= 1
            return strength
        return team_strength(home) + random.randint(0, 10), team_strength(away) + random.randint(0, 10)

    def season_complete(self):
        return all(g[0] < self.day for g in self.schedule)

    # ---------------------- Playoffs ----------------------
    def start_playoffs(self):
        standings = sorted(self.teams, key=lambda t: t.wins, reverse=True)
        top16 = standings[:16]
        self.playoffs = {"bracket": [(i, i+1) for i in range(0, len(top16), 2)], "results": []}

    def simulate_playoffs_to_champion(self):
        if not self.playoffs:
            return None
        bracket = self.playoffs.get("bracket", [])
        while len(bracket) > 1:
            next_round = []
            for a, b in bracket:
                home, away = self.teams[a], self.teams[b]
                hs, ascore = self.simulate_match(home, away)
                winner = a if hs > ascore else b
                next_round.append((winner,))
                self.playoffs["results"].append({"A": home.name, "B": away.name, "Score": f"{hs}-{ascore}", "Winner": self.teams[winner].name})
            bracket = [(next_round[i][0], next_round[i+1][0]) for i in range(0, len(next_round), 2) if i+1 < len(next_round)]
        champion_idx = bracket[0][0] if bracket else None
        if champion_idx is not None:
            self.playoffs["champion"] = self.teams[champion_idx].name
        return champion_idx

    # ---------------------- Awards, Patch, Archive ----------------------
    def calculate_awards(self, champion_idx: int):
        awards = {"MVP": self.teams[champion_idx].roster[0] if self.teams[champion_idx].roster else None}
        if awards["MVP"]:
            self.cards[awards["MVP"].strip()].awards.append("MVP")
        return awards

    def adjust_costs(self, awards: Dict):
        for cid, c in self.cards.items():
            if "MVP" in c.awards:
                c.cost += 2
            else:
                c.cost = max(1, c.cost - 0.5)

    def apply_patch(self):
        patch = {"nerfs": [], "buffs": []}
        for cid, c in self.cards.items():
            if random.random() < 0.05:
                c.attack -= 1
                patch["nerfs"].append(c.name)
            elif random.random() < 0.05:
                c.attack += 1
                patch["buffs"].append(c.name)
        return patch

    def retire_and_add_rookies(self):
        retired = []
        rookies = []
        for cid, c in list(self.cards.items()):
            c.age += 1
            if c.age >= c.lifespan:
                c.retired = True
                retired.append(c.name)
        for i in range(5):
            cid = f"R{i}_{self.season}"
            rookie = Card(cid, f"Rookie {i}", "NewGen", "Melee", 5, 5, 5, 5, 5, 5.0)
            self.cards[cid] = rookie
            rookies.append(rookie.name)
        return retired, rookies

    def archive_season(self, awards, patch, retired, rookies, champ_idx):
        self.past_seasons[self.season] = {
            "standings": self.standings_table(),
            "awards": awards,
            "patch_notes": patch,
            "retirements": retired,
            "rookies": rookies,
            "playoffs": self.playoffs,
            "transactions": self.transactions,
        }

    # ---------------------- Standings ----------------------
    def standings_table(self):
        return [{"Team": t.name, "W": t.wins, "L": t.losses, "Streak": t.streak} for t in self.teams]

    # ---------------------- Utilities ----------------------
    def reset_new_league(self):
        self.__init__()
        self.start_preseason()

    def run_full_season_if_needed(self):
        while not self.season_complete():
            self.simulate_next_day()
        champ_idx = self.simulate_playoffs_to_champion()
        awards = self.calculate_awards(champ_idx)
        self.adjust_costs(awards)
        patch = self.apply_patch()
        retired, rookies = self.retire_and_add_rookies()
        self.archive_season(awards, patch, retired, rookies, champ_idx)
        self.season += 1
        self.day = 1
        self.start_preseason()

    def generate_calendar(self):
        self.schedule = []
        days = 30
        team_indices = list(range(len(self.teams)))
        for d in range(1, days+1):
            a, b = random.sample(team_indices, 2)
            self.schedule.append((d, a, b))

    def start_preseason(self):
        if not self.teams:
            for i in range(30):
                self.teams
import json
import os
import random
import math
from typing import List, Dict, Optional, Tuple

SAVE_FILE = "league_save.json"

# ==========================================================
# Data Models
# ==========================================================
class Card:
    """Represents a single card in the league.

    Attributes used by the UI:
      - id, name, archetype, attack_type
      - attack, defense, speed, stamina, special  (all /100)
      - cost, base_cost
      - age, lifespan, retired
      - awards: List[str]
      - history: season-by-season snapshots (free-form dicts)
    """
    def __init__(
        self,
        cid: str,
        name: str,
        archetype: str,
        attack_type: str,
        attack: int,
        defense: int,
        speed: int,
        stamina: int,
        special: int,
        cost: float,
        age: int = 0,
        lifespan: int = 6,
        retired: bool = False,
    ):
        self.id = cid
        self.name = name
        self.archetype = archetype
        self.attack_type = attack_type
        self.attack = int(attack)
        self.defense = int(defense)
        self.speed = int(speed)
        self.stamina = int(stamina)
        self.special = int(special)
        self.base_cost = float(cost)
        self.cost = float(cost)
        self.age = int(age)
        self.lifespan = int(lifespan)
        self.retired = bool(retired)
        self.awards: List[str] = []
        self.history: List[Dict] = []

    # ---- Serialization ----
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "archetype": self.archetype,
            "attack_type": self.attack_type,
            "attack": self.attack,
            "defense": self.defense,
            "speed": self.speed,
            "stamina": self.stamina,
            "special": self.special,
            "base_cost": self.base_cost,
            "cost": self.cost,
            "age": self.age,
            "lifespan": self.lifespan,
            "retired": self.retired,
            "awards": list(self.awards),
            "history": list(self.history),
        }

    @staticmethod
    def from_dict(d: Dict) -> "Card":
        c = Card(
            d["id"],
            d["name"],
            d.get("archetype", "Hybrid"),
            d.get("attack_type", "Melee"),
            int(d.get("attack", 50)),
            int(d.get("defense", 50)),
            int(d.get("speed", 50)),
            int(d.get("stamina", 50)),
            int(d.get("special", 50)),
            float(d.get("base_cost", d.get("cost", 5.0))),
            int(d.get("age", 0)),
            int(d.get("lifespan", 6)),
            bool(d.get("retired", False)),
        )
        c.cost = float(d.get("cost", c.base_cost))
        c.awards = list(d.get("awards", []))
        c.history = list(d.get("history", []))
        return c


class Team:
    """Represents a fantasy team run by a GM."""

    def __init__(self, name: str, logo: str, gm_personality: str):
        self.name = name
        self.logo = logo
        self.gm_personality = gm_personality
        self.wins = 0
        self.losses = 0
        self.streak = 0  # +n = win streak, -n = losing streak
        self.roster: List[str] = []       # 3 starters (card ids)
        self.backup: Optional[str] = None # 1 backup (card id)
        self.cost_spent = 0.0
        self.shop_points_left = 0.0       # set at end of draft = leftover cap
        self.boosts: List[Dict] = []      # active boosts purchased in shop
        self.trades_used = 0              # count card trades used this season

    # ---- Serialization ----
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "logo": self.logo,
            "gm_personality": self.gm_personality,
            "wins": self.wins,
            "losses": self.losses,
            "streak": self.streak,
            "roster": list(self.roster),
            "backup": self.backup,
            "cost_spent": self.cost_spent,
            "shop_points_left": self.shop_points_left,
            "boosts": list(self.boosts),
            "trades_used": self.trades_used,
        }

    @staticmethod
    def from_dict(d: Dict) -> "Team":
        t = Team(d["name"], d.get("logo", "🏰"), d.get("gm_personality", "balanced"))
        t.wins = int(d.get("wins", 0))
        t.losses = int(d.get("losses", 0))
        t.streak = int(d.get("streak", 0))
        t.roster = list(d.get("roster", []))
        t.backup = d.get("backup")
        t.cost_spent = float(d.get("cost_spent", 0.0))
        t.shop_points_left = float(d.get("shop_points_left", 0.0))
        t.boosts = list(d.get("boosts", []))
        t.trades_used = int(d.get("trades_used", 0))
        return t


# ==========================================================
# League Engine
# ==========================================================
class League:
    """Core league simulation used by the Streamlit UI.

    API relied on by the current app.py (keep names stable):
      - attributes: season, day, max_team_cost, teams, cards, schedule,
                    results, transactions, rivalries, playoffs,
                    past_seasons, shop_catalog
      - methods: save, load, start_preseason, generate_calendar,
                 simulate_next_day, season_complete,
                 start_playoffs, simulate_playoffs_to_champion,
                 calculate_awards, adjust_costs, apply_patch,
                 retire_and_add_rookies, archive_season,
                 standings_table, purchase_boost,
                 trade_finder_offers, execute_trade,
                 run_full_season_if_needed, reset_new_league
    """

    # ---------------------- Init ----------------------
    def __init__(self):
        self.season: int = 1
        self.day: int = 1
        # Salary-cap spec from planning: 20 points max
        self.max_team_cost: float = 20.0

        self.teams: List[Team] = []
        self.cards: Dict[str, Card] = {}
        self.schedule: List[Tuple[int, int, int]] = []  # (day, home_idx, away_idx)
        self.results: List[Dict] = []
        self.transactions: List[str] = []
        self.rivalries: Dict[Tuple[int, int], Dict] = {}
        self.playoffs: Dict = {}
        self.past_seasons: Dict[int, Dict] = {}

        self.shop_catalog: List[Dict] = self._default_shop_catalog()

        self.rng_seed: int = random.randint(1, 1_000_000)
        random.seed(self.rng_seed)

    # ---------------------- Save / Load ----------------------
    def save(self, path: str = SAVE_FILE) -> None:
        data = {
            "season": self.season,
            "day": self.day,
            "max_team_cost": self.max_team_cost,
            "teams": [t.to_dict() for t in self.teams],
            "cards": {cid: c.to_dict() for cid, c in self.cards.items()},
            "schedule": list(self.schedule),
            "results": list(self.results),
            "transactions": list(self.transactions),
            "rivalries": {f"{a}-{b}": v for (a, b), v in self.rivalries.items()},
            "playoffs": self.playoffs,
            "past_seasons": self.past_seasons,
            "shop_catalog": self.shop_catalog,
            "rng_seed": self.rng_seed,
        }
        with open(path, "w") as f:
            json.dump(data, f)

    @staticmethod
    def load(path: str) -> Optional["League"]:
        """Load league from JSON file, or return None if missing/corrupt.
        This is tolerant to older save formats (uses .get defaults).
        """
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r") as f:
                data = json.load(f)
            L = League()
            L.season = int(data.get("season", 1))
            L.day = int(data.get("day", 1))
            L.max_team_cost = float(data.get("max_team_cost", 20.0))
            L.teams = [Team.from_dict(td) for td in data.get("teams", [])]
            L.cards = {cid: Card.from_dict(cd) for cid, cd in data.get("cards", {}).items()}
            L.schedule = [tuple(x) for x in data.get("schedule", [])]
            L.results = list(data.get("results", []))
            L.transactions = list(data.get("transactions", []))
            # Rivalries were stored with "a-b" keys for json-friendly format.
            riv = {}
            for k, v in data.get("rivalries", {}).items():
                try:
                    a, b = k.split("-")
                    riv[(int(a), int(b))] = v
                except Exception:
                    continue
            L.rivalries = riv
            L.playoffs = data.get("playoffs", {})
            L.past_seasons = data.get("past_seasons", {})
            L.shop_catalog = data.get("shop_catalog", L._default_shop_catalog())
            L.rng_seed = int(data.get("rng_seed", random.randint(1, 1_000_000)))
            random.seed(L.rng_seed)
            return L
        except Exception as e:
            print("Error loading league:", e)
            return None

    # ---------------------- Shop ----------------------
    def _default_shop_catalog(self) -> List[Dict]:
        # Costs expressed in leftover cap points (shop_points_left)
        return [
            {"key": "atk_boost", "label": "+2 ATK (3 games)", "pts": 4, "stat": "attack", "amount": 2, "games": 3, "teamwide": False},
            {"key": "def_boost", "label": "+2 DEF (3 games)", "pts": 4, "stat": "defense", "amount": 2, "games": 3, "teamwide": False},
            {"key": "spd_boost", "label": "+2 SPD (3 games)", "pts": 4, "stat": "speed", "amount": 2, "games": 3, "teamwide": False},
            {"key": "team_atk", "label": "+1 ATK (team, 2 games)", "pts": 6, "stat": "attack", "amount": 1, "games": 2, "teamwide": True},
            {"key": "stamina_reset", "label": "Reset fatigue (1 card)", "pts": 3, "stat": "stamina_reset", "amount": 0, "games": 0, "teamwide": False},
        ]

    def purchase_boost(self, team_idx: int, item_key: str, target_card: Optional[str] = None) -> Tuple[bool, str]:
        team = self.teams[team_idx]
        item = next((x for x in self.shop_catalog if x["key"] == item_key), None)
        if not item:
            return False, "Item not found."
        if team.shop_points_left < item["pts"]:
            return False, "Not enough shop points."
        # Target needed for non-teamwide boosts (except teamwide items)
        if not item["teamwide"] and item["stat"] != "stamina_reset" and not target_card:
            return False, "Select a target card."
        team.shop_points_left -= float(item["pts"])
        boost = {
            "key": item["key"],
            "stat": item["stat"],
            "amount": item["amount"],
            "teamwide": item["teamwide"],
            "games_left": item["games"],
        }
        if target_card:
            boost["target"] = target_card
        team.boosts.append(boost)
        self.transactions.append(f"{team.name} purchased {item['label']}")
        return True, f"{team.name} purchased {item['label']}"

    # ---------------------- Season Flow ----------------------
    def start_preseason(self) -> None:
        """Create cards/teams if missing, then draft 3+1 per team under cap.
        Also regenerates schedule and resets team records.
        """
        if not self.cards:
            self._generate_initial_cards(target=160)
        if not self.teams:
            self._generate_teams(n=30)
        # reset team records
        for T in self.teams:
            T.wins = T.losses = T.streak = 0
            T.roster = []
            T.backup = None
            T.boosts = []
            T.trades_used = 0
            T.cost_spent = 0.0
            T.shop_points_left = 0.0
        # perform draft
        self._fantasy_draft()
        # calendar & rivalries
        self.generate_calendar()
        self._initialize_rivalries()

    def generate_calendar(self) -> None:
        """20 weeks with 40 total regular-season game days.
        We'll schedule 1 game per day, pairing random teams (no repeats heavy enforcement).
        """
        self.schedule = []
        n_days = 40
        n_teams = len(self.teams)
        for d in range(1, n_days + 1):
            a, b = random.sample(range(n_teams), 2)
            self.schedule.append((d, a, b))
        self.day = 1

    def _initialize_rivalries(self) -> None:
        self.rivalries = {}
        for (d, a, b) in self.schedule:
            key = (min(a, b), max(a, b))
            if key not in self.rivalries:
                self.rivalries[key] = {"games": 0, "a_wins": 0, "b_wins": 0}
            self.rivalries[key]["games"] += 1

    # ---------------------- Simulation ----------------------
    def simulate_next_day(self) -> List[Dict]:
        games = [g for g in self.schedule if g[0] == self.day]
        recaps: List[Dict] = []
        if not games:
            # still advance day until end of schedule
            if not self.season_complete():
                self.day += 1
            return recaps
        for _, a, b in games:
            home = self.teams[a]
            away = self.teams[b]
            hs, ascore, detail = self._simulate_match(a, b)
            if hs > ascore:
                self._apply_result(home, away, winner_is_home=True)
                winner = home.name
                # rivalry stats
                self._bump_rivalry(a, b, a_win=True)
            else:
                self._apply_result(home, away, winner_is_home=False)
                winner = away.name
                self._bump_rivalry(a, b, a_win=False)
            recap = {
                "day": self.day,
                "home": home.name,
                "away": away.name,
                "home_score": hs,
                "away_score": ascore,
                "winner": winner,
                "comment": detail,
            }
            self.results.append(recap)
            recaps.append(recap)
        self.day += 1
        return recaps

    def _apply_result(self, home: Team, away: Team, winner_is_home: bool) -> None:
        if winner_is_home:
            home.wins += 1
            home.streak = home.streak + 1 if home.streak >= 0 else 1
            away.losses += 1
            away.streak = away.streak - 1 if away.streak <= 0 else -1
        else:
            away.wins += 1
            away.streak = away.streak + 1 if away.streak >= 0 else 1
            home.losses += 1
            home.streak = home.streak - 1 if home.streak <= 0 else -1

    def _bump_rivalry(self, a_idx: int, b_idx: int, a_win: bool) -> None:
        key = (min(a_idx, b_idx), max(a_idx, b_idx))
        rv = self.rivalries.get(key)
        if not rv:
            rv = {"games": 0, "a_wins": 0, "b_wins": 0}
            self.rivalries[key] = rv
        rv["games"] += 0  # already incremented at schedule creation
        if a_idx < b_idx:
            if a_win:
                rv["a_wins"] += 1
            else:
                rv["b_wins"] += 1
        else:
            if a_win:
                rv["b_wins"] += 1
            else:
                rv["a_wins"] += 1

    def _simulate_match(self, home_idx: int, away_idx: int) -> Tuple[int, int, str]:
        home = self.teams[home_idx]
        away = self.teams[away_idx]

        def card_power(c: Card) -> float:
            return c.attack + c.defense + c.speed + c.stamina + c.special

        def apply_boosts(team: Team, base: float) -> float:
            bonus = 0.0
            to_remove = []
            for b in team.boosts:
                if b.get("games_left", 0) <= 0:
                    continue
                if b["teamwide"]:
                    # +amount per starter
                    bonus += float(b["amount"]) * 3.0
                else:
                    # single card boost → approximate +amount
                    bonus += float(b["amount"]) * 1.0
                b["games_left"] -= 1
                if b["games_left"] <= 0:
                    to_remove.append(b)
            # cleanup expired
            for b in to_remove:
                try:
                    team.boosts.remove(b)
                except ValueError:
                    pass
            return base + bonus

        def team_strength(T: Team) -> float:
            base = 0.0
            # Sum starters
            for cid in T.roster:
                c = self.cards.get(cid)
                if not c or c.retired:
                    continue
                base += card_power(c)
            # Backup may sub if a random fatigue check triggers (simple model)
            if T.backup and random.random() < 0.15:
                cbu = self.cards.get(T.backup)
                if cbu and not cbu.retired:
                    base += 0.25 * card_power(cbu)
            # apply boosts
            base = apply_boosts(T, base)
            return base

        hs = int(team_strength(home) / 25.0 + random.randint(0, 10))
        ascore = int(team_strength(away) / 25.0 + random.randint(0, 10))
        detail = "Regular season clash"
        return hs, ascore, detail

    def season_complete(self) -> bool:
        return self.day > (self.schedule[-1][0] if self.schedule else 0)

    # ---------------------- Playoffs ----------------------
    def start_playoffs(self) -> None:
        # Seed top 16 by wins (ties arbitrary)
        order = sorted(range(len(self.teams)), key=lambda i: self.teams[i].wins, reverse=True)
        seeds = order[:16]
        # Round pairs 1v16, 8v9, etc.
        pairs = []
        for i in range(8):
            pairs.append((seeds[i], seeds[15 - i]))
        self.playoffs = {
            "round": 1,
            "round_lengths": {1: 3, 2: 5, 3: 5, 4: 7},  # Bo3, Bo5, Bo5, Bo7
            "pairs": pairs,
            "series": {f"{a}-{b}": {"a_wins": 0, "b_wins": 0} for a, b in pairs},
            "results": [],
            "champion": None,
        }

    def simulate_playoffs_to_champion(self) -> Optional[int]:
        if not self.playoffs:
            return None
        while self.playoffs.get("champion") is None:
            self._simulate_playoff_round()
        champ_name = self.playoffs.get("champion")
        for i, T in enumerate(self.teams):
            if T.name == champ_name:
                return i
        return None

    def _simulate_playoff_round(self) -> None:
        r = int(self.playoffs.get("round", 1))
        length = self.playoffs["round_lengths"].get(r, 7)
        pairs = list(self.playoffs.get("pairs", []))
        winners: List[int] = []
        for a, b in pairs:
            key = f"{a}-{b}"
            series = self.playoffs["series"].get(key, {"a_wins": 0, "b_wins": 0})
            a_wins = series["a_wins"]
            b_wins = series["b_wins"]
            # play until someone reaches majority
            needed = (length // 2) + 1
            while a_wins < needed and b_wins < needed:
                hs, ascore, _ = self._simulate_match(a, b)
                if hs > ascore:
                    a_wins += 1
                else:
                    b_wins += 1
            series["a_wins"], series["b_wins"] = a_wins, b_wins
            self.playoffs["series"][key] = series
            self.playoffs["results"].append({
                "round": r,
                "A": self.teams[a].name,
                "B": self.teams[b].name,
                "best_of": length,
                "final": f"{a_wins}-{b_wins}",
                "winner": self.teams[a].name if a_wins > b_wins else self.teams[b].name,
            })
            winners.append(a if a_wins > b_wins else b)
        if len(winners) == 1:
            self.playoffs["champion"] = self.teams[winners[0]].name
            return
        # next round re-seed bracket style
        next_pairs = []
        for i in range(0, len(winners), 2):
            if i + 1 < len(winners):
                next_pairs.append((winners[i], winners[i + 1]))
        self.playoffs["round"] = r + 1
        self.playoffs["pairs"] = next_pairs
        self.playoffs["series"] = {f"{a}-{b}": {"a_wins": 0, "b_wins": 0} for a, b in next_pairs}

    # ---------------------- Awards / Patch / Lifecycle ----------------------
    def calculate_awards(self, champion_idx: Optional[int]) -> Dict:
        """Very light-weight awards to satisfy UI needs (can be expanded)."""
        awards = {"MVP": None}
        # MVP: strongest card on best regular-season team
        best_team_idx = max(range(len(self.teams)), key=lambda i: self.teams[i].wins)
        best_team = self.teams[best_team_idx]
        best_cid = None
        best_power = -1
        for cid in best_team.roster:
            c = self.cards.get(cid)
            if not c:
                continue
            p = c.attack + c.defense + c.speed + c.stamina + c.special
            if p > best_power:
                best_power = p
                best_cid = cid
        if best_cid:
            awards["MVP"] = best_cid
            self.cards[best_cid].awards.append("MVP")
        # Finals MVP if champion known: top power on champion roster
        if champion_idx is not None:
            champ = self.teams[champion_idx]
            top_cid = None
            top_pow = -1
            for cid in champ.roster:
                c = self.cards.get(cid)
                if not c:
                    continue
                p = c.attack + c.defense + c.speed + c.stamina + c.special
                if p > top_pow:
                    top_pow = p
                    top_cid = cid
            if top_cid:
                self.cards[top_cid].awards.append("Finals MVP")
                awards["Finals MVP"] = top_cid
        return awards

    def adjust_costs(self, awards: Dict) -> None:
        # Simple economics: MVP +1.5 cost, others -0.2 floor 1
        for c in self.cards.values():
            if c.retired:
                continue
            if any(a in c.awards for a in ("MVP", "Finals MVP")):
                c.cost = min(10.0, c.cost + 1.5)
            else:
                c.cost = max(1.0, c.cost - 0.2)

    def apply_patch(self) -> Dict:
        """Random buffs/nerfs each season to keep meta shifting."""
        patch = {"buffs": [], "nerfs": []}
        for c in self.cards.values():
            if c.retired:
                continue
            r = random.random()
            if r < 0.05:  # nerf
                delta = random.randint(1, 3)
                c.attack = max(1, c.attack - delta)
                patch["nerfs"].append({"card": c.name, "attack": -delta})
            elif r < 0.10:  # buff
                delta = random.randint(1, 3)
                c.attack = min(100, c.attack + delta)
                patch["buffs"].append({"card": c.name, "attack": +delta})
        return patch

    def retire_and_add_rookies(self) -> Tuple[List[Dict], List[Dict]]:
        """Age everyone, retire ~3, add 4 rookies, keep total between 160–170."""
        retired: List[Dict] = []
        for c in self.cards.values():
            if c.retired:
                continue
            c.age += 1
            if c.age >= c.lifespan and random.random() < 0.6:
                c.retired = True
                retired.append({"id": c.id, "name": c.name})
        # Ensure at least 3 retirements if pool is big
        actives = [c for c in self.cards.values() if not c.retired]
        need_force = max(0, 3 - len(retired)) if len(actives) > 100 else 0
        if need_force:
            force_list = random.sample([c for c in actives if c.age >= c.lifespan - 1], k=min(need_force, len(actives)))
            for c in force_list:
                c.retired = True
                retired.append({"id": c.id, "name": c.name})
        # Add 4 rookies
        rookies: List[Dict] = []
        for i in range(4):
            cid = f"S{self.season}_R{i}_{random.randint(1000,9999)}"
            archetype = random.choice(["Tank", "DPS", "Control", "Support", "Hybrid"])
            atk, dfn, spd, sta, spc = [random.randint(45, 75) for _ in range(5)]
            cost = self._cost_from_power(atk + dfn + spd + sta + spc)
            life = random.randint(3, 8)
            c = Card(cid, f"Rookie {i}", archetype, random.choice(["Melee", "Ranged"]), atk, dfn, spd, sta, spc, cost, age=0, lifespan=life, retired=False)
            self.cards[cid] = c
            rookies.append({"id": c.id, "name": c.name})
        # Clamp total 160–170 by retiring oldest extras if needed
        total = len(self.cards)
        if total > 170:
            extras = total - 170
            candidates = sorted([c for c in self.cards.values() if not c.retired], key=lambda x: (x.age, x.cost), reverse=True)
            for c in candidates[:extras]:
                c.retired = True
                retired.append({"id": c.id, "name": c.name})
        return retired, rookies

    def archive_season(self, awards: Dict, patch: Dict, retired: List[Dict], rookies: List[Dict], champ_idx: Optional[int]) -> None:
        self.past_seasons[self.season] = {
            "standings": self.standings_table(),
            "awards": awards,
            "patch_notes": patch,
            "retirements": retired,
            "rookies": rookies,
            "playoffs": self.playoffs,
            "transactions": list(self.transactions),
        }

    # ---------------------- Standings ----------------------
    def standings_table(self) -> List[Dict]:
        return [
            {"Team": t.name, "W": t.wins, "L": t.losses, "Streak": t.streak}
            for t in self.teams
        ]

    # ---------------------- Trades ----------------------
    def trade_finder_offers(self, own_team_idx: int, my_card_id: str) -> List[Dict]:
        """Return simple 1-for-1 offers that keep both teams under the cap."""
        offers: List[Dict] = []
        my_team = self.teams[own_team_idx]
        my_cost_minus = self.cards.get(my_card_id).cost if my_card_id in self.cards else 0.0
        for j, other in enumerate(self.teams):
            if j == own_team_idx:
                continue
            # consider their starters and backup
            pool = list(other.roster)
            if other.backup:
                pool.append(other.backup)
            for their_id in pool:
                c_their = self.cards.get(their_id)
                if not c_their or c_their.retired:
                    continue
                # compute hypothetical costs
                my_new_cost = my_team.cost_spent - my_cost_minus + c_their.cost
                their_new_cost = other.cost_spent - c_their.cost + my_cost_minus
                if my_new_cost <= self.max_team_cost and their_new_cost <= self.max_team_cost:
                    offers.append({
                        "team_name": other.name,
                        "team_idx": j,
                        "their_card": their_id,
                        "their_card_name": c_their.name,
                        "their_cost": c_their.cost,
                    })
        # Return up to 10 offers
        random.shuffle(offers)
        return offers[:10]

    def execute_trade(self, own_team_idx: int, my_card_id: str, other_team_idx: int, their_card_id: str) -> Tuple[bool, str]:
        A = self.teams[own_team_idx]
        B = self.teams[other_team_idx]
        if A.trades_used >= 1:
            return False, "You have already used your card trade this season."
        if my_card_id not in A.roster and my_card_id != A.backup:
            return False, "You don't own that card."
        if their_card_id not in B.roster and their_card_id != B.backup:
            return False, "Other team doesn't own that card."
        ca = self.cards.get(my_card_id)
        cb = self.cards.get(their_card_id)
        if not ca or not cb:
            return False, "Card not found."
        # compute new costs
        new_cost_A = A.cost_spent - ca.cost + cb.cost
        new_cost_B = B.cost_spent - cb.cost + ca.cost
        if new_cost_A > self.max_team_cost or new_cost_B > self.max_team_cost:
            return False, "Trade breaks salary cap."
        # swap (prefer swapping in starters if present; otherwise touch backup)
        def swap(team: Team, give_id: str, get_id: str) -> None:
            if give_id in team.roster:
                idx = team.roster.index(give_id)
                team.roster[idx] = get_id
            elif team.backup == give_id:
                team.backup = get_id

        swap(A, my_card_id, their_card_id)
        swap(B, their_card_id, my_card_id)
        A.cost_spent = new_cost_A
        B.cost_spent = new_cost_B
        A.trades_used += 1
        self.transactions.append(f"TRADE: {A.name} sent {ca.name} for {cb.name} from {B.name}")
        return True, "Trade executed."

    # ---------------------- Utilities ----------------------
    def reset_new_league(self) -> None:
        self.__init__()
        self.start_preseason()

    def run_full_season_if_needed(self) -> None:
        while not self.season_complete():
            self.simulate_next_day()
        champ_idx = None
        if not self.playoffs:
            self.start_playoffs()
        champ_idx = self.simulate_playoffs_to_champion()
        awards = self.calculate_awards(champ_idx)
        self.adjust_costs(awards)
        patch = self.apply_patch()
        retired, rookies = self.retire_and_add_rookies()
        self.archive_season(awards, patch, retired, rookies, champ_idx)
        # advance to next season
        self.season += 1
        self.results = []
        self.transactions = []
        self.playoffs = {}
        self.start_preseason()

    # ======================================================
    # Internal helpers
    # ======================================================
    def _generate_initial_cards(self, target: int = 160) -> None:
        """Generate a pool of cards with varied archetypes and lifespans.
        Costs scale loosely with total power so drafting fits a 20-point cap.
        """
        names = self._seed_card_names(target)
        for i in range(target):
            cid = f"C{i:03d}"
            name = names[i]
            archetype = random.choice(["Tank", "DPS", "Control", "Support", "Hybrid"])
            atk = random.randint(45, 90)
            dfn = random.randint(45, 90)
            spd = random.randint(45, 90)
            sta = random.randint(45, 90)
            spc = random.randint(45, 90)
            cost = self._cost_from_power(atk + dfn + spd + sta + spc)
            life = random.randint(3, 8)
            card = Card(
                cid,
                name,
                archetype,
                random.choice(["Melee", "Ranged"]),
                atk,
                dfn,
                spd,
                sta,
                spc,
                cost,
                lifespan=life,
            )
            self.cards[cid] = card

    def _cost_from_power(self, power: int) -> float:
        # Map total stat 225–450 roughly to cost 3.0–9.0, then clamp 1–10
        x = 3.0 + (power - 225) / 225.0 * 6.0
        return float(max(1.0, min(10.0, round(x, 1))))

    def _generate_teams(self, n: int = 30) -> None:
        logos = ["🐲", "🦅", "🦁", "🐺", "🦂", "🦄", "🐯", "🐻", "🦊", "🐼", "🐮", "🐵", "🦉", "🐗", "🐸"]
        styles = ["aggressive", "balanced", "cautious", "chaotic", "methodical"]
        for i in range(n):
            name = f"Team {chr(65 + (i % 26))}{'' if i < 26 else i}"
            logo = random.choice(logos)
            gm = random.choice(styles)
            self.teams.append(Team(name, logo, gm))

    def _fantasy_draft(self) -> None:
        """Each team drafts 3 starters + 1 backup under the 20-point cap.
        Draft order snake-style by random order.
        """
        # candidate pool: active cards only
        pool = [c for c in self.cards.values() if not c.retired]
        random.shuffle(pool)
        order = list(range(len(self.teams)))
        random.shuffle(order)
        rounds = 4  # 3 starters + 1 backup
        for r in range(rounds):
            order_iter = order if r % 2 == 0 else list(reversed(order))
            for ti in order_iter:
                T = self.teams[ti]
                # pick best affordable
                pick = self._best_affordable_card(pool, T.cost_spent, self.max_team_cost)
                if not pick:
                    # if no affordable left, pick the cheapest remaining
                    if not pool:
                        continue
                    pick = min(pool, key=lambda c: c.cost)
                # assign
                if r < 3:
                    T.roster.append(pick.id)
                else:
                    T.backup = pick.id
                T.cost_spent += pick.cost
                # remove from pool
                pool.remove(pick)
        # compute leftover -> shop points
        for T in self.teams:
            T.shop_points_left = max(0.0, round(self.max_team_cost - T.cost_spent, 2))

    def _best_affordable_card(self, pool: List[Card], current_cost: float, cap: float) -> Optional[Card]:
        affordable = [c for c in pool if current_cost + c.cost <= cap]
        if not affordable:
            return None
        # choose by highest total power
        return max(affordable, key=lambda c: c.attack + c.defense + c.speed + c.stamina + c.special)
