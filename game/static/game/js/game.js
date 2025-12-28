/**
 * RogueSweeper Game Logic
 * 
 * Handles all game interactions, API calls, and UI updates.
 * Uses the Fetch API for backend communication.
 * 
 * Requires window.gameConfig to be defined with:
 *   - urls: API endpoint URLs
 *   - messages: Translated UI messages
 * 
 * @author RogueSweeper Team
 */

const RogueSweeper = (function() {
    'use strict';

    // =============================================================================
    // Configuration (from window.gameConfig or fallback to window.API_URLS)
    // =============================================================================
    
    const getConfig = () => window.gameConfig || { urls: window.API_URLS, messages: {} };
    const getUrl = (key) => getConfig().urls?.[key] || window.API_URLS?.[key] || '';
    const getMessage = (key, fallback = '') => getConfig().messages?.[key] || fallback;

    // =============================================================================
    // State
    // =============================================================================
    
    let state = {
        isClueMode: false,
        gameData: null,
        timerInterval: null,
        elapsedSeconds: 0,
        isGameActive: false,
        hasSession: false
    };

    // =============================================================================
    // Touch State (for mobile long-press flagging)
    // =============================================================================
    
    const LONG_PRESS_DURATION = 500; // milliseconds
    let touchState = {
        timer: null,
        startX: 0,
        startY: 0,
        cell: null,
        isLongPress: false,
        moved: false,
        skipNextClick: false,  // Flag to prevent click after long press
        isFlagMode: false  // Flag mode toggle for mobile
    };

    // =============================================================================
    // DOM Elements
    // =============================================================================
    
    const elements = {
        grid: null,
        loading: null,
        gameOverOverlay: null,
        gameOverTitle: null,
        gameOverMessage: null,
        gameOverActions: null,
        gameStatus: null,
        // Stats
        statLevel: null,
        statScore: null,
        statMines: null,
        statFlags: null,
        statClues: null,
        statTime: null,
        // Buttons
        btnNewGame: null,
        btnClue: null,
        btnNextLevel: null,
        btnAbandon: null,
        // Modals
        leaderboardModal: null,
        statsModal: null,
        leaderboardBody: null,
        statsBody: null
    };

    // =============================================================================
    // Utility Functions
    // =============================================================================
    
    /**
     * Get CSRF token from meta tag or cookie
     * @returns {string} CSRF token
     */
    function getCsrfToken() {
        // First try meta tag
        const meta = document.querySelector('meta[name="csrf-token"]');
        if (meta && meta.getAttribute('content')) {
            return meta.getAttribute('content');
        }
        
        // Fallback to cookie
        const cookies = document.cookie.split(';');
        for (let cookie of cookies) {
            const [name, value] = cookie.trim().split('=');
            if (name === 'csrftoken') {
                return value;
            }
        }
        return '';
    }

    /**
     * Make an API request
     * @param {string} url - API endpoint
     * @param {string} method - HTTP method
     * @param {object} data - Request body data
     * @returns {Promise<object>} Response data
     */
    async function apiRequest(url, method = 'GET', data = null) {
        const options = {
            method: method,
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken()
            },
            credentials: 'same-origin'
        };

        if (data && method !== 'GET') {
            options.body = JSON.stringify(data);
        }

        try {
            const response = await fetch(url, options);
            
            if (response.status === 403) {
                // CSRF or authentication error - handle silently
                console.warn('403 Error - likely CSRF or session issue');
                return { error: 'forbidden', status: 403 };
            }
            
            if (response.status === 404) {
                return { error: 'not_found', status: 404 };
            }

            const responseData = await response.json();
            
            if (!response.ok) {
                console.error('API Error:', responseData);
                return { error: responseData.detail || 'Unknown error', status: response.status };
            }

            return responseData;
        } catch (error) {
            console.error('Network Error:', error);
            showError(getMessage('networkError', 'Network error. Please check your connection.'));
            return null;
        }
    }

    /**
     * Format seconds as MM:SS
     * @param {number} seconds - Total seconds
     * @returns {string} Formatted time
     */
    function formatTime(seconds) {
        const mins = Math.floor(seconds / 60);
        const secs = seconds % 60;
        return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    }

    /**
     * Show error message to user
     * @param {string} message - Error message
     */
    function showError(message) {
        // Create toast notification
        const toast = document.createElement('div');
        toast.className = 'position-fixed top-0 end-0 p-3';
        toast.style.zIndex = '9999';
        toast.innerHTML = `
            <div class="toast show bg-danger text-white" role="alert">
                <div class="toast-header bg-danger text-white">
                    <i class="bi bi-exclamation-triangle me-2"></i>
                    <strong class="me-auto">Error</strong>
                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="toast"></button>
                </div>
                <div class="toast-body">${message}</div>
            </div>
        `;
        document.body.appendChild(toast);
        
        setTimeout(() => toast.remove(), 5000);
    }

    // =============================================================================
    // Timer Functions
    // =============================================================================
    
    /**
     * Start the game timer
     */
    function startTimer() {
        if (state.timerInterval) {
            clearInterval(state.timerInterval);
        }
        
        state.timerInterval = setInterval(() => {
            if (state.isGameActive) {
                state.elapsedSeconds++;
                elements.statTime.textContent = formatTime(state.elapsedSeconds);
                
                // Sync with server every 30 seconds
                if (state.elapsedSeconds % 30 === 0) {
                    syncTime();
                }
            }
        }, 1000);
    }

    /**
     * Stop the game timer
     */
    function stopTimer() {
        if (state.timerInterval) {
            clearInterval(state.timerInterval);
            state.timerInterval = null;
        }
        state.isGameActive = false;
    }

    /**
     * Sync elapsed time with server
     */
    async function syncTime() {
        if (!state.hasSession) return;
        
        await apiRequest(getUrl('updateTime'), 'POST', {
            time_elapsed: state.elapsedSeconds
        });
    }

    // =============================================================================
    // Game Initialization
    // =============================================================================
    
    /**
     * Initialize the game application
     */
    function init() {
        // Cache DOM elements
        cacheElements();
        
        // Bind event listeners
        bindEvents();
        
        // Check for existing session
        checkExistingSession();
    }

    /**
     * Cache DOM element references
     */
    function cacheElements() {
        elements.grid = document.getElementById('game-grid');
        elements.loading = document.getElementById('game-loading');
        elements.gameOverOverlay = document.getElementById('game-over-overlay');
        elements.gameOverTitle = document.getElementById('game-over-title');
        elements.gameOverMessage = document.getElementById('game-over-message');
        elements.gameOverActions = document.getElementById('game-over-actions');
        elements.gameStatus = document.getElementById('game-status');
        
        // Stats
        elements.statLevel = document.getElementById('stat-level');
        elements.statScore = document.getElementById('stat-score');
        elements.statMines = document.getElementById('stat-mines');
        elements.statFlags = document.getElementById('stat-flags');
        elements.statClues = document.getElementById('stat-clues');
        elements.statTime = document.getElementById('stat-time');
        
        // Buttons
        elements.btnNewGame = document.getElementById('btn-new-game');
        elements.btnClue = document.getElementById('btn-clue');
        elements.btnNextLevel = document.getElementById('btn-next-level');
        elements.btnAbandon = document.getElementById('btn-abandon');
        elements.btnSaveProgress = document.getElementById('btn-save-progress');
        
        // Mobile flag mode toggle
        elements.flagModeToggle = document.getElementById('flag-mode-toggle');
        elements.btnModeReveal = document.getElementById('btn-mode-reveal');
        elements.btnModeFlag = document.getElementById('btn-mode-flag');
        
        // Modals
        elements.leaderboardModal = document.getElementById('leaderboardModal');
        elements.statsModal = document.getElementById('statsModal');
        elements.leaderboardBody = document.getElementById('leaderboard-body');
        elements.statsBody = document.getElementById('stats-body');
    }

    /**
     * Bind event listeners
     */
    function bindEvents() {
        // New Game button
        elements.btnNewGame.addEventListener('click', () => initGame(false));
        
        // Clue button
        elements.btnClue.addEventListener('click', toggleClueMode);
        
        // Next Level button
        elements.btnNextLevel.addEventListener('click', advanceToNextLevel);
        
        // Abandon button
        if (elements.btnAbandon) {
            elements.btnAbandon.addEventListener('click', abandonGame);
        }
        
        // Save Progress button (only for logged-in users)
        if (elements.btnSaveProgress) {
            elements.btnSaveProgress.addEventListener('click', saveProgress);
        }
        
        // Mobile flag mode toggle
        initMobileFlagMode();
        
        // Leaderboard link
        const leaderboardLink = document.getElementById('leaderboard-link');
        if (leaderboardLink) {
            leaderboardLink.addEventListener('click', (e) => {
                e.preventDefault();
                loadLeaderboard();
            });
        }
        
        // Stats link
        const statsLink = document.getElementById('stats-link');
        if (statsLink) {
            statsLink.addEventListener('click', (e) => {
                e.preventDefault();
                loadStats();
            });
        }
        
        // Keyboard shortcuts
        document.addEventListener('keydown', handleKeyboard);
    }

    /**
     * Initialize mobile flag mode toggle
     * Shows toggle on touch devices, handles button clicks
     */
    function initMobileFlagMode() {
        // Check if this is a touch device
        const isTouchDevice = ('ontouchstart' in window) || (navigator.maxTouchPoints > 0);
        
        if (isTouchDevice && elements.flagModeToggle) {
            // Show the toggle on touch devices
            elements.flagModeToggle.classList.remove('d-none');
            
            // Reveal mode button click
            if (elements.btnModeReveal) {
                elements.btnModeReveal.addEventListener('click', () => {
                    setFlagMode(false);
                });
            }
            
            // Flag mode button click
            if (elements.btnModeFlag) {
                elements.btnModeFlag.addEventListener('click', () => {
                    setFlagMode(true);
                });
            }
        }
    }

    /**
     * Set flag mode on/off
     * @param {boolean} enabled - Whether flag mode is enabled
     */
    function setFlagMode(enabled) {
        touchState.isFlagMode = enabled;
        
        if (elements.btnModeReveal && elements.btnModeFlag) {
            if (enabled) {
                elements.btnModeReveal.classList.remove('btn-primary', 'active');
                elements.btnModeReveal.classList.add('btn-outline-primary');
                elements.btnModeFlag.classList.remove('btn-outline-warning');
                elements.btnModeFlag.classList.add('btn-warning', 'active');
            } else {
                elements.btnModeReveal.classList.remove('btn-outline-primary');
                elements.btnModeReveal.classList.add('btn-primary', 'active');
                elements.btnModeFlag.classList.remove('btn-warning', 'active');
                elements.btnModeFlag.classList.add('btn-outline-warning');
            }
        }
    }

    /**
     * Handle keyboard shortcuts
     * @param {KeyboardEvent} e - Keyboard event
     */
    function handleKeyboard(e) {
        // Escape to cancel clue mode
        if (e.key === 'Escape' && state.isClueMode) {
            toggleClueMode();
        }
        
        // 'C' to toggle clue mode
        if (e.key === 'c' || e.key === 'C') {
            if (state.hasSession && !state.gameData?.board?.game_over) {
                toggleClueMode();
            }
        }
        
        // 'N' for new game
        if (e.key === 'n' || e.key === 'N') {
            if (e.ctrlKey || e.metaKey) {
                e.preventDefault();
                initGame(true);
            }
        }
    }

    /**
     * Check for existing game session
     */
    async function checkExistingSession() {
        showLoading(true);
        
        const data = await apiRequest(getUrl('session'));
        
        if (data && !data.error) {
            state.hasSession = true;
            state.gameData = data;
            state.elapsedSeconds = data.time_elapsed || 0;
            
            renderBoard(data.board);
            updateStats(data);
            
            if (!data.board.game_over) {
                state.isGameActive = true;
                startTimer();
                elements.btnAbandon.classList.remove('d-none');
                if (elements.btnSaveProgress) {
                    elements.btnSaveProgress.classList.remove('d-none');
                }
            } else {
                handleGameOver(data);
            }
        } else {
            // No active session - show welcome state
            showWelcome();
        }
        
        showLoading(false);
    }

    /**
     * Initialize a new game
     * @param {boolean} forceNew - Force new game even if one exists
     */
    async function initGame(forceNew = false) {
        showLoading(true);
        stopTimer();
        hideGameOver();
        
        const data = await apiRequest(getUrl('start'), 'POST', { force_new: forceNew });
        
        if (data && !data.error) {
            state.hasSession = true;
            state.gameData = data;
            state.elapsedSeconds = data.time_elapsed || 0;
            state.isGameActive = true;
            state.isClueMode = false;
            document.body.classList.remove('clue-mode');
            
            renderBoard(data.board);
            updateStats(data);
            startTimer();
            
            elements.btnAbandon.classList.remove('d-none');
            if (elements.btnSaveProgress) {
                elements.btnSaveProgress.classList.remove('d-none');
            }
            elements.btnNextLevel.classList.add('d-none');
            elements.gameStatus.textContent = getMessage('playing', 'Playing');
            elements.gameStatus.className = 'badge bg-success';
        } else if (data?.error) {
            showError(data.error);
        }
        
        showLoading(false);
    }

    /**
     * Show welcome state (no active game)
     */
    function showWelcome() {
        elements.grid.innerHTML = `
            <div class="text-center text-white p-5">
                <h3 class="mb-4">${getMessage('welcome', 'Welcome to RogueSweeper!')}</h3>
                <p class="lead mb-4">${getMessage('welcomeDesc', 'A roguelike Minesweeper with infinite levels.')}</p>
                <p class="mb-4">${getMessage('welcomeAction', 'Click "New Game" to start your run!')}</p>
            </div>
        `;
        elements.grid.classList.remove('d-none');
        elements.grid.style.display = 'block';
        elements.gameStatus.textContent = getMessage('ready', 'Ready');
        elements.gameStatus.className = 'badge bg-secondary';
    }

    // =============================================================================
    // Board Rendering
    // =============================================================================
    
    /**
     * Render the game board
     * @param {object} boardData - Board data from API
     */
    function renderBoard(boardData) {
        if (!boardData || !boardData.cells) {
            showWelcome();
            return;
        }
        
        const { rows, cols, cells } = boardData;
        
        // Update CSS variable for grid columns
        elements.grid.style.setProperty('--grid-cols', cols);
        
        // Clear existing grid
        elements.grid.innerHTML = '';
        
        // Create cells
        for (let row = 0; row < rows; row++) {
            for (let col = 0; col < cols; col++) {
                const cellValue = cells[row][col];
                const cell = createCell(row, col, cellValue);
                elements.grid.appendChild(cell);
            }
        }
        
        // Show grid
        elements.grid.classList.remove('d-none');
        elements.grid.style.display = 'grid';
    }

    /**
     * Create a cell element
     * @param {number} row - Row index
     * @param {number} col - Column index
     * @param {string|number} value - Cell value
     * @returns {HTMLElement} Cell element
     */
    function createCell(row, col, value) {
        const cell = document.createElement('div');
        cell.className = 'cell';
        cell.dataset.row = row;
        cell.dataset.col = col;
        
        // Apply cell state
        applyCellState(cell, value);
        
        // Check if device supports touch
        const isTouchDevice = ('ontouchstart' in window) || (navigator.maxTouchPoints > 0);
        
        if (isTouchDevice) {
            // Touch device: use touch events only
            cell.addEventListener('touchstart', handleTouchStart, { passive: false });
            cell.addEventListener('touchend', handleTouchEnd, { passive: false });
            cell.addEventListener('touchmove', handleTouchMove, { passive: false });
            cell.addEventListener('touchcancel', handleTouchCancel);
            // Prevent context menu on long press
            cell.addEventListener('contextmenu', (e) => e.preventDefault());
        } else {
            // Desktop: use mouse events
            cell.addEventListener('click', handleLeftClick);
            cell.addEventListener('contextmenu', handleRightClick);
            cell.addEventListener('auxclick', handleMiddleClick);
        }
        
        return cell;
    }

    /**
     * Apply visual state to a cell
     * @param {HTMLElement} cell - Cell element
     * @param {string|number} value - Cell value
     */
    function applyCellState(cell, value) {
        // Reset classes
        cell.className = 'cell';
        cell.textContent = '';
        cell.dataset.val = '';
        
        if (value === 'hidden') {
            cell.classList.add('hidden');
        } else if (value === 'flagged') {
            cell.classList.add('flagged');
        } else if (value === 'flagged_immune') {
            cell.classList.add('flagged-immune');
        } else if (value === 'mine') {
            cell.classList.add('revealed', 'mine');
        } else if (value === 'mine_hit') {
            cell.classList.add('revealed', 'mine-hit');
        } else if (typeof value === 'number') {
            cell.classList.add('revealed');
            cell.dataset.val = value;
            
            if (value === 0) {
                cell.classList.add('empty');
            } else {
                cell.textContent = value;
            }
        }
    }

    // =============================================================================
    // User Interactions
    // =============================================================================
    
    /**
     * Handle left click on cell
     * @param {MouseEvent} e - Click event
     */
    async function handleLeftClick(e) {
        // Skip this click if it's the result of a long press
        if (touchState.skipNextClick) {
            touchState.skipNextClick = false;
            e.preventDefault();
            return;
        }
        
        const cell = e.currentTarget;
        const row = parseInt(cell.dataset.row);
        const col = parseInt(cell.dataset.col);
        
        // Don't allow clicks if game is over
        if (state.gameData?.board?.game_over) {
            return;
        }
        
        let action = 'reveal';
        
        // Check if this is a revealed numbered cell (for chord action)
        if (cell.classList.contains('revealed') && !cell.classList.contains('empty')) {
            // Chord: reveal all unflagged neighbors if correct number of flags placed
            action = 'chord';
        } else if (!cell.classList.contains('hidden') && !cell.classList.contains('flagged') && !cell.classList.contains('flagged-immune')) {
            // Don't allow clicks on other revealed cells (empty cells)
            return;
        } else if (state.isClueMode) {
            // If clue mode is active, use clue action
            action = 'clue';
            toggleClueMode(); // Turn off clue mode after use
        }
        
        await performAction(row, col, action);
    }

    /**
     * Handle right click (flag) on cell
     * @param {MouseEvent} e - Click event
     */
    async function handleRightClick(e) {
        e.preventDefault();
        
        const cell = e.currentTarget;
        const row = parseInt(cell.dataset.row);
        const col = parseInt(cell.dataset.col);
        
        // Only allow flagging hidden cells
        if (!cell.classList.contains('hidden') && 
            !cell.classList.contains('flagged') &&
            !cell.classList.contains('flagged-immune')) {
            return;
        }
        
        // Don't allow if game is over
        if (state.gameData?.board?.game_over) {
            return;
        }
        
        await performAction(row, col, 'flag');
    }

    /**
     * Handle middle click (chord) on cell
     * @param {MouseEvent} e - Click event
     */
    async function handleMiddleClick(e) {
        if (e.button !== 1) return; // Only middle mouse button
        e.preventDefault();
        
        const cell = e.currentTarget;
        const row = parseInt(cell.dataset.row);
        const col = parseInt(cell.dataset.col);
        
        // Only allow chord on revealed number cells
        if (!cell.classList.contains('revealed') || cell.classList.contains('empty')) {
            return;
        }
        
        // Don't allow if game is over
        if (state.gameData?.board?.game_over) {
            return;
        }
        
        await performAction(row, col, 'chord');
    }

    // =============================================================================
    // Touch Handlers (Mobile Long-Press for Flagging)
    // =============================================================================

    /**
     * Handle touch start - begin long press timer
     * @param {TouchEvent} e - Touch event
     */
    function handleTouchStart(e) {
        const cell = e.currentTarget;
        
        // Store touch start position
        const touch = e.touches[0];
        touchState.startX = touch.clientX;
        touchState.startY = touch.clientY;
        touchState.cell = cell;
        touchState.isLongPress = false;
        touchState.moved = false;
        
        // Add visual feedback
        cell.classList.add('touch-active');
        
        // Start long press timer
        touchState.timer = setTimeout(() => {
            // Only flag if user hasn't moved
            if (!touchState.moved) {
                touchState.isLongPress = true;
                touchState.skipNextClick = true;  // Prevent the click event
                
                // Vibrate for haptic feedback (if supported)
                if (navigator.vibrate) {
                    navigator.vibrate(50);
                }
                
                // Perform flag action
                handleLongPressFlag(cell);
            }
        }, LONG_PRESS_DURATION);
    }

    /**
     * Handle touch move - cancel long press if moved too far
     * @param {TouchEvent} e - Touch event
     */
    function handleTouchMove(e) {
        if (!touchState.timer) return;
        
        const touch = e.touches[0];
        const deltaX = Math.abs(touch.clientX - touchState.startX);
        const deltaY = Math.abs(touch.clientY - touchState.startY);
        
        // If moved more than 10px, cancel long press
        if (deltaX > 10 || deltaY > 10) {
            touchState.moved = true;
            clearTimeout(touchState.timer);
            touchState.timer = null;
            
            if (touchState.cell) {
                touchState.cell.classList.remove('touch-active');
            }
        }
    }

    /**
     * Handle touch end - perform tap action if not long press
     * @param {TouchEvent} e - Touch event
     */
    function handleTouchEnd(e) {
        e.preventDefault(); // Prevent any default behavior and click events
        
        const cell = touchState.cell;
        
        // Clear the timer
        if (touchState.timer) {
            clearTimeout(touchState.timer);
            touchState.timer = null;
        }
        
        // Remove visual feedback
        if (cell) {
            cell.classList.remove('touch-active');
        }
        
        // If it was a long press, flag action already performed
        if (touchState.isLongPress) {
            touchState.isLongPress = false;
            return;
        }
        
        // If user moved, don't perform action
        if (touchState.moved) {
            return;
        }
        
        // Normal tap - perform reveal action (same as left click)
        if (cell) {
            handleTapReveal(cell);
        }
    }

    /**
     * Handle tap to reveal (for touch devices)
     * @param {HTMLElement} cell - The cell element
     */
    async function handleTapReveal(cell) {
        const row = parseInt(cell.dataset.row);
        const col = parseInt(cell.dataset.col);
        
        // Don't allow if game is over
        if (state.gameData?.board?.game_over) {
            return;
        }
        
        // If in flag mode, toggle flag instead of reveal
        if (touchState.isFlagMode) {
            // Only allow flagging hidden cells
            if (cell.classList.contains('hidden') || 
                cell.classList.contains('flagged') || 
                cell.classList.contains('flagged-immune')) {
                await performAction(row, col, 'flag');
            }
            return;
        }
        
        let action = 'reveal';
        
        // Check if this is a revealed numbered cell (for chord action)
        if (cell.classList.contains('revealed') && !cell.classList.contains('empty')) {
            action = 'chord';
        } else if (!cell.classList.contains('hidden') && !cell.classList.contains('flagged') && !cell.classList.contains('flagged-immune')) {
            // Don't allow taps on other revealed cells (empty cells)
            return;
        } else if (state.isClueMode) {
            // If clue mode is active, use clue action
            action = 'clue';
            toggleClueMode();
        }
        
        await performAction(row, col, action);
    }

    /**
     * Handle touch cancel
     * @param {TouchEvent} e - Touch event
     */
    function handleTouchCancel(e) {
        if (touchState.timer) {
            clearTimeout(touchState.timer);
            touchState.timer = null;
        }
        
        if (touchState.cell) {
            touchState.cell.classList.remove('touch-active');
        }
        
        touchState.isLongPress = false;
        touchState.moved = false;
    }

    /**
     * Handle long press flag action
     * @param {HTMLElement} cell - Cell element
     */
    async function handleLongPressFlag(cell) {
        const row = parseInt(cell.dataset.row);
        const col = parseInt(cell.dataset.col);
        
        // Only allow flagging hidden cells
        if (!cell.classList.contains('hidden') && 
            !cell.classList.contains('flagged') &&
            !cell.classList.contains('flagged-immune')) {
            return;
        }
        
        // Don't allow if game is over
        if (state.gameData?.board?.game_over) {
            return;
        }
        
        await performAction(row, col, 'flag');
    }

    /**
     * Perform a game action
     * @param {number} row - Row index
     * @param {number} col - Column index
     * @param {string} action - Action type
     */
    async function performAction(row, col, action) {
        const data = await apiRequest(getUrl('action'), 'POST', {
            row: row,
            col: col,
            action: action
        });
        
        if (data && !data.error) {
            state.gameData = data;
            renderBoard(data.board);
            updateStats(data);
            
            // Check for game over
            if (data.board.game_over) {
                handleGameOver(data);
            }
        } else if (data?.error) {
            showError(data.error);
        }
    }

    /**
     * Toggle clue mode
     */
    function toggleClueMode() {
        // Don't allow if no clues remaining
        if (!state.isClueMode && state.gameData?.clues_remaining <= 0) {
            showError(getMessage('noClues', 'No clues remaining!'));
            return;
        }
        
        state.isClueMode = !state.isClueMode;
        
        if (state.isClueMode) {
            document.body.classList.add('clue-mode');
            elements.btnClue.classList.add('active');
            elements.gameStatus.textContent = getMessage('clueMode', 'Clue Mode');
            elements.gameStatus.className = 'badge bg-warning text-dark';
        } else {
            document.body.classList.remove('clue-mode');
            elements.btnClue.classList.remove('active');
            elements.gameStatus.textContent = getMessage('playing', 'Playing');
            elements.gameStatus.className = 'badge bg-success';
        }
    }

    // =============================================================================
    // Stats Update
    // =============================================================================
    
    /**
     * Update stats display
     * @param {object} data - Session data from API
     */
    function updateStats(data) {
        if (!data) return;
        
        elements.statLevel.textContent = data.level_number || 1;
        elements.statScore.textContent = data.score || 0;
        
        // Display clues as "remaining/total"
        const cluesRemaining = data.clues_remaining ?? 1;
        const cluesTotal = data.clues_total ?? 1;
        elements.statClues.textContent = `${cluesRemaining}/${cluesTotal}`;
        
        // Board-specific stats
        if (data.board) {
            const minesRemaining = (data.board.mines_count || 0) - (data.board.flags_count || 0);
            elements.statMines.textContent = Math.max(0, minesRemaining);
            elements.statFlags.textContent = data.board.flags_count || 0;
        }
        
        // Update clue button state
        if (cluesRemaining > 0 && !data.board?.game_over) {
            elements.btnClue.disabled = false;
        } else {
            elements.btnClue.disabled = true;
            state.isClueMode = false;
            document.body.classList.remove('clue-mode');
        }
        
        // Warning state for low clues
        if (cluesRemaining === 0) {
            elements.statClues.classList.add('bg-danger');
            elements.statClues.classList.remove('bg-light', 'text-dark');
        } else {
            elements.statClues.classList.remove('bg-danger');
            elements.statClues.classList.add('bg-light', 'text-dark');
        }
        
        // Update time display
        elements.statTime.textContent = formatTime(state.elapsedSeconds);
    }

    // =============================================================================
    // Game Over Handling
    // =============================================================================
    
    /**
     * Handle game over state
     * @param {object} data - Session data from API
     */
    function handleGameOver(data) {
        stopTimer();
        syncTime(); // Final time sync
        
        const won = data.board.won;
        
        // Update status badge
        if (won) {
            elements.gameStatus.textContent = getMessage('victory', 'Victory!');
            elements.gameStatus.className = 'badge bg-success';
        } else {
            elements.gameStatus.textContent = getMessage('gameOver', 'Game Over');
            elements.gameStatus.className = 'badge bg-danger';
        }
        
        // Show game over overlay
        elements.gameOverOverlay.classList.remove('d-none');
        
        if (won) {
            elements.gameOverTitle.textContent = `🎉 ${getMessage('levelComplete', 'Level Complete!')}`;
            elements.gameOverTitle.className = 'display-4 mb-3 win';
            elements.gameOverMessage.textContent = `${getMessage('clearedLevel', 'You cleared Level')} ${data.level_number}! Score: ${data.score}`;
            
            // Show next level button
            elements.btnNextLevel.classList.remove('d-none');
            elements.btnAbandon.classList.add('d-none');
            if (elements.btnSaveProgress) {
                elements.btnSaveProgress.classList.add('d-none');
            }
            
            elements.gameOverActions.innerHTML = `
                <button class="btn btn-success btn-lg me-2" onclick="RogueSweeper.advanceToNextLevel()">
                    <i class="bi bi-arrow-right-circle me-2"></i>${getMessage('nextLevel', 'Next Level')}
                </button>
                <button class="btn btn-outline-light" onclick="RogueSweeper.initGame(true)">
                    <i class="bi bi-arrow-clockwise me-2"></i>${getMessage('newRun', 'New Run')}
                </button>
            `;
        } else {
            elements.gameOverTitle.textContent = `💥 ${getMessage('gameOver', 'Game Over!')}`;
            elements.gameOverTitle.className = 'display-4 mb-3 lose';
            elements.gameOverMessage.textContent = `${getMessage('reachedLevel', 'You reached Level')} ${data.level_number} ${getMessage('withScore', 'with')} ${data.score} ${getMessage('points', 'points')}.`;
            
            elements.btnNextLevel.classList.add('d-none');
            elements.btnAbandon.classList.add('d-none');
            if (elements.btnSaveProgress) {
                elements.btnSaveProgress.classList.add('d-none');
            }
            
            elements.gameOverActions.innerHTML = `
                <button class="btn btn-success btn-lg" onclick="RogueSweeper.initGame(true)">
                    <i class="bi bi-arrow-clockwise me-2"></i>${getMessage('tryAgain', 'Try Again')}
                </button>
            `;
        }
    }

    /**
     * Hide game over overlay
     */
    function hideGameOver() {
        elements.gameOverOverlay.classList.add('d-none');
    }

    /**
     * Advance to next level
     */
    async function advanceToNextLevel() {
        showLoading(true);
        hideGameOver();
        
        const data = await apiRequest(getUrl('nextLevel'), 'POST', { confirm: true });
        
        if (data && !data.error) {
            state.gameData = data;
            state.elapsedSeconds = data.time_elapsed || 0;
            state.isGameActive = true;
            
            renderBoard(data.board);
            updateStats(data);
            startTimer();
            
            elements.btnNextLevel.classList.add('d-none');
            elements.btnAbandon.classList.remove('d-none');
            if (elements.btnSaveProgress) {
                elements.btnSaveProgress.classList.remove('d-none');
            }
            elements.gameStatus.textContent = getMessage('playing', 'Playing');
            elements.gameStatus.className = 'badge bg-success';
        } else if (data?.error) {
            showError(data.error);
        }
        
        showLoading(false);
    }

    /**
     * Abandon current game
     */
    async function abandonGame() {
        if (!confirm(getMessage('confirmAbandon', 'Are you sure you want to abandon this run? Your progress will be saved to the leaderboard.'))) {
            return;
        }
        
        const data = await apiRequest(getUrl('abandon'), 'POST');
        
        if (data && !data.error) {
            state.hasSession = false;
            state.gameData = null;
            stopTimer();
            
            elements.btnAbandon.classList.add('d-none');
            if (elements.btnSaveProgress) {
                elements.btnSaveProgress.classList.add('d-none');
            }
            showWelcome();
            
            // Reset stats
            elements.statLevel.textContent = '1';
            elements.statScore.textContent = '0';
            elements.statMines.textContent = '10';
            elements.statFlags.textContent = '0';
            elements.statClues.textContent = '1';
            elements.statTime.textContent = '00:00';
        }
    }

    /**
     * Save progress for logged-in users
     * Saves current level and score to the player's profile
     */
    async function saveProgress() {
        if (!state.hasSession) {
            return;
        }
        
        // Disable button while saving
        if (elements.btnSaveProgress) {
            elements.btnSaveProgress.disabled = true;
            elements.btnSaveProgress.innerHTML = '<i class="bi bi-hourglass-split me-2"></i>Saving...';
        }
        
        const data = await apiRequest(getUrl('saveProgress'), 'POST');
        
        // Re-enable button
        if (elements.btnSaveProgress) {
            elements.btnSaveProgress.disabled = false;
            elements.btnSaveProgress.innerHTML = '<i class="bi bi-save me-2"></i>' + getMessage('saveProgress', 'Save Progress');
        }
        
        if (data && !data.error) {
            // Show success message
            const message = data.high_score_updated 
                ? getMessage('progressSavedWithHighScore', 'Progress saved! New high score!')
                : getMessage('progressSaved', 'Progress saved successfully!');
            
            showToast(message, 'success');
        } else if (data?.error) {
            showToast(getMessage('saveError', 'Could not save progress.'), 'danger');
        }
    }

    /**
     * Show a temporary toast notification
     * @param {string} message - The message to display
     * @param {string} type - Bootstrap color class (success, danger, warning, etc.)
     */
    function showToast(message, type = 'info') {
        // Create toast container if it doesn't exist
        let toastContainer = document.getElementById('toast-container');
        if (!toastContainer) {
            toastContainer = document.createElement('div');
            toastContainer.id = 'toast-container';
            toastContainer.className = 'toast-container position-fixed bottom-0 end-0 p-3';
            toastContainer.style.zIndex = '9999';
            document.body.appendChild(toastContainer);
        }
        
        // Create toast element
        const toastId = 'toast-' + Date.now();
        const toastHtml = `
            <div id="${toastId}" class="toast align-items-center text-white bg-${type} border-0" role="alert">
                <div class="d-flex">
                    <div class="toast-body">
                        ${message}
                    </div>
                    <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
                </div>
            </div>
        `;
        
        toastContainer.insertAdjacentHTML('beforeend', toastHtml);
        
        const toastElement = document.getElementById(toastId);
        const toast = new bootstrap.Toast(toastElement, { autohide: true, delay: 3000 });
        toast.show();
        
        // Remove from DOM after hidden
        toastElement.addEventListener('hidden.bs.toast', () => {
            toastElement.remove();
        });
    }

    // =============================================================================
    // Leaderboard & Stats
    // =============================================================================
    
    /**
     * Load and display leaderboard
     */
    async function loadLeaderboard() {
        const data = await apiRequest(getUrl('leaderboard') + '?limit=20');
        
        if (data && Array.isArray(data)) {
            let html = '';
            
            if (data.length === 0) {
                html = '<tr><td colspan="5" class="text-center">No scores yet!</td></tr>';
            } else {
                data.forEach(entry => {
                    const time = formatTime(entry.time_taken);
                    html += `
                        <tr>
                            <td><strong>${entry.rank}</strong></td>
                            <td>${entry.player_name}</td>
                            <td>${entry.final_score}</td>
                            <td>${entry.level_reached}</td>
                            <td>${time}</td>
                        </tr>
                    `;
                });
            }
            
            elements.leaderboardBody.innerHTML = html;
            
            // Show modal
            const modal = new bootstrap.Modal(elements.leaderboardModal);
            modal.show();
        }
    }

    /**
     * Load and display player stats
     */
    async function loadStats() {
        const data = await apiRequest(getUrl('stats'));
        
        if (data && data.player) {
            const player = data.player;
            const bestScore = data.best_score;
            
            let html = `
                <div class="mb-4">
                    <h6 class="text-muted">Player Info</h6>
                    <p class="mb-1"><strong>Username:</strong> ${player.username}</p>
                    <p class="mb-1"><strong>High Score:</strong> ${player.high_score}</p>
                    <p class="mb-1"><strong>Games Played:</strong> ${player.total_games_played}</p>
                    <p class="mb-0"><strong>Levels Won:</strong> ${player.total_games_won}</p>
                </div>
            `;
            
            if (bestScore) {
                html += `
                    <div class="mb-4">
                        <h6 class="text-muted">Best Run</h6>
                        <p class="mb-1"><strong>Score:</strong> ${bestScore.final_score}</p>
                        <p class="mb-1"><strong>Level Reached:</strong> ${bestScore.level_reached}</p>
                        <p class="mb-0"><strong>Time:</strong> ${formatTime(bestScore.time_taken)}</p>
                    </div>
                `;
            }
            
            if (data.recent_scores && data.recent_scores.length > 0) {
                html += `
                    <div>
                        <h6 class="text-muted">Recent Runs</h6>
                        <ul class="list-unstyled">
                `;
                data.recent_scores.forEach(score => {
                    html += `<li>Level ${score.level_reached} - ${score.final_score} pts</li>`;
                });
                html += '</ul></div>';
            }
            
            elements.statsBody.innerHTML = html;
            
            // Show modal
            const modal = new bootstrap.Modal(elements.statsModal);
            modal.show();
        }
    }

    // =============================================================================
    // Loading State
    // =============================================================================
    
    /**
     * Show/hide loading spinner
     * @param {boolean} show - Whether to show loading
     */
    function showLoading(show) {
        if (show) {
            elements.loading.classList.remove('d-none');
            elements.grid.classList.add('d-none');
        } else {
            elements.loading.classList.add('d-none');
        }
    }

    // =============================================================================
    // Public API
    // =============================================================================
    
    return {
        init: init,
        initGame: initGame,
        advanceToNextLevel: advanceToNextLevel,
        toggleClueMode: toggleClueMode
    };

})();
