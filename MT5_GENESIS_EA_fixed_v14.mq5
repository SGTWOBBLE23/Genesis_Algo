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
input int      Risk_Percent = 2;      // Risk percent per trade (default 2%)
input bool     Enable_Stats_Overlay = true; // Show account statistics overlay
input double   Fixed_SL_Points = 0;   // Fixed SL in points (0 = use signal SL)
input double   Fixed_TP_Points = 0;   // Fixed TP in points (0 = use signal TP)
input int      Max_Spread_Points = 0; // Max allowed spread (0 = no limit)
input bool     Debug_Mode = false;    // Enable debug mode

// Global variables
string AccountName = "";         // MT5 account name/number
int LastSignalId = 0;            // Last processed signal ID
CJAVal JsonToSend;               // JSON object to send to API
CJAVal JsonReceived;             // JSON object received from API
uint LastSignalCheckTime = 0;    // Last time signals were checked
uint LastHeartbeatTime = 0;      // Last time heartbeat was sent
CTrade Trade;                    // Trading object
CArrayString ProcessedSignals;   // Array to store processed signal IDs
CArrayString SentTrades;         // Array to store sent trade IDs

// Chart object settings
string SignalPrefix = "GENESIS_Signal_";
string LinePrefix = "GENESIS_Line_";
string TextPrefix = "GENESIS_Text_";
string LabelPrefix = "GENESIS_Label_";
string ArrowPrefix = "GENESIS_Arrow_";
string StatsLabelPrefix = "GENESIS_Stats_";
int SignalArrowSize = 3;
int ArrowOffset = 15;
color StopLossColor = clrRed;
color TakeProfitColor = clrGreen;
color BuyNowColor = clrBlue;
color SellNowColor = clrOrangeRed;
color AnticipatedLongColor = clrMediumSeaGreen;
color AnticipatedShortColor = clrCrimson;
color TextColor = clrWhite;
color StatsLabelColor = clrDarkSlateGray;
color StatsBorderColor = clrGray;
color StatsTextColor = clrWhite;
int StatsLabelWidth = 200;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   // Set account name as account number
   AccountName = IntegerToString(AccountInfoInteger(ACCOUNT_LOGIN));
   Print("EA Initialized for account ", AccountName);
   
   // Initialize last signal ID
   LastSignalId = 0;
   
   // Initialize debug mode
   if(Debug_Mode) {
      Print("Debug mode is enabled");
   }
   
   // Create stats label if enabled
   if(Enable_Stats_Overlay) {
      CreateStatsOverlay();
   }
   
   // Send initial heartbeat
   SendHeartbeat();
   
   // Send initial account status
   SendAccountStatus();
   
   // Set up trading object
   Trade.SetDeviationInPoints(10); // 1 pip deviation for market orders
   
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   // Clean up chart objects
   DeleteAllSignalObjects();
   DeleteAllSignalArrows();
   DeleteStatsOverlay();
   
   Print("EA terminated");
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   // Check for new signals at the specified interval
   if(GetTickCount() - LastSignalCheckTime > SIGNAL_CHECK_INTERVAL * 1000) {
      CheckForSignals();
      UpdateStatsOverlay();
      LastSignalCheckTime = GetTickCount();
   }
   
   // Send heartbeat at the specified interval
   if(GetTickCount() - LastHeartbeatTime > HEARTBEAT_INTERVAL * 1000) {
      SendHeartbeat();
      SendAccountStatus();
      SendTradeUpdates();
      LastHeartbeatTime = GetTickCount();
   }
}

//+------------------------------------------------------------------+
//| Check for new trading signals                                    |
//+------------------------------------------------------------------+
void CheckForSignals()
{
   // Clear existing JSON objects
   JsonToSend.Clear();
   JsonReceived.Clear();
   
   // Build URL parameters
   JsonToSend["account_id"] = AccountName;
   JsonToSend["last_signal_id"] = LastSignalId;
   
   // Add list of available symbols
   CJAVal symbols;
   int symbolCount = 0;
   string currSymbol;
   for(int s=0; s<SymbolsTotal(false); s++) {
      currSymbol = SymbolName(s, false);
      symbols[symbolCount++] = currSymbol;
   }
   JsonToSend["symbols"] = symbols;
   
   // Send request to API
   string jsonString = JsonToSend.Serialize();
   string response = "";
   
   // Only log the send part in debug mode
   if(Debug_Mode) {
      Print("Checking for signals. Last signal ID: ", LastSignalId);
   }
   
   bool success = SendPostRequest(SIGNALS_URL, jsonString, response);
   
   if(success) {
      // Parse response
      JsonReceived.Deserialize(response);
      
      if(JsonReceived["status"].ToStr() == "success") {
         // Process any new signals
         CJAVal signals = JsonReceived["signals"];
         int signalCount = signals.Size();
         
         if(signalCount > 0) {
            Print("Received ", signalCount, " new signals");
            
            for(int i=0; i<signalCount; i++) {
               CJAVal signal = signals[i];
               ProcessSignal(signal);
            }
         } else if(Debug_Mode) {
            Print("No new signals received");
         }
      }
      else {
         Print("API Error: ", JsonReceived["message"].ToStr());
      }
   }
   else {
      Print("Failed to connect to API");
   }
}

