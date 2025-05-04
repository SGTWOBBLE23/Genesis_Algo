
//+------------------------------------------------------------------+
//| Return symbol's digits                                           |
//+------------------------------------------------------------------+
int GetSymbolDigits(const string sym)
{
    int digits = (int)SymbolInfoInteger(sym, SYMBOL_DIGITS);
    if(digits < 0)
        digits = _Digits;
    return digits;
}
//+------------------------------------------------------------------+

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
//--- Updated API constants 2025-05-03
#define API_ENDPOINT "https://4c1f2076-899e-4ced-962a-2903ca4a9bac-00-29hcpk84r1chm.picard.replit.dev"
#define MT5_API_PATH "/mt5"
#define GET_SIGNALS_PATH "/get_signals"
#define HEARTBEAT_PATH "/heartbeat"
#define ACCOUNT_STATUS_PATH "/account_status"
#define TRADE_UPDATE_PATH "/update_trades"
#define TRADE_REPORT_PATH "/trade_report"
const string SIGNALS_URL      = API_ENDPOINT + MT5_API_PATH + GET_SIGNALS_PATH;
const string HEARTBEAT_URL    = API_ENDPOINT + MT5_API_PATH + HEARTBEAT_PATH;
const string ACCOUNT_STATUS_URL = API_ENDPOINT + MT5_API_PATH + ACCOUNT_STATUS_PATH;
const string TRADE_UPDATE_URL   = API_ENDPOINT + MT5_API_PATH + TRADE_UPDATE_PATH;
const string TRADE_REPORT_URL   = API_ENDPOINT + MT5_API_PATH + TRADE_REPORT_PATH;

