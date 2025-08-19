# league.py
# Core backend logic for Clash Royale Fantasy League simulator.
# Handles teams, cards, games, playoffs, awards, patches, retirements, etc.

import os
import json
import random
from typing import List, Dict, Tuple, Optional

SAVE_FILE = "league_state.json"

# ------------------ Card ------------------
class Card:
    def __init__(self, id: str, name: str, archetype: str,
                 atk: int, defense: int, speed: int, hit_speed: int,
                 atk_type: int, synergy: int, cost: int, lifespan: int):
        self.id = id
        self.name = name
        self.archetype = archetype  # Tank/DPS/Control/Support/Hybrid
        self.atk = atk
        self.defense = defense
        self.speed = speed
        self.hit_speed = hit_speed
        self.atk_type = atk_type
        self.synergy = synergy
        self.cost = cost
        self.lifespan = lifespan
        self.seasons_played = 0
        self.fatigue = 100
        self.retired = False
        self.usage_count = 0
        self.awards: List[str] = []
        self.stats: Dict[str, float] = {
            "games": 0,
            "avg_contribution": 0.0,
            "career_games": 0,
            "career_contribution": 0.0,
        }

    @property
    def total_power(self) -> float:
        vals = [self.atk, self.defense, self.speed,
                self.hit_speed, self.atk_type, self.synergy]
        return sum(vals)/len(vals)

    def contribute(self) -> float:
        base = (self.atk + self.defense + self.speed + self.hit_speed + self.atk_type)/5
        bonus = self.synergy * 0.05
        fatigue_penalty = (100 - self.fatigue) * 0.2
        score = base + bonus - fatigue_penalty
        self.usage_count += 1
        self.stats["games"] += 1
        self.stats["career_games"] += 1
        self.stats["avg_contribution"] = (
            (self.stats["avg_contribution"] * (self.stats["games"]-1)) + score
        )/self.stats["games"]
        self.stats["career_contribution"] = (
            (self.stats["career_contribution"] * (self.stats["career_games"]-1)) + score
        )/self.stats["career_games"]
        self.fatigue = max(0, self.fatigue - random.randint(5,15))
        return max(0, score)

    def recover(self):
        self.fatigue = min(100, self.fatigue + random.randint(5,15))

    def season_reset(self):
        self.fatigue = 100
        self.usage_count = 0
        self.seasons_played += 1
        if self.seasons_played >= self.lifespan:
            self.retired = True

    def to_dict(self):
        return self.__dict__

    @classmethod
    def from_dict(cls, data: dict):
        c = cls(
            id=data["id"], name=data["name"], archetype=data.get("archetype","Hybrid"),
            atk=data["atk"], defense=data["defense"], speed=data["speed"],
            hit_speed=data["hit_speed"], atk_type=data["atk_type"], synergy=data["synergy"],
            cost=data["cost"], lifespan=data.get("lifespan",5)
        )
        c.__dict__.update(data)
        return c

# ------------------ Team ------------------
class Team:
    def __init__(self, name: str, logo: str, color: str):
        self.name = name
        self.logo = logo
        self.color = color
        self.roster: List[str] = []
        self.backup: Optional[str] = None
        self.wins = 0
        self.losses = 0
        self.championships = 0
        self.history: List[str] = []

    def reset_season(self):
        self.wins = 0
        self.losses = 0

    def record_game(self, win: bool):
        if win: self.wins += 1
        else: self.losses += 1

    def to_dict(self):
        return self.__dict__

    @classmethod
    def from_dict(cls, data: dict):
        t = cls(data["name"], data.get("logo",""), data.get("color","#FFFFFF"))
        t.__dict__.update(data)
        return t

