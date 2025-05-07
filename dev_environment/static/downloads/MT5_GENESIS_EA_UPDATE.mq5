//+------------------------------------------------------------------+
//|                                             MT5_GENESIS_EA.mq5 |
//|                                       GENESIS Trading Platform |
//|                                                                |
//+------------------------------------------------------------------+
#property copyright "GENESIS Trading Platform"
#property link      ""
#property version   "1.01"
#property strict

// Include required libraries
#include <Trade/Trade.mqh>           // For trading operations
#include <Arrays/ArrayString.mqh>    // For string array operations
#include <JAson.mqh>                 // For JSON operations, needs to be installed
#include <StdLib.mqh>               // For ErrorDescription()

bool IsMarketOpenForSymbol(string symbol, bool force_execution=false);
// Constants
#define API_ENDPOINT "https://4c1f2076-899e-4ced-962a-2903ca4a9bac-00-29hcpk84r1chm.picard.replit.dev/mt5_ea_api"  // Replace with your GENESIS platform URL
#define API_TIMEOUT  5000            // Timeout for API requests in milliseconds
#define SIGNAL_CHECK_INTERVAL 10     // How often to check for new signals (seconds)
#define HEARTBEAT_INTERVAL 60        // How often to send heartbeat (seconds)
#define ACCOUNT_UPDATE_INTERVAL 15   // How often to update account status (seconds)
#define TRADES_UPDATE_INTERVAL 20    // How often to update trades (seconds)

// Input parameters
input string   API_Key      = "";    // API Key for authentication
input string   AccountName  = "";    // Account name/identifier
input bool     AutoTrade    = true;  // Automatically execute trades
input bool     SendReports  = true;  // Send trade reports back to GENESIS
input double   LotMultiplier = 1.0;  // Multiplier for lot size from signals
input int      SlippagePoints = 10;  // Maximum allowed slippage in points
input bool     SendHeartbeat = true; // Send heartbeat to GENESIS platform

// Global variables
CTrade         Trade;                // Trading object
CJAVal         JsonToSend;           // JSON object for sending data
CJAVal         JsonReceived;         // JSON object for receiving data
int            LastSignalId = 0;     // Last processed signal ID
datetime       LastSignalCheck = 0;  // Last time signals were checked
datetime       LastHeartbeat = 0;    // Last time heartbeat was sent
datetime       LastAccountUpdate = 0; // Last time account status was updated
datetime       LastTradesUpdate = 0;  // Last time trades were updated
string         ActiveSymbols[];      // List of symbols in Market Watch
int            RetryCount = 0;       // Counter for API retry attempts
bool           InitialSetupDone = false; // Flag for initial setup
int            TerminalNumber = 0;   // Unique identifier for this terminal


// Global variables for signal arrows
color    AnticipatedLongColor = clrDodgerBlue;    // Color for anticipated long signals
color    AnticipatedShortColor = clrCrimson;      // Color for anticipated short signals
int      ArrowSize = 3;                           // Size of the signal arrows
int      ArrowOffset = 5;                         // Offset from price in points
string   ArrowPrefix = "GENESIS_Arrow_";         // Prefix for arrow objects


//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
    // Print startup message
    Print("GENESIS EA starting up...");
    
    // Generate a unique terminal identifier
    TerminalNumber = MathRand();
    
    // Set up trading parameters
    Trade.SetDeviationInPoints(SlippagePoints);
    Trade.SetExpertMagicNumber(123456); // Set a unique magic number
    
    // Get all symbols in Market Watch
    GetActiveSymbols();
    
    // Initialize JSON object
    JsonToSend.Clear();
    
    // Send initial heartbeat
    if(SendHeartbeat) {
        SendHeartbeatToGenesis();
    }
    
    // Send initial account status update
    UpdateAccountStatus();
    
    // Send initial trades update
    UpdateTrades();
    
    // Create timer for checking signals and heartbeat
    EventSetTimer(1);  // 1 second timer
    
    // Mark initial setup as complete
    InitialSetupDone = true;
    
    // Clear any existing objects on the chart
    DeleteAllSignalArrows();
    return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
    // Delete timer
    EventKillTimer();
    
    // Print shutdown message
    Print("GENESIS EA shutting down, reason: ", GetDeinitReasonText(reason));
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
    // Main trading logic happens in OnTimer
}