//+------------------------------------------------------------------+
//| Process a single trading signal                                  |
//+------------------------------------------------------------------+
void ProcessSignal(CJAVal &signal)
{
   // Extract signal parameters
   int signalId = signal["id"].ToInt();
   string symbol = signal["asset"]["symbol"].ToStr();
   string action = signal["action"].ToStr();
   double entryPrice = NormalizeDouble(signal["entry_price"].ToDbl(), GetSymbolDigits(symbol));
   double stopLoss = NormalizeDouble(signal["stop_loss"].ToDbl(), GetSymbolDigits(symbol));
   double takeProfit = NormalizeDouble(signal["take_profit"].ToDbl(), GetSymbolDigits(symbol));
   double confidence = signal["confidence"].ToDbl();
   double positionSize = signal["position_size"].ToDbl();
   bool forceExecution = signal["force_execution"].ToBool();
   
   // Update LastSignalId if this is a higher ID
   if(signalId > LastSignalId) {
      LastSignalId = signalId;
   }
   
   // Skip if we've already processed this signal
   string signalIdStr = IntegerToString(signalId);
   if(IsSignalProcessed(signalIdStr)) {
      Print("Signal #", signalIdStr, " already processed, skipping");
      return;
   }
   
   // Mark as processed
   MarkSignalAsProcessed(signalIdStr);
   
   // Check if symbol exists
   if(!SymbolSelect(symbol, true)) {
      Print("Symbol ", symbol, " not found, skipping signal #", signalIdStr);
      SendTradeReport(signalId, symbol, action, 0, 0, entryPrice, stopLoss, takeProfit, "error", "Symbol not available");
      return;
   }
   
   // Check if market is open for this symbol
   if(!IsMarketOpenForSymbol(symbol, forceExecution)) {
      Print("Market closed for ", symbol, ", skipping signal #", signalIdStr);
      SendTradeReport(signalId, symbol, action, 0, 0, entryPrice, stopLoss, takeProfit, "error", "Market closed");
      return;
   }
   
   // Check spread if Max_Spread_Points is set
   if(Max_Spread_Points > 0) {
      long currentSpread = SymbolInfoInteger(symbol, SYMBOL_SPREAD);
      if(currentSpread > Max_Spread_Points) {
         Print("Spread too high for ", symbol, " (", currentSpread, " > ", Max_Spread_Points, "), skipping signal #", signalIdStr);
         SendTradeReport(signalId, symbol, action, 0, 0, entryPrice, stopLoss, takeProfit, "error", "Spread too high");
         return;
      }
   }
   
   // Draw signal on chart
   if(_Symbol == symbol) {
      DrawSignalOnChart(signalId, action, entryPrice, stopLoss, takeProfit);
   }
   
   // Log the signal
   Print("Processing signal #", signalIdStr, ": ", action, " ", symbol, " at ", entryPrice, ", SL: ", stopLoss, ", TP: ", takeProfit);
   
   // Execute trade based on action type
   if(action == "BUY_NOW" || action == "SELL_NOW" || forceExecution) {
      // Immediate execution
      ExecuteTrade(signalId, symbol, action, entryPrice, stopLoss, takeProfit, positionSize);
   }
   else if(action == "ANTICIPATED_LONG" || action == "ANTICIPATED_SHORT") {
      // Place pending order
      PlacePendingOrder(signalId, symbol, action, entryPrice, stopLoss, takeProfit, positionSize);
   }
   else {
      // Unknown action
      Print("Unknown action type: ", action, " for signal #", signalIdStr);
      SendTradeReport(signalId, symbol, action, 0, 0, entryPrice, stopLoss, takeProfit, "error", "Invalid action type");
   }
}

//+------------------------------------------------------------------+
//| Execute immediate trade based on signal                          |
//+------------------------------------------------------------------+
void ExecuteTrade(int signalId, string symbol, string action, double entryPrice, 
                 double stopLoss, double takeProfit, double positionSize)
{
   // Apply fixed SL/TP if configured
   if(Fixed_SL_Points > 0) {
      // Calculate new SL based on direction
      if(action == "BUY_NOW" || action == "ANTICIPATED_LONG") {
         stopLoss = entryPrice - Fixed_SL_Points * SymbolInfoDouble(symbol, SYMBOL_POINT);
      }
      else if(action == "SELL_NOW" || action == "ANTICIPATED_SHORT") {
         stopLoss = entryPrice + Fixed_SL_Points * SymbolInfoDouble(symbol, SYMBOL_POINT);
      }
   }
   
   if(Fixed_TP_Points > 0) {
      // Calculate new TP based on direction
      if(action == "BUY_NOW" || action == "ANTICIPATED_LONG") {
         takeProfit = entryPrice + Fixed_TP_Points * SymbolInfoDouble(symbol, SYMBOL_POINT);
      }
      else if(action == "SELL_NOW" || action == "ANTICIPATED_SHORT") {
         takeProfit = entryPrice - Fixed_TP_Points * SymbolInfoDouble(symbol, SYMBOL_POINT);
      }
   }
   
   // Normalize prices to symbol digits
   stopLoss = NormalizeDouble(stopLoss, GetSymbolDigits(symbol));
   takeProfit = NormalizeDouble(takeProfit, GetSymbolDigits(symbol));
   
   // Calculate lot size if position_size is not provided
   double lotSize = positionSize;
   if(lotSize <= 0) {
      lotSize = CalculateLotSize(symbol, Risk_Percent, entryPrice, stopLoss);
   }
   
   // Validate lot size
   double minLot = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
   double maxLot = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MAX);
   double lotStep = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
   
   lotSize = MathMax(minLot, lotSize);
   lotSize = MathMin(maxLot, lotSize);
   lotSize = NormalizeDouble(MathFloor(lotSize / lotStep) * lotStep, 2); // Round to nearest lot step
   
   // Determine order type
   ENUM_ORDER_TYPE orderType;
   if(action == "BUY_NOW" || action == "ANTICIPATED_LONG") {
      orderType = ORDER_TYPE_BUY;
   }
   else {
      orderType = ORDER_TYPE_SELL;
   }
   
   // Place order
   Trade.SetExpertMagicNumber(signalId); // Use signal ID as magic number
   
   bool success = false;
   ulong ticket = 0;
   string errorMessage = "";
   
   // Use current market price
   double currentBid = SymbolInfoDouble(symbol, SYMBOL_BID);
   double currentAsk = SymbolInfoDouble(symbol, SYMBOL_ASK);
   
   double executionPrice = (orderType == ORDER_TYPE_BUY) ? currentAsk : currentBid;
   
   // Execute trade
   success = Trade.PositionOpen(symbol, orderType, lotSize, executionPrice, stopLoss, takeProfit, "GENESIS #"+IntegerToString(signalId));
   
   if(success) {
      ticket = Trade.ResultOrder();
      Print("Trade executed: Ticket #", ticket, " for signal #", signalId);
      executionPrice = Trade.ResultPrice();
      
      // Report success back to the API
      SendTradeReport(signalId, symbol, action, ticket, lotSize, executionPrice, stopLoss, takeProfit, "success", "Trade executed");
   }
   else {
      errorMessage = "Error " + IntegerToString(Trade.ResultRetcode()) + ": " + Trade.ResultRetcodeDescription();
      Print("Trade execution failed for signal #", signalId, ": ", errorMessage);
      
      // Report error back to the API
      SendTradeReport(signalId, symbol, action, 0, lotSize, executionPrice, stopLoss, takeProfit, "error", errorMessage);
   }
}

