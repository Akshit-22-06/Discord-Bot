from game.models import GameState

class GameManager:
    def __init__(self):
        self.active_games: dict[int, GameState] = {}

    def get_or_create_game(self, channel_id: int) -> GameState:
        if channel_id not in self.active_games:
            self.active_games[channel_id] = GameState(channel_id)
        return self.active_games[channel_id]

    def get_game(self, channel_id: int) -> GameState:
        return self.active_games.get(channel_id)

    def remove_game(self, channel_id: int):
        if channel_id in self.active_games:
            del self.active_games[channel_id]

game_manager = GameManager()