//+------------------------------------------------------------------+
//| Timer function                                                   |
//+------------------------------------------------------------------+
void OnTimer()
{
    // Check if it's time for a heartbeat
    if(SendHeartbeat && (TimeCurrent() - LastHeartbeat) >= HEARTBEAT_INTERVAL) {
        SendHeartbeatToGenesis();
        LastHeartbeat = TimeCurrent();
    }
    
    // Check if it's time to update account status
    if((TimeCurrent() - LastAccountUpdate) >= ACCOUNT_UPDATE_INTERVAL) {
        UpdateAccountStatus();
        LastAccountUpdate = TimeCurrent();
    }
    
    // Check if it's time to update trades
    if((TimeCurrent() - LastTradesUpdate) >= TRADES_UPDATE_INTERVAL) {
        UpdateTrades();
        LastTradesUpdate = TimeCurrent();
    }
    
    // Check if it's time to check for new signals
    if((TimeCurrent() - LastSignalCheck) >= SIGNAL_CHECK_INTERVAL) {
        GetNewSignalsFromGenesis();
        LastSignalCheck = TimeCurrent();
    }
}

//+------------------------------------------------------------------+
//| Get all active symbols from Market Watch                         |
//+------------------------------------------------------------------+
void GetActiveSymbols()
{
    int symbolsTotal = SymbolsTotal(true);
    ArrayResize(ActiveSymbols, symbolsTotal);
    
    for(int i = 0; i < symbolsTotal; i++) {
        ActiveSymbols[i] = SymbolName(i, true);
    }
    
    Print("Found ", symbolsTotal, " active symbols in Market Watch");
}

//+------------------------------------------------------------------+
//| Send heartbeat to GENESIS platform                               |
//+------------------------------------------------------------------+
bool SendHeartbeatToGenesis()
{
    // Prepare JSON data
    JsonToSend.Clear();
    JsonToSend["account_id"] = AccountInfoString(ACCOUNT_NAME);
    JsonToSend["terminal_id"] = IntegerToString(TerminalNumber);
    JsonToSend["connection_time"] = TimeToString(TimeCurrent(), TIME_DATE|TIME_SECONDS);
    
    // Send request
    string jsonString = JsonToSend.Serialize();
    string response = "";
    
    bool success = SendPostRequest(API_ENDPOINT + "/heartbeat", jsonString, response);
    
    if(success) {
        // Parse response
        JsonReceived.Clear();
        JsonReceived.Deserialize(response);
        
        if(JsonReceived["status"].ToStr() == "success") {
            Print("Heartbeat sent successfully. Server time: ", JsonReceived["server_time"].ToStr());
            return true;
        }
        else {
            Print("Error sending heartbeat: ", JsonReceived["message"].ToStr());
            return false;
        }
    }
    else {
        Print("Failed to send heartbeat request");
        return false;
    }
}

//+------------------------------------------------------------------+
//| Update account status to GENESIS platform                          |
//+------------------------------------------------------------------+
bool UpdateAccountStatus()
{
    // Prepare JSON data for account status
    JsonToSend.Clear();
    JsonToSend["account_id"] = AccountInfoString(ACCOUNT_NAME);
    JsonToSend["balance"] = AccountInfoDouble(ACCOUNT_BALANCE);
    JsonToSend["equity"] = AccountInfoDouble(ACCOUNT_EQUITY);
    JsonToSend["margin"] = AccountInfoDouble(ACCOUNT_MARGIN);
    JsonToSend["free_margin"] = AccountInfoDouble(ACCOUNT_MARGIN_FREE);
    JsonToSend["leverage"] = AccountInfoInteger(ACCOUNT_LEVERAGE);
    JsonToSend["open_positions"] = PositionsTotal();
    
    // Send request
    string jsonString = JsonToSend.Serialize();
    string response = "";
    
    Print("Sending account status update: ", jsonString);
    bool success = SendPostRequest(API_ENDPOINT + "/account_status", jsonString, response);
    
    if(success) {
        // Parse response
        JsonReceived.Clear();
        JsonReceived.Deserialize(response);
        
        if(JsonReceived["status"].ToStr() == "success") {
            Print("Account status update sent successfully.");
            return true;
        }
        else {
            Print("Error sending account status: ", JsonReceived["message"].ToStr());
            return false;
        }
    }
    else {
        Print("Failed to send account status update request");
        return false;
    }
}

