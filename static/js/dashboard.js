/**
 * GENESIS Trading Platform - Dashboard functionality
 * Simplified version without card layouts
 */

// Global variables
let activeTrades = [];
let priceData = {};

// Initialize Dashboard when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Load current signals
    loadCurrentSignals();
    
    // Connect to WebSocket for real-time updates
    connectWebSocket();
    
    // Set up interval updates
    setInterval(loadCurrentSignals, 60000); // Update signals every minute
});

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
            console.log('Trade data processed');
        })
        .catch(error => {
            console.error('Error fetching active trades:', error);
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
 * Update the signals display in the UI with a simple table layout
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
    header.className = 'mb-3';
    header.innerHTML = '<h5>Latest Trading Signals</h5>';
    container.appendChild(header);
    
    if (signals.length === 0) {
        // Show no signals message
        const emptyMessage = document.createElement('div');
        emptyMessage.className = 'alert alert-info';
        emptyMessage.textContent = 'No active signals';
        container.appendChild(emptyMessage);
        return;
    }
    
    // Sort signals by created_at in descending order (newest first)
    signals.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
    
    // Create a simple table for signals
    const table = document.createElement('table');
    table.className = 'table table-striped table-dark';
    
    // Create table header
    const thead = document.createElement('thead');
    thead.innerHTML = `
        <tr>
            <th>Symbol</th>
            <th>Action</th>
            <th>Entry</th>
            <th>SL</th>
            <th>TP</th>
            <th>Confidence</th>
            <th>Status</th>
            <th>Created</th>
            <th>Actions</th>
        </tr>
    `;
    table.appendChild(thead);
    
    // Create table body
    const tbody = document.createElement('tbody');
    
    // Add signals as table rows
    signals.forEach(signal => {
        const date = new Date(signal.created_at);
        const dateStr = `${date.getMonth()+1}/${date.getDate()}/${date.getFullYear()} ${date.getHours()}:${date.getMinutes().toString().padStart(2, '0')}`;
        
        const tr = document.createElement('tr');
        
        // Set classes for BUY/SELL styling
        if (signal.action === 'BUY_NOW' || signal.action === 'ANTICIPATED_LONG') {
            tr.classList.add('buy-signal');
        } else if (signal.action === 'SELL_NOW' || signal.action === 'ANTICIPATED_SHORT') {
            tr.classList.add('sell-signal');
        }
        
        // Add status class if there's an error
        if (signal.status === 'ERROR') {
            tr.classList.add('error-signal');
        }
        
        tr.innerHTML = `
            <td>${signal.symbol.replace('_', '')}</td>
            <td>${signal.action.replace('_', ' ')}</td>
            <td>${signal.entry || '--'}</td>
            <td>${signal.sl || '--'}</td>
            <td>${signal.tp || '--'}</td>
            <td>${Math.round(signal.confidence * 100)}%</td>
            <td>${signal.status}</td>
            <td>${dateStr}</td>
            <td>
                <button class="btn btn-sm btn-primary" onclick="executeSignal(${signal.id});">Execute</button>
                <button class="btn btn-sm btn-info" onclick="viewSignalChart(${signal.id});">Chart</button>
            </td>
        `;
        
        tbody.appendChild(tr);
    });
    
    table.appendChild(tbody);
    container.appendChild(table);
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
    
    console.log("Executing trade for signal " + signalId);
    
    // Find the button - look for the button inside the row for this signal
    const button = document.querySelector(`button[onclick="executeSignal(${signalId});"]`);
    let originalText = 'Execute';
    
    // Update button if found
    if (button) {
        try {
            originalText = button.textContent;
            button.textContent = 'Sending...';
            button.disabled = true;
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
        if (data.status === 'success') {
            // Show success message
            showAlert(`Signal ${signalId} executed successfully. Trade sent to MT5.`, 'success');
            
            // Update button if found
            if (button) {
                try {
                    button.textContent = 'Executed ✓';
                    button.className = 'btn btn-sm btn-success';
                    button.disabled = true;
                } catch (e) {
                    console.error('Error updating button after success:', e);
                }
            }
            
            // Reload signals to reflect the updated status
            setTimeout(loadCurrentSignals, 1000);
        } else {
            // Show error message
            showAlert(`Error executing signal: ${data.message}`, 'danger');
            
            // Update button if found
            if (button) {
                try {
                    button.textContent = originalText;
                    button.disabled = false;
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
                
                if (data.type === 'new_signal') {
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
