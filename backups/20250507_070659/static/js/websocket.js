/**
 * GENESIS Trading Platform - WebSocket client
 * Handles real-time communication for price updates and signals
 */

class WebSocketClient {
    constructor(endpoint) {
        this.endpoint = endpoint;
        this.socket = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 10;
        this.reconnectDelay = 2000; // ms
        this.callbacks = {
            onConnect: [],
            onDisconnect: [],
            onError: [],
            onMessage: [],
            onPriceUpdate: [],
            onSignal: [],
            onTrade: []
        };
    }

    /**
     * Connect to the WebSocket server
     */
    connect() {
        try {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}${this.endpoint}`;
            
            console.log(`Connecting to WebSocket: ${wsUrl}`);
            this.socket = new WebSocket(wsUrl);
            
            this.socket.onopen = (event) => {
                console.log('WebSocket connected');
                this.reconnectAttempts = 0;
                this._triggerCallbacks('onConnect', event);
            };
            
            this.socket.onclose = (event) => {
                console.log(`WebSocket disconnected: ${event.code} ${event.reason}`);
                this._triggerCallbacks('onDisconnect', event);
                this._attemptReconnect();
            };
            
            this.socket.onerror = (error) => {
                console.error('WebSocket error:', error);
                this._triggerCallbacks('onError', error);
            };
            
            this.socket.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    this._triggerCallbacks('onMessage', data);
                    
                    // Handle specific message types
                    switch (data.type) {
                        case 'price_update':
                            this._triggerCallbacks('onPriceUpdate', data.data);
                            break;
                        case 'new_signal':
                            this._triggerCallbacks('onSignal', data.data);
                            break;
                        case 'new_trade':
                        case 'trade_update':
                        case 'trade_closed':
                            this._triggerCallbacks('onTrade', data.data);
                            break;
                    }
                } catch (error) {
                    console.error('Error processing WebSocket message:', error);
                }
            };
        } catch (error) {
            console.error('Error creating WebSocket connection:', error);
        }
    }

    /**
     * Send data to the WebSocket server
     * @param {Object} data - Data to send
     */
    send(data) {
        if (this.socket && this.socket.readyState === WebSocket.OPEN) {
            this.socket.send(JSON.stringify(data));
        } else {
            console.error('WebSocket not connected. Cannot send message.');
        }
    }

    /**
     * Close the WebSocket connection
     */
    disconnect() {
        if (this.socket) {
            this.socket.close(1000, "User initiated disconnect");
        }
    }

    /**
     * Register a callback for a specific event
     * @param {string} event - Event name
     * @param {Function} callback - Callback function
     */
    on(event, callback) {
        if (this.callbacks[event]) {
            this.callbacks[event].push(callback);
        } else {
            console.error(`Unknown event: ${event}`);
        }
    }

    /**
     * Remove a callback for a specific event
     * @param {string} event - Event name
     * @param {Function} callback - Callback function to remove
     */
    off(event, callback) {
        if (this.callbacks[event]) {
            this.callbacks[event] = this.callbacks[event].filter(cb => cb !== callback);
        }
    }

    /**
     * Trigger all callbacks for a specific event
     * @param {string} event - Event name
     * @param {any} data - Data to pass to callbacks
     * @private
     */
    _triggerCallbacks(event, data) {
        if (this.callbacks[event]) {
            this.callbacks[event].forEach(callback => {
                try {
                    callback(data);
                } catch (error) {
                    console.error(`Error in ${event} callback:`, error);
                }
            });
        }
    }

    /**
     * Attempt to reconnect to the WebSocket server
     * @private
     */
    _attemptReconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            console.log(`Attempting to reconnect (${this.reconnectAttempts}/${this.maxReconnectAttempts})...`);
            
            setTimeout(() => {
                this.connect();
            }, this.reconnectDelay * this.reconnectAttempts);
        } else {
            console.error('Maximum reconnection attempts reached. Please refresh the page.');
        }
    }
}

// Create global WebSocket instance
const wsClient = new WebSocketClient('/api/signals/ws');

// Connect automatically when script is loaded
document.addEventListener('DOMContentLoaded', () => {
    wsClient.connect();
    
    // Example event listeners
    wsClient.on('onConnect', () => {
        console.log('WebSocket connection established');
        // Update UI to show connected status
        const statusEl = document.getElementById('ws-status');
        if (statusEl) {
            statusEl.className = 'badge badge-success';
            statusEl.textContent = 'Connected';
        }
    });
    
    wsClient.on('onDisconnect', () => {
        // Update UI to show disconnected status
        const statusEl = document.getElementById('ws-status');
        if (statusEl) {
            statusEl.className = 'badge badge-danger';
            statusEl.textContent = 'Disconnected';
        }
    });
    
    // Handle price updates
    wsClient.on('onPriceUpdate', (priceData) => {
        // Update price displays
        const bidEl = document.getElementById(`${priceData.symbol}-bid`);
        const askEl = document.getElementById(`${priceData.symbol}-ask`);
        
        if (bidEl) bidEl.textContent = parseFloat(priceData.bid).toFixed(5);
        if (askEl) askEl.textContent = parseFloat(priceData.ask).toFixed(5);
    });
});