//+------------------------------------------------------------------+
//| Update trades to GENESIS platform                               |
//+------------------------------------------------------------------+
bool UpdateTrades()
{
    // Prepare JSON data
    JsonToSend.Clear();
    JsonToSend["account_id"] = AccountInfoString(ACCOUNT_NAME);
    
    // Create JSON object for trades
    CJAVal trades;
    trades.Clear();
    
    // Loop through all open positions
    int totalPositions = PositionsTotal();
    Print("Total positions to report: ", totalPositions);
    
    for(int i = 0; i < totalPositions; i++) {
        // Get position information
        ulong ticket = PositionGetTicket(i);
        if(!PositionSelectByTicket(ticket)) continue;
        
        // Get position details
        string symbol = PositionGetString(POSITION_SYMBOL);
        double volume = PositionGetDouble(POSITION_VOLUME);
        double price_open = PositionGetDouble(POSITION_PRICE_OPEN);
        double price_current = PositionGetDouble(POSITION_PRICE_CURRENT);
        double sl = PositionGetDouble(POSITION_SL);
        double tp = PositionGetDouble(POSITION_TP);
        double profit = PositionGetDouble(POSITION_PROFIT);
        double swap = PositionGetDouble(POSITION_SWAP);
        double commission = 0; // Not directly available in MT5
        datetime time_open = (datetime)PositionGetInteger(POSITION_TIME);
        ENUM_POSITION_TYPE type = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
        
        string side = (type == POSITION_TYPE_BUY) ? "BUY" : "SELL";
        string status = "OPEN"; // Since we're looping through open positions
        
        // Create trade object
        CJAVal trade;
        trade.Clear();
        trade["ticket"] = IntegerToString(ticket);
        trade["symbol"] = symbol;
        trade["volume"] = DoubleToString(volume, 2);
        trade["price_open"] = DoubleToString(price_open, _Digits);
        trade["price_current"] = DoubleToString(price_current, _Digits);
        trade["sl"] = (sl == 0.0) ? "" : DoubleToString(sl, _Digits);
        trade["tp"] = (tp == 0.0) ? "" : DoubleToString(tp, _Digits);
        trade["profit"] = DoubleToString(profit, 2);
        trade["swap"] = DoubleToString(swap, 2);
        trade["commission"] = DoubleToString(commission, 2);
        trade["time_open"] = TimeToString(time_open, TIME_DATE|TIME_SECONDS);
        trade["side"] = side;
        trade["status"] = status;
        
        // Add to trades array using ticket as key
        trades[IntegerToString(ticket)] = trade;
    }
    
    // Add trades object to main JSON
    JsonToSend["trades"] = trades;
    
    // Send request
    string jsonString = JsonToSend.Serialize();
    string response = "";
    
    Print("Sending trades update: ", jsonString);
    bool success = SendPostRequest(API_ENDPOINT + "/update_trades", jsonString, response);
    
    if(success) {
        // Parse response
        JsonReceived.Clear();
        JsonReceived.Deserialize(response);
        
        if(JsonReceived["status"].ToStr() == "success") {
            Print("Trades update sent successfully. Updated ", JsonReceived["updated_count"].ToInt(), " trades.");
            return true;
        }
        else {
            Print("Error sending trades update: ", JsonReceived["message"].ToStr());
            return false;
        }
    }
    else {
        Print("Failed to send trades update request");
        return false;
    }
}

