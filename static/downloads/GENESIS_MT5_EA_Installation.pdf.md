# GENESIS MT5 Expert Advisor - Installation Guide

## Overview

The GENESIS MT5 Expert Advisor (EA) enables direct communication between your MetaTrader 5 platform and the GENESIS AI Trading System. This integration allows for seamless transfer of account data, trade execution, and automated trading based on AI-generated signals.

## Prerequisites

1. MetaTrader 5 platform installed
2. A broker account compatible with MetaTrader 5
3. Basic knowledge of how to use MetaTrader 5
4. GENESIS trading platform credentials

## Installation Steps

### Step 1: Download Files

Download the GENESIS_MT5_EA.mq5 file from the GENESIS platform's settings page under the "Connections" tab.

### Step 2: Place Files in MT5 Directory

1. Open your MetaTrader 5 platform
2. Go to File > Open Data Folder
3. Navigate to MQL5 > Experts
4. Copy the GENESIS_MT5_EA.mq5 file to this directory

### Step 3: Compile the EA

1. In MetaTrader 5, go to View > Navigator (or press Ctrl+N)
2. In the Navigator panel, expand the "Expert Advisors" section
3. Right-click on "GENESIS_MT5_EA" and select "Compile"
4. Ensure there are no compilation errors

### Step 4: Configure MT5 for External Connections

1. In MetaTrader 5, go to Tools > Options
2. Select the "Expert Advisors" tab
3. Check the following options:
   - Allow automated trading
   - Allow WebRequest for listed URL
4. In the "WebRequest" field, add: http://localhost:5500
5. Click "OK" to save changes

### Step 5: Configure the EA

1. Drag the GENESIS_MT5_EA from the Navigator panel onto any chart
2. In the EA settings dialog, configure the following parameters:
   - APIEndpoint: Set to http://localhost:5500/api/v1 (or the endpoint provided in your GENESIS dashboard)
   - APIToken: Leave blank for now (will be configured from the GENESIS platform)
3. Set other parameters as needed:
   - RiskPercent: Default is 1.0% of account balance per trade
   - AutoSL: Enable/disable automatic Stop Loss
   - AutoTP: Enable/disable automatic Take Profit
   - DefaultSLPips: Default Stop Loss in pips if not specified by signal
   - DefaultTPPips: Default Take Profit in pips if not specified by signal

### Step 6: Connect to GENESIS Platform

1. Log into your GENESIS platform
2. Go to Settings > Connections
3. In the MT5 section, set the following:
   - Endpoint: http://localhost:5500/api/v1
   - Click "Generate Token" and copy the generated token
4. Go back to your MT5 platform
5. Right-click on the chart with the EA and select "Expert Advisors" > "Properties"
6. Paste the token into the APIToken field
7. Click "OK" to save

### Step 7: Test the Connection

1. In the GENESIS platform, go to the Connections page
2. Click "Test MT5 Connection"
3. If successful, you should see a green "Connected" status indicator
4. Your account balance and other MT5 information should now appear in the GENESIS dashboard

## Troubleshooting

### Common Issues

1. **Connection Failed**
   - Ensure the MT5 platform is running with the EA attached to a chart
   - Verify that the APIEndpoint matches what's configured in the GENESIS platform
   - Check that the APIToken is correctly copied from the GENESIS platform
   - Confirm that WebRequest is allowed for localhost in MT5 settings

2. **Compilation Errors**
   - Ensure you have the latest MetaTrader 5 version
   - Check that all required libraries are available in your MT5 installation

3. **EA Not Showing Account Data**
   - Restart the MT5 platform
   - Check the "Experts" tab in MT5 for any error messages
   - Verify that automated trading is enabled in MT5

### Advanced Configuration

For advanced users, the EA can be configured directly from the GENESIS platform. Any changes made in the platform's settings will be automatically synced to the EA on the next connection cycle.

## Updates

The EA will be periodically updated with new features and improvements. Always download the latest version from the GENESIS platform to ensure optimal performance.

## Security Notes

- The EA communicates with the GENESIS platform using secure HTTP connections
- All sensitive data is transmitted with token-based authentication
- No trading passwords or access credentials are stored or transmitted
- The EA only performs actions explicitly authorized by the GENESIS platform

## Support

For additional support, please contact GENESIS support through the platform's help section.

---

© 2025 GENESIS AI Trading Systems