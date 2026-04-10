from game.connect4_engine import Connect4Engine
import time

engine = Connect4Engine(1, 2)
engine.is_pve = True

start = time.time()
engine.bot_play()
print(f"Time taken: {time.time() - start:.2f} seconds")
