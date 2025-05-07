/**
 * GENESIS Trading Platform - Settings page functionality
 */

// Global state
let currentTab = 'connections';
let riskProfiles = [];
let currentRiskProfile = null;

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Set up tab switching
    setupTabs();
    
    // Load settings data
    loadSettings();
    
    // Set up form submission handlers
    setupFormHandlers();
    
    // Initialize test buttons
    initializeTestButtons();
});

/**
 * Set up tab switching functionality
 */
function setupTabs() {
    const tabs = document.querySelectorAll('.tab');
    const tabContents = document.querySelectorAll('.tab-content');
    
    tabs.forEach(tab => {
        tab.addEventListener('click', function() {
            // Get the target tab ID
            const target = this.getAttribute('data-tab');
            
            // Remove active class from all tabs and contents
            tabs.forEach(t => t.classList.remove('active'));
            tabContents.forEach(c => c.classList.remove('active'));
            
            // Add active class to clicked tab and corresponding content
            this.classList.add('active');
            document.getElementById(target).classList.add('active');
            
            // Update current tab
            currentTab = target;
            
            // Special actions for specific tabs
            if (target === 'risk-ml') {
                loadRiskProfiles();
            }
        });
    });
}

/**
 * Load settings data from the API
 */
function loadSettings() {
    // Load each settings section
    loadSectionSettings('connections');
    loadSectionSettings('risk-ml');
    loadSectionSettings('notifications');
    loadSectionSettings('maintenance');
}

/**
 * Load settings for a specific section
 * @param {string} section - The settings section name
 */
function loadSectionSettings(section) {
    fetch(`/api/settings/${section}`)
        .then(response => {
            if (!response.ok) {
                throw new Error(`Network response was not ok: ${response.statusText}`);
            }
            return response.json();
        })
        .then(data => {
            populateSettingsForm(section, data);
        })
        .catch(error => {
            console.error(`Error loading ${section} settings:`, error);
            showAlert(`Failed to load ${section} settings: ${error.message}`, 'danger');
        });
}

/**
 * Populate form fields with settings data
 * @param {string} section - The settings section name
 * @param {Object} data - The settings data object
 */
function populateSettingsForm(section, data) {
    // Get the form for this section
    const form = document.getElementById(`${section}-form`);
    if (!form) return;
    
    // Loop through each input in the form
    Array.from(form.elements).forEach(input => {
        if (input.name && data[input.name] !== undefined) {
            // For checkboxes
            if (input.type === 'checkbox') {
                input.checked = !!data[input.name];
            } 
            // For all other inputs
            else {
                input.value = data[input.name];
            }
        }
    });
}

/**
 * Load risk profiles from the API
 */
function loadRiskProfiles() {
    fetch('/api/risk-profiles')
        .then(response => {
            if (!response.ok) {
                throw new Error(`Network response was not ok: ${response.statusText}`);
            }
            return response.json();
        })
        .then(data => {
            riskProfiles = data;
            updateRiskProfilesList();
        })
        .catch(error => {
            console.error('Error loading risk profiles:', error);
            showAlert(`Failed to load risk profiles: ${error.message}`, 'danger');
        });
}

/**
 * Update the risk profiles list in the UI
 */
function updateRiskProfilesList() {
    const profilesList = document.getElementById('risk-profiles-list');
    if (!profilesList) return;
    
    // Clear existing list
    profilesList.innerHTML = '';
    
    // Add each profile
    riskProfiles.forEach(profile => {
        const item = document.createElement('div');
        item.className = 'risk-profile-item';
        
        if (profile.is_default) {
            item.classList.add('active');
            currentRiskProfile = profile;
        }
        
        item.innerHTML = `
            <div class="profile-header">
                <h4>${profile.name}</h4>
                <div class="profile-actions">
                    ${profile.is_default ? '<span class="badge badge-primary">Default</span>' : ''}
                    <button class="btn btn-sm btn-outline" onclick="editRiskProfile(${profile.id})">Edit</button>
                    ${!profile.is_default ? `<button class="btn btn-sm btn-danger" onclick="deleteRiskProfile(${profile.id})">Delete</button>` : ''}
                    ${!profile.is_default ? `<button class="btn btn-sm btn-secondary" onclick="setDefaultRiskProfile(${profile.id})">Set Default</button>` : ''}
                </div>
            </div>
            <div class="profile-details">
                <div>Max Risk Per Trade: ${profile.json_rules.max_risk_per_trade}%</div>
                <div>Max Daily Risk: ${profile.json_rules.max_daily_risk}%</div>
                <div>Min Signal Confidence: ${profile.json_rules.min_signal_confidence * 100}%</div>
            </div>
        `;
        
        profilesList.appendChild(item);
    });
    
    // Update risk profile editor if a profile is selected
    if (currentRiskProfile) {
        updateRiskProfileEditor(currentRiskProfile);
    }
}

