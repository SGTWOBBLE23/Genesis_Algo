/**
 * GENESIS Trading Platform - Dashboard functionality
 */

// Global variables
let activeCharts = {};
let activeTrades = [];
let priceData = {};

// Initialize Dashboard when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Initialize the charts
    initializeCharts();
    
    // Load active trades
    loadActiveTrades();
    
    // Load current signals
    loadCurrentSignals();
    
    // Connect to WebSocket for real-time updates
    connectWebSocket();
    
    // Set up interval updates
    setInterval(updateTradePnL, 5000); // Update P&L every 5 seconds
    setInterval(loadCurrentSignals, 60000); // Update signals every minute
});

/**
 * Initialize price charts for tracked symbols
 */
function initializeCharts() {
    const symbols = ['XAUUSD', 'GBPJPY', 'GBPUSD', 'EURUSD', 'AAPL', 'NAS100', 'BTCUSD'];
    const chartContainer = document.getElementById('charts-container');
    
    // Create chart containers
    symbols.forEach(symbol => {
        // Create card for chart
        const card = document.createElement('div');
        card.className = 'card';
        card.innerHTML = `
            <div class="card-header">
                <h3>${symbol}</h3>
                <div class="price-indicator">
                    <span class="bid">Bid: <strong id="${symbol}-bid">--</strong></span>
                    <span class="ask">Ask: <strong id="${symbol}-ask">--</strong></span>
                </div>
            </div>
            <div class="card-body">
                <canvas id="chart-${symbol}" width="400" height="250"></canvas>
            </div>
            <div class="card-footer" id="signals-${symbol}">
                <div class="spinner-border spinner-border-sm" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
                Waiting for signals...
            </div>
        `;
        
        chartContainer.appendChild(card);
        
        // Initialize chart
        const ctx = document.getElementById(`chart-${symbol}`).getContext('2d');
        
        activeCharts[symbol] = new Chart(ctx, {
            type: 'candlestick',
            data: {
                datasets: [{
                    label: symbol,
                    data: []
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                const candle = context.raw;
                                return [
                                    `Open: ${candle.o}`,
                                    `High: ${candle.h}`,
                                    `Low: ${candle.l}`,
                                    `Close: ${candle.c}`
                                ];
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        display: true,
                        title: {
                            display: true,
                            text: 'Time'
                        }
                    },
                    y: {
                        display: true,
                        title: {
                            display: true,
                            text: 'Price'
                        }
                    }
                }
            }
        });
        
        // Fetch initial chart data
        fetchChartData(symbol);
    });
    
    console.log("Charts initialized");
}

/**
 * Fetch chart data for a symbol
 * @param {string} symbol - The trading symbol
 */
function fetchChartData(symbol) {
    // Adding timestamp to prevent caching
    fetch(`/api/candles/${symbol}?t=${Date.now()}`)
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json();
        })
        .then(data => {
            updateChart(symbol, data);
        })
        .catch(error => {
            console.error('Error fetching chart data:', error);
        });
}

/**
 * Update chart with new candle data
 * @param {string} symbol - The trading symbol
 * @param {Array} candles - Array of candle data objects
 */
function updateChart(symbol, candles) {
    if (!activeCharts[symbol]) {
        console.error(`Chart for ${symbol} not found`);
        return;
    }
    
    // Format data for chart.js
    const chartData = candles.map(candle => ({
        x: new Date(candle.time).getTime(),
        o: candle.open,
        h: candle.high,
        l: candle.low,
        c: candle.close
    }));
    
    // Update chart
    activeCharts[symbol].data.datasets[0].data = chartData;
    activeCharts[symbol].update();
    
    // Update latest prices
    if (chartData.length > 0) {
        const latest = chartData[chartData.length - 1];
        
        // Calculate bid/ask spread for display (simplified)
        const spread = 0.0002 * latest.c; // 2 pips spread (example)
        const bid = (latest.c - spread/2).toFixed(5);
        const ask = (latest.c + spread/2).toFixed(5);
        
        // Store price data
        priceData[symbol] = {
            bid: parseFloat(bid),
            ask: parseFloat(ask),
            timestamp: new Date().toISOString()
        };
        
        // Update UI
        document.getElementById(`${symbol}-bid`).textContent = bid;
        document.getElementById(`${symbol}-ask`).textContent = ask;
    }
}

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
 */
