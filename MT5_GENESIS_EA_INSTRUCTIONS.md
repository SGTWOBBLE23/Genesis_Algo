# MT5 GENESIS EA Update Instructions

## Problem Identified
We've identified that while your MT5 EA is successfully connecting to the server (we see "Trade update received" messages in the logs), it's not sending your actual trade data to the server. This is why you're only seeing the sample/test trades dated in 2025 rather than your own trades.

## Solution
We've created an updated version of the MT5 Expert Advisor (version 10) that properly implements the trade data synchronization. This fixed version will send both open and closed trades from your MT5 terminal to the GENESIS platform.

## Steps to Update

1. **Download the updated EA file**
   - Download the `MT5_GENESIS_EA_fixed_v10.mq5` file from the downloads section of the GENESIS application

2. **Install in MetaTrader 5**
   - Open MetaTrader 5
   - Go to File → Open Data Folder
   - Navigate to MQL5 → Experts
   - Copy the downloaded `MT5_GENESIS_EA_fixed_v10.mq5` file into this folder

3. **Compile the EA**
   - In MetaTrader 5, go to View → Navigator (or press Ctrl+N)
   - In the Navigator panel, open the "Expert Advisors" section
   - Right-click the new EA file and select "Compile"
   - Make sure there are no compilation errors

4. **Update the WebRequest allowed URLs**
   - In MetaTrader 5, go to Tools → Options → Expert Advisors
   - Make sure the URL `https://genesis.replit.app` is added to the "WebRequest allowed URLs" list
   - If it's not there, add it and click OK

5. **Attach to Chart**
   - Open any chart for a trading instrument (e.g., EURUSD, XAUUSD)
   - Drag and drop the newly compiled EA onto the chart
   - In the EA settings dialog, make sure:
     - Set the `ServerURL` to `https://genesis.replit.app`
     - Enter your `AccountID` if needed (or leave empty to use your account number)
     - Adjust other parameters if needed
   - Click OK to start the EA

6. **Verify Connection**
   - Check the "Experts" tab in MetaTrader 5 to see if any connection errors are reported
   - Go to your GENESIS platform website and refresh the trading history page
   - You should now see your actual trades being displayed

## Key Improvements

The updated EA implements the following improvements:

1. Proper trade data format in the JSON payload when sending updates to the server
2. Includes both open and recently closed trades from history
3. Better error handling and logging
4. More efficient handling of trade updates

## Troubleshooting

If you don't see your trades after updating:

1. Make sure the EA is running (green face icon in the upper right corner of the chart)
2. Check the "Experts" tab for any error messages
3. Verify that "Allow WebRequest for listed URL" is enabled and the correct URL is added
4. Try restarting MetaTrader 5
5. Check your internet connection

If problems persist, please contact support with any error messages from the "Experts" tab.