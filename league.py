# league.py
from __future__ import annotations
import json, random, math, os
from dataclasses import dataclass, asdict, field
from typing import List, Dict, Optional, Tuple

SAVE_FILE = "league_save.json"

ARCHETYPES = ["Tank", "DPS", "Support", "Control", "Speedster"]
ATTACK_TYPES = ["Melee", "Ranged", "AoE", "Magic", "Pierce"]

def clamp(v, lo, hi): return max(lo, min(hi, v))

# --------- Data Models ---------
@dataclass
class Card:
    id: str
    name: str
    archetype: str
    attack_type: str
    attack: int
    defense: int
    speed: int
    stamina: int
    special: int
    base_cost: float
    cost: float
    age: int = 0
    lifespan: int = 10
    last_changed_season: Optional[int] = None
    history: List[Dict] = field(default_factory=list)  # per-season snapshots
    popularity: float = 0.5  # 0..1
    awards: List[str] = field(default_factory=list)
    retired: bool = False

    def power_score(self):
        # Simple weighted total; special is a spice stat
        return self.attack*0.34 + self.defense*0.28 + self.speed*0.22 + self.stamina*0.10 + self.special*0.06

    def season_snapshot(self, season:int) -> Dict:
        return {
            "season": season,
            "attack": self.attack, "defense": self.defense, "speed": self.speed,
            "stamina": self.stamina, "special": self.special, "cost": self.cost,
            "popularity": self.popularity, "awards": list(self.awards)
        }

@dataclass
class Team:
    name: str
    logo: str
    color: str
    gm_personality: str  # "Win-Now", "Rebuilder", "Balanced", "Wildcard"
    roster: List[str] = field(default_factory=list)  # 3 starters
    backup: Optional[str] = None
    wins: int = 0
    losses: int = 0
    streak: int = 0
    momentum: float = 0.0  # -0.10..+0.10
    cost_spent: float = 0.0
    shop_points_left: float = 0.0
    boosts: List[Dict] = field(default_factory=list)  # active timed boosts
    transactions: List[str] = field(default_factory=list)

    def add_result(self, win: bool):
        if win:
            self.wins += 1
            self.streak = self.streak + 1 if self.streak >= 0 else 1
        else:
            self.losses += 1
            self.streak = self.streak - 1 if self.streak <= 0 else -1
        # Momentum +/-2% per game, capped ±10%
        if self.streak > 0:
            self.momentum = clamp(0.02 * self.streak, -0.10, 0.10)
        elif self.streak < 0:
            self.momentum = clamp(-0.02 * abs(self.streak), -0.10, 0.10)
        else:
            self.momentum = 0.0

