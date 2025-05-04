/**
 * GENESIS Trading Platform - Trading History functionality
 */

// Global state
let trades = [];
let currentPage = 1;
let pageSize = 20;
let totalTrades = 0;
let totalPages = 0;
let statsRefreshTimer = null;
let tradesRefreshTimer = null;
let activeFilters = {
    symbol: '',
    status: '',
    startDate: '',
    endDate: ''
};

/**
 * Filter out duplicate trades and sort by date
 * @param {Array} tradeData - Array of trade objects from the API
 * @returns {Array} Filtered and sorted trades array
 */
function filterAndSortTrades(tradeData) {
    console.log('Filtering and sorting', tradeData.length, 'trades');
    
    // First, remove duplicate tickets by creating a map with ticket as key
    const uniqueTradesMap = new Map();
    
    tradeData.forEach(trade => {
        // Use the ticket as the unique identifier
        const key = trade.ticket;
        
        // If the ticket is already in the map, only keep the latest version
        // based on updated_at timestamp
        if (key && uniqueTradesMap.has(key)) {
            const existingTrade = uniqueTradesMap.get(key);
            const existingUpdated = new Date(existingTrade.updated_at || 0);
            const newUpdated = new Date(trade.updated_at || 0);
            
            // Replace only if this trade is newer
            if (newUpdated > existingUpdated) {
                uniqueTradesMap.set(key, trade);
            }
        } else if (key) {
            // Add the trade to the map if it's not already there
            uniqueTradesMap.set(key, trade);
        } else {
            // If no ticket, use the ID as fallback
            uniqueTradesMap.set(`id-${trade.id}`, trade);
        }
    });
    
    // Convert the Map back to an array
    let uniqueTrades = Array.from(uniqueTradesMap.values());
    console.log('After filtering duplicates:', uniqueTrades.length, 'trades');
    
    // Sort trades by opened_at date (most recent first)
    uniqueTrades.sort((a, b) => {
        const dateA = a.opened_at ? new Date(a.opened_at) : new Date(0);
        const dateB = b.opened_at ? new Date(b.opened_at) : new Date(0);
        return dateB - dateA; // Latest first
    });
    
    console.log('Completed filtering and sorting trades');
    return uniqueTrades;
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Load initial trades
    loadTrades();
    
    // Update trading statistics
    updateTradingStats();
    
    // Set up pagination buttons
    setupPagination();
    
    // Set up filter form
    setupFilters();
    
    // Set up export button
    const exportBtn = document.getElementById('export-trades-btn');
    if (exportBtn) {
        exportBtn.addEventListener('click', exportTrades);
    }
    
    // Periodically refresh data
    // Clear any existing timers
    if (tradesRefreshTimer) clearInterval(tradesRefreshTimer);
    if (statsRefreshTimer) clearInterval(statsRefreshTimer);
    
    // Set up separate timers with different intervals
    tradesRefreshTimer = setInterval(loadTrades, 30000); // Refresh trades every 30 seconds
    statsRefreshTimer = setInterval(updateTradingStats, 15000); // Refresh stats every 15 seconds
});

/**
 * Load trades from API with pagination and filters
 */
function loadTrades() {
    // Show loading state
    showLoading(true);
    
    // Build query parameters
    let params = new URLSearchParams({
        page: currentPage,
        limit: pageSize
    });
    
    // Add any active filters
    if (activeFilters.symbol) {
        params.append('symbol', activeFilters.symbol);
    }
    if (activeFilters.status) {
        params.append('status', activeFilters.status);
    }
    if (activeFilters.startDate) {
        params.append('start_date', activeFilters.startDate);
    }
    if (activeFilters.endDate) {
        params.append('end_date', activeFilters.endDate);
    }
    
    const apiUrl = `/api/trades?${params.toString()}`;
    console.log('Fetching trades from:', apiUrl);
    
    // Fetch trades
    fetch(apiUrl)
        .then(response => {
            console.log('API response status:', response.status);
            if (!response.ok) {
                throw new Error(`Network response was not ok: ${response.statusText}`);
            }
            return response.json();
        })
        .then(data => {
            console.log('Received trade data:', data);
            
            // Filter out duplicate tickets and sort by date
            trades = filterAndSortTrades(data.data);
            totalTrades = trades.length;
            totalPages = Math.ceil(totalTrades / pageSize);
            currentPage = Math.min(currentPage, totalPages || 1);
            
            // Update UI
            updateTradesTable();
            updatePagination();
            
            // Hide loading
            showLoading(false);
        })
        .catch(error => {
            console.error('Error loading trades:', error);
            showAlert(`Failed to load trades: ${error.message}`, 'danger');
            showLoading(false);
        });
}

