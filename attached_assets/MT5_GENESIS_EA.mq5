//+------------------------------------------------------------------+
//|                                             MT5_GENESIS_EA.mq5 |
//|                                       GENESIS Trading Platform |
//|                                                                |
//+------------------------------------------------------------------+
#property copyright "GENESIS Trading Platform"
#property link      ""
#property version   "1.00"
#property strict

// Include required libraries
#include <Trade/Trade.mqh>           // For trading operations
#include <Arrays/ArrayString.mqh>    // For string array operations
#include <JAson.mqh>                 // For JSON operations, needs to be installed
#include <StdLib.mqh>               // For ErrorDescription()

bool IsMarketOpenForSymbol(string symbol, bool force_execution=false);
// Constants
#define API_ENDPOINT "https://daff8876-e606-4c4e-9a8e-5e11d74ef5e3-00-1blloyttmbbgt.riker.replit.dev/mt5_ea_api"  // Replace with your GENESIS platform URL
#define API_TIMEOUT  5000            // Timeout for API requests in milliseconds
#define SIGNAL_CHECK_INTERVAL 10     // How often to check for new signals (seconds)
#define HEARTBEAT_INTERVAL 60        // How often to send heartbeat (seconds)

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
    
    // Create timer for checking signals and heartbeat
    EventSetTimer(1);  // 1 second timer
    
    // Mark initial setup as complete
    InitialSetupDone = true;
    
    // Clear any existing objects on the chart
    DeleteAllSignalArrows();
    return(INIT_SUCCEEDED);
    
    // Test arrow drawing
    Print("Testing signal arrow drawing functionality...");
    double currentPrice = SymbolInfoDouble(_Symbol, SYMBOL_BID);
    double arrowUp = currentPrice + 200 * Point();
    double arrowDown = currentPrice - 200 * Point();
    
    // Draw test arrows
    Print("Drawing test ANTICIPATED LONG arrow at price ", DoubleToString(arrowUp, Digits()));
    DrawSignalArrow(999, _Symbol, "ANTICIPATED LONG", arrowUp);
    
    Print("Drawing test ANTICIPATED SHORT arrow at price ", DoubleToString(arrowDown, Digits()));
    DrawSignalArrow(998, _Symbol, "ANTICIPATED SHORT", arrowDown);
    
    // Mark initial setup as complete
    InitialSetupDone = true;
    
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

// (original anticipated check removed)
// moved earlier

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
    
    if(direction == "BUY") {
        orderType = ORDER_TYPE_BUY;
        price = ask;
    }
    else if(direction == "SELL") {
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
                         double price, double sl, double tp, double volume)
{
    // Prepare JSON data
    JsonToSend.Clear();
    JsonToSend["signal_id"] = signalId;
    JsonToSend["ticket"] = ticket;
    JsonToSend["action"] = direction;
    JsonToSend["symbol"] = symbol;
    JsonToSend["price"] = price;
    JsonToSend["sl"] = sl;
    JsonToSend["tp"] = tp;
    JsonToSend["volume"] = volume;
    
    // Send request
    string jsonString = JsonToSend.Serialize();
    string response = "";
    
    bool success = SendPostRequest(API_ENDPOINT + "/report_trade", jsonString, response);
    
    if(success) {
        // Parse response
        JsonReceived.Clear();
        JsonReceived.Deserialize(response);
        
        if(JsonReceived["status"].ToStr() == "success") {
            Print("Trade reported successfully. Trade ID: ", JsonReceived["trade_id"].ToStr());
            return true;
        }
        else {
            Print("Error reporting trade: ", JsonReceived["message"].ToStr());
            return false;
        }
    }
    else {
        Print("Failed to send trade report");
        return false;
    }
}
//+------------------------------------------------------------------+
//| Report a failed trade to GENESIS platform                         |
//+------------------------------------------------------------------+
bool ReportFailedTradeToGenesis(int signalId, int errorCode, string symbol, string direction)
{
    // Prepare JSON data
    JsonToSend.Clear();
    JsonToSend["signal_id"] = signalId;
    JsonToSend["success"] = false;
    JsonToSend["error_code"] = errorCode;
    JsonToSend["error_description"] = ErrorDescription(errorCode);
    JsonToSend["symbol"] = symbol;
    JsonToSend["action"] = direction;
    JsonToSend["execution_time"] = TimeToString(TimeCurrent(), TIME_DATE|TIME_SECONDS);
    
    // Send request
    string jsonString = JsonToSend.Serialize();
    string response = "";
    
    bool success = SendPostRequest(API_ENDPOINT + "/report_trade", jsonString, response);
    
    if(success) {
        // Parse response
        JsonReceived.Clear();
        JsonReceived.Deserialize(response);
        
        if(JsonReceived["status"].ToStr() == "success") {
            Print("Failed trade reported successfully for signal ID: ", signalId);
            return true;
        }
        else {
            Print("Error reporting failed trade: ", JsonReceived["message"].ToStr());
            return false;
        }
    }
    else {
        Print("Failed to send failed trade report");
        return false;
    }
}

