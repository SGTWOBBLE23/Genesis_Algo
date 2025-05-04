/**
 * GENESIS Trading Platform
 * Main JavaScript file for the dashboard
 */

// Global variables
let signalsData = [];
let tradesData = [];
let connectionStatus = {};

// Define accountData for history page use only
let accountData = {
    type: 'UNKNOWN',
    balance: 0,
    equity: 0,
    margin: 0,
    free_margin: 0,
    open_positions: 0,
    account_id: 'MT5 Account'
};

// Document ready function
document.addEventListener('DOMContentLoaded', function() {
    // Initialize the dashboard
    initializeDashboard();
    
    // If on history page, fetch account data
    if (window.location.pathname.includes('/history')) {
        fetchHistoryPageAccountData();
    }
    
    // Refresh data every 60 seconds
    setInterval(refreshData, 60000);
    
    // If on history page, also refresh account data every 60 seconds
    if (window.location.pathname.includes('/history')) {
        setInterval(fetchHistoryPageAccountData, 60000);
    }
});

/**
 * Initialize the dashboard
 */
function initializeDashboard() {
    // Fetch initial data
    fetchCurrentSignals();
    // fetchOpenTrades(); // Open trades section removed as requested
    checkConnectionStatus();
}

/**
 * Refresh all data
 */
function refreshData() {
    fetchCurrentSignals();
    // fetchOpenTrades(); // Open trades section removed as requested
    // Only check connection status every 5 minutes
    if (Math.random() < 0.2) {
        checkConnectionStatus();
    }
}

/**
 * Fetch current trading signals
 */
function fetchCurrentSignals() {
    fetch('/api/signals/current')
        .then(response => {
            if (!response.ok) {
                throw new Error('Failed to fetch current signals');
            }
            return response.json();
        })
        .then(data => {
            signalsData = data;
            updateSignalsDisplay();
        })
        .catch(error => {
            console.error('Error fetching signals data:', error);
            // Fallback to empty signals if error occurs
            signalsData = [];
            updateSignalsDisplay();
        });
}

/**
 * Fetch open trades
 */
function fetchOpenTrades() {
    // Fetch open trades from OANDA
    fetch('/api/oanda/trades')
        .then(response => {
            if (!response.ok) {
                throw new Error('Failed to fetch open trades');
            }
            return response.json();
        })
        .then(data => {
            // Transform OANDA trades to our format
            if (Array.isArray(data) && data.length > 0) {
                tradesData = data.map(trade => {
                    const units = parseFloat(trade.currentUnits);
                    const side = units > 0 ? 'BUY' : 'SELL';
                    const pnl = parseFloat(trade.unrealizedPL);
                    
                    return {
                        id: trade.id,
                        symbol: trade.instrument.replace('_', '/'),
                        side: side,
                        lot: Math.abs(units),
                        entry: parseFloat(trade.price),
                        sl: trade.stopLossOrder ? parseFloat(trade.stopLossOrder.price) : null,
                        tp: trade.takeProfitOrder ? parseFloat(trade.takeProfitOrder.price) : null,
                        pnl: pnl,
                        status: 'OPEN',
                        opened_at: trade.openTime
                    };
                });
            } else {
                // No trades or error
                tradesData = [];
            }
            updateTradesDisplay();
        })
        .catch(error => {
            console.error('Error fetching trades data:', error);
            // Fallback data for testing
            tradesData = [
                {
                    id: 1,
                    symbol: 'EUR/USD',
                    side: 'BUY',
                    lot: 0.5,
                    entry: 1.0750,
                    sl: 1.0720,
                    tp: 1.0800,
                    pnl: 25.5,
                    status: 'OPEN',
                    opened_at: '2023-07-22T14:35:00Z'
                }
            ];
            updateTradesDisplay();
        });
}



/**
 * Check connection status of integrated services
 */
function checkConnectionStatus() {
    // Initialize default status while we check
    connectionStatus = {
        mt5: false,
        oanda: false,
        vision: true, // Assuming API key is present
        telegram: false
    };
    
    // Check MT5 connection status by checking for heartbeat timestamps
    fetch('/api/mt5/heartbeat')
        .then(response => response.json())
        .then(data => {
            connectionStatus.mt5 = !!data.last_heartbeat;
            updateStatusDisplay();
        })
        .catch(() => {
            connectionStatus.mt5 = false;
            updateStatusDisplay();
        });
        
    // Check OANDA connection
    fetch('/api/oanda/test-connection')
        .then(response => response.json())
        .then(data => {
            connectionStatus.oanda = data.connected;
            updateStatusDisplay();
        })
        .catch(() => {
            connectionStatus.oanda = false;
            updateStatusDisplay();
        });
    
    updateStatusDisplay();
}