/**
 * Update the trades table with current data
 */
function updateTradesTable() {
    console.log('Starting updateTradesTable function');
    const tableBody = document.getElementById('trades-table-body');
    if (!tableBody) {
        console.error('Could not find trades-table-body element');
        return;
    }
    
    // Clear existing rows
    tableBody.innerHTML = '';
    
    console.log('Trades array length:', trades.length);
    
    if (trades.length === 0) {
        console.log('No trades found, showing empty state message');
        // Show a more informative empty state with guidance
        const emptyRow = document.createElement('tr');
        emptyRow.innerHTML = `<td colspan="10" class="text-center">
            <div class="alert alert-info mb-0">
                <i class="bi bi-info-circle me-2"></i>
                <strong>No trades found.</strong> 
                <p class="mb-0 mt-2">To see your trading history here:</p>
                <ol class="text-start mt-2 mb-0">
                    <li>Ensure your MetaTrader 5 terminal is running</li>
                    <li>Verify the GENESIS EA is installed and configured</li>
                    <li>Execute some trades in your MT5 terminal</li>
                </ol>
                <p class="mt-2 mb-0"><small>Trade data will automatically appear here once trades are executed or closed.</small></p>
            </div>
        </td>`;
        tableBody.appendChild(emptyRow);
        return;
    }
    
    // Add each trade
    console.log('Starting to add trades to the table');
    trades.forEach((trade, index) => {
        console.log(`Processing trade ${index + 1}:`, trade);
        const row = document.createElement('tr');
        
        // Format dates
        const openedDate = trade.opened_at ? new Date(trade.opened_at) : null;
        const closedDate = trade.closed_at ? new Date(trade.closed_at) : null;
        console.log('Formatted dates:', { openedDate, closedDate });
        
        // Format P&L with color
        const pnlClass = trade.pnl > 0 ? 'text-success' : (trade.pnl < 0 ? 'text-danger' : '');
        
        const badgeClass = getBadgeClass(trade.status);
        console.log('Badge and PNL classes:', { badgeClass, pnlClass });
        
        row.innerHTML = `
            <td>${trade.id}</td>
            <td>${trade.symbol}</td>
            <td>
                <span class="badge ${trade.side === 'BUY' ? 'bg-success' : 'bg-danger'}">
                    ${trade.side}
                </span>
            </td>
            <td>${trade.lot}</td>
            <td>${trade.entry !== null ? trade.entry.toFixed(5) : '--'}</td>
            <td>${trade.exit !== null ? trade.exit.toFixed(5) : '--'}</td>
            <td class="${pnlClass}">${trade.pnl !== null ? trade.pnl.toFixed(2) : '--'}</td>
            <td>
                <span class="badge ${badgeClass}">
                    ${trade.status}
                </span>
            </td>
            <td>${openedDate ? formatDate(openedDate) : '--'}</td>
            <td>${closedDate ? formatDate(closedDate) : '--'}</td>
        `;
        
        tableBody.appendChild(row);
        console.log(`Added trade ${index + 1} to table`);
    });
    console.log('Finished adding all trades to the table');
}

/**
 * Format date for display
 * @param {Date} date - Date to format
 * @returns {string} Formatted date string
 */
function formatDate(date) {
    if (!date) return '--';
    
    const options = {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false
    };
    
    return date.toLocaleDateString(undefined, options);
}

/**
 * Get badge class for trade status
 * @param {string} status - Trade status
 * @returns {string} Badge class name
 */
function getBadgeClass(status) {
    switch (status) {
        case 'OPEN':
            return 'bg-primary';
        case 'CLOSED':
            return 'bg-secondary';
        case 'CANCELLED':
            return 'bg-danger';
        case 'PARTIALLY_CLOSED':
            return 'bg-warning';
        default:
            return 'bg-info';
    }
}

/**
 * Set up pagination buttons
 */
function setupPagination() {
    // Previous page button
    const prevBtn = document.getElementById('prev-page-btn');
    if (prevBtn) {
        prevBtn.addEventListener('click', () => {
            if (currentPage > 1) {
                currentPage--;
                loadTrades();
            }
        });
    }
    
    // Next page button
    const nextBtn = document.getElementById('next-page-btn');
    if (nextBtn) {
        nextBtn.addEventListener('click', () => {
            if (currentPage < totalPages) {
                currentPage++;
                loadTrades();
            }
        });
    }
    
    // Page size dropdown
    const pageSizeSelect = document.getElementById('page-size');
    if (pageSizeSelect) {
        pageSizeSelect.value = pageSize;
        pageSizeSelect.addEventListener('change', () => {
            pageSize = parseInt(pageSizeSelect.value);
            currentPage = 1; // Reset to first page
            loadTrades();
        });
    }
}