/**
 * Update the risk profile editor with the selected profile
 * @param {Object} profile - The risk profile object
 */
function updateRiskProfileEditor(profile) {
    const editor = document.getElementById('risk-profile-editor');
    if (!editor) return;
    
    // Set profile name
    const nameInput = editor.querySelector('#profile-name');
    if (nameInput) nameInput.value = profile.name;
    
    // Set max risk per trade
    const maxRiskInput = editor.querySelector('#max-risk-per-trade');
    if (maxRiskInput) maxRiskInput.value = profile.json_rules.max_risk_per_trade;
    
    // Set max daily risk
    const maxDailyRiskInput = editor.querySelector('#max-daily-risk');
    if (maxDailyRiskInput) maxDailyRiskInput.value = profile.json_rules.max_daily_risk;
    
    // Set min signal confidence
    const minConfidenceInput = editor.querySelector('#min-signal-confidence');
    if (minConfidenceInput) minConfidenceInput.value = profile.json_rules.min_signal_confidence * 100;
    
    // Set trailing stop
    const trailingStopInput = editor.querySelector('#trailing-stop');
    if (trailingStopInput) trailingStopInput.checked = profile.json_rules.trailing_stop;
    
    // Set break even
    const breakEvenInput = editor.querySelector('#break-even');
    if (breakEvenInput) breakEvenInput.checked = profile.json_rules.break_even;
    
    // Set break even pips
    const breakEvenPipsInput = editor.querySelector('#break-even-pips');
    if (breakEvenPipsInput) breakEvenPipsInput.value = profile.json_rules.break_even_pips;
    
    // Set max position sizes
    const symbols = ['XAUUSD', 'GBPJPY', 'GBPUSD', 'EURUSD', 'AAPL', 'NAS100', 'BTCUSD', 'default'];
    symbols.forEach(symbol => {
        const input = editor.querySelector(`#max-size-${symbol.toLowerCase()}`);
        if (input) {
            input.value = profile.json_rules.max_position_size[symbol] || profile.json_rules.max_position_size.default;
        }
    });
}

/**
 * Edit a risk profile
 * @param {number} profileId - The profile ID to edit
 */
function editRiskProfile(profileId) {
    // Find profile by ID
    const profile = riskProfiles.find(p => p.id === profileId);
    if (!profile) return;
    
    // Set as current profile and update editor
    currentRiskProfile = profile;
    updateRiskProfileEditor(profile);
    
    // Show editor
    const editor = document.getElementById('risk-profile-editor');
    if (editor) editor.style.display = 'block';
}

/**
 * Create a new risk profile
 */
function createNewRiskProfile() {
    // Create default profile template
    currentRiskProfile = {
        id: null,
        name: "New Profile",
        json_rules: {
            max_risk_per_trade: 2.0,
            max_daily_risk: 5.0,
            max_position_size: {
                XAUUSD: 0.5,
                GBPJPY: 0.5,
                GBPUSD: 0.5,
                EURUSD: 0.5,
                AAPL: 0.5,
                NAS100: 0.2,
                BTCUSD: 0.1,
                default: 0.01
            },
            min_signal_confidence: 0.6,
            trailing_stop: true,
            break_even: true,
            break_even_pips: 20,
            max_spread: {
                XAUUSD: 0.5,
                GBPJPY: 1.5,
                GBPUSD: 1.0,
                EURUSD: 0.8,
                AAPL: 0.03,
                NAS100: 1.0,
                BTCUSD: 10.0,
                default: 10.0
            }
        },
        is_default: false
    };
    
    // Update editor
    updateRiskProfileEditor(currentRiskProfile);
    
    // Show editor
    const editor = document.getElementById('risk-profile-editor');
    if (editor) editor.style.display = 'block';
}

/**
 * Delete a risk profile
 * @param {number} profileId - The profile ID to delete
 */
