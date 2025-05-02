# MT5 GENESIS Expert Advisor - Installation Guide

## Overview

The MT5 GENESIS Expert Advisor connects your MetaTrader 5 platform to the GENESIS AI Trading System. This integration enables two-way communication between your trading platform and the GENESIS system for automated trade execution and real-time account monitoring.

## Prerequisites

1. MetaTrader 5 platform installed
2. A broker account compatible with MetaTrader 5
3. JAson.mqh library for MetaTrader 5 (installation instructions below)

## Installation Steps

### Step 1: Install Required Libraries

The MT5 GENESIS EA requires the JAson library for JSON handling. To install:

1. In MetaTrader 5, open the Market tab
2. Search for "JAson"
3. Download and install the library

Alternatively, you can:
1. Download the JAson.mqh file from the MQL5 community website
2. Place it in the MQL5/Include directory of your MetaTrader 5 installation

### Step 2: Install the EA

1. Download the MT5_GENESIS_EA.mq5 file from the GENESIS platform
2. Open your MetaTrader 5 platform
3. Go to File > Open Data Folder
4. Navigate to MQL5 > Experts
5. Copy the MT5_GENESIS_EA.mq5 file to this directory

### Step 3: Compile the EA

1. In MetaTrader 5, go to View > Navigator (or press Ctrl+N)
2. In the Navigator panel, expand the "Expert Advisors" section
3. Right-click on "MT5_GENESIS_EA" and select "Compile"
4. Ensure there are no compilation errors in the "Experts" tab

### Step 4: Configure MT5 for Internet Access

1. In MetaTrader 5, go to Tools > Options
2. Select the "Expert Advisors" tab
3. Check the following options:
   - Allow automated trading
   - Allow WebRequest for listed URL
4. In the "WebRequest" field, add the GENESIS platform URL:
   `https://4c1f2076-899e-4ced-962a-2903ca4a9bac-00-29hcpk84r1chm.picard.replit.dev/mt5_ea_api`
5. Click "OK" to save changes

### Step 5: Configure the EA

1. Drag the MT5_GENESIS_EA from the Navigator panel onto any chart
2. In the EA settings dialog, configure the following parameters:
   - API_Key: Leave blank (managed by platform)
   - AccountName: Enter a unique name to identify this account in GENESIS
   - AutoTrade: Set to true for automatic trade execution
   - SendReports: Set to true to report trade executions
   - LotMultiplier: Set to adjust the default lot size
   - SlippagePoints: Maximum allowed slippage
   - SendHeartbeat: Set to true to maintain connection

### Step 6: Test Connection

1. With the EA running on a chart, check the "Experts" tab for connection messages
2. You should see "Heartbeat sent successfully" messages every 60 seconds
3. In the GENESIS platform, navigate to the Connections page to verify the MT5 connection is active

## Troubleshooting

### Common Issues

1. **Compilation Errors**
   - Ensure JAson.mqh is correctly installed
   - Check for any syntax errors in the EA code

2. **Connection Errors**
   - Verify the URL is correctly added to the WebRequest allowlist
   - Check your internet connection
   - Ensure the GENESIS platform is running

3. **No Signals Being Received**
   - Check if the EA is properly initialized
   - Verify your account has access to signal generation
   - Ensure the symbols in Market Watch match those in GENESIS signals

### Advanced Settings

The EA has several advanced parameters that can be adjusted in the source code:

- `SIGNAL_CHECK_INTERVAL`: How often to check for new signals (seconds)
- `HEARTBEAT_INTERVAL`: How often to send heartbeat (seconds)

## Security Notes

- The EA communicates with the GENESIS platform using secure HTTPS
- No password or sensitive credentials are transmitted
- All trading actions require explicit signals from the GENESIS platform

## Support

For additional support, contact the GENESIS support team through the platform's help section.

---

© 2025 GENESIS Trading Platform
