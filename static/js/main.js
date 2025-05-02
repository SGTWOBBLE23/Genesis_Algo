/**
 * GENESIS Trading Platform
 * Main JavaScript file for the dashboard
 */

// Global variables
let signalsData = [];
let tradesData = [];
let accountData = {};
let connectionStatus = {};

// Document ready function
document.addEventListener('DOMContentLoaded', function() {
    // Initialize the dashboard
    initializeDashboard();
    
    // Refresh data every 60 seconds
    setInterval(refreshData, 60000);
});

/**
 * Initialize the dashboard
 */
function initializeDashboard() {
    // Fetch initial data
    fetchCurrentSignals();
    fetchOpenTrades();
    fetchAccountInfo();
    checkConnectionStatus();
}

/**
 * Refresh all data
 */
function refreshData() {
    fetchCurrentSignals();
    fetchOpenTrades();
    fetchAccountInfo();
    // Only check connection status every 5 minutes
    if (Math.random() < 0.2) {
        checkConnectionStatus();
    }
}

/**
 * Fetch current trading signals
 */
function fetchCurrentSignals() {
    // Simulated fetch for development
    // In production, replace with actual API call
    setTimeout(() => {
        // Sample data for development
        signalsData = [
            {
                id: 1,
                symbol: 'EURUSD',
                action: 'BUY_NOW',
                entry: 1.0750,
                sl: 1.0720,
                tp: 1.0800,
                confidence: 0.85,
                status: 'ACTIVE',
                created_at: '2023-07-22T14:30:00Z'
            },
            {
                id: 2,
                symbol: 'GBPUSD',
                action: 'ANTICIPATED_SHORT',
                entry: 1.2650,
                sl: 1.2700,
                tp: 1.2550,
                confidence: 0.75,
                status: 'PENDING',
                created_at: '2023-07-22T15:15:00Z'
            }
        ];
        updateSignalsDisplay();
    }, 300);
}

/**
 * Fetch open trades
 */
function fetchOpenTrades() {
    // Simulated fetch for development
    // In production, replace with actual API call
    setTimeout(() => {
        // Sample data for development
        tradesData = [
            {
                id: 1,
                symbol: 'EURUSD',
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
    }, 500);
}

/**
 * Fetch account information
 */
function fetchAccountInfo() {
    // Simulated fetch for development
    // In production, replace with actual API call
    setTimeout(() => {
        // Sample data for development
        accountData = {
            balance: 10256.75,
            open_positions: 1,
            daily_pnl: 25.5
        };
        updateAccountDisplay();
    }, 400);
}

/**
 * Check connection status of integrated services
 */
function checkConnectionStatus() {
    // Simulated check for development
    // In production, replace with actual API call
    setTimeout(() => {
        // Sample data for development
        connectionStatus = {
            mt5: true,
            oanda: true,
            vision: true,
            telegram: true
        };
        updateStatusDisplay();
    }, 600);
}

/**
 * Update signals display
 */
function updateSignalsDisplay() {
    const container = document.getElementById('signals-container');
    if (!container) return;
    
    if (signalsData.length === 0) {
        container.innerHTML = '<p>No active signals.</p>';
        return;
    }
    
    let html = '<div class="table-responsive"><table class="table table-hover"><thead><tr>';
    html += '<th>Symbol</th><th>Action</th><th>Entry</th><th>SL</th><th>TP</th><th>Confidence</th><th>Status</th><th>Actions</th>';
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
        html += `<td>`;
        if (signal.status === 'PENDING' || signal.status === 'ACTIVE') {
            html += `<button class="btn btn-sm btn-primary me-1" onclick="executeTrade(${signal.id})">Execute</button>`;
            html += `<button class="btn btn-sm btn-danger" onclick="cancelSignal(${signal.id})">Cancel</button>`;
        } else {
            html += `<span class="text-muted">No actions</span>`;
        }
        html += `</td>`;
        html += '</tr>';
    });
    
    html += '</tbody></table></div>';
    container.innerHTML = html;
}

/**
 * Update trades display
 */
function updateTradesDisplay() {
    const container = document.getElementById('trades-container');
    if (!container) return;
    
    if (tradesData.length === 0) {
        container.innerHTML = '<p>No open trades.</p>';
        return;
    }
    
    let html = '<div class="table-responsive"><table class="table table-hover"><thead><tr>';
    html += '<th>Symbol</th><th>Side</th><th>Lot</th><th>Entry</th><th>SL</th><th>TP</th><th>P&L</th><th>Status</th><th>Actions</th>';
    html += '</tr></thead><tbody>';
    
    tradesData.forEach(trade => {
        const pnlClass = trade.pnl > 0 ? 'text-success' : (trade.pnl < 0 ? 'text-danger' : '');
        
        html += `<tr data-id="${trade.id}">`;
        html += `<td>${trade.symbol}</td>`;
        html += `<td>${trade.side}</td>`;
        html += `<td>${trade.lot}</td>`;
        html += `<td>${trade.entry}</td>`;
        html += `<td>${trade.sl || '-'}</td>`;
        html += `<td>${trade.tp || '-'}</td>`;
        html += `<td class="${pnlClass}">${trade.pnl > 0 ? '+' : ''}${trade.pnl}</td>`;
        html += `<td><span class="badge bg-${trade.status === 'OPEN' ? 'success' : 'secondary'}">${trade.status}</span></td>`;
        html += `<td>`;
        if (trade.status === 'OPEN') {
            html += `<button class="btn btn-sm btn-warning" onclick="closeTrade(${trade.id})">Close</button>`;
        } else {
            html += `<span class="text-muted">No actions</span>`;
        }
        html += `</td>`;
        html += '</tr>';
    });
    
    html += '</tbody></table></div>';
    container.innerHTML = html;
}

/**
 * Update account information display
 */
function updateAccountDisplay() {
    const container = document.getElementById('account-info');
    if (!container) return;
    
    const pnlClass = accountData.daily_pnl > 0 ? 'text-success' : (accountData.daily_pnl < 0 ? 'text-danger' : '');
    
    let html = `<p>Balance: $${accountData.balance.toFixed(2)}</p>`;
    html += `<p>Open Positions: ${accountData.open_positions}</p>`;
    html += `<p>P&L Today: <span class="${pnlClass}">${accountData.daily_pnl > 0 ? '+' : ''}$${accountData.daily_pnl.toFixed(2)}</span></p>`;
    
    container.innerHTML = html;
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