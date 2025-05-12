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
#property version   "1.10"
#property strict

// Include required libraries
#include <Trade/Trade.mqh>           // For trading operations
#include <Arrays/ArrayString.mqh>    // For string array operations
#include <JAson.mqh>                 // For JSON operations, needs to be installed
#include <StdLib.mqh>
#define DBG  if(DebugLogs) Print               // For ErrorDescription()
//--- Updated API constants with enhanced connection handling
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
#define API_TIMEOUT  10000           // Increased timeout for API requests in milliseconds
#define SIGNAL_CHECK_INTERVAL 10     // How often to check for new signals (seconds)
#define HEARTBEAT_INTERVAL 30        // REDUCED from 60 to 30 seconds for more frequent heartbeats
#define MAX_CONNECTION_RETRIES 3     // Number of times to retry a failed connection

// Input parameters
input string   API_Key      = "";    // API Key for authentication
input string   AccountName  = "";    // Account name/identifier
input bool     AutoTrade    = true;  // Automatically execute trades
input bool     SendReports  = true;  // Send trade reports back to GENESIS
input double   LotMultiplier = 1.0;  // Multiplier for lot size from signals
input int      SlippagePoints = 10;  // Maximum allowed slippage in points
input bool     SendHeartbeat = true; // Send heartbeat to GENESIS platform
input bool     ShowAlerts   = true;  // Pop-up alerts
input bool     DebugLogs    = true;  // INCREASED: verbose housekeeping prints for debugging

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
bool           ServerConnected = false; // NEW: Track server connection status

// Global variables for signal arrows
color    EntryBuyColor  = clrLime;     // Entry arrow for executed buys
color    EntrySellColor = clrRed;      // Entry arrow for executed sells
string   LinePrefix = "GENESIS_Line_"; // Prefix for entry/SL/TP lines

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
    DBG("GENESIS EA debug logs enabled!");
    
    // Generate a unique terminal identifier
    TerminalNumber = MathRand();
    Print("Terminal identifier: ", TerminalNumber);
    
    // Set up trading parameters
    Trade.SetDeviationInPoints(SlippagePoints);
    Trade.SetExpertMagicNumber(123456); // Set a unique magic number
    
    // Get all symbols in Market Watch
    GetActiveSymbols();
    
    // Initialize JSON object
    JsonToSend.Clear();
    
    // Send initial heartbeat with extra connection attempts
    if(SendHeartbeat) {
        bool connected = false;
        for(int i=0; i<MAX_CONNECTION_RETRIES && !connected; i++) {
            connected = SendHeartbeatToGenesis();
            if(!connected) {
                Print("Initial heartbeat attempt ", i+1, " failed, retrying...");
                Sleep(1000); // Wait 1 second before retry
            }
        }
        
        if(connected) {
            Print("Successfully connected to GENESIS platform!");
            ServerConnected = true;
        } else {
            Print("WARNING: Could not establish connection to GENESIS platform after ", MAX_CONNECTION_RETRIES, " attempts");
        }
    }
    
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
    DBG("GENESIS EA shutting down, reason: ", GetDeinitReasonText(reason));
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
   // ── 1.  Send account status every 15 s ─────────────────────────
   static datetime lastAccountUpdate = 0;
   if((TimeCurrent() - lastAccountUpdate) >= 15)
     {
      SendAccountStatus();
      lastAccountUpdate = TimeCurrent();
     }

   // ── 2.  Send trade updates every 20 s ──────────────────────────
   static datetime lastTradeUpdate = 0;
   if((TimeCurrent() - lastTradeUpdate) >= 20)
     {
      SendTradeUpdates();                 // <-- keep just this ONE call
      lastTradeUpdate = TimeCurrent();
     }

   // ── 3.  Heart-beat to server (if enabled) ─────────────────────
   if(SendHeartbeat && (TimeCurrent() - LastHeartbeat) >= HEARTBEAT_INTERVAL)
     {
      bool heartbeatSuccess = SendHeartbeatToGenesis();
      if(heartbeatSuccess && !ServerConnected) {
          Print("Connection to GENESIS platform restored!");
          ServerConnected = true;
      } else if(!heartbeatSuccess && ServerConnected) {
          Print("WARNING: Connection to GENESIS platform lost!");
          ServerConnected = false;
      }
      LastHeartbeat = TimeCurrent();
     }

   // ── 4.  Poll for new Genesis signals ──────────────────────────
   if((TimeCurrent() - LastSignalCheck) >= SIGNAL_CHECK_INTERVAL)
     {
      // Only check for signals if we're connected
      if(ServerConnected) {
          GetNewSignalsFromGenesis();
      } else {
          DBG("Skipping signal check - not connected to server");
      }
      LastSignalCheck = TimeCurrent();
     }
  }