//+------------------------------------------------------------------+
//| Get new signals from GENESIS platform                            |
//+------------------------------------------------------------------+
void GetNewSignalsFromGenesis()
{
    // More detailed logging about API call
    Print("Attempting to get signals from URL: ", API_ENDPOINT, "/get-signals");

    // Prepare JSON data
    JsonToSend.Clear();
    JsonToSend["account_id"] = AccountInfoString(ACCOUNT_NAME);
    JsonToSend["last_signal_id"] = LastSignalId;
    
    // Create a JSON array with active symbols
    CJAVal symbolsArray;
    symbolsArray.Clear();
    for(int i = 0; i < ArraySize(ActiveSymbols); i++) {
        symbolsArray.Add(NULL, ActiveSymbols[i]);
    }
    JsonToSend["symbols"] = symbolsArray;
    
    // Send request
    string jsonString = JsonToSend.Serialize();
    string response = "";
    
    bool success = SendPostRequest(API_ENDPOINT + "/get_signals", jsonString, response);
    
    if(success) {
        // Parse response
        JsonReceived.Clear();
        JsonReceived.Deserialize(response);
        
        if(JsonReceived["status"].ToStr() == "success") {
            // Process signals
            CJAVal signals = JsonReceived["signals"];
            int signalsCount = signals.Size();
            
            Print("Received ", signalsCount, " new signals");
            
            for(int i = 0; i < signalsCount; i++) {

                CJAVal signal = signals[i];
                
                // Get signal data
                int signalId = (int)signal["id"].ToInt();
                string symbol = signal["asset"]["symbol"].ToStr();
                string direction = signal["action"].ToStr();
                double entry = signal["entry_price"].ToDbl();
                double stopLoss = signal["stop_loss"].ToDbl();
                double takeProfit = signal["take_profit"].ToDbl();
                double confidence = signal["confidence"].ToDbl();
                double lotSize = signal["position_size"].ToDbl() * LotMultiplier;
                bool force_execution = signal["force_execution"].ToBool();


                
                // Keep track of the highest signal ID
                if(signalId > LastSignalId) {
                    LastSignalId = signalId;
                }
                
                // Log detailed info about each signal AFTER extraction
                PrintFormat("Processing signal %d of %d:", i+1, signalsCount);
                Print("  ID: ", signalId);
                Print("  Symbol: ", symbol);
                Print("  Action: ", direction);
                Print("  Entry: ", DoubleToString(entry, _Digits));
                Print("  Stop Loss: ", DoubleToString(stopLoss, _Digits));
                Print("  Take Profit: ", DoubleToString(takeProfit, _Digits));
                // Check if we should trade this signal
                if(AutoTrade) {
                    ProcessTradeSignal(signalId, symbol, direction, entry, stopLoss, takeProfit, lotSize, force_execution);
                }
                else {
                    // Just print the signal
                    Print("Signal: ID=", signalId, " Symbol=", symbol, " Direction=", direction, 
                          " Entry=", entry, " SL=", stopLoss, " TP=", takeProfit,
                          " Confidence=", confidence, " Lot=", lotSize);
                          
                    // Alert the user
                    string alertMessage = StringFormat("GENESIS SIGNAL\nSymbol: %s\nDirection: %s\nEntry: %.4f\nSL: %.4f\nTP: %.4f", 
                                                      symbol, direction, entry, stopLoss, takeProfit);
                    Alert(alertMessage);
                }
            }
        }
        else {
            Print("Error getting signals: ", JsonReceived["message"].ToStr());
        }
    }
    else {
        Print("Failed to send signal request");
    }
}