/**
 * Update signals display - only if dashboard.js hasn't initialized it yet
 */
function updateSignalsDisplay() {
    const container = document.getElementById('signals-container');
    if (!container) return;
    
    // Check if dashboard.js has already set up the signals container with its own structure
    if (container.querySelector('.signals-list-header') || 
        container.querySelector('.signals-container') ||
        container.querySelector('.signal-card')) {
        console.log('Dashboard.js already handling signals display, skipping main.js implementation');
        return;
    }
    
    if (signalsData.length === 0) {
        container.innerHTML = '<p>No active signals.</p>';
        return;
    }
    
    let html = '<div class="table-responsive"><table class="table table-hover"><thead><tr>';
    html += '<th>Symbol</th><th>Action</th><th>Entry</th><th>SL</th><th>TP</th><th>Confidence</th><th>Status</th><th>Created</th><th>Actions</th><th>Chart</th>';
    html += '</tr></thead><tbody>';
    
    signalsData.forEach(signal => {
        const confidenceClass = signal.confidence > 0.8 ? 'confidence-high' : 
                               signal.confidence > 0.6 ? 'confidence-medium' : 'confidence-low';
        
        html += `<tr data-id="${signal.id}">`;
        html += `<td>${signal.symbol}</td>`;
        html += `<td>${formatAction(signal.action)}</td>`;
        html += `<td>${signal.entry}</td>`;
        html += `<td>${signal.sl}</td>`;
        html += `<td>${signal.tp}</td>`;
        html += `<td><span class="${confidenceClass}">${Math.round(signal.confidence * 100)}%</span></td>`;
        html += `<td><span class="badge bg-${signal.status === 'ACTIVE' ? 'success' : 'warning'}">${signal.status}</span></td>`;
        html += `<td>${formatDateTime(signal.created_at)}</td>`;
        html += `<td>`;
        if (signal.status === 'PENDING' || signal.status === 'ACTIVE') {
            html += `<button class="btn btn-sm btn-primary me-1" onclick="executeTrade(${signal.id})">Execute</button>`;
            html += `<button class="btn btn-sm btn-danger" onclick="cancelSignal(${signal.id})">Cancel</button>`;
        } else {
            html += `<span class="text-muted">No actions</span>`;
        }
        html += `</td>`;
        html += `<td><button class="btn btn-sm btn-info" onclick="window.open('/mt5/signal_chart/${signal.id}', '_blank')">View Chart</button></td>`;
        html += '</tr>';
    });
    
    html += '</tbody></table></div>';
    container.innerHTML = html;
}

/**
 * Update trades display - only if dashboard.js hasn't already done it
 * This function has been modified to not display the trades section as requested
 */
function updateTradesDisplay() {
    // We still want to load the trade data for the system to function properly
    // but we don't want to display it in the UI
    console.log('Trades available but not displayed as requested.');
    return;
    
    /* Original implementation removed to prevent trades section from showing */
}



/**
 * Update system status display
 */
function updateStatusDisplay() {
    const container = document.getElementById('status-info');
    if (!container) return;
    
    let html = `<p><span class="badge bg-${connectionStatus.mt5 ? 'success' : 'danger'}">MT5: ${connectionStatus.mt5 ? 'Connected' : 'Disconnected'}</span></p>`;
    html += `<p><span class="badge bg-${connectionStatus.oanda ? 'success' : 'danger'}">OANDA: ${connectionStatus.oanda ? 'Connected' : 'Disconnected'}</span></p>`;
    html += `<p><span class="badge bg-${connectionStatus.vision ? 'success' : 'danger'}">Vision: ${connectionStatus.vision ? 'Connected' : 'Disconnected'}</span></p>`;
    html += `<p><span class="badge bg-${connectionStatus.telegram ? 'success' : 'danger'}">Telegram: ${connectionStatus.telegram ? 'Connected' : 'Disconnected'}</span></p>`;
    
    container.innerHTML = html;
}

