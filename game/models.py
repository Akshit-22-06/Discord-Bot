from enum import Enum
import random

class Role(Enum):
    VILLAGER = "Villager"
    MAFIA = "Mafia"
    COP = "Cop"
    DOCTOR = "Doctor"

class GamePhase(Enum):
    LOBBY = "Lobby"
    DAY = "Day"
    NIGHT = "Night"
    ENDED = "Ended"

class Player:
    def __init__(self, user_id: int, name: str):
        self.user_id = user_id
        self.name = name
        self.role: Role = None
        self.is_alive = True
        self.protected = False

class GameState:
    def __init__(self, channel_id: int):
        self.channel_id = channel_id
        self.players: dict[int, Player] = {}
        self.phase = GamePhase.LOBBY
        self.day_number = 0
        
        # State trackers for current phase
        self.votes = {}  # voter_id -> target_id (during day)
        self.mafia_target = None
        self.doctor_target = None
        self.cop_target = None

    def add_player(self, user_id: int, name: str) -> bool:
        if self.phase != GamePhase.LOBBY:
            return False
        if user_id not in self.players:
            self.players[user_id] = Player(user_id, name)
            return True
        return False

    def remove_player(self, user_id: int) -> bool:
        if self.phase != GamePhase.LOBBY:
            return False
        if user_id in self.players:
            del self.players[user_id]
            return True
        return False

    def assign_roles(self):
        player_list = list(self.players.values())
        random.shuffle(player_list)
        
        num_players = len(player_list)
        # Simplified ratio: 1 Mafia per 3 players, 1 Cop if >= 4, 1 Doctor if >= 5
        num_mafia = max(1, num_players // 3)
        
        roles_pool = [Role.MAFIA] * num_mafia
        if num_players >= 4:
            roles_pool.append(Role.COP)
        if num_players >= 5:
            roles_pool.append(Role.DOCTOR)
            
        while len(roles_pool) < num_players:
            roles_pool.append(Role.VILLAGER)
            
        for i, player in enumerate(player_list):
            player.role = roles_pool[i]

    def get_alive_players(self):
        return [p for p in self.players.values() if p.is_alive]

    def get_players_by_role(self, role: Role):
        return [p for p in self.get_alive_players() if p.role == role]

    def check_win_condition(self):
        alive = self.get_alive_players()
        mafia = [p for p in alive if p.role == Role.MAFIA]
        town = [p for p in alive if p.role in (Role.VILLAGER, Role.COP, Role.DOCTOR)]
        
        if len(mafia) == 0:
            self.phase = GamePhase.ENDED
            return "Town wins!"
        elif len(mafia) >= len(town):
            self.phase = GamePhase.ENDED
            return "Mafia wins!"
            
        return None
