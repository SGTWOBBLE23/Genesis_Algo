/**
 * GENESIS Trading Platform - Dashboard functionality
 */

// Global variables
let activeTrades = [];
let priceData = {};

// Initialize Dashboard when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Load active trades (functions available but not displayed in UI)
    loadActiveTrades();
    
    // Load current signals
    loadCurrentSignals();
    
    // Connect to WebSocket for real-time updates
    connectWebSocket();
    
    // Set up interval updates
    setInterval(updateTradePnL, 5000); // Update P&L every 5 seconds
    setInterval(loadCurrentSignals, 60000); // Update signals every minute
});

// Chart-related functions have been removed as they are no longer needed
// for this version of the dashboard

/**
 * Load active trades from the API
 */
function loadActiveTrades() {
    fetch('/api/trades?status=OPEN')
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json();
        })
        .then(data => {
            activeTrades = data.data;
            updateTradesTable();
        })
        .catch(error => {
            console.error('Error fetching active trades:', error);
        });
}

/**
 * Update the active trades table in the UI
 * This function has been modified to not display trades as requested
 */
function updateTradesTable() {
    // Trade section UI has been removed as requested
    // We just log that trades data is being processed but not displayed
    console.log('Trade data processed but UI display removed as requested');
    return;
    
    /* Original implementation hidden to prevent trades display */
}

/**
 * Update P&L for active trades based on current prices
 */
function updateTradePnL() {
    if (activeTrades.length === 0 || Object.keys(priceData).length === 0) {
        return; // No trades or no price data
    }
    
    // Update P&L for each trade based on current prices
    activeTrades.forEach(trade => {
        const symbolPrice = priceData[trade.symbol];
        if (!symbolPrice) return;
        
        // Calculate P&L (simplified)
        let currentPrice;
        if (trade.side === 'BUY') {
            currentPrice = symbolPrice.bid; // Sell at bid for long positions
            trade.pnl = (currentPrice - trade.entry) * trade.lot * 100000; // Example calculation
        } else {
            currentPrice = symbolPrice.ask; // Buy at ask for short positions
            trade.pnl = (trade.entry - currentPrice) * trade.lot * 100000; // Example calculation
        }
    });
    
    // Update table with new P&L
    updateTradesTable();
}

/**
 * Close a trade by ID
 * @param {number} tradeId - The trade ID to close
 */
function closeTrade(tradeId) {
    if (!confirm('Are you sure you want to close this trade?')) {
        return;
    }
    
    fetch(`/api/trade/${tradeId}/close`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        }
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Network response was not ok');
        }
        return response.json();
    })
    .then(data => {
        // Remove trade from active trades
        activeTrades = activeTrades.filter(trade => trade.id !== tradeId);
        updateTradesTable();
        
        // Show success message
        showAlert('Trade closed successfully', 'success');
    })
    .catch(error => {
        console.error('Error closing trade:', error);
        showAlert('Failed to close trade: ' + error.message, 'danger');
    });
}

/**
 * Show an alert message
 * @param {string} message - Alert message
 * @param {string} type - Alert type (success, danger, warning, info)
 */
function showAlert(message, type = 'info') {
    const alertsContainer = document.getElementById('alerts-container');
    
    // Check if alerts container exists
    if (!alertsContainer) {
        console.log(`Alert message (${type}): ${message}`);
        return;
    }
    
    const alert = document.createElement('div');
    alert.className = `alert alert-${type} alert-dismissible fade show`;
    alert.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;
    
    alertsContainer.appendChild(alert);
    
    // Auto-dismiss after 5 seconds
    setTimeout(() => {
        alert.classList.remove('show');
        setTimeout(() => alert.remove(), 150);
    }, 5000);
}



/**
 * Load current signals from the API
 */
function loadCurrentSignals() {
    fetch('/api/signals/current')
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json();
        })
        .then(signals => {
            updateSignalsTable(signals);
        })
        .catch(error => {
            console.error('Error fetching signals:', error);
        });
}

/**
 * Update the signals display in the UI with a rectangular box layout
 * @param {Array} signals - List of signal objects
 */
