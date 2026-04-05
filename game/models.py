from enum import Enum
import random

class Role(Enum):
    VILLAGER = "Villager"
    MAFIA = "Mafia"
    COP = "Cop"
    DOCTOR = "Doctor"

class BotPersonality(Enum):
    AGGRESSIVE = "Aggressive"  # votes quickly and loudly
    PARANOID   = "Paranoid"   # trusts no one, unpredictable
    PASSIVE    = "Passive"    # quiet, rarely votes
    DETECTIVE  = "Detective"  # logical, uses deduction

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
        self.is_bot = False

class BotPlayer(Player):
    """An AI-controlled player with a specific personality."""
    def __init__(self, user_id: int, name: str, personality: BotPersonality):
        super().__init__(user_id, name)
        self.is_bot = True
        self.personality = personality

class GameState:
    def __init__(self, channel_id: int):
        self.channel_id = channel_id
        self.players: dict[int, Player] = {}
        self.phase = GamePhase.LOBBY
        self.day_number = 0
        self._bot_id_counter = -1  # Bots use negative IDs (never clash with Discord user IDs)

        # State trackers for current phase
        self.votes = {}           # voter_id -> target_id (during day)
        self.mafia_target = None
        self.doctor_target = None
        self.cop_target = None
        self.cop_results: dict[int, str] = {}  # target_id -> "Mafia"|"Town"

    def add_player(self, user_id: int, name: str) -> bool:
        if self.phase != GamePhase.LOBBY:
            return False
        if user_id not in self.players:
            self.players[user_id] = Player(user_id, name)
            return True
        return False

    def add_bot(self, name: str, personality: 'BotPersonality') -> 'BotPlayer':
        """Add an AI bot to the lobby with a unique negative ID."""
        bot_id = self._bot_id_counter
        self._bot_id_counter -= 1
        bot = BotPlayer(bot_id, name, personality)
        self.players[bot_id] = bot
        return bot

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

    def get_alive_humans(self):
        return [p for p in self.get_alive_players() if not p.is_bot]

    def get_alive_bots(self):
        return [p for p in self.get_alive_players() if p.is_bot]

    def get_players_by_role(self, role: Role):
        return [p for p in self.get_alive_players() if p.role == role]

    def check_win_condition(self):
        alive = self.get_alive_players()
        mafia = [p for p in alive if p.role == Role.MAFIA]
        town = [p for p in alive if p.role in (Role.VILLAGER, Role.COP, Role.DOCTOR)]
        
        if len(mafia) == 0:
            self.phase = GamePhase.ENDED
            return "Town wins! 🏘️ All Mafia members have been eliminated."
        elif len(mafia) >= len(town):
            self.phase = GamePhase.ENDED
            return "Mafia wins! 🔪 The Mafia now controls the town."

        return None