bool IsMarketOpenForSymbol(string symbol, bool force_execution=false);
// Constants
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
    // Send account status every 15 seconds
    static datetime LastAccountUpdate = 0;
    if((TimeCurrent() - LastAccountUpdate) >= 15) {
        SendAccountStatus();
        LastAccountUpdate = TimeCurrent();
    }

    // Send trade updates every 20 seconds
    static datetime LastTradeUpdate = 0;
    if((TimeCurrent() - LastTradeUpdate) >= 20) {
        SendTradeUpdates();
        LastTradeUpdate = TimeCurrent();
    }

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
    JsonToSend["account_id"] = AccountName;
    JsonToSend["terminal_id"] = IntegerToString(TerminalNumber);
    JsonToSend["connection_time"] = TimeToString(TimeCurrent(), TIME_DATE|TIME_SECONDS);
    
    // Send request
    string jsonString = JsonToSend.Serialize();
    string response = "";
    
    bool success = SendPostRequest(HEARTBEAT_URL, jsonString, response);
    
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
    Print("Attempting to get signals from URL: ", SIGNALS_URL);

    // Prepare JSON data
    JsonToSend.Clear();
    JsonToSend["account_id"] = AccountName;
    JsonToSend["last_signal_id"] = LastSignalId;
    
    // Create a JSON array with active symbols
    CJAVal symbolsArray;
    symbolsArray.Clear();
    for(int i = 0; i < ArraySize(ActiveSymbols); i++) {
        symbolsArray.Add(ActiveSymbols[i]);
    }
    JsonToSend["symbols"] = symbolsArray;
    
    // Send request
    string jsonString = JsonToSend.Serialize();
    string response = "";
    
    bool success = SendPostRequest(SIGNALS_URL, jsonString, response);
    
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
          " Lot=", lotSize, " Anticipated=", isAnticipated);
    
    // Check if symbol is valid
    if(!SymbolSelect(symbol, true)) {
        Print("Symbol ", symbol, " is not available. Signal cannot be processed.");
        if(SendReports) {
            SendTradeReport(signalId, symbol, direction, 0, 0, 0, 0, 0, "error", "Symbol not found");
        }
        return;
    }
    
    // Check if market is open for this symbol
    if(!IsMarketOpenForSymbol(symbol, force_execution)) {
        Print("Market for ", symbol, " is closed. Signal will be executed when market opens.");
        if(SendReports) {
            SendTradeReport(signalId, symbol, direction, 0, 0, 0, 0, 0, "pending", "Market closed");
        }
        // Draw an arrow on chart for anticipated signals
        if(isAnticipated) {
            DrawSignalArrow(signalId, symbol, direction, entry);
        }
        return;
    }
    
    // Determine order type
    ENUM_ORDER_TYPE orderType;
    
    if(StringFind(direction, "BUY") >= 0 || StringFind(direction, "LONG") >= 0) {
        orderType = ORDER_TYPE_BUY;
    }
    else if(StringFind(direction, "SELL") >= 0 || StringFind(direction, "SHORT") >= 0) {
        orderType = ORDER_TYPE_SELL;
    }
    else {
        Print("Invalid direction: ", direction);
        if(SendReports) {
            SendTradeReport(signalId, symbol, direction, 0, 0, 0, 0, 0, "error", "Invalid direction");
        }
        return;
    }
    
    // Handle anticipated vs immediate signals differently
    if(isAnticipated) {
        // Draw an arrow on chart for anticipated signals
        DrawSignalArrow(signalId, symbol, direction, entry);
        
        // For anticipated signals, we set a limit or stop order at the specified entry price
        double currentPrice = SymbolInfoDouble(symbol, SYMBOL_ASK);
        if(orderType == ORDER_TYPE_SELL)
            currentPrice = SymbolInfoDouble(symbol, SYMBOL_BID);
        
        ENUM_ORDER_TYPE pendingOrderType;
        
        if(orderType == ORDER_TYPE_BUY) {
            if(entry < currentPrice) {
                pendingOrderType = ORDER_TYPE_BUY_LIMIT; // Buy at a lower price than current
            }
            else {
                pendingOrderType = ORDER_TYPE_BUY_STOP; // Buy at a higher price than current
            }
        }
        else { // SELL
            if(entry > currentPrice) {
                pendingOrderType = ORDER_TYPE_SELL_LIMIT; // Sell at a higher price than current
            }
            else {
                pendingOrderType = ORDER_TYPE_SELL_STOP; // Sell at a lower price than current
            }
        }
        
        // Place the pending order
        Print("Placing pending order: ", EnumToString(pendingOrderType), " for ", symbol, " at ", DoubleToString(entry, GetSymbolDigits(symbol)),
              " with SL: ", DoubleToString(stopLoss, GetSymbolDigits(symbol)), " TP: ", DoubleToString(takeProfit, GetSymbolDigits(symbol)),
              " Lot: ", DoubleToString(lotSize, 2));
              
        // Use Trade.OrderOpen() for pending orders
        bool success = Trade.OrderOpen(
            symbol,
            pendingOrderType,
            lotSize,
            0, // Current price, will be filled in by OrderOpen
            entry, // Price to trigger the order
            stopLoss,
            takeProfit,
            0, // No expiration
            0, // No expiration time
            "GENESIS Signal #" + IntegerToString(signalId)
        );
        
        if(success) {
            ulong ticket = Trade.ResultOrder();
            Print("Pending order placed successfully. Ticket: ", ticket);
            if(SendReports) {
                SendTradeReport(signalId, symbol, direction, ticket, lotSize, entry, stopLoss, takeProfit, "pending", "Pending order placed");
            }
        }
        else {
            int errorCode = GetLastError();
            string errorDesc = ErrorDescription(errorCode);
            Print("Failed to place pending order. Error: ", errorCode, " - ", errorDesc);
            if(SendReports) {
                SendTradeReport(signalId, symbol, direction, 0, lotSize, entry, stopLoss, takeProfit, "error", "Error placing pending order: " + errorDesc);
            }
        }
    }
    else {
        // For immediate signals, place a market order
        Print("Placing market order: ", EnumToString(orderType), " for ", symbol,
              " with SL: ", DoubleToString(stopLoss, GetSymbolDigits(symbol)), " TP: ", DoubleToString(takeProfit, GetSymbolDigits(symbol)),
              " Lot: ", DoubleToString(lotSize, 2));
              
        // Use Trade.PositionOpen() for market orders
        bool success = Trade.PositionOpen(
            symbol,
            orderType,
            lotSize,
            0, // Current price, will be filled in by PositionOpen
            stopLoss,
            takeProfit,
            "GENESIS Signal #" + IntegerToString(signalId)
        );
        
        if(success) {
            ulong ticket = Trade.ResultDeal();
            double price = Trade.ResultPrice();
            Print("Market order executed successfully. Ticket: ", ticket, " Price: ", DoubleToString(price, GetSymbolDigits(symbol)));
            if(SendReports) {
                SendTradeReport(signalId, symbol, direction, ticket, lotSize, price, stopLoss, takeProfit, "success", "Trade executed");
            }
        }
        else {
            int errorCode = GetLastError();
            string errorDesc = ErrorDescription(errorCode);
            Print("Failed to execute market order. Error: ", errorCode, " - ", errorDesc);
            if(SendReports) {
                SendTradeReport(signalId, symbol, direction, 0, lotSize, 0, stopLoss, takeProfit, "error", "Error executing market order: " + errorDesc);
            }
        }
    }
}