/**
 * Update pagination controls
 */
function updatePagination() {
    // Update page indicator
    const pageIndicator = document.getElementById('page-indicator');
    if (pageIndicator) {
        pageIndicator.textContent = `Page ${currentPage} of ${totalPages}`;
    }
    
    // Update total count
    const totalIndicator = document.getElementById('total-trades');
    if (totalIndicator) {
        totalIndicator.textContent = `${totalTrades} trades`;
    }
    
    // Update button states
    const prevBtn = document.getElementById('prev-page-btn');
    if (prevBtn) {
        prevBtn.disabled = currentPage <= 1;
    }
    
    const nextBtn = document.getElementById('next-page-btn');
    if (nextBtn) {
        nextBtn.disabled = currentPage >= totalPages;
    }
}

/**
 * Set up filter form
 */
function setupFilters() {
    const filterForm = document.getElementById('filter-form');
    if (!filterForm) return;
    
    filterForm.addEventListener('submit', function(event) {
        event.preventDefault();
        
        // Update active filters
        activeFilters.symbol = document.getElementById('filter-symbol').value;
        activeFilters.status = document.getElementById('filter-status').value;
        activeFilters.startDate = document.getElementById('filter-start-date').value;
        activeFilters.endDate = document.getElementById('filter-end-date').value;
        
        // Reset to first page
        currentPage = 1;
        
        // Load trades with new filters
        loadTrades();
    });
    
    // Reset filters button
    const resetBtn = document.getElementById('reset-filters-btn');
    if (resetBtn) {
        resetBtn.addEventListener('click', function() {
            filterForm.reset();
            
            // Clear active filters
            activeFilters.symbol = '';
            activeFilters.status = '';
            activeFilters.startDate = '';
            activeFilters.endDate = '';
            
            // Reset to first page
            currentPage = 1;
            
            // Load trades without filters
            loadTrades();
        });
    }
}

/**
 * Update trading statistics
 */
function updateTradingStats() {
    // Show the stats section with loading state if needed
    const statsSection = document.querySelector('.card.mt-4');
    if (statsSection) {
        statsSection.style.opacity = '1';
    }
    
    // Fetch stats from API
    fetch('/api/trades/stats')
        .then(response => {
            if (!response.ok) {
                throw new Error(`Network response was not ok: ${response.statusText}`);
            }
            return response.json();
        })
        .then(data => {
            // Update UI with stats
            updateStatsUI(data);
            
            // Make sure the stats section remains visible after update
            if (statsSection) {
                statsSection.style.opacity = '1';
            }
        })
        .catch(error => {
            console.error('Error loading trading stats:', error);
            // Show a more informative empty state in the stats UI
            updateStatsUI({});
        });
}

/**
 * Update stats UI elements
 * @param {Object} stats - Trading statistics data
 */