function deleteRiskProfile(profileId) {
    if (!confirm('Are you sure you want to delete this risk profile?')) {
        return;
    }
    
    fetch(`/api/risk-profiles/${profileId}`, {
        method: 'DELETE'
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`Network response was not ok: ${response.statusText}`);
        }
        return response.json();
    })
    .then(data => {
        showAlert('Risk profile deleted successfully', 'success');
        loadRiskProfiles();
    })
    .catch(error => {
        console.error('Error deleting risk profile:', error);
        showAlert(`Failed to delete risk profile: ${error.message}`, 'danger');
    });
}

/**
 * Set a risk profile as the default
 * @param {number} profileId - The profile ID to set as default
 */
function setDefaultRiskProfile(profileId) {
    fetch(`/api/risk-profiles/${profileId}/default`, {
        method: 'POST'
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`Network response was not ok: ${response.statusText}`);
        }
        return response.json();
    })
    .then(data => {
        showAlert('Default risk profile updated successfully', 'success');
        loadRiskProfiles();
    })
    .catch(error => {
        console.error('Error setting default risk profile:', error);
        showAlert(`Failed to set default risk profile: ${error.message}`, 'danger');
    });
}

/**
 * Save a risk profile
 */
function saveRiskProfile() {
    // Get form data
    const editor = document.getElementById('risk-profile-editor');
    if (!editor) return;
    
    const nameInput = editor.querySelector('#profile-name');
    const maxRiskInput = editor.querySelector('#max-risk-per-trade');
    const maxDailyRiskInput = editor.querySelector('#max-daily-risk');
    const minConfidenceInput = editor.querySelector('#min-signal-confidence');
    const trailingStopInput = editor.querySelector('#trailing-stop');
    const breakEvenInput = editor.querySelector('#break-even');
    const breakEvenPipsInput = editor.querySelector('#break-even-pips');
    
    // Validate required fields
    if (!nameInput.value) {
        showAlert('Profile name is required', 'danger');
        return;
    }
    
    // Update profile object
    const isNew = !currentRiskProfile.id;
    
    currentRiskProfile.name = nameInput.value;
    currentRiskProfile.json_rules.max_risk_per_trade = parseFloat(maxRiskInput.value);
    currentRiskProfile.json_rules.max_daily_risk = parseFloat(maxDailyRiskInput.value);
    currentRiskProfile.json_rules.min_signal_confidence = parseFloat(minConfidenceInput.value) / 100;
    currentRiskProfile.json_rules.trailing_stop = trailingStopInput.checked;
    currentRiskProfile.json_rules.break_even = breakEvenInput.checked;
    currentRiskProfile.json_rules.break_even_pips = parseInt(breakEvenPipsInput.value);
    
    // Update position sizes
    const symbols = ['XAUUSD', 'GBPJPY', 'GBPUSD', 'EURUSD', 'AAPL', 'NAS100', 'BTCUSD', 'default'];
    symbols.forEach(symbol => {
        const input = editor.querySelector(`#max-size-${symbol.toLowerCase()}`);
        if (input) {
            currentRiskProfile.json_rules.max_position_size[symbol] = parseFloat(input.value);
        }
    });
    
    // API call
    const url = isNew ? '/api/risk-profiles' : `/api/risk-profiles/${currentRiskProfile.id}`;
    const method = isNew ? 'POST' : 'PUT';
    
    fetch(url, {
        method: method,
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(currentRiskProfile)
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`Network response was not ok: ${response.statusText}`);
        }
        return response.json();
    })
    .then(data => {
        showAlert('Risk profile saved successfully', 'success');
        loadRiskProfiles();
    })
    .catch(error => {
        console.error('Error saving risk profile:', error);
        showAlert(`Failed to save risk profile: ${error.message}`, 'danger');
    });
}

/**
 * Set up form submission handlers
 */
function setupFormHandlers() {
    // Handle forms for each tab
    const forms = {
        'connections': document.getElementById('connections-form'),
        'risk-ml': document.getElementById('risk-ml-form'),
        'notifications': document.getElementById('notifications-form'),
        'maintenance': document.getElementById('maintenance-form')
    };
    
    // Set up handler for each form
    Object.entries(forms).forEach(([section, form]) => {
        if (form) {
            form.addEventListener('submit', function(event) {
                event.preventDefault();
                saveSettings(section, form);
            });
        }
    });
    
    // Set up risk profile actions
    const newProfileBtn = document.getElementById('new-profile-btn');
    if (newProfileBtn) {
        newProfileBtn.addEventListener('click', createNewRiskProfile);
    }
    
    const saveProfileBtn = document.getElementById('save-profile-btn');
    if (saveProfileBtn) {
        saveProfileBtn.addEventListener('click', saveRiskProfile);
    }
    
    // Set up ML actions
    const retrainMlBtn = document.getElementById('retrain-ml-btn');
    if (retrainMlBtn) {
        retrainMlBtn.addEventListener('click', retrainMlModel);
    }
}