//+------------------------------------------------------------------+
//| Draw a signal arrow on the chart                                 |
//+------------------------------------------------------------------+
void DrawSignalArrow(int signalId, string symbol, string direction, double price)
{
    // Generate a unique object name
    string objName = ArrowPrefix + IntegerToString(signalId);
    
    // Delete existing arrow with same name if it exists
    ObjectDelete(0, objName);
    
    // Determine arrow type and color based on direction
    int arrowCode;
    color arrowColor;
    
    if(StringFind(direction, "LONG") >= 0 || StringFind(direction, "BUY") >= 0) {
        arrowCode = OBJ_ARROW_UP;
        arrowColor = AnticipatedLongColor;
    }
    else {
        arrowCode = OBJ_ARROW_DOWN;
        arrowColor = AnticipatedShortColor;
    }
    
    // Calculate arrow position
    double arrowPrice = price;
    if(arrowCode == OBJ_ARROW_UP) {
        arrowPrice -= ArrowOffset * SymbolInfoDouble(symbol, SYMBOL_POINT);
    }
    else {
        arrowPrice += ArrowOffset * SymbolInfoDouble(symbol, SYMBOL_POINT);
    }
    
    // Create the arrow object
    if(ObjectCreate(0, objName, OBJ_ARROW, 0, TimeCurrent(), arrowPrice)) {
        ObjectSetInteger(0, objName, OBJPROP_ARROWCODE, arrowCode);
        ObjectSetInteger(0, objName, OBJPROP_COLOR, arrowColor);
        ObjectSetInteger(0, objName, OBJPROP_WIDTH, ArrowSize);
        ObjectSetInteger(0, objName, OBJPROP_SELECTABLE, false);
        ObjectSetString(0, objName, OBJPROP_TOOLTIP, "GENESIS Signal #" + IntegerToString(signalId) + "\n" + direction);
        ChartRedraw(0); // Refresh chart to show the arrow
        Print("Drew signal arrow on chart: ", objName, " at ", DoubleToString(arrowPrice, Digits()));
    }
    else {
        Print("Failed to create signal arrow on chart: ", objName, ", error: ", GetLastError());
    }
}

//+------------------------------------------------------------------+
//| Delete all signal arrows from the chart                          |
//+------------------------------------------------------------------+
void DeleteAllSignalArrows()
{
    int totalObjects = ObjectsTotal(0, 0, -1);
    
    for(int i = totalObjects - 1; i >= 0; i--) {
        string objName = ObjectName(0, i);
        if(StringFind(objName, ArrowPrefix) == 0) {
            ObjectDelete(0, objName);
        }
    }
    
    ChartRedraw(0);
    Print("Deleted all signal arrows from chart");
}