function updateStatsUI(stats) {
    // Check if there's data to display
    const hasData = stats && stats.total_trades && stats.total_trades > 0;
    
    // Get the stats card body for adding a message if needed
    const statsCardBody = document.querySelector('.card.mt-4 .card-body');
    const existingMessage = document.getElementById('no-stats-message');
    
    // Handle empty state with a message
    if (!hasData) {
        if (statsCardBody && !existingMessage) {
            // Add an informative message when there's no data
            const noDataMsg = document.createElement('div');
            noDataMsg.id = 'no-stats-message';
            noDataMsg.className = 'alert alert-info';
            noDataMsg.innerHTML = 'No closed trades found. Waiting for trade data from MT5 terminal. Statistics will appear once trades are completed.';
            
            // Insert before the first child of card body
            const firstChild = statsCardBody.querySelector('.row');
            if (firstChild) {
                statsCardBody.insertBefore(noDataMsg, firstChild);
            } else {
                statsCardBody.appendChild(noDataMsg);
            }
        }
    } else if (existingMessage) {
        // Remove the message if it exists and we now have data
        existingMessage.remove();
    }
    
    // Update win rate
    const winRateEl = document.getElementById('win-rate');
    if (winRateEl) {
        if (hasData && stats.win_rate !== undefined && !isNaN(stats.win_rate)) {
            winRateEl.textContent = `${stats.win_rate.toFixed(1)}%`;
        } else {
            winRateEl.textContent = '0.0%';
        }
    }
    
    // Update total trades
    const totalTradesEl = document.getElementById('total-closed-trades');
    if (totalTradesEl) {
        totalTradesEl.textContent = hasData ? stats.total_trades : 0;
    }
    
    // Update profit factor
    const profitFactorEl = document.getElementById('profit-factor');
    if (profitFactorEl) {
        if (hasData && stats.profit_factor !== undefined && !isNaN(stats.profit_factor)) {
            profitFactorEl.textContent = stats.profit_factor.toFixed(2);
        } else {
            profitFactorEl.textContent = '0.00';
        }
    }
    
    // Update average win
    const avgWinEl = document.getElementById('avg-win');
    if (avgWinEl) {
        avgWinEl.className = ''; // Clear any existing classes
        if (hasData && stats.avg_win !== undefined && !isNaN(stats.avg_win)) {
            avgWinEl.textContent = `$${stats.avg_win.toFixed(2)}`;
            avgWinEl.classList.add('text-success');
        } else {
            avgWinEl.textContent = '$0.00';
        }
    }
    
    // Update average loss
    const avgLossEl = document.getElementById('avg-loss');
    if (avgLossEl) {
        avgLossEl.className = ''; // Clear any existing classes
        if (hasData && stats.avg_loss !== undefined && !isNaN(stats.avg_loss)) {
            avgLossEl.textContent = `$${Math.abs(stats.avg_loss).toFixed(2)}`;
            avgLossEl.classList.add('text-danger');
        } else {
            avgLossEl.textContent = '$0.00';
        }
    }
    
    // Update total profit
    const totalProfitEl = document.getElementById('total-profit');
    if (totalProfitEl) {
        totalProfitEl.className = ''; // Clear any existing classes
        if (hasData && stats.total_profit !== undefined && !isNaN(stats.total_profit)) {
            totalProfitEl.textContent = `$${stats.total_profit.toFixed(2)}`;
            
            if (stats.total_profit > 0) {
                totalProfitEl.classList.add('text-success');
            } else if (stats.total_profit < 0) {
                totalProfitEl.classList.add('text-danger');
            }
        } else {
            totalProfitEl.textContent = '$0.00';
        }
    }
}

/**
 * Export trades to CSV file
 */
function exportTrades() {
    // Show loading state
    const exportBtn = document.getElementById('export-trades-btn');
    if (exportBtn) {
        const originalText = exportBtn.textContent;
        exportBtn.disabled = true;
        exportBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Exporting...';
        
        // Build query parameters including all current filters
        let params = new URLSearchParams();
        
        // Add any active filters
        if (activeFilters.symbol) {
            params.append('symbol', activeFilters.symbol);
        }
        if (activeFilters.status) {
            params.append('status', activeFilters.status);
        }
        if (activeFilters.startDate) {
            params.append('start_date', activeFilters.startDate);
        }
        if (activeFilters.endDate) {
            params.append('end_date', activeFilters.endDate);
        }
        
        // Fetch all trades for export (no pagination)
        fetch(`/api/trades/export?${params.toString()}`)
            .then(response => {
                if (!response.ok) {
                    throw new Error(`Network response was not ok: ${response.statusText}`);
                }
                return response.blob();
            })
            .then(blob => {
                // Create download link
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.style.display = 'none';
                a.href = url;
                a.download = `trades_export_${new Date().toISOString().slice(0, 10)}.csv`;
                
                // Append to document and trigger download
                document.body.appendChild(a);
                a.click();
                
                // Clean up
                window.URL.revokeObjectURL(url);
                a.remove();
                
                showAlert('Trades exported successfully', 'success');
            })
            .catch(error => {
                console.error('Error exporting trades:', error);
                showAlert(`Failed to export trades: ${error.message}`, 'danger');
            })
            .finally(() => {
                // Reset button
                exportBtn.disabled = false;
                exportBtn.textContent = originalText;
            });
    }
}

/**
 * Show or hide loading state
 * @param {boolean} isLoading - Whether loading is in progress
 */
function showLoading(isLoading) {
    const loadingIndicator = document.getElementById('loading-indicator');
    const tableContainer = document.getElementById('trades-table-container');
    
    if (loadingIndicator) {
        loadingIndicator.style.display = isLoading ? 'block' : 'none';
    }
    
    if (tableContainer) {
        tableContainer.classList.toggle('loading', isLoading);
    }
}

/**
 * Show an alert message
 * @param {string} message - Alert message
 * @param {string} type - Alert type (success, danger, warning, info)
 */
function showAlert(message, type = 'info') {
    const alertsContainer = document.getElementById('alerts-container');
    if (!alertsContainer) return;
    
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

// Monthly chart functionality removed per user request
