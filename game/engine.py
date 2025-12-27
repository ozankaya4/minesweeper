"""
RogueSweeper Game Engine

This module contains the core game logic for the Minesweeper gameplay.
All methods are stateless and operate on the board_state dictionary,
making it easy to test and integrate with the Django models.

Author: RogueSweeper Team
"""

from __future__ import annotations

import random
from typing import Any


class GameEngine:
    """
    Core game engine for RogueSweeper Minesweeper logic.
    
    This class provides static methods for all game operations including
    board initialization, cell revealing, flagging, and win/loss detection.
    All methods are pure functions that take a board state and return
    a modified copy, making the engine stateless and testable.
    
    Board State Structure:
        {
            "rows": int,              # Grid height
            "cols": int,              # Grid width
            "mines": [[r, c], ...],   # Mine positions as [row, col] pairs
            "revealed": [[r, c], ...], # Revealed cell positions
            "flagged": [[r, c], ...],  # Flagged cell positions
            "immune_flags": [[r, c], ...],  # Flags placed by Clue (cannot be removed)
            "adjacent_counts": {       # Pre-calculated adjacent mine counts
                "r,c": int,            # Key format: "row,col"
                ...
            },
            "game_over": bool,        # Whether the game has ended
            "won": bool,              # Whether the player won
            "initialized": bool       # Whether mines have been placed
        }
    """
    
    # Directions for adjacent cells (8 neighbors)
    DIRECTIONS: list[tuple[int, int]] = [
        (-1, -1), (-1, 0), (-1, 1),
        (0, -1),           (0, 1),
        (1, -1),  (1, 0),  (1, 1),
    ]
    
    @staticmethod
    def initialize_board(
        rows: int,
        cols: int,
        mine_count: int,
        safe_start: tuple[int, int]
    ) -> dict[str, Any]:
        """
        Initialize a new game board with randomly placed mines.
        
        Generates mine positions while ensuring the safe_start cell and
        its immediate neighbors are never mines. This guarantees the
        player cannot lose on their first click.
        
        Args:
            rows: Number of rows in the grid.
            cols: Number of columns in the grid.
            mine_count: Number of mines to place on the board.
            safe_start: Tuple of (row, col) for the first click position.
                       This cell and its neighbors will never contain mines.
        
        Returns:
            A complete board state dictionary with mines placed and
            adjacent_counts calculated. The 'initialized' flag is set to True.
        
        Raises:
            ValueError: If mine_count exceeds available safe cells.
        
        Example:
            >>> board = GameEngine.initialize_board(8, 8, 10, (4, 4))
            >>> board['initialized']
            True
            >>> len(board['mines'])
            10
        """
        safe_row, safe_col = safe_start
        
        # Build set of excluded cells (safe_start + neighbors)
        excluded_cells: set[tuple[int, int]] = {safe_start}
        for dr, dc in GameEngine.DIRECTIONS:
            nr, nc = safe_row + dr, safe_col + dc
            if 0 <= nr < rows and 0 <= nc < cols:
                excluded_cells.add((nr, nc))
        
        # Build list of all possible mine locations
        all_cells: list[tuple[int, int]] = [
            (r, c)
            for r in range(rows)
            for c in range(cols)
            if (r, c) not in excluded_cells
        ]
        
        # Validate mine count
        if mine_count > len(all_cells):
            raise ValueError(
                f"Cannot place {mine_count} mines. "
                f"Only {len(all_cells)} cells available after excluding safe zone."
            )
        
        # Randomly select mine positions
        mine_positions = random.sample(all_cells, mine_count)
        mines_set: set[tuple[int, int]] = set(mine_positions)
        
        # Calculate adjacent mine counts for all non-mine cells
        adjacent_counts: dict[str, int] = {}
        for r in range(rows):
            for c in range(cols):
                if (r, c) not in mines_set:
                    count = GameEngine._count_adjacent_mines(
                        r, c, rows, cols, mines_set
                    )
                    adjacent_counts[f"{r},{c}"] = count
        
        # Build and return the initialized board state
        return {
            "rows": rows,
            "cols": cols,
            "mines": [[r, c] for r, c in mine_positions],
            "revealed": [],
            "flagged": [],
            "immune_flags": [],
            "adjacent_counts": adjacent_counts,
            "game_over": False,
            "won": False,
            "initialized": True,
        }
    
    @staticmethod
    def _count_adjacent_mines(
        row: int,
        col: int,
        rows: int,
        cols: int,
        mines: set[tuple[int, int]]
    ) -> int:
        """
        Count the number of mines adjacent to a given cell.
        
        Args:
            row: Row index of the cell.
            col: Column index of the cell.
            rows: Total number of rows in the grid.
            cols: Total number of columns in the grid.
            mines: Set of mine positions as (row, col) tuples.
        
        Returns:
            Number of adjacent mines (0-8).
        """
        count = 0
        for dr, dc in GameEngine.DIRECTIONS:
            nr, nc = row + dr, col + dc
            if 0 <= nr < rows and 0 <= nc < cols:
                if (nr, nc) in mines:
                    count += 1
        return count
    
    @staticmethod
    def reveal_cell(
        board: dict[str, Any],
        row: int,
        col: int,
        mine_count: int | None = None
    ) -> dict[str, Any]:
        """
        Reveal a cell on the board.
        
        Handles all reveal logic including:
        - First-click initialization (deferred mine placement)
        - Mine hit detection (game over)
        - Flood fill for empty cells (0 adjacent mines)
        - Win condition checking
        
        Args:
            board: Current board state dictionary.
            row: Row index of the cell to reveal.
            col: Column index of the cell to reveal.
            mine_count: Number of mines to place if board needs initialization.
                       Required if board['initialized'] is False.
        
        Returns:
            Updated board state dictionary.
        
        Raises:
            ValueError: If mine_count not provided for uninitialized board.
        
        Example:
            >>> board = GameEngine.reveal_cell(board, 4, 4)
            >>> [4, 4] in board['revealed']
            True
        """
        # Don't allow reveals after game over
        if board.get("game_over", False):
            return board
        
        rows = board["rows"]
        cols = board["cols"]
        
        # Validate coordinates
        if not (0 <= row < rows and 0 <= col < cols):
            return board
        
        # Initialize board on first click if needed
        if not board.get("initialized", False):
            if mine_count is None:
                raise ValueError(
                    "mine_count must be provided for uninitialized board"
                )
            board = GameEngine.initialize_board(rows, cols, mine_count, (row, col))
        
        # Convert to sets for efficient lookups
        revealed_set = GameEngine._to_coord_set(board.get("revealed", []))
        flagged_set = GameEngine._to_coord_set(board.get("flagged", []))
        mines_set = GameEngine._to_coord_set(board.get("mines", []))
        
        # Don't reveal flagged or already revealed cells
        if (row, col) in flagged_set or (row, col) in revealed_set:
            return board
        
        # Check if hit a mine
        if (row, col) in mines_set:
            board = dict(board)  # Create copy to avoid mutation
            board["game_over"] = True
            board["won"] = False
            # Reveal all mines on game over
            for mine_r, mine_c in mines_set:
                revealed_set.add((mine_r, mine_c))
            board["revealed"] = [[r, c] for r, c in revealed_set]
            return board
        
        # Reveal the cell (and flood fill if empty)
        new_revealed = GameEngine._flood_fill_reveal(
            row, col, rows, cols, revealed_set, flagged_set, mines_set, board
        )
        
        # Update board with newly revealed cells
        board = dict(board)
        board["revealed"] = [[r, c] for r, c in new_revealed]
        
        # Check win condition
        board = GameEngine._check_win_condition(board)
        
        return board
    
    @staticmethod
    def _flood_fill_reveal(
        start_row: int,
        start_col: int,
        rows: int,
        cols: int,
        revealed: set[tuple[int, int]],
        flagged: set[tuple[int, int]],
        mines: set[tuple[int, int]],
        board: dict[str, Any]
    ) -> set[tuple[int, int]]:
        """
        Perform flood fill to reveal connected empty cells.
        
        When revealing a cell with 0 adjacent mines, automatically reveals
        all connected cells until cells with adjacent mines are reached.
        
        Args:
            start_row: Starting row for flood fill.
            start_col: Starting column for flood fill.
            rows: Total rows in grid.
            cols: Total columns in grid.
            revealed: Set of already revealed positions.
            flagged: Set of flagged positions.
            mines: Set of mine positions.
            board: Board state (for adjacent_counts lookup).
        
        Returns:
            Updated set of revealed cell positions.
        """
        # Create a copy of revealed set to modify
        new_revealed = set(revealed)
        
        # Use a stack for iterative flood fill (avoid recursion limit)
        stack: list[tuple[int, int]] = [(start_row, start_col)]
        
        while stack:
            r, c = stack.pop()
            
            # Skip if already processed, flagged, or is a mine
            if (r, c) in new_revealed or (r, c) in flagged or (r, c) in mines:
                continue
            
            # Reveal this cell
            new_revealed.add((r, c))
            
            # Get adjacent count for this cell
            adjacent_count = board.get("adjacent_counts", {}).get(f"{r},{c}", 0)
            
            # If empty cell (0 adjacent mines), add neighbors to stack
            if adjacent_count == 0:
                for dr, dc in GameEngine.DIRECTIONS:
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < rows and 0 <= nc < cols:
                        if (nr, nc) not in new_revealed:
                            stack.append((nr, nc))
        
        return new_revealed
    
    @staticmethod
    def _check_win_condition(board: dict[str, Any]) -> dict[str, Any]:
        """
        Check if the player has won the game.
        
        Win condition: All non-mine cells have been revealed.
        
        Args:
            board: Current board state.
        
        Returns:
            Updated board state with game_over and won flags set if won.
        """
        rows = board["rows"]
        cols = board["cols"]
        total_cells = rows * cols
        
        mines_count = len(board.get("mines", []))
        revealed_count = len(board.get("revealed", []))
        
        # Win if all non-mine cells are revealed
        if revealed_count == total_cells - mines_count:
            board = dict(board)
            board["game_over"] = True
            board["won"] = True
        
        return board
    
    @staticmethod
    def toggle_flag(
        board: dict[str, Any],
        row: int,
        col: int
    ) -> dict[str, Any]:
        """
        Toggle a flag on/off for a cell.
        
        Flags mark suspected mine locations. Flagged cells cannot be
        revealed until the flag is removed.
        
        Args:
            board: Current board state dictionary.
            row: Row index of the cell to toggle.
            col: Column index of the cell to toggle.
        
        Returns:
            Updated board state dictionary with flag toggled.
        
        Example:
            >>> board = GameEngine.toggle_flag(board, 2, 3)
            >>> [2, 3] in board['flagged']
            True
            >>> board = GameEngine.toggle_flag(board, 2, 3)
            >>> [2, 3] in board['flagged']
            False
        """
        # Don't allow flagging after game over
        if board.get("game_over", False):
            return board
        
        rows = board["rows"]
        cols = board["cols"]
        
        # Validate coordinates
        if not (0 <= row < rows and 0 <= col < cols):
            return board
        
        revealed_set = GameEngine._to_coord_set(board.get("revealed", []))
        
        # Can't flag revealed cells
        if (row, col) in revealed_set:
            return board
        
        # Can't toggle immune flags (placed by Clue power-up)
        immune_set = GameEngine._to_coord_set(board.get("immune_flags", []))
        if (row, col) in immune_set:
            return board
        
        # Toggle flag
        board = dict(board)
        flagged = [list(f) for f in board.get("flagged", [])]
        
        coord = [row, col]
        if coord in flagged:
            flagged.remove(coord)
        else:
            flagged.append(coord)
        
        board["flagged"] = flagged
        return board
    
    @staticmethod
    def apply_clue(
        board: dict[str, Any],
        row: int,
        col: int,
        mine_count: int | None = None
    ) -> dict[str, Any]:
        """
        Apply the Clue power-up to test a target cell.
        
        The Clue power-up allows the player to safely test any cell:
        - If the cell is a mine, it gets flagged with an immune flag
          (cannot be removed) and does NOT trigger game over.
        - If the cell is safe, it gets revealed normally.
        
        Args:
            board: Current board state dictionary.
            row: Row index of the target cell.
            col: Column index of the target cell.
            mine_count: Number of mines to place if board needs initialization.
                       Required if board['initialized'] is False.
        
        Returns:
            Updated board state dictionary.
        
        Example:
            >>> # Using clue on a mine - gets flagged safely
            >>> board = GameEngine.apply_clue(board, 2, 3)
            >>> [2, 3] in board['immune_flags']
            True
            >>> board['game_over']
            False
        """
        # Don't allow clues after game over
        if board.get("game_over", False):
            return board
        
        rows = board.get("rows", 0)
        cols_count = board.get("cols", 0)
        
        # Validate coordinates
        if not (0 <= row < rows and 0 <= col < cols_count):
            return board
        
        # If board not initialized, delegate to reveal_cell
        # (first click is always safe, so clue acts as normal reveal)
        if not board.get("initialized", False):
            return GameEngine.reveal_cell(board, row, col, mine_count)
        
        # Check if cell is already revealed or flagged
        revealed_set = GameEngine._to_coord_set(board.get("revealed", []))
        flagged_set = GameEngine._to_coord_set(board.get("flagged", []))
        
        if (row, col) in revealed_set or (row, col) in flagged_set:
            return board
        
        # Check if the target cell is a mine
        mines_set = GameEngine._to_coord_set(board.get("mines", []))
        
        if (row, col) in mines_set:
            # Cell is a mine - add immune flag (safe discovery)
            board = dict(board)
            
            # Add to flagged list
            flagged = [list(f) for f in board.get("flagged", [])]
            flagged.append([row, col])
            board["flagged"] = flagged
            
            # Add to immune_flags list (cannot be removed)
            immune_flags = [list(f) for f in board.get("immune_flags", [])]
            immune_flags.append([row, col])
            board["immune_flags"] = immune_flags
            
            return board
        else:
            # Cell is safe - delegate to reveal_cell
            return GameEngine.reveal_cell(board, row, col)
    
    @staticmethod
    def render_for_frontend(
        board: dict[str, Any],
        show_all: bool = False
    ) -> dict[str, Any]:
        """
        Create a sanitized board representation for the frontend.
        
        This method prepares the board data for sending to the client,
        hiding mine locations unless the game is over. This prevents
        cheating by inspecting API responses.
        
        Args:
            board: Current board state dictionary.
            show_all: If True, reveals all mine locations (for game over display).
                     Defaults to False.
        
        Returns:
            A dictionary containing only the information the frontend
            should have access to:
            - rows, cols: Grid dimensions
            - cells: 2D array of cell states for rendering
            - game_over, won: Game state flags
            - flags_count: Number of flags placed
            - mines_count: Total mines (for counter display)
        
        Cell states in the 'cells' array:
            - "hidden": Unrevealed cell
            - "flagged": Cell with a flag (player-placed)
            - "flagged_immune": Cell with an immune flag (placed by Clue)
            - "mine": Revealed mine (only when show_all=True or game_over)
            - "mine_hit": The mine that was clicked (caused game over)
            - 0-8: Number of adjacent mines (revealed safe cell)
        
        Example:
            >>> frontend_data = GameEngine.render_for_frontend(board)
            >>> frontend_data['cells'][0][0]  # Hidden cell
            'hidden'
        """
        rows = board.get("rows", 0)
        cols = board.get("cols", 0)
        game_over = board.get("game_over", False)
        won = board.get("won", False)
        
        revealed_set = GameEngine._to_coord_set(board.get("revealed", []))
        flagged_set = GameEngine._to_coord_set(board.get("flagged", []))
        immune_set = GameEngine._to_coord_set(board.get("immune_flags", []))
        mines_set = GameEngine._to_coord_set(board.get("mines", []))
        adjacent_counts = board.get("adjacent_counts", {})
        
        # Determine if we should show mines
        reveal_mines = show_all or game_over
        
        # Build the cells grid
        cells: list[list[str | int]] = []
        for r in range(rows):
            row_cells: list[str | int] = []
            for c in range(cols):
                cell_state: str | int
                
                if (r, c) in revealed_set:
                    if (r, c) in mines_set:
                        # This was the mine that was hit
                        cell_state = "mine_hit"
                    else:
                        # Show adjacent count
                        cell_state = adjacent_counts.get(f"{r},{c}", 0)
                elif (r, c) in immune_set:
                    # Immune flag (placed by Clue power-up)
                    cell_state = "flagged_immune"
                elif (r, c) in flagged_set:
                    # Regular player-placed flag
                    cell_state = "flagged"
                elif reveal_mines and (r, c) in mines_set:
                    cell_state = "mine"
                else:
                    cell_state = "hidden"
                
                row_cells.append(cell_state)
            cells.append(row_cells)
        
        return {
            "rows": rows,
            "cols": cols,
            "cells": cells,
            "game_over": game_over,
            "won": won,
            "flags_count": len(flagged_set),
            "mines_count": len(mines_set),
            "revealed_count": len(revealed_set),
            "initialized": board.get("initialized", False),
        }
    
    @staticmethod
    def _to_coord_set(coord_list: list[list[int]]) -> set[tuple[int, int]]:
        """
        Convert a list of [row, col] pairs to a set of (row, col) tuples.
        
        Args:
            coord_list: List of coordinates as [row, col] lists.
        
        Returns:
            Set of coordinates as (row, col) tuples for efficient lookup.
        """
        return {(coord[0], coord[1]) for coord in coord_list}
    
    @staticmethod
    def calculate_score(
        level: int,
        cells_revealed: int,
        time_elapsed: int,
        clues_used: int,
        won: bool
    ) -> int:
        """
        Calculate the score for a completed level.
        
        Scoring formula:
        - Base points: 100 * level
        - Cell bonus: 10 points per revealed cell
        - Time bonus: max(0, 300 - time_elapsed) points (bonus for speed)
        - Clue penalty: -50 points per clue used
        - Win bonus: 500 * level points for completing the level
        
        Args:
            level: Current level number.
            cells_revealed: Number of cells revealed.
            time_elapsed: Time taken in seconds.
            clues_used: Number of clues used.
            won: Whether the level was completed successfully.
        
        Returns:
            Calculated score (minimum 0).
        
        Example:
            >>> GameEngine.calculate_score(1, 50, 120, 0, True)
            1230  # 100 + 500 + 180 + 500 - 50
        """
        base_score = 100 * level
        cell_bonus = 10 * cells_revealed
        time_bonus = max(0, 300 - time_elapsed)
        clue_penalty = 50 * clues_used
        win_bonus = 500 * level if won else 0
        
        total = base_score + cell_bonus + time_bonus - clue_penalty + win_bonus
        return max(0, total)
    
    @staticmethod
    def chord_reveal(
        board: dict[str, Any],
        row: int,
        col: int
    ) -> dict[str, Any]:
        """
        Perform a chord reveal (reveal all unflagged neighbors).
        
        Chord reveal is triggered when clicking on a revealed number cell.
        If the number of adjacent flags equals the cell's number, all
        unflagged neighbors are revealed. This is a common Minesweeper
        mechanic for faster gameplay.
        
        Args:
            board: Current board state dictionary.
            row: Row index of the cell to chord.
            col: Column index of the cell to chord.
        
        Returns:
            Updated board state dictionary.
        
        Note:
            If the flags are incorrectly placed, this can trigger a game over
            by revealing a mine.
        """
        if board.get("game_over", False):
            return board
        
        rows = board["rows"]
        cols = board["cols"]
        
        # Validate coordinates
        if not (0 <= row < rows and 0 <= col < cols):
            return board
        
        revealed_set = GameEngine._to_coord_set(board.get("revealed", []))
        flagged_set = GameEngine._to_coord_set(board.get("flagged", []))
        
        # Can only chord on revealed cells
        if (row, col) not in revealed_set:
            return board
        
        # Get the adjacent count for this cell
        adjacent_count = board.get("adjacent_counts", {}).get(f"{row},{col}", 0)
        
        if adjacent_count == 0:
            return board
        
        # Count adjacent flags
        adjacent_flags = 0
        neighbors: list[tuple[int, int]] = []
        for dr, dc in GameEngine.DIRECTIONS:
            nr, nc = row + dr, col + dc
            if 0 <= nr < rows and 0 <= nc < cols:
                neighbors.append((nr, nc))
                if (nr, nc) in flagged_set:
                    adjacent_flags += 1
        
        # Only chord if flag count matches adjacent mine count
        if adjacent_flags != adjacent_count:
            return board
        
        # Reveal all unflagged, unrevealed neighbors
        for nr, nc in neighbors:
            if (nr, nc) not in flagged_set and (nr, nc) not in revealed_set:
                board = GameEngine.reveal_cell(board, nr, nc)
                # Check if game ended
                if board.get("game_over", False):
                    break
        
        return board