# ------------------ League ------------------
class League:
    def __init__(self):
        self.season = 1
        self.day = 1
        self.cards: Dict[str, Card] = {}
        self.teams: List[Team] = []
        self.schedule: List[Tuple[int,int,int]] = [] # (day, home_idx, away_idx)
        self.results: List[dict] = []
        self.transactions: List[str] = []
        self.archive_data: List[dict] = []
        self.rivalries: Dict[Tuple[int,int], int] = {}
        self.max_team_cost = 20
        self._init_cards()
        self._init_teams()
        self.generate_calendar()

    # ---- Init ----
    def _init_cards(self):
        for i in range(160):
            arche = random.choice(["Tank","DPS","Control","Support","Hybrid"])
            c = Card(
                id=f"C{i}",
                name=f"Card{i}",
                archetype=arche,
                atk=random.randint(50,100),
                defense=random.randint(50,100),
                speed=random.randint(50,100),
                hit_speed=random.randint(50,100),
                atk_type=random.randint(50,100),
                synergy=random.randint(50,100),
                cost=random.randint(1,10),
                lifespan=random.randint(3,8)
            )
            self.cards[c.id] = c

    def _init_teams(self):
        for i in range(30):
            t = Team(f"Team{i}", "🏰", "#"+''.join(random.choice("0123456789ABCDEF") for _ in range(6)))
            self.teams.append(t)
        self.start_preseason()

    # ---- Draft / Preseason ----
    def start_preseason(self):
        card_ids = [cid for cid,c in self.cards.items() if not c.retired]
        random.shuffle(card_ids)
        idx = 0
        for team in self.teams:
            team.roster = []
            cost_used = 0
            while len(team.roster) < 3 and idx < len(card_ids):
                cid = card_ids[idx]; idx+=1
                if cost_used + self.cards[cid].cost <= self.max_team_cost:
                    team.roster.append(cid)
                    cost_used += self.cards[cid].cost
            if idx < len(card_ids):
                team.backup = card_ids[idx]; idx+=1
            else: team.backup=None
            team.reset_season()

    # ---- Calendar ----
    def generate_calendar(self):
        self.schedule=[]
        days=20
        for d in range(1,days+1):
            matchups = list(range(len(self.teams)))
            random.shuffle(matchups)
            for i in range(0,len(matchups),2):
                if i+1<len(matchups):
                    self.schedule.append((d, matchups[i], matchups[i+1]))
        self.day=1

    def season_complete(self) -> bool:
        return all(d < self.day for d,_,_ in self.schedule)

    # ---- Simulation ----
    def simulate_next_day(self):
        games = [g for g in self.schedule if g[0]==self.day]
        recaps=[]
        for d,hi,ai in games:
            home=self.teams[hi]; away=self.teams[ai]
            home_score = sum(self.cards[cid].contribute() for cid in home.roster if cid in self.cards)
            away_score = sum(self.cards[cid].contribute() for cid in away.roster if cid in self.cards)
            if home.backup and self.cards[home.backup].fatigue<40:
                home_score += self.cards[home.backup].contribute()
            if away.backup and self.cards[away.backup].fatigue<40:
                away_score += self.cards[away.backup].contribute()
            if home_score>away_score:
                home.record_game(True); away.record_game(False); winner=home.name
            else:
                home.record_game(False); away.record_game(True); winner=away.name
            recaps.append({"day":d,"home":home.name,"away":away.name,
                           "home_score":round(home_score,1),
                           "away_score":round(away_score,1),
                           "winner":winner,"comment":"Hard fought!"})
            self.results.append(recaps[-1])
        for t in self.teams:
            for cid in t.roster:
                self.cards[cid].recover()
            if t.backup: self.cards[t.backup].recover()
        self.day+=1
        return recaps

    # ---- Playoffs ----
    def simulate_playoffs_to_champion(self) -> int:
        ranked=sorted(range(len(self.teams)), key=lambda i:self.teams[i].wins, reverse=True)
        contenders=ranked[:16]
        round_size=16
        while round_size>1:
            nxt=[]
            for i in range(0,round_size,2):
                t1=self.teams[contenders[i]]
                t2=self.teams[contenders[i+1]]
                score1=sum(self.cards[cid].contribute() for cid in t1.roster if cid in self.cards)
                score2=sum(self.cards[cid].contribute() for cid in t2.roster if cid in self.cards)
                if score1>=score2: nxt.append(contenders[i])
                else: nxt.append(contenders[i+1])
            contenders=nxt; round_size//=2
        champ_idx=contenders[0]
        self.teams[champ_idx].championships+=1
        return champ_idx

    # ---- Awards ----
    def calculate_awards(self, champ_idx:int) -> Dict[str,str]:
        best_card=max(self.cards.values(), key=lambda c:c.stats["avg_contribution"] if c.stats["games"]>0 else 0)
        awards={"MVP":best_card.id, "Finals MVP":best_card.id, "Champion":self.teams[champ_idx].name}
        best_card.awards.append("MVP")
        return awards

    # ---- Patch / Retire / Add rookies ----
    def apply_patch(self) -> Dict[str,int]:
        modified={}
        for c in random.sample(list(self.cards.values()), k=5):
            delta=random.choice([-10,-5,+5,+10])
            c.atk=max(10,min(100,c.atk+delta))
            modified[c.id]=delta
        return modified

    def retire_and_add_rookies(self) -> Tuple[List[str],List[Card]]:
        retired=[]; rookies=[]
        for c in self.cards.values():
            if not c.retired and c.seasons_played>=c.lifespan:
                c.retired=True; retired.append(c.id)
        for i in range(4):
            idx=len(self.cards)+i
            nc=Card(f"N{idx}",f"NewCard{idx}",
                archetype=random.choice(["Tank","DPS","Control","Support","Hybrid"]),
                atk=random.randint(50,100),defense=random.randint(50,100),
                speed=random.randint(50,100),hit_speed=random.randint(50,100),
                atk_type=random.randint(50,100),synergy=random.randint(50,100),
                cost=random.randint(1,10),lifespan=random.randint(3,8))
            self.cards[nc.id]=nc; rookies.append(nc)
        return retired, rookies

    def archive_season(self, awards, patch, retired, rookies, champ_idx):
        self.archive_data.append({
            "season":self.season,"awards":awards,"patch":patch,
            "retired":retired,"rookies":[r.id for r in rookies],
            "champion":self.teams[champ_idx].name
        })
        for c in self.cards.values(): c.season_reset()

    # ---- Save / Load ----
    def save(self):
        data={"season":self.season,"day":self.day,
              "cards":{cid:c.to_dict() for cid,c in self.cards.items()},
              "teams":[t.to_dict() for t in self.teams],
              "schedule":self.schedule,"results":self.results,
              "transactions":self.transactions,"archive_data":self.archive_data,
              "rivalries":self.rivalries,"max_team_cost":self.max_team_cost}
        with open(SAVE_FILE,"w") as f: json.dump(data,f)

    @classmethod
    def load(cls,path:str)->Optional["League"]:
        if not os.path.exists(path): return None
        with open(path) as f: data=json.load(f)
        L=cls.__new__(cls)
        L.season=data["season"]; L.day=data["day"]
        L.cards={cid:Card.from_dict(cd) for cid,cd in data["cards"].items()}
        L.teams=[Team.from_dict(td) for td in data["teams"]]
        L.schedule=[tuple(x) for x in data["schedule"]]
        L.results=data["results"]; L.transactions=data["transactions"]
        L.archive_data=data["archive_data"]; L.rivalries={tuple(map(int,k.strip("()").split(","))):v for k,v in data.get("rivalries",{}).items()}
        L.max_team_cost=data.get("max_team_cost",20)
        return L
