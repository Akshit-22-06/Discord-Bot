import random

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

    def simulate_drop(self, col: int, piece: int) -> bool:
        """Simulates dropping a piece completely isolated to check win conditions."""
        temp_r = -1
        for r in range(self.rows - 1, -1, -1):
            if self.board[r][col] == self.EMPTY:
                self.board[r][col] = piece
                temp_r = r
                break
        
        if temp_r == -1:
            return False
            
        win = self.check_win(piece)
        
        # Revert
        self.board[temp_r][col] = self.EMPTY
        return win

    def bot_play(self) -> int:
        """Determines best column and automatically plays it."""
        valid_locations = self.get_valid_locations()
        if not valid_locations:
            return -1

        # 1. Win if possible
        for col in valid_locations:
            if self.simulate_drop(col, self.current_turn):
                self.drop_piece(col)
                return col

        # 2. Block the opponent if they are about to win
        opponent_piece = self.P1 if self.current_turn == self.P2 else self.P2
        for col in valid_locations:
            if self.simulate_drop(col, opponent_piece):
                self.drop_piece(col)
                return col

        # 3. Bias strictly towards the center
        if 3 in valid_locations and random.random() > 0.2:
            self.drop_piece(3)
            return 3

        # 4. Fallback random
        col = random.choice(valid_locations)
        self.drop_piece(col)
        return col