//+------------------------------------------------------------------+
//| Send a trade report back to GENESIS                              |
//+------------------------------------------------------------------+
void SendTradeReport(int signalId, string symbol, string direction, ulong ticket, double lotSize,
                     double entryPrice, double stopLoss, double takeProfit, string status, string message)
{
    // Prepare JSON data
    JsonToSend.Clear();
    JsonToSend["signal_id"] = signalId;
    JsonToSend["account_id"] = AccountName;
    JsonToSend["symbol"] = symbol;
    JsonToSend["action"] = direction;
    JsonToSend["ticket"] = IntegerToString(ticket);
    JsonToSend["lot_size"] = DoubleToString(lotSize, 2);
    JsonToSend["entry_price"] = DoubleToString(entryPrice, GetSymbolDigits(symbol));
    JsonToSend["stop_loss"] = DoubleToString(stopLoss, GetSymbolDigits(symbol));
    JsonToSend["take_profit"] = DoubleToString(takeProfit, GetSymbolDigits(symbol));
    JsonToSend["execution_time"] = TimeToString(TimeCurrent(), TIME_DATE|TIME_SECONDS);
    JsonToSend["status"] = status;
    JsonToSend["message"] = message;
    
    // Send request
    string jsonString = JsonToSend.Serialize();
    string response = "";
    
    bool success = SendPostRequest(API_ENDPOINT + MT5_API_PATH + "/trade_report", jsonString, response);
    
    if(success) {
        // Parse response
        JsonReceived.Clear();
        JsonReceived.Deserialize(response);
        
        if(JsonReceived["status"].ToStr() == "success") {
            Print("Trade report sent successfully for signal #", signalId);
        }
        else {
            Print("Error sending trade report: ", JsonReceived["message"].ToStr());
        }
    }
    else {
        Print("Failed to send trade report for signal #", signalId);
    }
}

//+------------------------------------------------------------------+
//| Send a POST request to the API                                   |
//+------------------------------------------------------------------+
bool SendPostRequest(string url, string postData, string &responseData)
{
    int timeout = API_TIMEOUT;
    char data[];
    char result[];
    string headers = "Content-Type: application/json\r\n";
    int res = -1;
    
    // Add API key to headers if provided
    if(StringLen(API_Key) > 0) {
        headers = headers + "Authorization: Bearer " + API_Key + "\r\n";
    }
    
    // Convert post data to char array
    int dataSize = StringToCharArray(postData, data) - 1;
    
    // Allow for retries
    int maxRetries = 3;
    int retryDelay = 1000; // 1 second
    
    for(int i = 0; i < maxRetries; i++) {
        res = WebRequest("POST", url, headers, timeout, data, result, headers);
        
        if(res == 200) {
            // Success
            responseData = CharArrayToString(result, 0, ArraySize(result));
            return true;
        }
        else {
            // Failed
            int errorCode = GetLastError();
            
            // 4060 = No connection to server
            // 4061 = Connection to server failed
            // 4062 = Timeout
            if(errorCode == 4060 || errorCode == 4061 || errorCode == 4062) {
                Print("Temporary error, retrying in ", retryDelay/1000, " seconds. Error: ", errorCode, " - ", ErrorDescription(errorCode));
                Sleep(retryDelay);
                retryDelay *= 2; // Exponential backoff
                continue;
            }
            else {
                // More serious error
                Print("WebRequest failed. URL: ", url, " Error: ", errorCode, " - ", ErrorDescription(errorCode));
                break;
            }
        }
    }
    
    return false;
}

//+------------------------------------------------------------------+
//| Convert deinitialization reason code to text                     |
//+------------------------------------------------------------------+
string GetDeinitReasonText(int reasonCode)
{
    string text = "Unknown reason";
    
    switch(reasonCode) {
        case REASON_PROGRAM:     text = "Program called by ExpertRemove()"; break;
        case REASON_REMOVE:      text = "Program removed from chart"; break;
        case REASON_RECOMPILE:   text = "Program recompiled"; break;
        case REASON_CHARTCHANGE: text = "Symbol or timeframe changed"; break;
        case REASON_CHARTCLOSE:  text = "Chart closed"; break;
        case REASON_PARAMETERS:  text = "Parameters changed"; break;
        case REASON_ACCOUNT:     text = "Another account activated"; break;
        case REASON_TEMPLATE:    text = "New template applied"; break;
        case REASON_INITFAILED:  text = "OnInit() handler returned non-zero value"; break;
        case REASON_CLOSE:       text = "Terminal closed"; break;
    }
    
    return text;
}