//+------------------------------------------------------------------+
//| Place pending order based on signal                              |
//+------------------------------------------------------------------+
void PlacePendingOrder(int signalId, string symbol, string action, double entryPrice, 
                      double stopLoss, double takeProfit, double positionSize)
{
   // Apply fixed SL/TP if configured
   if(Fixed_SL_Points > 0) {
      // Calculate new SL based on direction
      if(action == "BUY_NOW" || action == "ANTICIPATED_LONG") {
         stopLoss = entryPrice - Fixed_SL_Points * SymbolInfoDouble(symbol, SYMBOL_POINT);
      }
      else if(action == "SELL_NOW" || action == "ANTICIPATED_SHORT") {
         stopLoss = entryPrice + Fixed_SL_Points * SymbolInfoDouble(symbol, SYMBOL_POINT);
      }
   }
   
   if(Fixed_TP_Points > 0) {
      // Calculate new TP based on direction
      if(action == "BUY_NOW" || action == "ANTICIPATED_LONG") {
         takeProfit = entryPrice + Fixed_TP_Points * SymbolInfoDouble(symbol, SYMBOL_POINT);
      }
      else if(action == "SELL_NOW" || action == "ANTICIPATED_SHORT") {
         takeProfit = entryPrice - Fixed_TP_Points * SymbolInfoDouble(symbol, SYMBOL_POINT);
      }
   }
   
   // Normalize prices to symbol digits
   entryPrice = NormalizeDouble(entryPrice, GetSymbolDigits(symbol));
   stopLoss = NormalizeDouble(stopLoss, GetSymbolDigits(symbol));
   takeProfit = NormalizeDouble(takeProfit, GetSymbolDigits(symbol));
   
   // Calculate lot size if position_size is not provided
   double lotSize = positionSize;
   if(lotSize <= 0) {
      lotSize = CalculateLotSize(symbol, Risk_Percent, entryPrice, stopLoss);
   }
   
   // Validate lot size
   double minLot = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
   double maxLot = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MAX);
   double lotStep = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
   
   lotSize = MathMax(minLot, lotSize);
   lotSize = MathMin(maxLot, lotSize);
   lotSize = NormalizeDouble(MathFloor(lotSize / lotStep) * lotStep, 2); // Round to nearest lot step
   
   // Determine order type
   ENUM_ORDER_TYPE orderType;
   
   // Get current market price
   double currentBid = SymbolInfoDouble(symbol, SYMBOL_BID);
   double currentAsk = SymbolInfoDouble(symbol, SYMBOL_ASK);
   
   // For anticipated long, if entry is below market, it's a BUY LIMIT
   // If entry is above market, it's a BUY STOP
   if(action == "ANTICIPATED_LONG") {
      if(entryPrice < currentAsk) {
         orderType = ORDER_TYPE_BUY_LIMIT;
      } else {
         orderType = ORDER_TYPE_BUY_STOP;
      }
   }
   // For anticipated short, if entry is above market, it's a SELL LIMIT
   // If entry is below market, it's a SELL STOP
   else if(action == "ANTICIPATED_SHORT") {
      if(entryPrice > currentBid) {
         orderType = ORDER_TYPE_SELL_LIMIT;
      } else {
         orderType = ORDER_TYPE_SELL_STOP;
      }
   }
   
   // Place the pending order
   Trade.SetExpertMagicNumber(signalId); // Use signal ID as magic number
   
   bool success = false;
   ulong ticket = 0;
   string errorMessage = "";
   
   // Calculate expiration time (24 hours from now)
   datetime expirationTime = TimeCurrent() + 24 * 60 * 60;
   
   // Execute pending order
   success = Trade.OrderOpen(symbol, orderType, lotSize, 0, entryPrice, stopLoss, takeProfit, 
                            ORDER_TIME_SPECIFIED, expirationTime, "GENESIS #"+IntegerToString(signalId));
   
   if(success) {
      ticket = Trade.ResultOrder();
      Print("Pending order placed: Ticket #", ticket, " for signal #", signalId);
      
      // Report success back to the API
      SendTradeReport(signalId, symbol, action, ticket, lotSize, entryPrice, stopLoss, takeProfit, "success", "Pending order placed");
   }
   else {
      errorMessage = "Error " + IntegerToString(Trade.ResultRetcode()) + ": " + Trade.ResultRetcodeDescription();
      Print("Pending order failed for signal #", signalId, ": ", errorMessage);
      
      // Report error back to the API
      SendTradeReport(signalId, symbol, action, 0, lotSize, entryPrice, stopLoss, takeProfit, "error", errorMessage);
   }
}

//+------------------------------------------------------------------+
//| Calculate lot size based on risk percentage and stop loss        |
//+------------------------------------------------------------------+
double CalculateLotSize(string symbol, double riskPercent, double entryPrice, double stopLoss)
{
   // Return minimum lot size if stop loss is not valid
   if(stopLoss <= 0 || entryPrice <= 0) {
      return SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
   }
   
   // Calculate risk amount
   double accountBalance = AccountInfoDouble(ACCOUNT_BALANCE);
   double riskAmount = accountBalance * riskPercent / 100.0;
   
   // Calculate SL distance in price
   double slDistance = MathAbs(entryPrice - stopLoss);
   
   // Calculate tick value and size
   double tickSize = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_SIZE);
   double tickValue = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_VALUE);
   
   // Calculate lot size based on risk
   double lotSize = 0;
   if(slDistance > 0 && tickSize > 0 && tickValue > 0) {
      // Calculate number of ticks in SL
      double numTicks = slDistance / tickSize;
      
      // Calculate lot size
      lotSize = riskAmount / (numTicks * tickValue);
   }
   else {
      // Fallback to minimum lot size
      lotSize = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
   }
   
   return lotSize;
}