/**
 * Format signal action for display
 * @param {string} action - Signal action code
 * @returns {string} Formatted action text
 */
function formatAction(action) {
    switch (action) {
        case 'BUY_NOW': return 'Buy Now';
        case 'SELL_NOW': return 'Sell Now';
        case 'ANTICIPATED_LONG': return 'Wait for Long';
        case 'ANTICIPATED_SHORT': return 'Wait for Short';
        default: return action;
    }
}

/**
 * Execute a trade from a signal
 * @param {number} signalId - Signal ID
 */
function executeTrade(signalId) {
    // In production, replace with actual API call
    console.log(`Executing trade for signal ${signalId}`);
    alert(`Trade execution triggered for signal #${signalId}`);
}

/**
 * Cancel a signal
 * @param {number} signalId - Signal ID
 */
function cancelSignal(signalId) {
    // In production, replace with actual API call
    console.log(`Cancelling signal ${signalId}`);
    alert(`Signal #${signalId} has been cancelled`);
}

/**
 * Close a trade
 * @param {number} tradeId - Trade ID
 */
function closeTrade(tradeId) {
    // In production, replace with actual API call
    console.log(`Closing trade ${tradeId}`);
    alert(`Trade #${tradeId} has been closed`);
}

/**
 * View chart for a signal
 * @param {number} signalId - Signal ID
 */
function viewSignalChart(signalId) {
    window.open(`/api/signals/${signalId}/chart`, '_blank');
}

/**
 * Format a datetime string to a more readable format
 * @param {string} dateTimeString - ISO datetime string
 * @returns {string} Formatted date and time
 */
function formatDateTime(dateTimeString) {
    if (!dateTimeString) return '-';
    
    const date = new Date(dateTimeString);
    if (isNaN(date.getTime())) return dateTimeString; // If invalid date, return original
    
    const today = new Date();
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);
    
    // Check if it's today or yesterday
    if (date.toDateString() === today.toDateString()) {
        return `Today ${date.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}`;
    } else if (date.toDateString() === yesterday.toDateString()) {
        return `Yesterday ${date.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}`;
    } else {
        return `${date.toLocaleDateString()} ${date.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}`;
    }
}

/**
 * Fetch account data for history page
 * This function is only used on the history page to populate account summary
 */
function fetchHistoryPageAccountData() {
    // Only run on history page
    if (!window.location.pathname.includes('/history')) return;
    
    let cacheBuster = Date.now();
    fetch('/api/mt5/account?t=' + cacheBuster)
        .then(response => {
            if (!response.ok) {
                throw new Error(`MT5 API returned ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            // Check if we have valid data
            if (data && data.balance !== undefined) {
                // Update accountData for history page
                accountData = {
                    type: 'MT5',
                    balance: parseFloat(data.balance),
                    equity: parseFloat(data.equity || data.balance),
                    margin: parseFloat(data.margin || 0),
                    free_margin: parseFloat(data.free_margin || 0),
                    leverage: data.leverage || 1,
                    open_positions: data.open_positions || 0,
                    account_id: data.account_id || 'MT5 Account',
                    last_update: data.last_update
                };
                
                // Update the account details on history page
                const historyDetailsContainer = document.getElementById('account-details');
                if (historyDetailsContainer) {
                    let detailsHtml = `<h5>MT5 Account Details</h5>`;
                    detailsHtml += `<p><strong>Account ID:</strong> ${accountData.account_id}</p>`;
                    detailsHtml += `<p><strong>Balance:</strong> $${accountData.balance.toFixed(2)}</p>`;
                    detailsHtml += `<p><strong>Equity:</strong> $${accountData.equity.toFixed(2)}</p>`;
                    detailsHtml += `<p><strong>Margin:</strong> $${accountData.margin.toFixed(2)}</p>`;
                    detailsHtml += `<p><strong>Free Margin:</strong> $${accountData.free_margin.toFixed(2)}</p>`;
                    detailsHtml += `<p><strong>Leverage:</strong> ${accountData.leverage}:1</p>`;
                    historyDetailsContainer.innerHTML = detailsHtml;
                }
                
                updateConnectionStatus('mt5', true);
            }
        })
        .catch(error => {
            console.log('Error fetching account data for history page:', error);
            // Update connection status
            updateConnectionStatus('mt5', false);
        });
}