//+------------------------------------------------------------------+
//| Process a trade signal and execute it                            |
//+------------------------------------------------------------------+
void ProcessTradeSignal(int signalId, string symbol, string direction, double entry, double stopLoss, double takeProfit, double lotSize, bool force_execution=false)
{
    bool isAnticipated = StringFind(direction, "ANTICIPATED") >= 0;
    // Detailed logging for signal processing
    Print("ProcessTradeSignal called: ID=", signalId, " Symbol=", symbol, " Direction=", direction, 
          " Entry=", DoubleToString(entry, _Digits), " SL=", stopLoss, " TP=", takeProfit, 
          " Lot=", lotSize, " force_execution=", force_execution);
    // moved earlier
    Print("Is Anticipated Signal: ", isAnticipated ? "YES" : "NO", " (", direction, ")");

    // Draw anticipated signal arrows on the chart
    if(isAnticipated) {
        DrawSignalArrow(signalId, symbol, direction, entry);
    }

    // Skip trade execution for anticipated signals
    if(isAnticipated) {
        Print("Anticipated signal: ID=", signalId, " Symbol=", symbol, " Direction=", direction, 
              " Entry=", entry, " SL=", stopLoss, " TP=", takeProfit);

        // Alert the user
        string alertMessage = StringFormat("GENESIS ANTICIPATED SIGNAL\nSymbol: %s\nDirection: %s\nEntry: %.4f\nSL: %.4f\nTP: %.4f", 
                                          symbol, direction, entry, stopLoss, takeProfit);
        Alert(alertMessage);
        return;
    }
    // Check if symbol exists
    if(!SymbolSelect(symbol, true)) {
        Print("Symbol ", symbol, " not found in Market Watch");
        return;
    }
    
    // Check if we're within trading hours
    if(!IsMarketOpenForSymbol(symbol, force_execution)) {
        Print("Market is closed for ", symbol);
        return;
    }
    
    // Get current market price
    double bid = SymbolInfoDouble(symbol, SYMBOL_BID);
    double ask = SymbolInfoDouble(symbol, SYMBOL_ASK);
    
    // Adjust lot size to symbol requirements
    lotSize = NormalizeVolume(symbol, lotSize);
    
    // Determine trade type
    ENUM_ORDER_TYPE orderType;
    double price;
    
    if(direction == "BUY" || direction == "BUY_NOW") {
        orderType = ORDER_TYPE_BUY;
        price = ask;
    }
    else if(direction == "SELL" || direction == "SELL_NOW") {
        orderType = ORDER_TYPE_SELL;
        price = bid;
    }
    else {
        Print("Unknown direction: ", direction);
        return;
    }
    
    // Execute the trade
    bool result = Trade.PositionOpen(
        symbol,
        orderType,
        lotSize,
        price,
        stopLoss,
        takeProfit,
        "GENESIS-" + IntegerToString(signalId)
    );
    
    if(result) {
        int ticket = (int)Trade.ResultOrder();
        Print("Trade executed: Ticket=", ticket, " Symbol=", symbol, " Type=", EnumToString(orderType), 
              " Volume=", lotSize, " Price=", price, " SL=", stopLoss, " TP=", takeProfit);
              
        // Report trade to GENESIS
        if(SendReports) {
            ReportTradeToGenesis(signalId, ticket, symbol, direction, price, stopLoss, takeProfit, lotSize);
        }
    }
    else {
        int errorCode = GetLastError();
        Print("Trade execution failed: Error=", errorCode, " Description=", ErrorDescription(errorCode));
        
        // Report failed trade to GENESIS
        if(SendReports) {
            ReportFailedTradeToGenesis(signalId, errorCode, symbol, direction);
        }
    }
}

//+------------------------------------------------------------------+
//| Report a trade to GENESIS platform                               |
//+------------------------------------------------------------------+
bool ReportTradeToGenesis(int signalId, int ticket, string symbol, string direction, 
                         double price, double stopLoss, double takeProfit, double lotSize)
{
    // Prepare JSON data
    JsonToSend.Clear();
    JsonToSend["account_id"] = AccountInfoString(ACCOUNT_NAME);
    JsonToSend["signal_id"] = signalId;
    JsonToSend["ticket"] = ticket;
    JsonToSend["symbol"] = symbol;
    JsonToSend["direction"] = direction;
    JsonToSend["price"] = price;
    JsonToSend["stop_loss"] = stopLoss;
    JsonToSend["take_profit"] = takeProfit;
    JsonToSend["lot_size"] = lotSize;
    JsonToSend["status"] = "OPEN";
    JsonToSend["open_time"] = TimeToString(TimeCurrent(), TIME_DATE|TIME_SECONDS);
    
    // Send request
    string jsonString = JsonToSend.Serialize();
    string response = "";
    
    bool success = SendPostRequest(API_ENDPOINT + "/trade_report", jsonString, response);
    
    if(success) {
        // Parse response
        JsonReceived.Clear();
        JsonReceived.Deserialize(response);
        
        if(JsonReceived["status"].ToStr() == "success") {
            Print("Trade report sent successfully");
            return true;
        }
        else {
            Print("Error sending trade report: ", JsonReceived["message"].ToStr());
            return false;
        }
    }
    else {
        Print("Failed to send trade report request");
        return false;
    }
}