//+------------------------------------------------------------------+
//| Check if market is open for a specific symbol                    |
//+------------------------------------------------------------------+
bool IsMarketOpenForSymbol(string symbol, bool force_execution=false)
{
    // If force execution is enabled, return true regardless
    if(force_execution) {
        Print("Force execution enabled for ", symbol, ", bypassing market open check");
        return true;
    }
    
    // Get trading session info
    datetime now = TimeCurrent();
    
    // Check if trading is allowed for the symbol
    long tradeMode;
    if(SymbolInfoInteger(symbol, SYMBOL_TRADE_MODE, tradeMode)) {
        if(tradeMode == SYMBOL_TRADE_MODE_DISABLED) {
            Print("Trading is disabled for ", symbol);
            return false;
        }
    }
    
    // Check if outside of defined trading sessions
    datetime sess_from, sess_to;
    if(SymbolInfoSessionQuote(symbol, MONDAY, 0, sess_from, sess_to)) {
        MqlDateTime timeStruct;
        TimeToStruct(now, timeStruct);
        
        int day_of_week = timeStruct.day_of_week;
        datetime from, to;
        
        // Check if current time is within a trading session
        if(SymbolInfoSessionQuote(symbol, (ENUM_DAY_OF_WEEK)day_of_week, 0, from, to)) {
            if(now >= from && now <= to) {
                return true;
            }
            else {
                // Check additional sessions for the day
                for(int session = 1; session < 10; session++) {
                    if(SymbolInfoSessionQuote(symbol, (ENUM_DAY_OF_WEEK)day_of_week, session, from, to)) {
                        if(now >= from && now <= to) {
                            return true;
                        }
                    }
                    else {
                        break; // No more sessions
                    }
                }
                Print("Market for ", symbol, " is closed now");
                return false;
            }
        }
    }
    
    // Default to true if no sessions defined or if checks pass
    return true;
}

//+------------------------------------------------------------------+

//| Send account status to GENESIS                                     |

//+------------------------------------------------------------------+

void SendAccountStatus()
{

    JsonToSend.Clear();

    JsonToSend["account_id"] = AccountName;

    JsonToSend["balance"] = AccountInfoDouble(ACCOUNT_BALANCE);

    JsonToSend["equity"] = AccountInfoDouble(ACCOUNT_EQUITY);

    JsonToSend["margin"] = AccountInfoDouble(ACCOUNT_MARGIN);

    JsonToSend["free_margin"] = AccountInfoDouble(ACCOUNT_FREEMARGIN);

    string jsonString = JsonToSend.Serialize();

    string response = "";

    SendPostRequest(ACCOUNT_STATUS_URL, jsonString, response);

}


//+------------------------------------------------------------------+

//| Send open trades to GENESIS                                       |

//+------------------------------------------------------------------+



