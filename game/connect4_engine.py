import random
import math

class Connect4Engine:
    EMPTY = 0
    P1 = 1
    P2 = 2

    def __init__(self, player1_id: int, player2_id: int):
        self.rows = 6
        self.cols = 7
        self.board = [[self.EMPTY for _ in range(self.cols)] for _ in range(self.rows)]
        self.players = {self.P1: player1_id, self.P2: player2_id}
        self.current_turn = self.P1
        self.winner = None
        self.is_draw = False

    def drop_piece(self, col: int) -> bool:
        """Attempts to drop a piece into the specified column (0-indexed). Returns True if valid."""
        if col < 0 or col >= self.cols:
            return False
            
        if self.winner or self.is_draw:
            return False

        # Drop the piece to the lowest available row
        for r in range(self.rows - 1, -1, -1):
            if self.board[r][col] == self.EMPTY:
                self.board[r][col] = self.current_turn
                
                if self.check_win(self.current_turn):
                    self.winner = self.current_turn
                elif self.check_draw():
                    self.is_draw = True
                else:
                    # Swap turns
                    self.current_turn = self.P2 if self.current_turn == self.P1 else self.P1
                    
                return True
                
        return False # Column is full

    def check_win(self, piece: int) -> bool:
        # Check horizontal
        for c in range(self.cols - 3):
            for r in range(self.rows):
                if self.board[r][c] == piece and self.board[r][c+1] == piece and self.board[r][c+2] == piece and self.board[r][c+3] == piece:
                    return True

        # Check vertical
        for c in range(self.cols):
            for r in range(self.rows - 3):
                if self.board[r][c] == piece and self.board[r+1][c] == piece and self.board[r+2][c] == piece and self.board[r+3][c] == piece:
                    return True

        # Check positive slope diagonals
        for c in range(self.cols - 3):
            for r in range(self.rows - 3):
                if self.board[r][c] == piece and self.board[r+1][c+1] == piece and self.board[r+2][c+2] == piece and self.board[r+3][c+3] == piece:
                    return True

        # Check negative slope diagonals
        for c in range(self.cols - 3):
            for r in range(3, self.rows):
                if self.board[r][c] == piece and self.board[r-1][c+1] == piece and self.board[r-2][c+2] == piece and self.board[r-3][c+3] == piece:
                    return True

        return False

    def check_draw(self) -> bool:
        for c in range(self.cols):
            if self.board[0][c] == self.EMPTY:
                return False
        return True

    def render_emoji_board(self) -> str:
        """Returns the board as a string of Discord emojis."""
        emojis = {self.EMPTY: "⚪", self.P1: "🔴", self.P2: "🟡"}
        output = ""
        for r in range(self.rows):
            row_str = "".join([emojis[cell] for cell in self.board[r]])
            output += row_str + "\n"
            
        # Add column numbers at the bottom
        output += "1️⃣2️⃣3️⃣4️⃣5️⃣6️⃣7️⃣"
        return output

    def get_valid_locations(self):
        valid_locations = []
        for col in range(self.cols):
            if self.board[0][col] == self.EMPTY:
                valid_locations.append(col)
        return valid_locations

    def get_next_open_row(self, col: int) -> int:
        for r in range(self.rows - 1, -1, -1):
            if self.board[r][col] == self.EMPTY:
                return r
        return -1

    def inner_evaluate_window(self, window: list, piece: int) -> int:
        score = 0
        opp_piece = self.P1 if piece == self.P2 else self.P2

        if window.count(piece) == 4:
            score += 100
        elif window.count(piece) == 3 and window.count(self.EMPTY) == 1:
            score += 5
        elif window.count(piece) == 2 and window.count(self.EMPTY) == 2:
            score += 2

        if window.count(opp_piece) == 3 and window.count(self.EMPTY) == 1:
            score -= 80 # Heavily penalize opponent having 3 inline

        return score

    def score_position(self, piece: int) -> int:
        score = 0

        # Score center column
        center_array = [self.board[r][self.cols//2] for r in range(self.rows)]
        center_count = center_array.count(piece)
        score += center_count * 3

        # Score Horizontal
        for r in range(self.rows):
            row_array = self.board[r]
            for c in range(self.cols - 3):
                window = row_array[c:c+4]
                score += self.inner_evaluate_window(window, piece)

        # Score Vertical
        for c in range(self.cols):
            col_array = [self.board[r][c] for r in range(self.rows)]
            for r in range(self.rows - 3):
                window = col_array[r:r+4]
                score += self.inner_evaluate_window(window, piece)

        # Score positive sloped diagonal
        for r in range(self.rows - 3):
            for c in range(self.cols - 3):
                window = [self.board[r+i][c+i] for i in range(4)]
                score += self.inner_evaluate_window(window, piece)

        # Score negative sloped diagonal
        for r in range(self.rows - 3):
            for c in range(self.cols - 3):
                window = [self.board[r+3-i][c+i] for i in range(4)]
                score += self.inner_evaluate_window(window, piece)

        return score

    def is_terminal_node(self) -> bool:
        return self.check_win(self.P1) or self.check_win(self.P2) or len(self.get_valid_locations()) == 0

    def minimax(self, depth: int, alpha: float, beta: float, maximizingPlayer: bool):
        valid_locations = self.get_valid_locations()
        is_terminal = self.is_terminal_node()
        
        bot_piece = self.current_turn
        opp_piece = self.P1 if self.current_turn == self.P2 else self.P2

        if depth == 0 or is_terminal:
            if is_terminal:
                if self.check_win(bot_piece):
                    return (None, 100000000000000)
                elif self.check_win(opp_piece):
                    return (None, -10000000000000)
                else: # Draw
                    return (None, 0)
            else: # Depth is zero
                return (None, self.score_position(bot_piece))

        # We shuffle valid locations so the AI's playstyle isn't extremely uniform on equal scores
        shuffled_locations = valid_locations.copy()
        random.shuffle(shuffled_locations)

        if maximizingPlayer:
            value = -math.inf
            best_col = shuffled_locations[0] if shuffled_locations else None
            for col in shuffled_locations:
                row = self.get_next_open_row(col)
                if row == -1: continue # Just in case
                
                # Temporarily drop piece
                self.board[row][col] = bot_piece
                
                new_score = self.minimax(depth-1, alpha, beta, False)[1]
                
                # Undo 
                self.board[row][col] = self.EMPTY
                
                if new_score > value:
                    value = new_score
                    best_col = col
                alpha = max(alpha, value)
                if alpha >= beta:
                    break
            return best_col, value

        else: # Minimizing player
            value = math.inf
            best_col = shuffled_locations[0] if shuffled_locations else None
            for col in shuffled_locations:
                row = self.get_next_open_row(col)
                if row == -1: continue
                
                # Temporarily drop piece
                self.board[row][col] = opp_piece
                
                new_score = self.minimax(depth-1, alpha, beta, True)[1]
                
                # Undo
                self.board[row][col] = self.EMPTY
                
                if new_score < value:
                    value = new_score
                    best_col = col
                beta = min(beta, value)
                if alpha >= beta:
                    break
            return best_col, value

    def bot_play(self) -> int:
        """Determines best column using Minimax (depth=5) and automatically plays it."""
        valid_locations = self.get_valid_locations()
        if not valid_locations:
            return -1

        col, minimax_score = self.minimax(5, -math.inf, math.inf, True)

        if col is None or col not in valid_locations:
            col = random.choice(valid_locations)

        self.drop_piece(col)
        return col

