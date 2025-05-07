# GENESIS MT5 EA Installation Guide

## Introduction

This document provides step-by-step instructions for installing and configuring the MT5 GENESIS EA (Expert Advisor) that connects your MetaTrader 5 terminal to the GENESIS Trading Platform.

## Prerequisites

1. MetaTrader 5 terminal installed
2. Account with a broker (demo or live)
3. Basic knowledge of MetaTrader 5 operation

## Installation Steps

### 1. Download the Required Files

- Download the MT5_GENESIS_EA_Latest.mq5 file from the GENESIS Trading Platform
- Download the JAson.mqh library file if you don't already have it installed

### 2. Install the JAson Library

1. Open MetaTrader 5
2. Click on "File" > "Open Data Folder"
3. Navigate to "MQL5" > "Include"
4. Copy the JAson.mqh file into this folder

### 3. Install the EA

1. In MetaTrader 5, press F4 to open the MetaEditor
2. Click on "File" > "Open"
3. Navigate to the location where you downloaded the MT5_GENESIS_EA_Latest.mq5 file
4. Open the file
5. Click on "Compile" (F7) to compile the EA
6. If compilation is successful, you will see a message saying "0 errors, 0 warnings"

### 4. Configure the EA

1. Close the MetaEditor and return to MetaTrader 5
2. Click on "View" > "Navigator" (or press Ctrl+N)
3. Expand the "Expert Advisors" section in the Navigator panel
4. Find "MT5_GENESIS_EA_Latest" in the list
5. Drag and drop the EA onto any chart
6. A configuration window will appear

### 5. EA Settings

- **API_Key**: Leave blank (not currently used)
- **AccountName**: Enter your account name or ID for identification (can be any name you choose)
- **AutoTrade**: Set to true if you want the EA to automatically execute trades based on signals
- **SendReports**: Set to true to send trade reports back to GENESIS platform
- **LotMultiplier**: Adjust if you want to scale the position size (1.0 = use the exact lot size from signals)
- **SlippagePoints**: Maximum allowed slippage in points (10 is recommended)
- **SendHeartbeat**: Set to true to maintain connection with GENESIS platform

### 6. Activate the EA

1. Make sure the "AutoTrading" button in the top toolbar is enabled (should be green)
2. Click "OK" on the EA settings
3. The EA should now show a smiley face icon in the top-right corner of the chart
4. Check the "Experts" tab at the bottom of MetaTrader 5 to see if the EA is running correctly

### 7. Verify Connection

The EA will attempt to connect to the GENESIS platform immediately. Check the "Experts" log to see if the connection is successful. You should see messages like:

```
GENESIS EA starting up...
Found X active symbols in Market Watch
Heartbeat sent successfully. Server time: [timestamp]
```

## Troubleshooting

- If you see connection errors, make sure your internet connection is working
- Check that the GENESIS platform is online and accessible
- Ensure your broker allows EA operation and outgoing HTTP requests
- If compilation fails, make sure you have installed the JAson.mqh library correctly

## Important Notes

- The EA will send a heartbeat to the platform every 60 seconds to maintain connection
- It will check for new signals every 10 seconds
- Trade updates are sent every 20 seconds
- Account status updates are sent every 15 seconds

## Support

If you encounter any issues with the installation or operation of the EA, please contact GENESIS Trading Platform support.