//+------------------------------------------------------------------+
//| Send open trades and history to GENESIS                          |
//+------------------------------------------------------------------+
// Define a simple string array at a global level to track sent trades
string g_sentTradeIds[100];  // Fixed size array
int g_sentTradeCount = 0;
// Function to check if a trade was already sent
bool IsTradeAlreadySent(string tradeId)
{
   for(int i=0; i<g_sentTradeCount; i++)
   {
      if(g_sentTradeIds[i] == tradeId)
         return true;
   }
   return false;
}
// Function to mark a trade as sent
void MarkTradeAsSent(string tradeId)
{
   if(g_sentTradeCount < 100)  // Avoid buffer overflow
   {
      g_sentTradeIds[g_sentTradeCount] = tradeId;
      g_sentTradeCount++;
   }
}
void SendTradeUpdates()
{
   Print("======= STARTING TRADE UPDATES =======");
   
   JsonToSend.Clear();
   JsonToSend["account_id"] = AccountName;
   
   // Create a JSON object for trades data
   CJAVal trades;
   trades.Clear();
   
   bool hasData = false;
   
   // --- Open positions -------------------------------------------------
   int total = PositionsTotal();
   Print("Found " + IntegerToString(total) + " open positions");
   
   for(int i=0; i<total; i++)
   {
      ulong ticket = PositionGetTicket(i);
      if(PositionSelectByTicket(ticket))
      {
         string symbol = PositionGetString(POSITION_SYMBOL);
         double open_price = PositionGetDouble(POSITION_PRICE_OPEN);
         double current_price = PositionGetDouble(POSITION_PRICE_CURRENT);
         double profit = PositionGetDouble(POSITION_PROFIT);
         datetime open_time = (datetime)PositionGetInteger(POSITION_TIME);
         
         Print("Processing open position: Ticket=" + IntegerToString(ticket) + 
               ", Symbol=" + symbol +
               ", Open Price=" + DoubleToString(open_price, 5) +
               ", Current Price=" + DoubleToString(current_price, 5) +
               ", Profit=" + DoubleToString(profit, 2) +
               ", Open Time=" + TimeToString(open_time, TIME_DATE|TIME_SECONDS));
         
         // Use the ticket as identifier
         string tradeId = "open_" + IntegerToString(ticket);
         
         // Only send if we haven't sent it before
         if(!IsTradeAlreadySent(tradeId))
         {
            CJAVal trade;
            trade["symbol"] = symbol;
            trade["lot"] = DoubleToString(PositionGetDouble(POSITION_VOLUME), 2);
            trade["type"] = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) ? "BUY" : "SELL";
            trade["open_price"] = DoubleToString(open_price, GetSymbolDigits(symbol));
            trade["sl"] = DoubleToString(PositionGetDouble(POSITION_SL), GetSymbolDigits(symbol));
            trade["tp"] = DoubleToString(PositionGetDouble(POSITION_TP), GetSymbolDigits(symbol));
            trade["profit"] = DoubleToString(profit, 2);
            
            // IMPORTANT: Make sure open_time is sent correctly
            if(open_time > 0)
            {
               trade["opened_at"] = TimeToString(open_time, TIME_DATE|TIME_SECONDS);
               Print("Setting opened_at to: " + TimeToString(open_time, TIME_DATE|TIME_SECONDS));
            }
            
            trade["status"] = "OPEN";
            
            // Add to trades object with ticket as key
            trades[IntegerToString(ticket)] = trade;
            MarkTradeAsSent(tradeId);
            hasData = true;
            Print("Added open position to update: Ticket=" + IntegerToString(ticket));
         }
      }
   }
   
   // --- Closed trades (last 30 days) ------------------------------------
   datetime endTime = TimeCurrent();
   datetime startTime = endTime - 30*24*60*60;   // 30-day window
   
   bool historySelected = HistorySelect(startTime, endTime);
   Print("History select returned: " + (historySelected ? "true" : "false") + 
         " for period " + TimeToString(startTime) + " to " + TimeToString(endTime));
   
   if(historySelected)
   {
      int dealsTotal = HistoryDealsTotal();
      Print("Found " + IntegerToString(dealsTotal) + " total deals in history");
      
      // First, collect all OUT deals to get closed positions
      int closedDealsCount = 0;
      
      for(int i=0; i<dealsTotal; i++)
      {
         ulong dealTicket = HistoryDealGetTicket(i);
         
         if(dealTicket <= 0) {
            Print("Invalid deal ticket at index " + IntegerToString(i));
            continue;
         }
         
         if(HistoryDealGetInteger(dealTicket, DEAL_ENTRY) == DEAL_ENTRY_OUT)
         {
            ENUM_DEAL_TYPE dealType = (ENUM_DEAL_TYPE)HistoryDealGetInteger(dealTicket, DEAL_TYPE);
            
            if(dealType == DEAL_TYPE_BUY || dealType == DEAL_TYPE_SELL)
            {
               string symbol = HistoryDealGetString(dealTicket, DEAL_SYMBOL);
               double volume = HistoryDealGetDouble(dealTicket, DEAL_VOLUME);
               double price = HistoryDealGetDouble(dealTicket, DEAL_PRICE);
               double profit = HistoryDealGetDouble(dealTicket, DEAL_PROFIT);
               datetime closeTime = (datetime)HistoryDealGetInteger(dealTicket, DEAL_TIME);
               ulong posId = HistoryDealGetInteger(dealTicket, DEAL_POSITION_ID);
               
               // Use position ID as identifier for closed trades
               string tradeId = "closed_" + IntegerToString(posId);
               
               // Only process if we haven't seen this position before
               if(!IsTradeAlreadySent(tradeId))
               {
                  Print("Found closed deal: Deal=" + IntegerToString(dealTicket) + 
                        ", Position=" + IntegerToString(posId) + 
                        ", Symbol=" + symbol + 
                        ", Volume=" + DoubleToString(volume, 2) + 
                        ", Exit Price=" + DoubleToString(price, 5) + 
                        ", Profit=" + DoubleToString(profit, 2) + 
                        ", Close Time=" + TimeToString(closeTime, TIME_DATE|TIME_SECONDS));
                  
                  // Look for matching IN deal for this position
                  double entryPrice = 0;
                  datetime openTime = 0;
                  string type = (dealType == DEAL_TYPE_BUY) ? "SELL" : "BUY";  // Opposite of closing deal
                  
                  // Search for the entry deal with the same position ID
                  for(int j=0; j<dealsTotal; j++)
                  {
                     ulong inDealTicket = HistoryDealGetTicket(j);
                     
                     if(inDealTicket <= 0) continue;
                     
                     if(HistoryDealGetInteger(inDealTicket, DEAL_POSITION_ID) == posId && 
                        HistoryDealGetInteger(inDealTicket, DEAL_ENTRY) == DEAL_ENTRY_IN)
                     {
                        entryPrice = HistoryDealGetDouble(inDealTicket, DEAL_PRICE);
                        openTime = (datetime)HistoryDealGetInteger(inDealTicket, DEAL_TIME);
                        ENUM_DEAL_TYPE inDealType = (ENUM_DEAL_TYPE)HistoryDealGetInteger(inDealTicket, DEAL_TYPE);
                        type = (inDealType == DEAL_TYPE_BUY) ? "BUY" : "SELL";
                        
                        Print("Found matching entry deal: Deal=" + IntegerToString(inDealTicket) + 
                              ", Entry Price=" + DoubleToString(entryPrice, 5) + 
                              ", Open Time=" + TimeToString(openTime, TIME_DATE|TIME_SECONDS) + 
                              ", Type=" + type);
                        break;
                     }
                  }
                  
                  // Create trade object for this closed position
                  CJAVal trade;
                  trade["symbol"] = symbol;
                  trade["lot"] = DoubleToString(volume, 2);
                  trade["type"] = type;
                  trade["open_price"] = DoubleToString(entryPrice, GetSymbolDigits(symbol));
                  trade["exit_price"] = DoubleToString(price, GetSymbolDigits(symbol));
                  trade["profit"] = DoubleToString(profit, 2);
                  trade["status"] = "CLOSED";
                  
                  // IMPORTANT: Make sure opened_at is included 
                  if(openTime > 0)
                  {
                     trade["opened_at"] = TimeToString(openTime, TIME_DATE|TIME_SECONDS);
                     Print("Setting opened_at to: " + TimeToString(openTime, TIME_DATE|TIME_SECONDS));
                  }
                  
                  // IMPORTANT: Make sure closed_at uses the actual close time
                  trade["closed_at"] = TimeToString(closeTime, TIME_DATE|TIME_SECONDS);
                  Print("Setting closed_at to: " + TimeToString(closeTime, TIME_DATE|TIME_SECONDS));
                  
                  // Use position ID as key
                  trades[IntegerToString(posId)] = trade;
                  MarkTradeAsSent(tradeId);
                  closedDealsCount++;
                  hasData = true;
                  Print("Added closed position to update: Position=" + IntegerToString(posId));
               }
            }
         }
      }
      
      Print("Added " + IntegerToString(closedDealsCount) + " closed trades to the update");
   }
   else
   {
      Print("Failed to select history for the period");
   }
   
   // Add trades to main JSON
   JsonToSend["trades"] = trades;
   
   // Log the full payload for debugging
   string jsonString = JsonToSend.Serialize();
   Print("Trade update payload: " + jsonString);
   
   // Only send if we have data
   if(hasData) {
      string response = "";
      bool success = SendPostRequest(TRADE_UPDATE_URL, jsonString, response);
      
      if(success) {
         Print("Trade updates sent successfully. Response: " + response);
      }
      else {
         Print("Failed to send trade updates");
      }
   }
   else {
      Print("No trade data found to send");
   }
   
   Print("======= COMPLETED TRADE UPDATES =======");
}