//+------------------------------------------------------------------+
//| Check if market is open for a symbol                             |
//+------------------------------------------------------------------+
bool IsMarketOpenForSymbol(string symbol, bool force_execution=false)
{
   // If force execution is true, treat market as open
   if(force_execution) {
      return true;
   }

   // Check if it's a crypto symbol - allow trading 24/7
   if(StringFind(symbol, "BTC") >= 0 || StringFind(symbol, "ETH") >= 0 ||
      StringFind(symbol, "XRP") >= 0 || StringFind(symbol, "LTC") >= 0 ||
      StringFind(symbol, "BCH") >= 0 || StringFind(symbol, "ADA") >= 0 ||
      StringFind(symbol, "DOT") >= 0 || StringFind(symbol, "DOGE") >= 0 ||
      StringFind(symbol, "SOL") >= 0 || StringFind(symbol, "BNB") >= 0) {
      return true;
   }

   // Get trading session info
   MqlDateTime now;
   TimeToStruct(TimeCurrent(), now);
   
   // Check if symbol is tradable
   return SymbolInfoInteger(symbol, SYMBOL_TRADE_MODE) != SYMBOL_TRADE_MODE_DISABLED &&
          SymbolInfoInteger(symbol, SYMBOL_TRADE_MODE) != SYMBOL_TRADE_MODE_CLOSEONLY &&
          SymbolInfoInteger(symbol, SYMBOL_TRADE_MODE) != SYMBOL_TRADE_MODE_DISABLED;
}

//+------------------------------------------------------------------+
//| Draw trading signal on the chart                                 |
//+------------------------------------------------------------------+
void DrawSignalOnChart(int signalId, string action, double price, double stopLoss, double takeProfit)
{
   // Delete any existing objects for this signal
   DeleteSignalObjects(signalId);
   
   // Create signal label name
   string labelName = SignalPrefix + IntegerToString(signalId);
   
   // Create signal arrow on chart
   CreateSignalArrow(signalId, action, price);
   
   // Draw horizontal lines for entry, SL, TP
   string entryLineName = LinePrefix + "Entry_" + IntegerToString(signalId);
   string slLineName = LinePrefix + "SL_" + IntegerToString(signalId);
   string tpLineName = LinePrefix + "TP_" + IntegerToString(signalId);
   
   // Determine color based on action
   color entryColor;
   string direction;
   if(action == "BUY_NOW" || action == "ANTICIPATED_LONG") {
      entryColor = BuyNowColor;
      direction = "BUY";
   }
   else if(action == "SELL_NOW" || action == "ANTICIPATED_SHORT") {
      entryColor = SellNowColor;
      direction = "SELL";
   }
   else {
      // Unknown action, use default color
      entryColor = clrYellow;
      direction = action;
   }
   
   // Calculate SL/TP distance in points
   double slDistance = 0;
   double tpDistance = 0;
   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   
   if(stopLoss > 0) {
      if(action == "BUY_NOW" || action == "ANTICIPATED_LONG") {
         slDistance = (price - stopLoss) / point;
      }
      else {
         slDistance = (stopLoss - price) / point;
      }
   }
   
   if(takeProfit > 0) {
      if(action == "BUY_NOW" || action == "ANTICIPATED_LONG") {
         tpDistance = (takeProfit - price) / point;
      }
      else {
         tpDistance = (price - takeProfit) / point;
      }
   }
   
   // Draw entry line if price is valid
   if(price > 0) {
      if(ObjectCreate(0, entryLineName, OBJ_HLINE, 0, 0, price)) {
         ObjectSetInteger(0, entryLineName, OBJPROP_COLOR, entryColor);
         ObjectSetInteger(0, entryLineName, OBJPROP_WIDTH, 1);
         ObjectSetInteger(0, entryLineName, OBJPROP_STYLE, STYLE_SOLID);
         ObjectSetString(0, entryLineName, OBJPROP_TOOLTIP, "GENESIS Signal #" + IntegerToString(signalId) + "\nEntry: " + direction);
      }
   }
   
   // Draw stop loss line if SL is valid
   if(stopLoss > 0) {
      if(ObjectCreate(0, slLineName, OBJ_HLINE, 0, 0, stopLoss)) {
         ObjectSetInteger(0, slLineName, OBJPROP_COLOR, StopLossColor);
         ObjectSetInteger(0, slLineName, OBJPROP_WIDTH, 1);
         ObjectSetInteger(0, slLineName, OBJPROP_STYLE, STYLE_SOLID);
         ObjectSetString(0, slLineName, OBJPROP_TOOLTIP, "GENESIS Signal #" + IntegerToString(signalId) + "\nStop Loss: " + DoubleToString(slDistance, 0) + " points");
      }
   }
   
   // Draw take profit line if TP is valid
   if(takeProfit > 0) {
      if(ObjectCreate(0, tpLineName, OBJ_HLINE, 0, 0, takeProfit)) {
         ObjectSetInteger(0, tpLineName, OBJPROP_COLOR, TakeProfitColor);
         ObjectSetInteger(0, tpLineName, OBJPROP_WIDTH, 1);
         ObjectSetInteger(0, tpLineName, OBJPROP_STYLE, STYLE_SOLID);
         ObjectSetString(0, tpLineName, OBJPROP_TOOLTIP, "GENESIS Signal #" + IntegerToString(signalId) + "\nTake Profit: " + DoubleToString(tpDistance, 0) + " points");
      }
   }
   
   // Add label with signal details
   string textName = TextPrefix + IntegerToString(signalId);
   string signalText = "#" + IntegerToString(signalId) + ": " + direction;
   if(slDistance > 0) signalText += " SL:" + DoubleToString(slDistance, 0);
   if(tpDistance > 0) signalText += " TP:" + DoubleToString(tpDistance, 0);
   
   datetime labelTime = TimeCurrent();
   if(ObjectCreate(0, textName, OBJ_TEXT, 0, labelTime, price)) {
      ObjectSetString(0, textName, OBJPROP_TEXT, signalText);
      ObjectSetInteger(0, textName, OBJPROP_COLOR, TextColor);
      ObjectSetInteger(0, textName, OBJPROP_FONTSIZE, 8);
      ObjectSetString(0, textName, OBJPROP_FONT, "Arial");
      ObjectSetString(0, textName, OBJPROP_TOOLTIP, "GENESIS Signal #" + IntegerToString(signalId));
   }
   
   ChartRedraw(0); // Refresh chart to show all objects
}