function updateTradesTable() {
    const tableBody = document.getElementById('active-trades-body');
    if (!tableBody) return;
    
    // Clear existing rows
    tableBody.innerHTML = '';
    
    if (activeTrades.length === 0) {
        // Show no trades message
        const row = document.createElement('tr');
        row.innerHTML = '<td colspan="7" class="text-center">No active trades</td>';
        tableBody.appendChild(row);
        return;
    }
    
    // Add trades to table
    activeTrades.forEach(trade => {
        const row = document.createElement('tr');
        
        // Format P&L with color
        const pnlClass = trade.pnl > 0 ? 'positive' : (trade.pnl < 0 ? 'negative' : '');
        
        row.innerHTML = `
            <td>${trade.symbol}</td>
            <td>${trade.side}</td>
            <td>${trade.lot}</td>
            <td>${trade.entry}</td>
            <td>${trade.sl || '--'}</td>
            <td>${trade.tp || '--'}</td>
            <td class="${pnlClass}">${trade.pnl ? trade.pnl.toFixed(2) : '0.00'}</td>
            <td>
                <button class="btn btn-sm btn-danger" onclick="closeTrade(${trade.id})">Close</button>
            </td>
        `;
        
        tableBody.appendChild(row);
    });
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
            // For testing purposes, if there are no signals, add some sample ones
            if (signals.length === 0) {
                signals = [
                    { id: 1, symbol: 'GBPUSD', action: 'ANTICIPATED_LONG', entry: 1.33, sl: 1.32, tp: 1.33, confidence: 0.80, status: 'ACTIVE', created_at: new Date().toISOString() },
                    { id: 2, symbol: 'EURUSD', action: 'SELL_NOW', entry: 1.13, sl: 1.13, tp: 1.13, confidence: 0.80, status: 'ACTIVE', created_at: new Date().toISOString() },
                    { id: 3, symbol: 'XAUUSD', action: 'ANTICIPATED_LONG', entry: 3241.00, sl: 3250.00, tp: 3235.00, confidence: 0.70, status: 'ACTIVE', created_at: new Date().toISOString() },
                    { id: 4, symbol: 'GBPUSD', action: 'SELL_NOW', entry: 1.33, sl: 1.32, tp: 1.33, confidence: 0.80, status: 'ACTIVE', created_at: new Date().toISOString() },
                    { id: 5, symbol: 'XAUUSD', action: 'ANTICIPATED_SHORT', entry: 3241.00, sl: 3225.00, tp: 3250.00, confidence: 0.70, status: 'ACTIVE', created_at: new Date().toISOString() },
                    { id: 6, symbol: 'GBPUSD', action: 'ANTICIPATED_SHORT', entry: 1.33, sl: 1.32, tp: 1.33, confidence: 0.75, status: 'ACTIVE', created_at: new Date().toISOString() }
                ];
            }
            updateSignalsTable(signals);
        })
        .catch(error => {
            console.error('Error fetching signals:', error);
        });
}

/**
 * Update the signals display in the UI with a card layout
 * @param {Array} signals - List of signal objects
 */
function updateSignalsTable(signals) {
    const container = document.getElementById('signals-container');
    if (!container) return;
    
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
        emptyMessage.className = 'p-3 text-center';
        emptyMessage.textContent = 'No active signals';
        signalsContainer.appendChild(emptyMessage);
        return;
    }
    
    // Sort signals by created_at in descending order (newest first)
    signals.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
    
    // Add signals as cards
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
        card.innerHTML = `
            <div class="signal-symbol">${signal.symbol.replace('_', '')}</div>
            <div class="signal-action"><span class="action-badge ${actionClass}">${signal.action.replace('_', ' ')}</span></div>
            <div class="signal-details">${signal.entry || '--'}</div>
            <div class="signal-details">${signal.sl || '--'}</div>
            <div class="signal-details">${signal.tp || '--'}</div>
            <div class="signal-details"><span class="${confidenceClass}">${Math.round(signal.confidence * 100)}%</span></div>
            <div class="signal-timestamp">${dateStr}</div>
        `;
        
        // Add click handler to view chart
        card.addEventListener('click', function() {
            viewSignalChart(signal.id);
        });
        
        // Make the card appear clickable
        card.style.cursor = 'pointer';
        
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



function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/api/signals/ws`;
    
    const socket = new WebSocket(wsUrl);
    
    socket.onopen = function(e) {
        console.log('WebSocket connection established');
    };
    
    socket.onmessage = function(event) {
        const data = JSON.parse(event.data);
        
        if (data.type === 'price_update') {
            // Update price data
            const symbol = data.data.symbol;
            priceData[symbol] = {
                bid: data.data.bid,
                ask: data.data.ask,
                timestamp: data.data.timestamp
            };
            
            // Update UI
            document.getElementById(`${symbol}-bid`).textContent = data.data.bid.toFixed(5);
            document.getElementById(`${symbol}-ask`).textContent = data.data.ask.toFixed(5);
            
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
        console.error(`WebSocket error: ${error.message}`);
    };
}