/**
 * Save settings for a specific section
 * @param {string} section - The settings section name
 * @param {HTMLFormElement} form - The form element
 */
function saveSettings(section, form) {
    // Collect form data
    const formData = new FormData(form);
    const settings = {};
    
    // Convert FormData to object
    for (const [key, value] of formData.entries()) {
        // Handle checkboxes (they are only included if checked)
        if (form.elements[key].type === 'checkbox') {
            settings[key] = form.elements[key].checked;
        } else {
            settings[key] = value;
        }
    }
    
    // Add any missing checkboxes (unchecked ones aren't included in FormData)
    Array.from(form.elements).forEach(input => {
        if (input.type === 'checkbox' && !settings[input.name] && input.name) {
            settings[input.name] = false;
        }
    });
    
    // Send to API
    fetch(`/api/settings/${section}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ settings: settings })
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`Network response was not ok: ${response.statusText}`);
        }
        return response.json();
    })
    .then(data => {
        showAlert(`${section} settings saved successfully`, 'success');
    })
    .catch(error => {
        console.error(`Error saving ${section} settings:`, error);
        showAlert(`Failed to save ${section} settings: ${error.message}`, 'danger');
    });
}

/**
 * Initialize test buttons for connections
 */
function initializeTestButtons() {
    // Test MT5 connection
    const testMt5Btn = document.getElementById('test-mt5-btn');
    if (testMt5Btn) {
        testMt5Btn.addEventListener('click', function() {
            testConnection('mt5', 'Testing MT5 connection...');
        });
    }
    
    // Test OANDA connection
    const testOandaBtn = document.getElementById('test-oanda-btn');
    if (testOandaBtn) {
        testOandaBtn.addEventListener('click', function() {
            testConnection('oanda', 'Testing OANDA connection...');
        });
    }
    
    // Test Telegram connection
    const testTelegramBtn = document.getElementById('test-telegram-btn');
    if (testTelegramBtn) {
        testTelegramBtn.addEventListener('click', function() {
            testConnection('telegram', 'Testing Telegram notification...');
        });
    }
}

/**
 * Test a connection
 * @param {string} type - Connection type: 'mt5', 'oanda', or 'telegram'
 * @param {string} loadingMessage - Message to show during testing
 */
function testConnection(type, loadingMessage) {
    // Get button
    const btn = document.getElementById(`test-${type}-btn`);
    if (!btn) return;
    
    // Show loading state
    const originalText = btn.textContent;
    btn.disabled = true;
    btn.innerHTML = `<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> ${loadingMessage}`;
    
    // Make API call
    fetch(`/api/test/${type}`, {
        method: 'POST'
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`Network response was not ok: ${response.statusText}`);
        }
        return response.json();
    })
    .then(data => {
        showAlert(`${type.toUpperCase()} connection successful`, 'success');
    })
    .catch(error => {
        console.error(`Error testing ${type} connection:`, error);
        showAlert(`${type.toUpperCase()} connection failed: ${error.message}`, 'danger');
    })
    .finally(() => {
        // Reset button
        btn.disabled = false;
        btn.textContent = originalText;
    });
}

/**
 * Retrain ML model
 */
function retrainMlModel() {
    // Get button
    const btn = document.getElementById('retrain-ml-btn');
    if (!btn) return;
    
    // Show loading state
    const originalText = btn.textContent;
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Retraining model...';
    
    // Make API call
    fetch('/api/ml/retrain', {
        method: 'POST'
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`Network response was not ok: ${response.statusText}`);
        }
        return response.json();
    })
    .then(data => {
        showAlert(`ML model retraining initiated. ${data.message || ''}`, 'success');
    })
    .catch(error => {
        console.error('Error retraining ML model:', error);
        showAlert(`Failed to retrain ML model: ${error.message}`, 'danger');
    })
    .finally(() => {
        // Reset button
        btn.disabled = false;
        btn.textContent = originalText;
    });
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