//+------------------------------------------------------------------+
//| Sync positions after every trade event                           |
//+------------------------------------------------------------------+
void OnTradeTransaction(const MqlTradeTransaction &trans,
                        const MqlTradeRequest     &request,
                        const MqlTradeResult      &result)
  {
   // Fire only on meaningful order / deal changes
   if(trans.type==TRADE_TRANSACTION_DEAL_ADD     ||
      trans.type==TRADE_TRANSACTION_DEAL_UPDATE  ||
      trans.type==TRADE_TRANSACTION_ORDER_ADD    ||
      trans.type==TRADE_TRANSACTION_ORDER_UPDATE)
     {
      SendTradeUpdates();      // 🚀 push snapshot to the Python server
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
    // Print all symbols for easier debugging
    if(DebugLogs) {
        Print("Active symbols:");
        for(int i = 0; i < symbolsTotal; i++) {
            Print("  ", i+1, ": ", ActiveSymbols[i]);
        }
    }
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
    
    DBG("Sending heartbeat to: ", HEARTBEAT_URL);
    DBG("Heartbeat data: ", jsonString);
    
    bool success = SendPostRequest(HEARTBEAT_URL, jsonString, response);
    
    if(success) {
        // Parse response
        JsonReceived.Clear();
        bool parseSuccess = JsonReceived.Deserialize(response);
        
        if(!parseSuccess) {
            DBG("Failed to parse heartbeat response: ", response);
            return false;
        }
        
        if(JsonReceived["status"].ToStr() == "success") {
            DBG("Heartbeat sent successfully. Server time: ", JsonReceived["server_time"].ToStr());
            return true;
        }
        else {
            DBG("Error sending heartbeat: ", JsonReceived["message"].ToStr());
            return false;
        }
    }
    else {
        DBG("Failed to send heartbeat request");
        return false;
    }
}

//+------------------------------------------------------------------+
//| Get new signals from GENESIS platform                            |
//+------------------------------------------------------------------+
void GetNewSignalsFromGenesis()
{
    // More detailed logging about API call
    DBG("Attempting to get signals from URL: ", SIGNALS_URL);

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
    
    DBG("Sending signals request with data: ", jsonString);
    
    bool success = SendPostRequest(SIGNALS_URL, jsonString, response);
    
    if(success) {
        // Parse response
        JsonReceived.Clear();
        bool parseSuccess = JsonReceived.Deserialize(response);
        
        if(!parseSuccess) {
            DBG("Failed to parse signals response: ", response);
            return;
        }
        
        if(JsonReceived["status"].ToStr() == "success") {
            // Process signals
            CJAVal signals = JsonReceived["signals"];
            int signalsCount = signals.Size();
            
            DBG("Received ", signalsCount, " new signals");
            
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
                DBG("  ID: ", signalId);
                DBG("  Symbol: ", symbol);
                DBG("  Direction: ", direction);
                DBG("  Entry: ", DoubleToString(entry, GetSymbolDigits(symbol)));
                DBG("  Stop Loss: ", DoubleToString(stopLoss, GetSymbolDigits(symbol)));
                DBG("  Take Profit: ", DoubleToString(takeProfit, GetSymbolDigits(symbol)));
                DBG("  Confidence: ", DoubleToString(confidence, 2));
                DBG("  Lot Size: ", DoubleToString(lotSize, 2));
                DBG("  Force Execution: ", force_execution ? "Yes" : "No");
                
                // Check if symbol is valid
                if(!SymbolSelect(symbol, true)) {
                    DBG("  WARNING: Symbol ", symbol, " not available in Market Watch, trying to add it...");
                    if(!SymbolSelect(symbol, true)) {
                        DBG("  ERROR: Failed to add symbol ", symbol, " to Market Watch");
                        continue;
                    } else {
                        DBG("  SUCCESS: Added symbol ", symbol, " to Market Watch");
                    }
                }
                
                // Process signal based on direction
                bool success = false;
                if(direction == "BUY_NOW") {
                    DBG("  Processing BUY_NOW signal");
                    if(AutoTrade && IsMarketOpenForSymbol(symbol, force_execution)) {
                        success = ExecuteBuyOrder(symbol, lotSize, entry, stopLoss, takeProfit, signalId);
                    } else {
                        CreateBuySignalArrow(symbol, entry, signalId);
                    }
                } else if(direction == "SELL_NOW") {
                    DBG("  Processing SELL_NOW signal");
                    if(AutoTrade && IsMarketOpenForSymbol(symbol, force_execution)) {
                        success = ExecuteSellOrder(symbol, lotSize, entry, stopLoss, takeProfit, signalId);
                    } else {
                        CreateSellSignalArrow(symbol, entry, signalId);
                    }
                } else if(direction == "ANTICIPATED_LONG") {
                    DBG("  Processing ANTICIPATED_LONG signal");
                    // Create buy limit order or just show the signal
                    if(AutoTrade && IsMarketOpenForSymbol(symbol, force_execution)) {
                        success = PlaceBuyLimitOrder(symbol, lotSize, entry, stopLoss, takeProfit, signalId);
                    } else {
                        CreateAnticipatedLongArrow(symbol, entry, signalId);
                        DrawLevels(symbol, entry, stopLoss, takeProfit, AnticipatedLongColor, signalId);
                    }
                } else if(direction == "ANTICIPATED_SHORT") {
                    DBG("  Processing ANTICIPATED_SHORT signal");
                    // Create sell limit order or just show the signal
                    if(AutoTrade && IsMarketOpenForSymbol(symbol, force_execution)) {
                        success = PlaceSellLimitOrder(symbol, lotSize, entry, stopLoss, takeProfit, signalId);
                    } else {
                        CreateAnticipatedShortArrow(symbol, entry, signalId);
                        DrawLevels(symbol, entry, stopLoss, takeProfit, AnticipatedShortColor, signalId);
                    }
                } else {
                    DBG("  WARNING: Unknown signal direction: ", direction);
                }
                
                // Log success/failure
                if(AutoTrade && IsMarketOpenForSymbol(symbol, force_execution)) {
                    if(success) {
                        DBG("  Signal executed successfully");
                        SendTradeReport(signalId, symbol, direction, "success", "Trade executed");
                    } else {
                        DBG("  Failed to execute signal");
                        SendTradeReport(signalId, symbol, direction, "error", "Failed to execute trade");
                    }
                } else {
                    if(!AutoTrade) {
                        DBG("  Signal not executed (AutoTrade is disabled)");
                    } else {
                        DBG("  Signal not executed (Market is closed for this symbol)");
                    }
                }
            }
        }
        else {
            DBG("Error getting signals: ", JsonReceived["message"].ToStr());
        }
    }
    else {
        DBG("Failed to send signals request");
    }
}