//+------------------------------------------------------------------+
//| Report a closed trade to GENESIS platform                        |
//+------------------------------------------------------------------+
bool ReportTradeCloseToGenesis(int ticket, double closePrice, double profit, string reason)
{
    // Prepare JSON data
    JsonToSend.Clear();
    JsonToSend["ticket"] = ticket;
    JsonToSend["close_price"] = closePrice;
    JsonToSend["profit"] = profit;
    JsonToSend["reason"] = reason;
    
    // Send request
    string jsonString = JsonToSend.Serialize();
    string response = "";
    
    bool success = SendPostRequest(API_ENDPOINT + "/report_close", jsonString, response);
    
    if(success) {
        // Parse response
        JsonReceived.Clear();
        JsonReceived.Deserialize(response);
        
        if(JsonReceived["status"].ToStr() == "success") {
            Print("Trade close reported successfully. Trade ID: ", JsonReceived["trade_id"].ToStr());
            return true;
        }
        else {
            Print("Error reporting trade close: ", JsonReceived["message"].ToStr());
            return false;
        }
    }
    else {
        Print("Failed to send trade close report");
        return false;
    }
}

//+------------------------------------------------------------------+
//| Report account info to GENESIS platform                          |
//+------------------------------------------------------------------+
bool ReportAccountInfoToGenesis()
{
    // Prepare JSON data
    JsonToSend.Clear();
    JsonToSend["account_id"] = AccountInfoString(ACCOUNT_NAME);
    JsonToSend["balance"] = AccountInfoDouble(ACCOUNT_BALANCE);
    JsonToSend["equity"] = AccountInfoDouble(ACCOUNT_EQUITY);
    JsonToSend["margin"] = AccountInfoDouble(ACCOUNT_MARGIN);
    JsonToSend["free_margin"] = AccountInfoDouble(ACCOUNT_MARGIN_FREE);
    
    // Send request
    string jsonString = JsonToSend.Serialize();
    string response = "";
    
    bool success = SendPostRequest(API_ENDPOINT + "/account_info", jsonString, response);
    
    if(success) {
        // Parse response
        JsonReceived.Clear();
        JsonReceived.Deserialize(response);
        
        if(JsonReceived["status"].ToStr() == "success") {
            Print("Account info reported successfully");
            return true;
        }
        else {
            Print("Error reporting account info: ", JsonReceived["message"].ToStr());
            return false;
        }
    }
    else {
        Print("Failed to send account info");
        return false;
    }
}

//+------------------------------------------------------------------+
//| Send POST request to API                                         |
//+------------------------------------------------------------------+
bool SendPostRequest(string url, string data, string &response)
{
    char requestData[];
    char responseData[];
    
    // Convert string to char array
    StringToCharArray(data, requestData, 0, StringLen(data));
    
    // Headers
    string headers = "Content-Type: application/json\r\n";
    headers += "X-API-Key: " + API_Key + "\r\n";
    
    // Create WebRequest object
    int res = WebRequest("POST", url, headers, API_TIMEOUT, requestData, responseData, headers);
    
    // Check result
    if(res == -1) {
        int errorCode = GetLastError();
        Print("HTTP request failed: Error=", errorCode, " Description=", ErrorDescription(errorCode));
        
        // Handle common errors
        if(errorCode == 4060) {
            Print("WebRequest permission not granted. Please allow URL: " + url);
            Alert("Please enable WebRequest for URL: " + url);
        }
        
        // Retry logic
        if(RetryCount < 3) {
            RetryCount++;
            Print("Retrying... (Attempt ", RetryCount, " of 3)");
            Sleep(1000); // Wait 1 second before retry
            return SendPostRequest(url, data, response);
        }
        
        RetryCount = 0;
        return false;
    }
    
    // Reset retry counter
    RetryCount = 0;
    
    // Convert response data to string
    response = CharArrayToString(responseData);
    
    return true;
}

//+------------------------------------------------------------------+
//| Check if market is open for trading                              |
//+------------------------------------------------------------------+
bool IsMarketOpenForSymbol(string symbol, bool force_execution=false)
{
   #ifdef TEST_MODE
      Print("Test mode enabled - bypassing market check for ", symbol);
      return true;
   #endif

   if(force_execution)
   {
      Print("Force execution enabled - bypassing market check for ", symbol);
      return true;
   }

   datetime sessionStart, sessionEnd;
   MqlDateTime dt; TimeToStruct(TimeCurrent(), dt);
   int day = dt.day_of_week;   // 0=Sunday

   for(uint i=0;; i++)
   {
      if(!SymbolInfoSessionTrade(symbol, (ENUM_DAY_OF_WEEK)day, i, sessionStart, sessionEnd))
         break;              // no more sessions
      if(TimeCurrent()>=sessionStart && TimeCurrent()<=sessionEnd)
         return true;        // inside a valid session
   }
   return false;
}