//+------------------------------------------------------------------+
//| Delete all objects for a specific signal                         |
//+------------------------------------------------------------------+
void DeleteSignalObjects(int signalId)
{
   // Create object names for this signal
   string labelName = SignalPrefix + IntegerToString(signalId);
   string entryLineName = LinePrefix + "Entry_" + IntegerToString(signalId);
   string slLineName = LinePrefix + "SL_" + IntegerToString(signalId);
   string tpLineName = LinePrefix + "TP_" + IntegerToString(signalId);
   string textName = TextPrefix + IntegerToString(signalId);
   string arrowName = ArrowPrefix + IntegerToString(signalId);
   
   // Delete objects
   ObjectDelete(0, labelName);
   ObjectDelete(0, entryLineName);
   ObjectDelete(0, slLineName);
   ObjectDelete(0, tpLineName);
   ObjectDelete(0, textName);
   ObjectDelete(0, arrowName);
   
   ChartRedraw(0); // Refresh chart
}

//+------------------------------------------------------------------+
//| Delete all signal objects from the chart                         |
//+------------------------------------------------------------------+
void DeleteAllSignalObjects()
{
   int totalObjects = ObjectsTotal(0, 0, -1);
   
   for(int i = totalObjects - 1; i >= 0; i--) {
      string objName = ObjectName(0, i);
      
      if(StringFind(objName, SignalPrefix) == 0 ||
         StringFind(objName, LinePrefix) == 0 ||
         StringFind(objName, TextPrefix) == 0 ||
         StringFind(objName, ArrowPrefix) == 0) {
         ObjectDelete(0, objName);
      }
   }
   
   ChartRedraw(0);
}