//+------------------------------------------------------------------+
//| Report a failed trade to GENESIS platform                        |
//+------------------------------------------------------------------+
bool ReportFailedTradeToGenesis(int signalId, int errorCode, string symbol, string direction)
{
    // Prepare JSON data
    JsonToSend.Clear();
    JsonToSend["account_id"] = AccountInfoString(ACCOUNT_NAME);
    JsonToSend["signal_id"] = signalId;
    JsonToSend["symbol"] = symbol;
    JsonToSend["direction"] = direction;
    JsonToSend["error_code"] = errorCode;
    JsonToSend["error_description"] = ErrorDescription(errorCode);
    JsonToSend["status"] = "FAILED";
    
    // Send request
    string jsonString = JsonToSend.Serialize();
    string response = "";
    
    bool success = SendPostRequest(API_ENDPOINT + "/trade_report", jsonString, response);
    
    if(success) {
        // Parse response
        JsonReceived.Clear();
        JsonReceived.Deserialize(response);
        
        if(JsonReceived["status"].ToStr() == "success") {
            Print("Failed trade report sent successfully");
            return true;
        }
        else {
            Print("Error sending failed trade report: ", JsonReceived["message"].ToStr());
            return false;
        }
    }
    else {
        Print("Failed to send failed trade report request");
        return false;
    }
}

//+------------------------------------------------------------------+
//| Draw a signal arrow on the chart                                 |
//+------------------------------------------------------------------+
void DrawSignalArrow(int signalId, string symbol, string direction, double price)
{
    // Set the arrow code and color based on signal direction
    uchar arrowCode;
    color arrowColor;
    
    if(StringFind(direction, "LONG") >= 0 || StringFind(direction, "BUY") >= 0) {
        arrowCode = 233; // Up arrow
        arrowColor = AnticipatedLongColor;
    }
    else if(StringFind(direction, "SHORT") >= 0 || StringFind(direction, "SELL") >= 0) {
        arrowCode = 234; // Down arrow
        arrowColor = AnticipatedShortColor;
    }
    else {
        Print("Unknown direction for arrow: ", direction);
        return;
    }
    
    // Create a unique name for the arrow object
    string arrowName = ArrowPrefix + IntegerToString(signalId);
    
    // Calculate arrow position time (current bar)
    datetime time = iTime(symbol, 0, 0);
    
    // Set position for the arrow
    double arrowPrice;
    if(StringFind(direction, "LONG") >= 0 || StringFind(direction, "BUY") >= 0) {
        // For long signals, place arrow below the price
        arrowPrice = price - (ArrowOffset * SymbolInfoDouble(symbol, SYMBOL_POINT));
    }
    else {
        // For short signals, place arrow above the price
        arrowPrice = price + (ArrowOffset * SymbolInfoDouble(symbol, SYMBOL_POINT));
    }
    
    // Create arrow object
    if(ObjectCreate(0, arrowName, OBJ_ARROW, 0, time, arrowPrice)) {
        ObjectSetInteger(0, arrowName, OBJPROP_ARROWCODE, arrowCode);
        ObjectSetInteger(0, arrowName, OBJPROP_COLOR, arrowColor);
        ObjectSetInteger(0, arrowName, OBJPROP_WIDTH, ArrowSize);
        ObjectSetInteger(0, arrowName, OBJPROP_SELECTABLE, false);
        ObjectSetString(0, arrowName, OBJPROP_TOOLTIP, direction + " Signal #" + IntegerToString(signalId));
        ObjectSetInteger(0, arrowName, OBJPROP_ZORDER, 100); // Bring to front
        
        // Set anchor point based on direction
        if(StringFind(direction, "LONG") >= 0 || StringFind(direction, "BUY") >= 0) {
            ObjectSetInteger(0, arrowName, OBJPROP_ANCHOR, ANCHOR_TOP);
        }
        else {
            ObjectSetInteger(0, arrowName, OBJPROP_ANCHOR, ANCHOR_BOTTOM);
        }
        
        Print("Created signal arrow ", arrowName, " at price ", DoubleToString(arrowPrice, _Digits));
    }
    else {
        Print("Failed to create signal arrow ", arrowName, ". Error: ", GetLastError());
    }
}

//+------------------------------------------------------------------+
//| Delete all signal arrows from the chart                          |
//+------------------------------------------------------------------+
void DeleteAllSignalArrows()
{
    int totalObjects = ObjectsTotal(0);
    
    for(int i = totalObjects - 1; i >= 0; i--) {
        string objectName = ObjectName(0, i);
        
        if(StringFind(objectName, ArrowPrefix) == 0) {
            ObjectDelete(0, objectName);
        }
    }
    
    Print("Cleared all signal arrows from chart");
}

