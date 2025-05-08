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

/**
 * Initialize price charts for tracked symbols
 */
function initializeCharts() {
    // Focus on our 5 supported forex and metals assets
    const symbols = ['XAUUSD', 'GBPJPY', 'GBPUSD', 'EURUSD', 'USDJPY'];
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
            type: 'candlestick', // Using candlestick chart type for OHLC data
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
                                if (candle && candle.o !== undefined) {
                                    return [
                                        `Open: ${candle.o.toFixed(5)}`,
                                        `High: ${candle.h.toFixed(5)}`,
                                        `Low: ${candle.l.toFixed(5)}`,
                                        `Close: ${candle.c.toFixed(5)}`
                                    ];
                                }
                                return `Value: ${context.parsed.y}`;
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
    fetch(`/api/oanda/candles/${symbol}?t=${Date.now()}`)
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

    // Format data for chart.js bar chart
    const chartData = candles.map(candle => ({
        x: new Date(candle.time).getTime(),
        y: candle.close, // Use close price for bar chart
        // Keep OHLC data for tooltip
        o: candle.open,
        h: candle.high,
        l: candle.low,
        c: candle.close
    }));

    // Set bar colors based on price movement (green for up, red for down)
    activeCharts[symbol].data.datasets[0].backgroundColor = chartData.map((d, i) => {
        if (i === 0) return '#00c851'; // Default to green for first bar
        return chartData[i].y > chartData[i-1].y ? '#00c851' : '#ff3547'; // Green for up, red for down
    });

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
        emptyMessage.className = 'p-3 text-center w-100';
        emptyMessage.textContent = 'No active signals';
        signalsContainer.appendChild(emptyMessage);
        return;
    }

    // Sort signals by created_at in descending order (newest first)
    signals.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));

    // Log all available signals for debugging
    console.log('Available signals:', signals.map(s => s.symbol));

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

        // Get properly formatted symbol for display (remove underscore)
        const displaySymbol = signal.symbol.replace('_', '');

        card.innerHTML = `
            <div class="signal-header">
                <div class="signal-symbol">${displaySymbol}</div>
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

    // Show loading state by changing the button text and style
    const button = document.querySelector(`button[onclick="executeSignal(${signalId});"]`);
    const originalText = button.textContent;
    button.textContent = 'Sending...';
    button.disabled = true;
    button.style.opacity = '0.7';

    // Send request to execute the signal
    fetch(`/api/signals/${signalId}/execute`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        }
    })
    .then(response => response.json())
    .then(data => {
        // Reset button
        button.disabled = false;
        button.style.opacity = '1';

        if (data.status === 'success') {
            // Show success message
            showAlert(`Signal ${signalId} executed successfully. Trade sent to MT5.`, 'success');
            button.textContent = 'Executed ✓';
            button.classList.remove('signal-execute-button');
            button.classList.add('signal-executed-button');
            button.disabled = true;

            // Reload trades after a short delay
            setTimeout(loadActiveTrades, 2000);
        } else {
            // Show error message
            showAlert(`Error executing signal: ${data.message}`, 'danger');
            button.textContent = originalText;
        }
    })
    .catch(error => {
        // Show error message
        showAlert(`Error executing signal: ${error.message}`, 'danger');
        button.textContent = originalText;
        button.disabled = false;
        button.style.opacity = '1';
    });
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