//+------------------------------------------------------------------+
//| Normalize volume according to symbol requirements                |
//+------------------------------------------------------------------+
double NormalizeVolume(string symbol, double volume)
{
    double minVolume = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
    double maxVolume = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MAX);
    double stepVolume = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
    
    // Ensure volume is at least the minimum
    volume = MathMax(volume, minVolume);
    
    // Ensure volume does not exceed maximum
    volume = MathMin(volume, maxVolume);
    
    // Round to the nearest step
    volume = MathRound(volume / stepVolume) * stepVolume;
    
    return NormalizeDouble(volume, 2);
}

//+------------------------------------------------------------------+
//| Get text description of deinitialization reason                  |
//+------------------------------------------------------------------+
string GetDeinitReasonText(int reason)
{
    switch(reason) {
        case REASON_PROGRAM:
            return "Program called ExpertRemove()";
        case REASON_REMOVE:
            return "Expert removed from chart";
        case REASON_RECOMPILE:
            return "Expert recompiled";
        case REASON_CHARTCHANGE:
            return "Symbol or timeframe changed";
        case REASON_CHARTCLOSE:
            return "Chart closed";
        case REASON_PARAMETERS:
            return "Parameters changed";
        case REASON_ACCOUNT:
            return "Account changed";
        case REASON_TEMPLATE:
            return "Template changed";
        case REASON_INITFAILED:
            return "OnInit() returned non-zero value";
        case REASON_CLOSE:
            return "Terminal closed";
        default:
            return "Unknown reason: " + IntegerToString(reason);
    }
}

//+------------------------------------------------------------------+//+------------------------------------------------------------------+
//| Draw a signal arrow on the chart                                 |
//+------------------------------------------------------------------+
void DrawSignalArrow(int signalId, string symbol, string direction, double price)
{
    // Only draw signals on matching chart symbols
    if(symbol != _Symbol)
    {
        Print("Not drawing signal arrow for ", symbol, " on ", _Symbol, " chart (symbol mismatch)");
        return;
    }

    // Determine if this is an anticipated signal
    bool isAnticipated = StringFind(direction, "ANTICIPATED") >= 0;

    // We only draw arrows for anticipated signals
    if(!isAnticipated)
        return;

    string objName = ArrowPrefix + IntegerToString(signalId);

    // Delete any existing arrow with the same name
    ObjectDelete(0, objName);

    // Determine the arrow type and color
    uchar arrowCode;
    color arrowColor;

    if(StringFind(direction, "LONG") >= 0)
    {
        arrowCode = 233; // Up arrow
        arrowColor = AnticipatedLongColor;
        Alert("ANTICIPATED LONG signal ", signalId, " for ", symbol);
    }
    else if(StringFind(direction, "SHORT") >= 0)
    {
        arrowCode = 234; // Down arrow
        arrowColor = AnticipatedShortColor;
        Alert("ANTICIPATED SHORT signal ", signalId, " for ", symbol);
    }
    else
    {
        // Unknown direction
        return;
    }

    // Convert price to chart coordinates
    double y = price;

    // Add offset for better visibility
    if(arrowCode == 233)
        y -= ArrowOffset * Point(); // Up arrow, place below the price
    else
        y += ArrowOffset * Point(); // Down arrow, place above the price

    // Create the arrow object
    if(ObjectCreate(0, objName, OBJ_ARROW, 0, TimeCurrent(), y))
    {
        ObjectSetInteger(0, objName, OBJPROP_ARROWCODE, arrowCode);
        ObjectSetInteger(0, objName, OBJPROP_COLOR, arrowColor);
        ObjectSetInteger(0, objName, OBJPROP_WIDTH, ArrowSize);
        ObjectSetInteger(0, objName, OBJPROP_BACK, false);
        ObjectSetInteger(0, objName, OBJPROP_SELECTABLE, false);
        ObjectSetString(0, objName, OBJPROP_TEXT, direction + " #" + IntegerToString(signalId));
        Print("Drew ", direction, " arrow for signal ", signalId, " on ", symbol, " chart at price ", DoubleToString(price, _Digits));
        ChartRedraw();
    }
    else
    {
        Print("Failed to create arrow for signal ", signalId, ": ", GetLastError());
    }
}

void DeleteAllSignalArrows()
{
    for(int i = ObjectsTotal(0, 0, OBJ_ARROW) - 1; i >= 0; i--) {
        string objName = ObjectName(0, i, 0, OBJ_ARROW);

        if(StringFind(objName, ArrowPrefix) == 0) {
            ObjectDelete(0, objName);
        }
    }

    ChartRedraw();
    Print("Cleared all signal arrows from the chart");
}
//+------------------------------------------------------------------+