function updateSignalsTable(signals) {
    // Try to find the signals container
    let container = document.getElementById('signals-container');
    
    // If not found, check if we have a signals list in other containers
    if (!container) {
        console.log('Primary signals container not found, checking alternatives...');
        // Try to find any container with signals-list class
        const signalsList = document.querySelector('.signals-list');
        if (signalsList) {
            container = signalsList;
            console.log('Using alternative signals container');
        } else {
            console.error('No signals container found. Unable to display signals.');
            return;
        }
    }
    
    // Clear existing content
    container.innerHTML = '';
    
    // Create header
    const header = document.createElement('div');
    header.className = 'signals-list-header';
    header.innerHTML = `
        <h5 class="m-0">Latest Signals</h5>
        <a href="/signals" class="text-white">View All</a>
    `;
    container.appendChild(header);
    
    // Create signals container
    const signalsContainer = document.createElement('div');
    signalsContainer.className = 'signals-container';
    container.appendChild(signalsContainer);
    
    if (signals.length === 0) {
        // Show no signals message
        const emptyMessage = document.createElement('div');
        emptyMessage.className = 'p-3 text-center w-100';
        emptyMessage.textContent = 'No active signals';
        signalsContainer.appendChild(emptyMessage);
        return;
    }
    
    // Sort signals by created_at in descending order (newest first)
    signals.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
    
    // Add signals as rectangular boxes
    signals.forEach(signal => {
        // Format action badge class
        let actionClass = '';
        switch (signal.action) {
            case 'BUY_NOW':
                actionClass = 'action-buy-now';
                break;
            case 'SELL_NOW':
                actionClass = 'action-sell-now';
                break;
            case 'ANTICIPATED_LONG':
                actionClass = 'action-anticipated-long';
                break;
            case 'ANTICIPATED_SHORT':
                actionClass = 'action-anticipated-short';
                break;
        }
        
        // Format date
        const date = new Date(signal.created_at);
        const dateStr = `${date.getMonth()+1}/${date.getDate()}/${date.getFullYear()}, ${date.getHours()}:${date.getMinutes().toString().padStart(2, '0')} ${date.getHours() >= 12 ? 'PM' : 'AM'}`;
        
        // Format confidence class
        const confidenceClass = signal.confidence > 0.8 ? 'confidence-high' : 
                              signal.confidence > 0.6 ? 'confidence-medium' : 'confidence-low';
        
        // Create signal card
        const card = document.createElement('div');
        card.className = 'signal-card';
        card.setAttribute('data-action', signal.action);
        
        card.innerHTML = `
            <div class="signal-header">
                <div class="signal-symbol">${signal.symbol.replace('_', '')}</div>
                <span class="action-badge ${actionClass}">${signal.action.replace('_', ' ')}</span>
                ${signal.status === 'ERROR' ? '<span class="status-badge status-error">ERROR</span>' : ''}
            </div>
            
            <div class="signal-details-grid">
                <div class="signal-detail-item">
                    <div class="signal-detail-label">Entry</div>
                    <div class="signal-detail-value">${signal.entry || '--'}</div>
                </div>
                <div class="signal-detail-item">
                    <div class="signal-detail-label">Stop Loss</div>
                    <div class="signal-detail-value">${signal.sl || '--'}</div>
                </div>
                <div class="signal-detail-item">
                    <div class="signal-detail-label">Take Profit</div>
                    <div class="signal-detail-value">${signal.tp || '--'}</div>
                </div>
            </div>
            
            <div class="signal-detail-item" style="margin-bottom: 8px;">
                <div class="signal-detail-label">Confidence</div>
                <div class="signal-detail-value ${confidenceClass}">${Math.round(signal.confidence * 100)}%</div>
            </div>
            
            <div class="signal-footer">
                <div class="signal-timestamp">${dateStr}</div>
                <div class="signal-actions">
                    <button class="signal-execute-button" onclick="executeSignal(${signal.id});">Execute</button>
                    <button class="signal-chart-button" onclick="viewSignalChart(${signal.id});">View Chart</button>
                </div>
            </div>
        `;
        
        signalsContainer.appendChild(card);
    });
}

/**
 * View chart for a specific signal
 * @param {number} signalId - The signal ID
 */
function viewSignalChart(signalId) {
    // Open signal chart in a modal or new window
    window.open(`/mt5/signal_chart/${signalId}`, '_blank');
    console.log(`Viewing chart for signal ${signalId}`);
}

/**
 * Execute a signal, sending it to MT5 for trade execution
 * @param {number} signalId - The signal ID to execute
 */
