/**
 * GENESIS Trading Platform - Trading History functionality
 */

// Global state
let trades = [];
let currentPage = 1;
let pageSize = 20;
let totalTrades = 0;
let totalPages = 0;
let activeFilters = {
    symbol: '',
    status: '',
    startDate: '',
    endDate: ''
};

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Load initial trades
    loadTrades();
    
    // Set up pagination buttons
    setupPagination();
    
    // Set up filter form
    setupFilters();
    
    // Set up export button
    const exportBtn = document.getElementById('export-trades-btn');
    if (exportBtn) {
        exportBtn.addEventListener('click', exportTrades);
    }
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
    
    // Fetch trades
    fetch(`/api/trades?${params.toString()}`)
        .then(response => {
            if (!response.ok) {
                throw new Error(`Network response was not ok: ${response.statusText}`);
            }
            return response.json();
        })
        .then(data => {
            trades = data.data;
            totalTrades = data.total;
            totalPages = data.pages;
            currentPage = data.page;
            
            // Update UI
            updateTradesTable();
            updatePagination();
            updateTradingStats();
            
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
    const tableBody = document.getElementById('trades-table-body');
    if (!tableBody) return;
    
    // Clear existing rows
    tableBody.innerHTML = '';
    
    if (trades.length === 0) {
        // Show empty state
        const emptyRow = document.createElement('tr');
        emptyRow.innerHTML = `<td colspan="9" class="text-center">No trades found</td>`;
        tableBody.appendChild(emptyRow);
        return;
    }
    
    // Add each trade
    trades.forEach(trade => {
        const row = document.createElement('tr');
        
        // Format dates
        const openedDate = new Date(trade.opened_at);
        const closedDate = trade.closed_at ? new Date(trade.closed_at) : null;
        
        // Format P&L with color
        const pnlClass = trade.pnl > 0 ? 'positive' : (trade.pnl < 0 ? 'negative' : '');
        
        row.innerHTML = `
            <td>${trade.id}</td>
            <td>${trade.symbol}</td>
            <td>
                <span class="badge ${trade.side === 'BUY' ? 'badge-success' : 'badge-danger'}">
                    ${trade.side}
                </span>
            </td>
            <td>${trade.lot}</td>
            <td>${trade.entry || '--'}</td>
            <td>${trade.exit || '--'}</td>
            <td class="${pnlClass}">${trade.pnl ? trade.pnl.toFixed(2) : '--'}</td>
            <td>
                <span class="badge ${getBadgeClass(trade.status)}">
                    ${trade.status}
                </span>
            </td>
            <td>
                <div>${formatDate(openedDate)}</div>
                ${closedDate ? `<div>${formatDate(closedDate)}</div>` : ''}
            </td>
        `;
        
        tableBody.appendChild(row);
    });
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
            return 'badge-primary';
        case 'CLOSED':
            return 'badge-secondary';
        case 'CANCELLED':
            return 'badge-danger';
        case 'PARTIALLY_CLOSED':
            return 'badge-warning';
        default:
            return 'badge-info';
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
        })
        .catch(error => {
            console.error('Error loading trading stats:', error);
        });
}

/**
 * Update stats UI elements
 * @param {Object} stats - Trading statistics data
 */
function updateStatsUI(stats) {
    // Update win rate
    const winRateEl = document.getElementById('win-rate');
    if (winRateEl && stats.win_rate !== undefined) {
        winRateEl.textContent = `${stats.win_rate.toFixed(1)}%`;
    }
    
    // Update total trades
    const totalTradesEl = document.getElementById('total-closed-trades');
    if (totalTradesEl && stats.total_trades !== undefined) {
        totalTradesEl.textContent = stats.total_trades;
    }
    
    // Update profit factor
    const profitFactorEl = document.getElementById('profit-factor');
    if (profitFactorEl && stats.profit_factor !== undefined) {
        profitFactorEl.textContent = stats.profit_factor.toFixed(2);
    }
    
    // Update average win
    const avgWinEl = document.getElementById('avg-win');
    if (avgWinEl && stats.avg_win !== undefined) {
        avgWinEl.textContent = `$${stats.avg_win.toFixed(2)}`;
        avgWinEl.classList.add('text-success');
    }
    
    // Update average loss
    const avgLossEl = document.getElementById('avg-loss');
    if (avgLossEl && stats.avg_loss !== undefined) {
        avgLossEl.textContent = `$${Math.abs(stats.avg_loss).toFixed(2)}`;
        avgLossEl.classList.add('text-danger');
    }
    
    // Update total profit
    const totalProfitEl = document.getElementById('total-profit');
    if (totalProfitEl && stats.total_profit !== undefined) {
        totalProfitEl.textContent = `$${stats.total_profit.toFixed(2)}`;
        
        if (stats.total_profit > 0) {
            totalProfitEl.classList.add('text-success');
        } else if (stats.total_profit < 0) {
            totalProfitEl.classList.add('text-danger');
        }
    }
    
    // Monthly chart removed per user request
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
