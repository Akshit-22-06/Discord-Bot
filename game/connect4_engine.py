import random
import math
import time

class Connect4Engine:
    EMPTY = 0
    P1 = 1
    P2 = 2

    # Move ordering: prioritize center columns for better alpha-beta pruning
    MOVE_ORDER = [3, 2, 4, 1, 5, 0, 6]

    def __init__(self, player1_id: int, player2_id: int):
        self.rows = 6
        self.cols = 7
        self.board = [[self.EMPTY for _ in range(self.cols)] for _ in range(self.rows)]
        self.players = {self.P1: player1_id, self.P2: player2_id}
        self.current_turn = self.P1
        self.winner = None
        self.is_draw = False
        # Transposition table for caching evaluated positions
        self._tt = {}
        self._search_start = 0
        self._time_limit = 3.0
        self._search_aborted = False

    def _board_key(self):
        """Create a fast hashable key for the current board state using a compact integer encoding."""
        # Encode board as a single large integer (base-3 encoding: 0=empty, 1=P1, 2=P2)
        key = 0
        for r in range(self.rows):
            for c in range(self.cols):
                key = key * 3 + self.board[r][c]
        return key

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

    def _count_pieces(self):
        """Count total pieces on the board (used for depth bonus on winning faster)."""
        count = 0
        for r in range(self.rows):
            for c in range(self.cols):
                if self.board[r][c] != self.EMPTY:
                    count += 1
        return count

    # ==========================================
    # ADVANCED HEURISTIC EVALUATION
    # ==========================================

    def _evaluate_window(self, window: list, piece: int) -> int:
        """Evaluate a window of 4 cells with much stronger weights."""
        score = 0
        opp_piece = self.P1 if piece == self.P2 else self.P2
        
        piece_count = window.count(piece)
        opp_count = window.count(opp_piece)
        empty_count = window.count(self.EMPTY)

        # Only score windows that aren't "dead" (containing both players' pieces)
        if piece_count > 0 and opp_count > 0:
            return 0  # Dead window, no potential

        if piece_count == 4:
            score += 100000
        elif piece_count == 3 and empty_count == 1:
            score += 50
        elif piece_count == 2 and empty_count == 2:
            score += 10

        if opp_count == 3 and empty_count == 1:
            score -= 200  # Very heavily penalize opponent threats
        elif opp_count == 2 and empty_count == 2:
            score -= 8

        return score

    def score_position(self, piece: int) -> int:
        """Advanced position scoring with center control, threat analysis, and positional awareness."""
        score = 0
        opp_piece = self.P1 if piece == self.P2 else self.P2

        # Score center column (controlling the center is critical in Connect 4)
        center_array = [self.board[r][self.cols // 2] for r in range(self.rows)]
        center_count = center_array.count(piece)
        score += center_count * 6

        # Score adjacent-to-center columns
        for adj_col in [2, 4]:
            adj_array = [self.board[r][adj_col] for r in range(self.rows)]
            adj_count = adj_array.count(piece)
            score += adj_count * 3

        # Score all windows (horizontal, vertical, diagonal)
        # Horizontal
        for r in range(self.rows):
            row_array = self.board[r]
            for c in range(self.cols - 3):
                window = row_array[c:c + 4]
                score += self._evaluate_window(window, piece)

        # Vertical
        for c in range(self.cols):
            col_array = [self.board[r][c] for r in range(self.rows)]
            for r in range(self.rows - 3):
                window = col_array[r:r + 4]
                score += self._evaluate_window(window, piece)

        # Positive slope diagonal
        for r in range(self.rows - 3):
            for c in range(self.cols - 3):
                window = [self.board[r + i][c + i] for i in range(4)]
                score += self._evaluate_window(window, piece)

        # Negative slope diagonal
        for r in range(self.rows - 3):
            for c in range(self.cols - 3):
                window = [self.board[r + 3 - i][c + i] for i in range(4)]
                score += self._evaluate_window(window, piece)

        # Bonus: lower row pieces are generally more valuable (more stable)
        for r in range(self.rows):
            for c in range(self.cols):
                if self.board[r][c] == piece:
                    score += (r + 1)  # Bottom row = 6 pts, top = 1 pt

        return score

    def is_terminal_node(self) -> bool:
        return self.check_win(self.P1) or self.check_win(self.P2) or len(self.get_valid_locations()) == 0

    # ==========================================
    # THREAT DETECTION (instant win/block checks)
    # ==========================================

    def _find_winning_move(self, piece: int):
        """Check if 'piece' can win immediately. Returns the column or None."""
        for col in self.MOVE_ORDER:
            if self.board[0][col] != self.EMPTY:
                continue
            row = self.get_next_open_row(col)
            if row == -1:
                continue
            self.board[row][col] = piece
            win = self.check_win(piece)
            self.board[row][col] = self.EMPTY
            if win:
                return col
        return None

    # ==========================================
    # MINIMAX WITH ALPHA-BETA, TRANSPOSITION TABLE, AND MOVE ORDERING
    # ==========================================

    def _get_ordered_moves(self, valid_locations):
        """Return moves ordered by center-priority for better pruning."""
        return [col for col in self.MOVE_ORDER if col in valid_locations]

    def minimax(self, depth: int, alpha: float, beta: float, maximizingPlayer: bool):
        """
        Minimax with alpha-beta pruning, transposition table, move ordering,
        and time-based abort.
        """
        # Time-based abort: stop searching if time limit exceeded
        if self._search_aborted or (time.time() - self._search_start > self._time_limit):
            self._search_aborted = True
            return (None, 0)  # Abort: return neutral score

        valid_locations = self.get_valid_locations()
        is_terminal = self.is_terminal_node()
        
        bot_piece = self.current_turn
        opp_piece = self.P1 if self.current_turn == self.P2 else self.P2

        if depth == 0 or is_terminal:
            if is_terminal:
                if self.check_win(bot_piece):
                    # Prefer faster wins (add depth bonus)
                    return (None, 10000000 + depth)
                elif self.check_win(opp_piece):
                    # Prefer slower losses (subtract depth bonus)
                    return (None, -10000000 - depth)
                else:  # Draw
                    return (None, 0)
            else:  # Depth is zero
                return (None, self.score_position(bot_piece))

        # Check transposition table
        board_key = self._board_key()
        tt_key = (board_key, depth, maximizingPlayer)
        if tt_key in self._tt:
            return self._tt[tt_key]

        # Move ordering: center columns first for better alpha-beta pruning
        ordered_moves = self._get_ordered_moves(valid_locations)

        # Immediate threat detection: check for instant wins/blocks
        if maximizingPlayer:
            # Can we win right now?
            win_col = self._find_winning_move(bot_piece)
            if win_col is not None:
                result = (win_col, 10000000 + depth)
                self._tt[tt_key] = result
                return result
            # Must we block opponent's win?
            block_col = self._find_winning_move(opp_piece)
            if block_col is not None:
                # Force this move to be evaluated first
                ordered_moves = [block_col] + [c for c in ordered_moves if c != block_col]
        else:
            # Can opponent win right now?
            win_col = self._find_winning_move(opp_piece)
            if win_col is not None:
                result = (win_col, -10000000 - depth)
                self._tt[tt_key] = result
                return result
            # Must opponent block our win?
            block_col = self._find_winning_move(bot_piece)
            if block_col is not None:
                ordered_moves = [block_col] + [c for c in ordered_moves if c != block_col]

        if maximizingPlayer:
            value = -math.inf
            best_col = ordered_moves[0] if ordered_moves else None
            for col in ordered_moves:
                row = self.get_next_open_row(col)
                if row == -1:
                    continue
                
                # Temporarily drop piece
                self.board[row][col] = bot_piece
                new_score = self.minimax(depth - 1, alpha, beta, False)[1]
                # Undo
                self.board[row][col] = self.EMPTY
                
                if new_score > value:
                    value = new_score
                    best_col = col
                alpha = max(alpha, value)
                if alpha >= beta:
                    break
            result = (best_col, value)
            self._tt[tt_key] = result
            return result

        else:  # Minimizing player
            value = math.inf
            best_col = ordered_moves[0] if ordered_moves else None
            for col in ordered_moves:
                row = self.get_next_open_row(col)
                if row == -1:
                    continue
                
                # Temporarily drop piece
                self.board[row][col] = opp_piece
                new_score = self.minimax(depth - 1, alpha, beta, True)[1]
                # Undo
                self.board[row][col] = self.EMPTY
                
                if new_score < value:
                    value = new_score
                    best_col = col
                beta = min(beta, value)
                if alpha >= beta:
                    break
            result = (best_col, value)
            self._tt[tt_key] = result
            return result

    def bot_play(self) -> int:
        """
        Determines best column using iterative deepening Minimax.
        Searches up to depth 14 with a 4-second time limit.
        Uses transposition table, move ordering, and threat detection
        for near-perfect play.
        """
        valid_locations = self.get_valid_locations()
        if not valid_locations:
            return -1

        # If only one move available, just play it
        if len(valid_locations) == 1:
            self.drop_piece(valid_locations[0])
            return valid_locations[0]

        # Clear transposition table each move to keep memory bounded
        self._tt.clear()

        # Check for immediate win
        bot_piece = self.current_turn
        opp_piece = self.P1 if self.current_turn == self.P2 else self.P2
        win_col = self._find_winning_move(bot_piece)
        if win_col is not None:
            self.drop_piece(win_col)
            return win_col

        # Check for immediate block
        block_col = self._find_winning_move(opp_piece)
        if block_col is not None:
            self.drop_piece(block_col)
            return block_col

        # Iterative deepening: search progressively deeper
        best_col = valid_locations[0]
        self._time_limit = 3.0  # seconds - keeps Discord responsive
        self._search_start = time.time()
        max_depth = 16

        for depth in range(4, max_depth + 1):
            if time.time() - self._search_start > self._time_limit:
                break
            self._search_aborted = False
            try:
                col, score = self.minimax(depth, -math.inf, math.inf, True)
                # Only use result if search wasn't aborted
                if not self._search_aborted and col is not None and col in valid_locations:
                    best_col = col
                # If we found a guaranteed win, stop searching deeper
                if not self._search_aborted and score >= 10000000:
                    break
                if self._search_aborted:
                    break
            except Exception:
                break  # Safety: if anything goes wrong, use last best

        if best_col is None or best_col not in valid_locations:
            best_col = random.choice(valid_locations)

        self.drop_piece(best_col)
        return best_col