// The rest of your existing EA functions go here (unchanged)...

//+------------------------------------------------------------------+
//| Send a POST request to the API                                   |
//+------------------------------------------------------------------+
bool SendPostRequest(string url, string postData, string &response)
{
    // Initialize
    char data[];
    char result[];
    string result_headers;
    
    // Convert the POST data to char array
    StringToCharArray(postData, data, 0, StringLen(postData));
    
    // Define headers
    string headers = "Content-Type: application/json\r\n";
    if(API_Key != "") {
        headers += "Authorization: Bearer " + API_Key + "\r\n";
    }
    
    // Log request
    DBG("POST Request URL: ", url);
    DBG("POST Request Headers: ", headers);
    
    // Send request
    int res = WebRequest("POST", url, headers, API_TIMEOUT, data, result, result_headers);
    
    // Process the response
    if(res == 200) {
        response = CharArrayToString(result, 0, WHOLE_ARRAY);
        DBG("POST Request Successful (200 OK)");
        return true;
    } else {
        string errorDesc = GetWebErrorDescription(res);
        
        DBG("POST Request Failed with code: ", res);
        DBG("Error Description: ", errorDesc);
        
        if(res == -1) {
            // Check if WebRequest is allowed
            if(!WebRequestAllowed()) {
                DBG("WebRequest not allowed. Please go to Tools -> Options -> Expert Advisors and check 'Allow WebRequest for listed URL:' and add: ", API_ENDPOINT);
                Alert("WebRequest failed! Please enable WebRequest for ", API_ENDPOINT);
            } else {
                DBG("WebRequest failed due to a network error or the server is down");
            }
        }
        
        response = "";
        return false;
    }
}

// Include all your other original EA functions here...
// Just copy your existing functions from the original EA
// I'm leaving these out for brevity

//+------------------------------------------------------------------+
//| Get descriptive text for deinitialization reason code            |
//+------------------------------------------------------------------+
string GetDeinitReasonText(int reasonCode)
{
    switch(reasonCode) {
        case REASON_PROGRAM: return "Program called by ExpertRemove()";
        case REASON_REMOVE: return "Expert removed from chart";
        case REASON_RECOMPILE: return "Expert recompiled";
        case REASON_CHARTCHANGE: return "Symbol or timeframe changed";
        case REASON_CHARTCLOSE: return "Chart closed";
        case REASON_PARAMETERS: return "Parameters changed";
        case REASON_ACCOUNT: return "Another account activated";
        case REASON_TEMPLATE: return "New template applied";
        case REASON_INITFAILED: return "OnInit() handler returned non-zero value";
        case REASON_CLOSE: return "Terminal closed";
        default: return "Unknown reason: " + IntegerToString(reasonCode);
    }
}

//+------------------------------------------------------------------+
//| Get descriptive text for WebRequest error code                   |
//+------------------------------------------------------------------+
string GetWebErrorDescription(int errorCode)
{
    switch(errorCode) {
        case -1: return "Unknown error";
        case -2: return "Common error";
        case -3: return "Invalid parameters";
        case -4: return "Cannot connect to server";
        case -5: return "Connection timeout";
        case -6: return "HTTP error";
        case -7: return "No data";
        case -8: return "Buffer too small";
        case -9: return "Function is not allowed";
        case -10: return "File creation/opening error";
        case -11: return "Socket error";
        default: return "HTTP Response code: " + IntegerToString(errorCode);
    }
}