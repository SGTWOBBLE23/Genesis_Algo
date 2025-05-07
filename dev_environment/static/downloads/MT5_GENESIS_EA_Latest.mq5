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
const string SIGNALS_URL      = API_ENDPOINT + MT5_API_PATH + GET_SIGNALS_PATH;
const string HEARTBEAT_URL    = API_ENDPOINT + MT5_API_PATH + HEARTBEAT_PATH;
const string ACCOUNT_STATUS_URL = API_ENDPOINT + MT5_API_PATH + ACCOUNT_STATUS_PATH;
const string TRADE_UPDATE_URL   = API_ENDPOINT + MT5_API_PATH + TRADE_UPDATE_PATH;


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
    JsonToSend["account_id"] = AccountInfoString(ACCOUNT_NAME);
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

// Additional functions would follow...