//+------------------------------------------------------------------+
//| Send a POST request to the GENESIS API                           |
//+------------------------------------------------------------------+
bool SendPostRequest(string url, string postData, string &response)
{
    Print("Sending POST request to: ", url);
    Print("POST data: ", postData);
    
    char data[];
    ArrayResize(data, StringToCharArray(postData, data, 0, WHOLE_ARRAY, CP_UTF8) - 1);
    
    char result[];
    string result_headers;
    string sHeaders = "Content-Type: application/json\r\n";
    int timeout = API_TIMEOUT;
    
    int res = WebRequest("POST", url, sHeaders, timeout, data, result, result_headers);
    
    if(res != -1) { // -1 means error
        response = CharArrayToString(result, 0, WHOLE_ARRAY, CP_UTF8);
        Print("WebRequest response code: ", res);
        Print("Response headers: ", result_headers);
        Print("Response body: ", response);
        return true;
    }
    else {
        int errorCode = GetLastError();
        Print("WebRequest failed with error: ", errorCode, " - ", ErrorDescription(errorCode));
        
        if(errorCode == 4060) {
            Print("WARNING: URL access may be disabled. Please go to Tools -> Options -> Expert Advisors and check 'Allow WebRequest for listed URL:');
            Print("Add URL: ", url);
        }
        
        return false;
    }
}

//+------------------------------------------------------------------+
//| Normalize volume according to symbol settings                    |
//+------------------------------------------------------------------+
double NormalizeVolume(string symbol, double volume)
{
    double min_vol = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
    double max_vol = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MAX);
    double step = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
    
    // Ensure volume is between min and max
    volume = MathMax(min_vol, MathMin(max_vol, volume));
    
    // Round to the nearest step
    volume = MathRound(volume / step) * step;
    
    return volume;
}

//+------------------------------------------------------------------+
//| Get descriptive text for expert deinitialization reason          |
//+------------------------------------------------------------------+
string GetDeinitReasonText(int reason)
{
    switch(reason) {
        case REASON_PROGRAM:     return "Program called by ExpertRemove()";
        case REASON_REMOVE:      return "Expert removed from chart";
        case REASON_RECOMPILE:   return "Expert recompiled";
        case REASON_CHARTCHANGE: return "Symbol or timeframe changed";
        case REASON_CHARTCLOSE:  return "Chart closed";
        case REASON_PARAMETERS:  return "Input parameters changed";
        case REASON_ACCOUNT:     return "Account changed";
        case REASON_TEMPLATE:    return "New template applied";
        case REASON_INITFAILED:  return "OnInit() handler returned non-zero value";
        case REASON_CLOSE:       return "Terminal closed";
        default:                 return "Unknown reason: " + IntegerToString(reason);
    }
}

//+------------------------------------------------------------------+
//| Check if market is open for a specific symbol                   |
//+------------------------------------------------------------------+
bool IsMarketOpenForSymbol(string symbol, bool force_execution=false)
{
    // First, check if it's a Bitcoin symbol which can be traded on weekends
    if(StringFind(symbol, "BTC") >= 0 || 
       StringFind(symbol, "Bitcoin") >= 0 || 
       StringFind(symbol, "XBT") >= 0 || 
       StringFind(symbol, "BTCUSD") >= 0) {
        return true;  // Bitcoin markets run 24/7
    }
    
    // For forced execution, skip the check
    if(force_execution) {
        Print("Force execution enabled for ", symbol, ", bypassing market hours check");
        return true;
    }
    
    // Get the current day of week
    datetime current_time = TimeCurrent();
    int dayOfWeek = TimeDayOfWeek(current_time);
    
    // If it's Saturday or Sunday, markets are generally closed
    if(dayOfWeek == 0 || dayOfWeek == 6) { // 0 = Sunday, 6 = Saturday
        Print("Weekend market closure detected for ", symbol);
        return false;
    }
    
    // Check if the symbol trading is allowed at the current time
    // Using MQL5 specific function
    return (bool)SymbolInfoInteger(symbol, SYMBOL_TRADE_MODE) == SYMBOL_TRADE_MODE_FULL;
}