function executeSignal(signalId) {
    // Show confirmation dialog
    if (!confirm('Are you sure you want to execute this signal? This will send the trade to your connected MT5 terminal for execution.')) {
        return;
    }
    
    // Find the button
    const button = document.querySelector(`button[onclick="executeSignal(${signalId});"]`);
    let originalText = 'Execute';
    
    // Update button if found
    if (button) {
        try {
            originalText = button.textContent;
            button.textContent = 'Sending...';
            button.disabled = true;
            button.style.opacity = '0.7';
        } catch (e) {
            console.error('Error updating button:', e);
        }
    }
    
    // Send request to execute the signal
    fetch(`/api/signals/${signalId}/execute`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        }
    })
    .then(response => response.json())
    .then(data => {
        // Reset button if found
        if (button) {
            try {
                button.disabled = false;
                button.style.opacity = '1';
            } catch (e) {
                console.error('Error resetting button:', e);
            }
        }
        
        if (data.status === 'success') {
            // Show success message
            showAlert(`Signal ${signalId} executed successfully. Trade sent to MT5.`, 'success');
            
            // Update button if found
            if (button) {
                try {
                    button.textContent = 'Executed ✓';
                    button.classList.remove('signal-execute-button');
                    button.classList.add('signal-executed-button');
                    button.disabled = true;
                } catch (e) {
                    console.error('Error updating button after success:', e);
                }
            }
            
            // Reload trades after a short delay
            setTimeout(loadActiveTrades, 2000);
            
            // Reload signals to reflect the updated status
            setTimeout(loadCurrentSignals, 1000);
        } else {
            // Show error message
            showAlert(`Error executing signal: ${data.message}`, 'danger');
            
            // Update button if found
            if (button) {
                try {
                    button.textContent = originalText;
                } catch (e) {
                    console.error('Error restoring button text:', e);
                }
            }
        }
    })
    .catch(error => {
        // Show error message
        showAlert(`Error executing signal: ${error.message}`, 'danger');
        
        // Update button if found
        if (button) {
            try {
                button.textContent = originalText;
                button.disabled = false;
                button.style.opacity = '1';
            } catch (e) {
                console.error('Error resetting button after error:', e);
            }
        }
    });
}



function connectWebSocket() {
    try {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/api/signals/ws`;
        
        const socket = new WebSocket(wsUrl);
        
        socket.onopen = function(e) {
            console.log('WebSocket connection established');
        };
        
        socket.onmessage = function(event) {
            try {
                const data = JSON.parse(event.data);
                
                if (data.type === 'price_update') {
                    try {
                        // Update price data - only storing in memory for P&L calculations
                        // No UI elements are updated since chart elements have been removed
                        const symbol = data.data.symbol;
                        priceData[symbol] = {
                            bid: data.data.bid,
                            ask: data.data.ask,
                            timestamp: data.data.timestamp
                        };
                        
                        // No need to update UI elements since they don't exist in current layout
                        // This prevents JavaScript errors trying to access non-existent DOM elements
                    } catch (e) {
                        console.error('Error processing price update:', e);
                    }
                    
                } else if (data.type === 'new_signal') {
                    // Reload all signals
                    loadCurrentSignals();
                    
                    // Show alert
                    showAlert(`New signal for ${data.data.symbol}: ${data.data.action}`, 'info');
                    
                } else if (data.type === 'new_trade') {
                    // Add new trade
                    loadActiveTrades(); // Reload all trades
                    
                    // Show alert
                    showAlert(`New trade opened: ${data.data.symbol} ${data.data.side}`, 'success');
                }
            } catch (e) {
                console.error('Error processing WebSocket message:', e);
            }
        };
        
        socket.onclose = function(event) {
            if (event.wasClean) {
                console.log(`WebSocket connection closed cleanly, code=${event.code}, reason=${event.reason}`);
            } else {
                console.log('WebSocket connection died');
            }
            
            // Try to reconnect after 5 seconds
            setTimeout(connectWebSocket, 5000);
        };
        
        socket.onerror = function(error) {
            console.error(`WebSocket error:`, error);
        };
    } catch (e) {
        console.error('Error setting up WebSocket connection:', e);
        // Try to reconnect after 10 seconds if there was an error during setup
        setTimeout(connectWebSocket, 10000);
    }
}