# --------- League Engine ---------
class League:
    def __init__(self):
        self.season = 1
        self.day = 0  # calendar day index
        self.max_team_cost = 20.0
        self.teams: List[Team] = []
        self.cards: Dict[str, Card] = {}
        self.free_agents: List[str] = []
        self.draft_order: List[int] = []
        self.schedule: List[Tuple[int,int,int]] = []  # (day, team_idx_a, team_idx_b)
        self.results: List[Dict] = []
        self.transactions: List[str] = []
        self.past_seasons: Dict[int, Dict] = {}
        self.playoffs: Dict = {}
        self.shop_catalog = [
            {"key":"atk5","label":"+1 Attack (5 games)","pts":1.0,"stat":"attack","amount":1,"games":5,"teamwide":False},
            {"key":"def5","label":"+1 Defense (5 games)","pts":1.0,"stat":"defense","amount":1,"games":5,"teamwide":False},
            {"key":"spd5","label":"+1 Speed (5 games)","pts":1.0,"stat":"speed","amount":1,"games":5,"teamwide":False},
            {"key":"all2","label":"+1 All Stats (2 games)","pts":2.0,"stat":"all","amount":1,"games":2,"teamwide":False},
            {"key":"fatigue","label":"Reset Stamina (1 card)","pts":1.5,"stat":"stamina_reset","amount":0,"games":0,"teamwide":False},
            {"key":"chem","label":"Team Chemistry +2% (3 games)","pts":2.0,"stat":"chem","amount":0.02,"games":3,"teamwide":True},
            {"key":"rival","label":"Rivalry Bonus +3% (season)","pts":0.5,"stat":"rival","amount":0.03,"games":0,"teamwide":True},
        ]
        self.rivalries: Dict[Tuple[int,int], Dict] = {}  # (min_i,max_i)-> {"games": n, "a_wins":x, "b_wins":y}
        self.generate_initial_state()

    # ---------- Persistence ----------
    def to_dict(self):
        return {
            "season": self.season,
            "day": self.day,
            "max_team_cost": self.max_team_cost,
            "teams": [asdict(t) for t in self.teams],
            "cards": {cid: asdict(c) for cid,c in self.cards.items()},
            "free_agents": self.free_agents,
            "draft_order": self.draft_order,
            "schedule": self.schedule,
            "results": self.results,
            "transactions": self.transactions,
            "past_seasons": self.past_seasons,
            "playoffs": self.playoffs,
            "shop_catalog": self.shop_catalog,
            "rivalries": {f"{a}-{b}":v for (a,b),v in self.rivalries.items()}
        }

    @classmethod
    def from_dict(cls, data):
        L = cls.__new__(cls)
        for k in ["season","day","max_team_cost","free_agents","draft_order","schedule","results","transactions","past_seasons","playoffs","shop_catalog"]:
            setattr(L, k, data.get(k))
        # Teams
        L.teams = [Team(**t) for t in data["teams"]]
        # Cards
        L.cards = {cid: Card(**c) for cid,c in data["cards"].items()}
        # Rivalries
        L.rivalries = {}
        for k,v in data.get("rivalries", {}).items():
            a,b = map(int, k.split("-"))
            L.rivalries[(a,b)] = v
        return L

    def save(self, path: str = SAVE_FILE):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)

    @staticmethod
    def load(path: str = SAVE_FILE) -> Optional["League"]:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return League.from_dict(data)
        return None

    def reset_new_league(self):
        self.__init__()

    # ---------- Setup ----------
    def generate_initial_state(self):
        # 30 teams (user will rename Team 1)
        colors = ["#FF6B6B","#4D96FF","#06D6A0","#FFD166","#8338EC","#F06595",
                  "#48CAE4","#F8961E","#2EC4B6","#9B5DE5"]
        logos = ["🛡️","⚔️","🐲","🔥","❄️","⚡","🦅","🦂","🧊","🌪️"]
        personalities = ["Win-Now","Rebuilder","Balanced","Wildcard"]
        self.teams = []
        for i in range(30):
            self.teams.append(Team(
                name=f"Team {i+1}",
                logo=random.choice(logos),
                color=random.choice(colors),
                gm_personality=random.choice(personalities)
            ))
        # 120 cards in Season 1
        self.cards = {}
        for i in range(120):
            cid = f"C{i+1}"
            arc = random.choice(ARCHETYPES)
            atk_type = random.choice(ATTACK_TYPES)
            attack = random.randint(50, 95)
            defense = random.randint(45, 95)
            speed = random.randint(45, 95)
            stamina = random.randint(60, 95)
            special = random.randint(40, 90)
            lifespan = random.randint(8,15)
            base_cost = round(random.uniform(1.0,7.0),1)
            c = Card(
                id=cid,
                name=self._random_card_name(i),
                archetype=arc,
                attack_type=atk_type,
                attack=attack, defense=defense, speed=speed, stamina=stamina, special=special,
                base_cost=base_cost, cost=base_cost, lifespan=lifespan
            )
            self.cards[cid] = c
        self.transactions = []
        self.schedule = []
        self.results = []
        self.past_seasons = {}
        self.playoffs = {}
        self.free_agents = []
        self.generate_calendar()

    def _random_card_name(self, idx:int) -> str:
        a = ["Flame","Frost","Shadow","Crystal","Storm","Boulder","Volt","Inferno","Ghost","Steel","Arcane","Lava","Gale","Thorn","Rift","Blaze","Echo","Viper","Rune","Nova"]
        b = ["Knight","Archer","Golem","Mage","Assassin","Dragon","Sentinel","Djinn","Monk","Juggernaut","Spear","Warden","Harpy","Titan","Spirit","Ranger","Phantom","Seer","Giant","Shifter"]
        return f"{random.choice(a)} {random.choice(b)}"

    # ---------- Season Cycle ----------
    def start_preseason(self):
        # Draft lottery from last season standings (if season>1), else random
        standings = sorted(range(len(self.teams)), key=lambda i: (self.teams[i].wins - self.teams[i].losses))
        lottery_weights = []
        n = len(self.teams)
        for rank,i in enumerate(standings):
            # Worse teams get more weight
            lottery_weights.append((i, (rank+1)))
        pool = [i for i,w in lottery_weights for _ in range(w)]
        random.shuffle(pool)
        seen=set()
        order=[]
        for p in pool:
            if p not in seen:
                order.append(p); seen.add(p)
            if len(order)==len(self.teams): break
        self.draft_order = order
        # Draft 3 rounds
        self._perform_draft()
        # Free Agency: remaining cards available, sign 1 backup per team
        self._free_agency_signing()
        # Cost & shop points calc
        for t in self.teams:
            t.cost_spent = sum(self.cards[cid].cost for cid in t.roster if cid in self.cards)
            t.shop_points_left = max(0.0, self.max_team_cost - t.cost_spent)
            t.boosts.clear()
        self.transactions.append(f"Season {self.season} preseason completed: draft + FA.")

    def _perform_draft(self):
        # Everyone drafts 3 cards under the 20 cap. Simple heuristic: pick best value (power/cost).
        available = [cid for cid, c in self.cards.items() if not c.retired]
        random.shuffle(available)
        for t in self.teams:
            t.roster = []
            t.backup = None
            t.wins = t.losses = 0
            t.streak = 0
            t.momentum = 0.0
        rounds = 3
        for r in range(rounds):
            order = self.draft_order if r%2==0 else list(reversed(self.draft_order))
            for ti in order:
                team = self.teams[ti]
                # pick best value that keeps cost <= 20
                candidates = []
                for cid in available:
                    c = self.cards[cid]
                    new_cost = sum(self.cards[x].cost for x in team.roster) + c.cost
                    if new_cost <= self.max_team_cost:
                        # small synergy preference: if archetype matches existing, add a bit
                        synergy_bonus = 1.0
                        for rcid in team.roster:
                            if self.cards[rcid].archetype == c.archetype:
                                synergy_bonus += 0.05
                        candidates.append((cid, c.power_score()*synergy_bonus / max(0.5,c.cost)))
                if not candidates:
                    continue
                candidates.sort(key=lambda x: x[1], reverse=True)
                pick = candidates[0][0]
                team.roster.append(pick)
                available.remove(pick)
                self.transactions.append(f"Draft: {team.name} selected {self.cards[pick].name} (r{r+1}).")
        # leftovers are free agents
        self.free_agents = available

    def _free_agency_signing(self):
        # Each team may sign ONE backup for one season from free agents
        for team in self.teams:
            if team.backup: continue
            # sign best stamina or archetype complement
            best = None; best_score = -1
            for cid in self.free_agents:
                c = self.cards[cid]
                # must fit under cost cap if counted; backups don't count toward 20 (but still show as 1-year)
                val = c.stamina + 0.5*c.defense + 0.3*c.speed
                # slight bonus if archetype present
                for rcid in team.roster:
                    if self.cards[rcid].archetype == c.archetype: val += 5
                if val > best_score:
                    best_score = val; best = cid
            if best:
                team.backup = best
                self.transactions.append(f"Free Agency: {team.name} signed backup {self.cards[best].name} (1-year).")
                self.free_agents.remove(best)

    def generate_calendar(self):
        # 30-game season per team. We'll build a round-robin lite schedule then trim/extend to 30 games.
        n = len(self.teams)
        pairings = []
        for a in range(n):
            for b in range(a+1, n):
                pairings.append((a,b))
        random.shuffle(pairings)
        # Each team needs 30 games; add pairings until targets hit
        need = [30]*n
        self.schedule = []
        day = 1
        for (a,b) in pairings*4:  # allow repeats
            if need[a]>0 and need[b]>0:
                self.schedule.append((day,a,b))
                need[a]-=1; need[b]-=1
                day += 1
            if sum(need)==0: break
        self.day = 1
        # Init rivalry map (fixed pairs: neighboring indices as rivals)
        self.rivalries = {}
        for i in range(n):
            j = (i+1)%n
            key = (min(i,j), max(i,j))
            self.rivalries[key] = {"games":0,"a_wins":0,"b_wins":0}

    # ---------- Simulation ----------
    def simulate_next_day(self) -> List[Dict]:
        games_today = [g for g in self.schedule if g[0]==self.day]
        recaps = []
        for _, a, b in games_today:
            result = self._play_game(a,b)
            recaps.append(result)
        if games_today:
            self.day += 1
        return recaps

    def _play_game(self, a_idx:int, b_idx:int) -> Dict:
        ta, tb = self.teams[a_idx], self.teams[b_idx]
        # Rivalry flag
        rk = (min(a_idx,b_idx), max(a_idx,b_idx))
        rivalry_bonus = 0.05  # +5%
        is_rival = rk in self.rivalries
        # Compute team strength from active starters (swap in backup if stamina too low)
        def team_strength(team: Team) -> Tuple[float,List[str]]:
            starters = []
            for cid in team.roster:
                c = self.cards[cid]
                if c.stamina < 35 and team.backup:
                    starters.append(team.backup)
                else:
                    starters.append(cid)
            # apply synergy: if >=2 same archetype in starters -> +2 to all stats each (as spec)
            if len(starters)>=2:
                arches = [self.cards[x].archetype for x in starters]
                if len(set(arches))<len(arches):  # any match
                    synergy_mult = 1.0
                    base_boost = 2  # +2 to every stat ≈ ~+4% power
                else:
                    synergy_mult = 1.0
                    base_boost = 0
            else:
                base_boost = 0
                synergy_mult = 1.0
            total = 0.0
            for scid in starters:
                c = self.cards[scid]
                attack = c.attack + base_boost
                defense = c.defense + base_boost
                speed = c.speed + base_boost
                stamina = c.stamina + base_boost
                special = c.special + base_boost
                total += (attack*0.34 + defense*0.28 + speed*0.22 + stamina*0.10 + special*0.06)
            return total, starters

        a_power, a_used = team_strength(ta)
        b_power, b_used = team_strength(tb)

        # Apply momentum
        a_power *= (1.0 + ta.momentum)
        b_power *= (1.0 + tb.momentum)

        # Rivalry day + shop chemistry boost
        if is_rival:
            a_power *= 1.05
            b_power *= 1.05

        # Apply teamwide shop boosts (chemistry)
        a_power *= (1.0 + sum(b["amount"] for b in ta.boosts if b["teamwide"] and b["stat"]=="chem" and b["games_left"]>0))
        b_power *= (1.0 + sum(b["amount"] for b in tb.boosts if b["teamwide"] and b["stat"]=="chem" and b["games_left"]>0))

        # RNG 25%
        rng_a = random.uniform(0.85, 1.15)
        rng_b = random.uniform(0.85, 1.15)
        # Blend 75% stats, 25% RNG by exponent
        a_score = a_power * (rng_a**0.25)
        b_score = b_power * (rng_b**0.25)

        winner_idx = a_idx if a_score >= b_score else b_idx
        loser_idx  = b_idx if a_score >= b_score else a_idx
        self.teams[winner_idx].add_result(True)
        self.teams[loser_idx].add_result(False)

        # Fatigue: used starters lose stamina; backups recover a bit
        def fatigue_apply(team: Team, used_ids: List[str]):
            for cid in used_ids:
                self.cards[cid].stamina = clamp(self.cards[cid].stamina - random.randint(2,4), 0, 100)
            if team.backup and team.backup not in used_ids:
                self.cards[team.backup].stamina = clamp(self.cards[team.backup].stamina + 2, 0, 100)
        fatigue_apply(ta, a_used); fatigue_apply(tb, b_used)

        # Tick down boosts
        for T in (ta,tb):
            for b in T.boosts:
                if b["games_left"]>0: b["games_left"] -= 1
            T.boosts = [b for b in T.boosts if b.get("games_left",0)>0 or b["stat"] in ("rival",)]

        # Rivalry record update
        if rk in self.rivalries:
            self.rivalries[rk]["games"] += 1
            if winner_idx==rk[0]: self.rivalries[rk]["a_wins"] += 1
            else: self.rivalries[rk]["b_wins"] += 1

        recap = {
            "day": self.day,
            "home": self.teams[a_idx].name,
            "away": self.teams[b_idx].name,
            "home_score": round(a_score,1),
            "away_score": round(b_score,1),
            "winner": self.teams[winner_idx].name,
            "comment": self._commentary(a_idx,b_idx,winner_idx,a_score,b_score)
        }
        self.results.append(recap)
        return recap

    def _commentary(self, a_idx,b_idx,winner_idx, a_score,b_score)->str:
        A,B = self.teams[a_idx], self.teams[b_idx]
        margin = abs(a_score-b_score)
        upset = (winner_idx==a_idx and B.wins-A.wins>5) or (winner_idx==b_idx and A.wins-B.wins>5)
        if upset and margin<5: return f"Major upset! {self.teams[winner_idx].name} steals a close one."
        if margin>15: return f"{self.teams[winner_idx].name} dominates end to end."
        return f"{self.teams[winner_idx].name} edges out a tight match."

    # ---------- Shop ----------
    def purchase_boost(self, team_idx:int, key:str, target_card:Optional[str]=None):
        team = self.teams[team_idx]
        item = next((x for x in self.shop_catalog if x["key"]==key), None)
        if not item: return False, "Invalid boost."
        if team.shop_points_left < item["pts"]:
            return False, "Not enough points."
        b = {"key": key, "stat": item["stat"], "amount": item["amount"], "teamwide": item["teamwide"],
             "games_left": item["games"] if item["games"]>0 else 999, "target": target_card}
        # Apply immediate effects for stamina reset
        if key=="fatigue" and target_card:
            self.cards[target_card].stamina = 100
        team.boosts.append(b)
        team.shop_points_left = round(team.shop_points_left - item["pts"],2)
        self.transactions.append(f"Shop: {team.name} bought '{item['label']}'.")
        return True, "Boost purchased."

    # ---------- Trades ----------
    def trade_finder_offers(self, team_idx:int, card_id:str) -> List[Dict]:
        offers=[]
        my_team = self.teams[team_idx]
        my_card = self.cards[card_id]
        for ai_idx, T in enumerate(self.teams):
            if ai_idx==team_idx: continue
            # simple need/value check: AI offers one card that keeps both under cap
            for their_id in T.roster + ([T.backup] if T.backup else []):
                if not their_id: continue
                their = self.cards[their_id]
                my_new_cost = sum(self.cards[c].cost for c in my_team.roster if c!=card_id) + their.cost
                ai_new_cost = sum(self.cards[c].cost for c in T.roster if c!=their_id) + my_card.cost
                if my_new_cost <= self.max_team_cost and ai_new_cost <= self.max_team_cost:
                    # personality tweak
                    val_bias = 0.0
                    if T.gm_personality=="Win-Now": val_bias += 0.1*my_card.power_score()
                    if T.gm_personality=="Rebuilder": val_bias += 0.1*(their.cost - my_card.cost)
                    score = their.power_score() - my_card.power_score() + random.uniform(-5,5) + val_bias
                    offers.append({"from": ai_idx, "their": their_id, "score": score})
            random.shuffle(offers)
        offers = sorted(offers, key=lambda x: x["score"], reverse=True)[:5]
        # package
        packaged=[]
        for o in offers:
            packaged.append({
                "team_idx": o["from"],
                "team_name": self.teams[o["from"]].name,
                "their_card": o["their"],
                "their_card_name": self.cards[o["their"]].name,
                "their_cost": self.cards[o["their"]].cost
            })
        return packaged

    def execute_trade(self, a_idx:int, a_card:str, b_idx:int, b_card:str)->Tuple[bool,str]:
        A,B = self.teams[a_idx], self.teams[b_idx]
        if a_card not in (A.roster + ([A.backup] if A.backup else [])): return (False,"You don't own that card.")
        if b_card not in (B.roster + ([B.backup] if B.backup else [])): return (False,"Other team doesn't own that card.")
        # swap from roster only (ignore backups to simplify)
        def swap(roster, take, give):
            if take in roster:
                i = roster.index(take); roster[i] = give; return True
            return False
        swapped = swap(A.roster,a_card,b_card) or swap(B.roster,b_card,a_card)
        if not swapped:
            # try backups
            if A.backup==a_card: A.backup=b_card; swapped=True
            if B.backup==b_card: B.backup=a_card; swapped=True
        # cost sanity
        if sum(self.cards[c].cost for c in A.roster) > self.max_team_cost or sum(self.cards[c].cost for c in B.roster) > self.max_team_cost:
            return (False,"Trade breaks salary cap.")
        self.transactions.append(f"Trade: {A.name} traded {self.cards[a_card].name} ⟷ {B.name}'s {self.cards[b_card].name}.")
        return (True,"Trade executed.")

    # ---------- Standings / Playoffs ----------
    def standings_table(self) -> List[Dict]:
        tbl=[]
        for i,T in enumerate(self.teams):
            tbl.append({"Team": T.name, "W": T.wins, "L": T.losses, "Win%": round(T.wins/max(1,(T.wins+T.losses)),3), "Streak": T.streak})
        return sorted(tbl, key=lambda r: (-r["W"], r["L"]))

    def season_complete(self) -> bool:
        # check if last scheduled day played
        if not self.schedule: return False
        return self.day > max(d for d,_,_ in self.schedule)

    def start_playoffs(self):
        seeds = sorted(range(len(self.teams)), key=lambda i: (-self.teams[i].wins, self.teams[i].losses))
        top16 = seeds[:16]
        bracket = [(top16[i], top16[-(i+1)]) for i in range(8)]  # 1v16, 2v15...
        self.playoffs = {"round":1, "bracket": bracket, "results":[]}

    def simulate_playoffs_to_champion(self):
        if not self.playoffs: self.start_playoffs()
        round_num = 1
        contenders = [x for match in self.playoffs["bracket"] for x in match]
        while len(contenders)>1:
            winners=[]
            round_results=[]
            for a,b in self.playoffs["bracket"]:
                a_score = self.teams[a].wins + random.uniform(0,10)
                b_score = self.teams[b].wins + random.uniform(0,10)
                w = a if a_score>=b_score else b
                winners.append(w)
                round_results.append({"round":round_num, "a":self.teams[a].name, "b":self.teams[b].name, "winner": self.teams[w].name})
            self.playoffs["results"].extend(round_results)
            # next round pairings
            self.playoffs["bracket"] = [(winners[i], winners[-(i+1)]) for i in range(len(winners)//2)]
            round_num += 1
            contenders = winners
        champ = contenders[0]
        self.playoffs["champion"] = self.teams[champ].name
        return champ

    # ---------- Awards, Costs, Balance ----------
    def calculate_awards(self, playoff_champ_idx:int) -> Dict:
        # Simple heuristics using wins, popularity, usage, stamina
        awards = {}
        # MVP: best card by team record + card power
        all_cards = [self.cards[cid] for T in self.teams for cid in (T.roster + ([T.backup] if T.backup else [])) if cid in self.cards]
        mvp = max(all_cards, key=lambda c: c.power_score() + random.uniform(0,5))
        awards["MVP"] = mvp.id
        # ROTY: among rookies (age==0 at start of season)
        rookies = [c for c in self.cards.values() if c.age==0 and not c.retired]
        if rookies:
            awards["ROTY"] = random.choice(rookies).id
        # SCOY: best backup used (highest stamina + defense heuristic)
        backups = [self.cards[T.backup] for T in self.teams if T.backup]
        if backups:
            sco = max(backups, key=lambda c: c.stamina + c.defense + random.uniform(-5,5))
            awards["SCOY"] = sco.id
        # CCOY: biggest improvement vs last season (attack+def diff)
        improvements=[]
        for c in self.cards.values():
            if len(c.history)>=2:
                last, prev = c.history[-1], c.history[-2]
                diff = (last["attack"]+last["defense"]+last["speed"])-(prev["attack"]+prev["defense"]+prev["speed"])
                improvements.append((diff,c.id))
        if improvements:
            improvements.sort(reverse=True)
            awards["CCOY"] = improvements[0][1]
        # Playoff MVP: random from champion roster
        champ_team = self.teams[playoff_champ_idx]
        pmvp_id = random.choice(champ_team.roster)
        awards["Playoff MVP"] = pmvp_id
        # Best Duo (top synergy pair from same archetype)
        duo=None; duo_score=-1
        for T in self.teams:
            for i in range(len(T.roster)):
                for j in range(i+1, len(T.roster)):
                    a=self.cards[T.roster[i]]; b=self.cards[T.roster[j]]
                    if a.archetype==b.archetype:
                        s=a.power_score()+b.power_score()
                        if s>duo_score: duo=(a.id,b.id); duo_score=s
        if duo: awards["Best Duo"] = duo
        # Fan Favorite (popularity)
        fav = max(self.cards.values(), key=lambda c:c.popularity+random.uniform(-0.1,0.1))
        awards["Fan Favorite"] = fav.id
        # attach to cards
        for title, val in awards.items():
            if title=="Best Duo":
                self.cards[val[0]].awards.append(title)
                self.cards[val[1]].awards.append(title)
            else:
                self.cards[val].awards.append(title)
        return awards

    def adjust_costs(self, awards:Dict):
        # usage: cards on rosters count as used
        usage_counts: Dict[str,int] = {cid:0 for cid in self.cards}
        team_wins: Dict[str,int] = {cid:0 for cid in self.cards}
        for T in self.teams:
            for cid in T.roster + ([T.backup] if T.backup else []):
                if cid in usage_counts: usage_counts[cid]+=1
                for _ in range(T.wins): team_wins[cid]+=1
        # compute percentiles
        used = [cid for cid,cnt in usage_counts.items() if cnt>0]
        top_usage = set(sorted(used, key=lambda c: usage_counts[c], reverse=True)[:10])
        bot_usage = set(sorted(used, key=lambda c: usage_counts[c])[:10])

        for cid, c in self.cards.items():
            delta = 0.0
            # Win% proxy by team wins accumulation
            if team_wins[cid] > 18: delta += 0.5
            if team_wins[cid] < 8:  delta -= 0.5
            if cid in top_usage: delta += 0.25
            if cid in bot_usage: delta -= 0.25
            if cid == awards.get("MVP"): delta += 1.0
            for minor in ["SCOY","CCOY"]: 
                if cid == awards.get(minor): delta += 0.5
            if "Best Duo" in c.awards: delta += 0.25
            # Guardrails
            delta = clamp(delta, -1.0, 1.5)
            c.cost = clamp(round(c.cost + delta,1), 0.5, 10.0)

    # ---------- Patch, Retirement, Rookies ----------
    def apply_patch(self):
        # choose 30 cards not changed last season
        candidates = [c for c in self.cards.values() if not c.retired and c.last_changed_season != (self.season-1)]
        random.shuffle(candidates)
        selected = candidates[:30] if len(candidates)>=30 else candidates
        patch = {"buffs":[], "nerfs":[]}
        for c in selected:
            buff = random.choice([True, False])
            amt1 = random.randint(2,10); amt2 = random.randint(0,10)
            # pick stats
            stats = ["attack","defense","speed","stamina"]
            s1 = random.choice(stats); s2 = random.choice(stats)
            if buff:
                setattr(c, s1, clamp(getattr(c,s1)+amt1, 0, 100))
                if amt2>0: setattr(c, s2, clamp(getattr(c,s2)+max(2,amt2//2), 0, 100))
                patch["buffs"].append({"id":c.id,"name":c.name,"change":f"+{amt1} {s1}" + (f", +{max(2,amt2//2)} {s2}" if amt2>0 else "")})
            else:
                setattr(c, s1, clamp(getattr(c,s1)-amt1, 0, 100))
                if amt2>0: setattr(c, s2, clamp(getattr(c,s2)-max(2,amt2//2), 0, 100))
                patch["nerfs"].append({"id":c.id,"name":c.name,"change":f"-{amt1} {s1}" + (f", -{max(2,amt2//2)} {s2}" if amt2>0 else "")})
            c.last_changed_season = self.season
        return patch

    def retire_and_add_rookies(self):
        # retire up to 3 based on age nearing lifespan
        alive = [c for c in self.cards.values() if not c.retired]
        # mark aging
        for c in alive: c.age += 1
        retiring = sorted(alive, key=lambda c: (c.age/c.lifespan) + random.uniform(-0.1,0.1), reverse=True)[:3]
        retired=[]
        for c in retiring:
            if c.age >= c.lifespan and not c.retired:
                c.retired = True
                retired.append(c)
        # always cap at max 3 retirees overall
        retired = retired[:3]
        # add 3 rookies
        rookies=[]
        for i in range(3):
            cid = f"R{self.season}-{i+1}-{random.randint(1000,9999)}"
            arc = random.choice(ARCHETYPES)
            atk_type = random.choice(ATTACK_TYPES)
            attack = random.randint(55, 92); defense=random.randint(50,92); speed=random.randint(50,92)
            stamina=random.randint(65,95); special=random.randint(45,90)
            base_cost = round(random.uniform(1.5,7.5),1)
            c = Card(id=cid, name=self._random_card_name(i+1000), archetype=arc, attack_type=atk_type,
                     attack=attack, defense=defense, speed=speed, stamina=stamina, special=special,
                     base_cost=base_cost, cost=base_cost, lifespan=random.randint(8,15))
            self.cards[cid]=c; rookies.append(c)
        return retired, rookies

    # ---------- Archive ----------
    def archive_season(self, awards:Dict, patch:Dict, retired:List[Card], rookies:List[Card], champ_idx:int):
        # snapshot standings
        standings = self.standings_table()
        # playoff bracket results
        bracket = self.playoffs.get("results",[])
        champ = self.playoffs.get("champion","N/A")
        # transactions log copy
        trans = list(self.transactions)
        self.past_seasons[self.season] = {
            "standings": standings,
            "awards": awards,
            "playoffs": {"champion": champ, "rounds": bracket},
            "retirements": [{"id":c.id,"name":c.name,"lifespan":c.lifespan,"age":c.age} for c in retired],
            "transactions": trans,
            "patch_notes": patch
        }
        # card snapshots
        for c in self.cards.values():
            c.history.append(c.season_snapshot(self.season))

    # ---------- Season Runner ----------
    def run_full_season_if_needed(self):
        if self.day<=1 and not any(t.roster for t in self.teams):
            # Preseason for Season 1
            self.start_preseason()
        # Simulate remaining regular season
        while not self.season_complete():
            self.simulate_next_day()
        # Playoffs
        champ_idx = self.simulate_playoffs_to_champion()
        # Awards & costs
        awards = self.calculate_awards(champ_idx)
        self.adjust_costs(awards)
        # Patch, retirees, rookies for next season
        patch = self.apply_patch()
        retired, rookies = self.retire_and_add_rookies()
        # Archive
        self.archive_season(awards, patch, retired, rookies, champ_idx)
        # Prepare next season
        self.season += 1
        self.transactions = []
        self.results = []
        self.generate_calendar()
        self.start_preseason()