//+------------------------------------------------------------------+
//| Create arrow on chart for signal                                 |
//+------------------------------------------------------------------+
void CreateSignalArrow(int signalId, string action, double price)
{
   // Create arrow object name
   string objName = ArrowPrefix + IntegerToString(signalId);
   
   // Determine arrow code and color based on signal action
   int arrowCode;
   color arrowColor;
   string direction;
   
   if(action == "BUY_NOW") {
      arrowCode = OBJ_ARROW_BUY;
      arrowColor = BuyNowColor;
      direction = "BUY NOW";
   }
   else if(action == "SELL_NOW") {
      arrowCode = OBJ_ARROW_SELL;
      arrowColor = SellNowColor;
      direction = "SELL NOW";
   }
   else if(action == "ANTICIPATED_LONG") {
      arrowCode = OBJ_ARROW_UP;
      arrowColor = AnticipatedLongColor;
      direction = "ANTICIPATED LONG";
   }
   else if(action == "ANTICIPATED_SHORT") {
      arrowCode = OBJ_ARROW_DOWN;
      arrowColor = AnticipatedShortColor;
      direction = "ANTICIPATED SHORT";
   }
   else {
      // Unknown action, use default arrow
      arrowCode = OBJ_ARROW_THUMB_UP;
      arrowColor = clrYellow;
      direction = action;
   }
   
   // For buy/long signals, place arrow below price
   // For sell/short signals, place arrow above price
   if(action == "BUY_NOW" || action == "ANTICIPATED_LONG") {
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
      arrowPrice -= ArrowOffset * SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   }
   else {
      arrowPrice += ArrowOffset * SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   }
   
   // Create the arrow object
   if(ObjectCreate(0, objName, OBJ_ARROW, 0, TimeCurrent(), arrowPrice)) {
      ObjectSetInteger(0, objName, OBJPROP_ARROWCODE, arrowCode);
      ObjectSetInteger(0, objName, OBJPROP_COLOR, arrowColor);
      ObjectSetInteger(0, objName, OBJPROP_WIDTH, SignalArrowSize);
      ObjectSetInteger(0, objName, OBJPROP_SELECTABLE, false);
      ObjectSetString(0, objName, OBJPROP_TOOLTIP, "GENESIS Signal #" + IntegerToString(signalId) + "\n" + direction);
      ChartRedraw(0); // Refresh chart to show the arrow
      
      if(Debug_Mode) {
         Print("Drew signal arrow on chart: ", objName, " at ", DoubleToString(arrowPrice, GetSymbolDigits(_Symbol)));
      }
   }
   else if(Debug_Mode) {
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
   
   if(Debug_Mode) {
      Print("Deleted all signal arrows from chart");
   }
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
   JsonToSend["original_signal_id"] = signalId;  // Add for proper tracking
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
         if(Debug_Mode) {
            Print("Trade report sent successfully for signal #", signalId);
         }
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
   string result_headers;
   
   // Convert postData to char array
   StringToCharArray(postData, data, 0, StringLen(postData));
   
   // Send POST request
   int res = WebRequest("POST", url, NULL, NULL, timeout, data, ArraySize(data), result, result_headers);
   
   // Check for errors
   if(res == -1) {
      int error_code = GetLastError();
      Print("WebRequest failed with error: ", error_code, " - ", ErrorDescription(error_code));
      
      if(error_code == 4060) {
         // Permission issue with WebRequest
         Print("Make sure URL ", url, " is allowed in Expert Advisors tab of Terminal settings");
      }
      
      return false;
   }
   
   // Convert response to string
   responseData = CharArrayToString(result, 0, WHOLE_ARRAY);
   return true;
}

//+------------------------------------------------------------------+
//| Send heartbeat to GENESIS backend                                |
//+------------------------------------------------------------------+
void SendHeartbeat()
{
   // Prepare JSON data
   JsonToSend.Clear();
   JsonToSend["account_id"] = AccountName;
   JsonToSend["terminal_id"] = IntegerToString(TerminalInfoInteger(TERMINAL_COMMUNITY_ID));
   JsonToSend["connection_time"] = TimeToString(TimeCurrent(), TIME_DATE|TIME_SECONDS);
   
   // Send request
   string jsonString = JsonToSend.Serialize();
   string response = "";
   
   bool success = SendPostRequest(HEARTBEAT_URL, jsonString, response);
   
   if(success && Debug_Mode) {
      Print("Heartbeat sent successfully");
   }
   else if(!success) {
      Print("Failed to send heartbeat");
   }
}

//+------------------------------------------------------------------+
//| Send account status to GENESIS backend                           |
//+------------------------------------------------------------------+
void SendAccountStatus()
{
   // Prepare JSON data
   JsonToSend.Clear();
   JsonToSend["account_id"] = AccountName;
   JsonToSend["balance"] = AccountInfoDouble(ACCOUNT_BALANCE);
   JsonToSend["equity"] = AccountInfoDouble(ACCOUNT_EQUITY);
   JsonToSend["margin"] = AccountInfoDouble(ACCOUNT_MARGIN);
   JsonToSend["free_margin"] = AccountInfoDouble(ACCOUNT_MARGIN_FREE);
   JsonToSend["leverage"] = AccountInfoInteger(ACCOUNT_LEVERAGE);
   JsonToSend["open_positions"] = PositionsTotal();
   
   // Send request
   string jsonString = JsonToSend.Serialize();
   string response = "";
   
   bool success = SendPostRequest(ACCOUNT_STATUS_URL, jsonString, response);
   
   if(success && Debug_Mode) {
      Print("Account status sent successfully");
   }
   else if(!success) {
      Print("Failed to send account status");
   }
}

//+------------------------------------------------------------------+
//| Check if a signal ID has already been processed                  |
//+------------------------------------------------------------------+
bool IsSignalProcessed(string signalId)
{
   for(int i=0; i<ProcessedSignals.Total(); i++) {
      if(ProcessedSignals.At(i) == signalId) {
         return true;
      }
   }
   return false;
}

//+------------------------------------------------------------------+
//| Mark a signal as processed                                       |
//+------------------------------------------------------------------+
void MarkSignalAsProcessed(string signalId)
{
   ProcessedSignals.Add(signalId);
   // Trim the array if it gets too large
   if(ProcessedSignals.Total() > 100) {
      ProcessedSignals.Delete(0);
   }
}

//+------------------------------------------------------------------+
//| Check if a trade ID has already been sent                        |
//+------------------------------------------------------------------+
bool IsTradeAlreadySent(string tradeId)
{
   for(int i=0; i<SentTrades.Total(); i++) {
      if(SentTrades.At(i) == tradeId) {
         return true;
      }
   }
   return false;
}

//+------------------------------------------------------------------+
//| Mark a trade as sent                                             |
//+------------------------------------------------------------------+
void MarkTradeAsSent(string tradeId)
{
   SentTrades.Add(tradeId);
   // Trim the array if it gets too large
   if(SentTrades.Total() > 200) {
      SentTrades.Delete(0);
   }
}

//+------------------------------------------------------------------+
//| Create account statistics overlay                                |
//+------------------------------------------------------------------+
void CreateStatsOverlay()
{
   // Create background label
   string bgName = StatsLabelPrefix + "BG";
   if(ObjectCreate(0, bgName, OBJ_RECTANGLE_LABEL, 0, 0, 0)) {
      ObjectSetInteger(0, bgName, OBJPROP_CORNER, CORNER_LEFT_UPPER);
      ObjectSetInteger(0, bgName, OBJPROP_XDISTANCE, 10);
      ObjectSetInteger(0, bgName, OBJPROP_YDISTANCE, 10);
      ObjectSetInteger(0, bgName, OBJPROP_XSIZE, StatsLabelWidth);
      ObjectSetInteger(0, bgName, OBJPROP_YSIZE, 100);
      ObjectSetInteger(0, bgName, OBJPROP_COLOR, StatsBorderColor);
      ObjectSetInteger(0, bgName, OBJPROP_BGCOLOR, StatsLabelColor);
      ObjectSetInteger(0, bgName, OBJPROP_BORDER_TYPE, BORDER_FLAT);
      ObjectSetInteger(0, bgName, OBJPROP_WIDTH, 1);
      ObjectSetInteger(0, bgName, OBJPROP_BACK, false);
      ObjectSetInteger(0, bgName, OBJPROP_SELECTABLE, false);
   }
   
   // Create text labels
   string titleName = StatsLabelPrefix + "Title";
   string balanceName = StatsLabelPrefix + "Balance";
   string equityName = StatsLabelPrefix + "Equity";
   string marginName = StatsLabelPrefix + "Margin";
   string positionsName = StatsLabelPrefix + "Positions";
   
   // Title label
   if(ObjectCreate(0, titleName, OBJ_LABEL, 0, 0, 0)) {
      ObjectSetInteger(0, titleName, OBJPROP_CORNER, CORNER_LEFT_UPPER);
      ObjectSetInteger(0, titleName, OBJPROP_XDISTANCE, 15);
      ObjectSetInteger(0, titleName, OBJPROP_YDISTANCE, 15);
      ObjectSetString(0, titleName, OBJPROP_TEXT, "GENESIS Trading Stats");
      ObjectSetString(0, titleName, OBJPROP_FONT, "Arial");
      ObjectSetInteger(0, titleName, OBJPROP_FONTSIZE, 9);
      ObjectSetInteger(0, titleName, OBJPROP_COLOR, StatsTextColor);
      ObjectSetInteger(0, titleName, OBJPROP_SELECTABLE, false);
   }
   
   // Balance label
   if(ObjectCreate(0, balanceName, OBJ_LABEL, 0, 0, 0)) {
      ObjectSetInteger(0, balanceName, OBJPROP_CORNER, CORNER_LEFT_UPPER);
      ObjectSetInteger(0, balanceName, OBJPROP_XDISTANCE, 15);
      ObjectSetInteger(0, balanceName, OBJPROP_YDISTANCE, 35);
      ObjectSetString(0, balanceName, OBJPROP_TEXT, "Balance: 0.00");
      ObjectSetString(0, balanceName, OBJPROP_FONT, "Arial");
      ObjectSetInteger(0, balanceName, OBJPROP_FONTSIZE, 9);
      ObjectSetInteger(0, balanceName, OBJPROP_COLOR, StatsTextColor);
      ObjectSetInteger(0, balanceName, OBJPROP_SELECTABLE, false);
   }
   
   // Equity label
   if(ObjectCreate(0, equityName, OBJ_LABEL, 0, 0, 0)) {
      ObjectSetInteger(0, equityName, OBJPROP_CORNER, CORNER_LEFT_UPPER);
      ObjectSetInteger(0, equityName, OBJPROP_XDISTANCE, 15);
      ObjectSetInteger(0, equityName, OBJPROP_YDISTANCE, 52);
      ObjectSetString(0, equityName, OBJPROP_TEXT, "Equity: 0.00");
      ObjectSetString(0, equityName, OBJPROP_FONT, "Arial");
      ObjectSetInteger(0, equityName, OBJPROP_FONTSIZE, 9);
      ObjectSetInteger(0, equityName, OBJPROP_COLOR, StatsTextColor);
      ObjectSetInteger(0, equityName, OBJPROP_SELECTABLE, false);
   }
   
   // Margin label
   if(ObjectCreate(0, marginName, OBJ_LABEL, 0, 0, 0)) {
      ObjectSetInteger(0, marginName, OBJPROP_CORNER, CORNER_LEFT_UPPER);
      ObjectSetInteger(0, marginName, OBJPROP_XDISTANCE, 15);
      ObjectSetInteger(0, marginName, OBJPROP_YDISTANCE, 69);
      ObjectSetString(0, marginName, OBJPROP_TEXT, "Margin: 0.00");
      ObjectSetString(0, marginName, OBJPROP_FONT, "Arial");
      ObjectSetInteger(0, marginName, OBJPROP_FONTSIZE, 9);
      ObjectSetInteger(0, marginName, OBJPROP_COLOR, StatsTextColor);
      ObjectSetInteger(0, marginName, OBJPROP_SELECTABLE, false);
   }
   
   // Positions label
   if(ObjectCreate(0, positionsName, OBJ_LABEL, 0, 0, 0)) {
      ObjectSetInteger(0, positionsName, OBJPROP_CORNER, CORNER_LEFT_UPPER);
      ObjectSetInteger(0, positionsName, OBJPROP_XDISTANCE, 15);
      ObjectSetInteger(0, positionsName, OBJPROP_YDISTANCE, 86);
      ObjectSetString(0, positionsName, OBJPROP_TEXT, "Open Positions: 0");
      ObjectSetString(0, positionsName, OBJPROP_FONT, "Arial");
      ObjectSetInteger(0, positionsName, OBJPROP_FONTSIZE, 9);
      ObjectSetInteger(0, positionsName, OBJPROP_COLOR, StatsTextColor);
      ObjectSetInteger(0, positionsName, OBJPROP_SELECTABLE, false);
   }
   
   ChartRedraw();
}

//+------------------------------------------------------------------+
//| Update account statistics overlay                                 |
//+------------------------------------------------------------------+
void UpdateStatsOverlay()
{
   if(!Enable_Stats_Overlay) return;
   
   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   double margin = AccountInfoDouble(ACCOUNT_MARGIN);
   int positions = PositionsTotal();
   
   // Update text labels
   string balanceName = StatsLabelPrefix + "Balance";
   string equityName = StatsLabelPrefix + "Equity";
   string marginName = StatsLabelPrefix + "Margin";
   string positionsName = StatsLabelPrefix + "Positions";
   
   ObjectSetString(0, balanceName, OBJPROP_TEXT, "Balance: " + DoubleToString(balance, 2));
   ObjectSetString(0, equityName, OBJPROP_TEXT, "Equity: " + DoubleToString(equity, 2));
   ObjectSetString(0, marginName, OBJPROP_TEXT, "Margin: " + DoubleToString(margin, 2));
   ObjectSetString(0, positionsName, OBJPROP_TEXT, "Open Positions: " + IntegerToString(positions));
   
   ChartRedraw();
}

//+------------------------------------------------------------------+
//| Delete account statistics overlay                                 |
//+------------------------------------------------------------------+
void DeleteStatsOverlay()
{
   int totalObjects = ObjectsTotal(0, 0, -1);
   
   for(int i = totalObjects - 1; i >= 0; i--) {
      string objName = ObjectName(0, i);
      if(StringFind(objName, StatsLabelPrefix) == 0) {
         ObjectDelete(0, objName);
      }
   }
   
   ChartRedraw();
}

//+------------------------------------------------------------------+
//| Send trade updates (both open and closed positions)              |
//+------------------------------------------------------------------+
void SendTradeUpdates()
{
   // Initialize JSON structure
   JsonToSend.Clear();
   JsonToSend["account_id"] = AccountName;
   
   // Create trades object
   CJAVal trades;
   bool hasData = false;
   
   // First, collect open positions
   int openPositions = PositionsTotal();
   if(openPositions > 0 && Debug_Mode) {
      Print("Found ", openPositions, " open positions");
   }
   
   for(int i=0; i<openPositions; i++) {
      ulong posTicket = PositionGetTicket(i);
      if(posTicket <= 0) continue;
      
      // Get position details
      if(PositionSelectByTicket(posTicket)) {
         string symbol = PositionGetString(POSITION_SYMBOL);
         double volume = PositionGetDouble(POSITION_VOLUME);
         double openPrice = PositionGetDouble(POSITION_PRICE_OPEN);
         double currentPrice = PositionGetDouble(POSITION_PRICE_CURRENT);
         double profit = PositionGetDouble(POSITION_PROFIT);
         double sl = PositionGetDouble(POSITION_SL);
         double tp = PositionGetDouble(POSITION_TP);
         ENUM_POSITION_TYPE posType = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
         datetime openTime = (datetime)PositionGetInteger(POSITION_TIME);
         
         if(Debug_Mode) {
            Print("Processing open position: Ticket=", posTicket, ", Symbol=", symbol, ", Open Price=", openPrice, ", Current Price=", currentPrice, ", Profit=", profit);
            Print("Setting opened_at for position ", posTicket, " to: ", TimeToString(openTime, TIME_DATE|TIME_SECONDS));
         }
         
         // Create trade object
         CJAVal trade;
         trade["symbol"] = symbol;
         trade["lot"] = DoubleToString(volume, 2);
         trade["type"] = (posType == POSITION_TYPE_BUY) ? "BUY" : "SELL";
         trade["open_price"] = DoubleToString(openPrice, GetSymbolDigits(symbol));
         trade["current_price"] = DoubleToString(currentPrice, GetSymbolDigits(symbol));
         trade["profit"] = DoubleToString(profit, 2);
         trade["sl"] = DoubleToString(sl, GetSymbolDigits(symbol));
         trade["tp"] = DoubleToString(tp, GetSymbolDigits(symbol));
         trade["status"] = "OPEN";
         
         // Add opened_at timestamp
         if(openTime > 0) {
            trade["opened_at"] = TimeToString(openTime, TIME_DATE|TIME_SECONDS);
         }
         
         // Use position ticket as key
         trades[IntegerToString(posTicket)] = trade;
         hasData = true;
      }
   }
   
   // Then, search history for recent closed trades
   int closedDealsCount = 0;
   
   // Select history for last month
   datetime endTime = TimeCurrent();
   datetime startTime = endTime - 30 * 24 * 60 * 60; // 30 days ago
   
   if(Debug_Mode) {
      Print("History select returned: ", HistorySelect(startTime, endTime), " for period ", 
             TimeToString(startTime, TIME_DATE|TIME_MINUTES), " to ", 
             TimeToString(endTime, TIME_DATE|TIME_MINUTES));
   }
   
   if(HistorySelect(startTime, endTime)) {
      // Count deals in history
      int dealsTotal = HistoryDealsTotal();
      
      if(Debug_Mode) {
         Print("Found ", dealsTotal, " total deals in history");
      }
      
      // Process each deal in history
      for(int i=0; i<dealsTotal; i++) {
         ulong dealTicket = HistoryDealGetTicket(i);
         
         if(dealTicket <= 0) continue;
         
         // Check if this is a close/out deal 
         ENUM_DEAL_ENTRY dealEntry = (ENUM_DEAL_ENTRY)HistoryDealGetInteger(dealTicket, DEAL_ENTRY);
         
         if(dealEntry == DEAL_ENTRY_OUT) {
            // Get deal details
            string symbol = HistoryDealGetString(dealTicket, DEAL_SYMBOL);
            ulong posId = HistoryDealGetInteger(dealTicket, DEAL_POSITION_ID);
            double volume = HistoryDealGetDouble(dealTicket, DEAL_VOLUME);
            double price = HistoryDealGetDouble(dealTicket, DEAL_PRICE);
            double profit = HistoryDealGetDouble(dealTicket, DEAL_PROFIT);
            ENUM_DEAL_TYPE dealType = (ENUM_DEAL_TYPE)HistoryDealGetInteger(dealTicket, DEAL_TYPE);
            datetime closeTime = (datetime)HistoryDealGetInteger(dealTicket, DEAL_TIME);
            
            // Create a unique ID for this closed trade
            string tradeId = "closed_" + IntegerToString(posId);
            
            // Only process if we haven't seen this position before
            if(!IsTradeAlreadySent(tradeId))
            {
               if(Debug_Mode) {
                  Print("Found closed deal: Deal=", dealTicket, ", Position=", posId, ", Symbol=", symbol, ", Volume=", volume, ", Exit Price=", price, ", Profit=", profit, ", Close Time=", TimeToString(closeTime, TIME_DATE|TIME_SECONDS));
               }
               
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
                     
                     if(Debug_Mode) {
                        Print("Found matching entry deal: Deal=", inDealTicket, ", Entry Price=", entryPrice, ", Open Time=", TimeToString(openTime, TIME_DATE|TIME_SECONDS), ", Type=", type);
                     }
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
                  if(Debug_Mode) {
                     Print("Setting opened_at to: ", TimeToString(openTime, TIME_DATE|TIME_SECONDS));
                  }
               }
               
               // IMPORTANT: Make sure closed_at uses the actual close time
               trade["closed_at"] = TimeToString(closeTime, TIME_DATE|TIME_SECONDS);
               if(Debug_Mode) {
                  Print("Setting closed_at to: ", TimeToString(closeTime, TIME_DATE|TIME_SECONDS));
               }
               
               // Use position ID as key
               trades[IntegerToString(posId)] = trade;
               MarkTradeAsSent(tradeId);
               closedDealsCount++;
               hasData = true;
               if(Debug_Mode) {
                  Print("Added closed position to update: Position=", posId);
               }
            }
         }
      }
      
      if(Debug_Mode) {
         Print("Added ", closedDealsCount, " closed trades to the update");
      }
   }
   else if(Debug_Mode)
   {
      Print("Failed to select history for the period");
   }
   
   // Add trades to main JSON
   JsonToSend["trades"] = trades;
   
   // Log the full payload for debugging
   string jsonString = JsonToSend.Serialize();
   if(Debug_Mode) {
      Print("Trade update payload: ", jsonString);
   }
   
   // Only send if we have data
   if(hasData) {
      string response = "";
      bool success = SendPostRequest(TRADE_UPDATE_URL, jsonString, response);
      
      if(success) {
         if(Debug_Mode) {
            Print("Trade updates sent successfully. Response: ", response);
         }
      }
      else {
         Print("Failed to send trade updates");
      }
   }
   else if(Debug_Mode) {
      Print("No trade data found to send");
   }
   
   if(Debug_Mode) {
      Print("======= COMPLETED TRADE UPDATES =======");
   }
}