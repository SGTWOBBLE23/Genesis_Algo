//+------------------------------------------------------------------+
//|                                              GENESIS_MT5_EA.mq5 |
//|                                       Copyright 2025, GENESIS |
//|                                             https://genesis.ai |
//+------------------------------------------------------------------+
#property copyright "Copyright 2025, GENESIS"
#property link      "https://genesis.ai"
#property version   "1.05"

// Include necessary libraries
#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>
#include <Trade\OrderInfo.mqh>
#include <Trade\SymbolInfo.mqh>
#include <Tools\JsonWriter.mqh>

// API Configuration
string APIEndpoint = "http://localhost:5500/api/v1"; // Default endpoint
string APIToken = "";  // Security token

// Global variables
CTrade Trade;
CPositionInfo PositionInfo;
COrderInfo OrderInfo;
CSymbolInfo SymbolInfo;

// Timer interval in milliseconds (default: 1000ms = 1 second)
int TimerInterval = 1000;

// Additional parameters
double RiskPercent = 1.0;  // Default risk percentage
bool AutoSL = true;        // Auto Stop Loss
bool AutoTP = true;        // Auto Take Profit
int DefaultSLPips = 30;    // Default Stop Loss in pips
int DefaultTPPips = 60;    // Default Take Profit in pips

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   // Initialize timer for regular API communication
   EventSetMillisecondTimer(TimerInterval);
   
   // Output initialization message
   Print("GENESIS MT5 EA initialized. Connected to: ", APIEndpoint);
   
   // Send initial connection message
   SendHeartbeat();
   
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   // Kill the timer
   EventKillTimer();
   
   // Output shutdown message
   Print("GENESIS MT5 EA shutdown. Reason code: ", reason);
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   // Process pending signals
   ProcessPendingSignals();
}

//+------------------------------------------------------------------+
//| Timer function                                                   |
//+------------------------------------------------------------------+
void OnTimer()
{
   // Send heartbeat to keep connection alive
   SendHeartbeat();
   
   // Process pending signals
   ProcessPendingSignals();
   
   // Update trades status
   UpdateTradesStatus();
}

//+------------------------------------------------------------------+
//| Send heartbeat to the server                                     |
//+------------------------------------------------------------------+
void SendHeartbeat()
{
   // Prepare heartbeat data
   CJSONWriter json;
   
   json.WriteStart();
   json.Write("action", "heartbeat");
   json.Write("terminal_id", TerminalInfoString(TERMINAL_NAME));
   json.Write("account_id", AccountInfoInteger(ACCOUNT_LOGIN));
   json.Write("account_balance", AccountInfoDouble(ACCOUNT_BALANCE));
   json.Write("account_equity", AccountInfoDouble(ACCOUNT_EQUITY));
   json.Write("account_margin", AccountInfoDouble(ACCOUNT_MARGIN));
   json.Write("account_free_margin", AccountInfoDouble(ACCOUNT_MARGIN_FREE));
   json.Write("account_currency", AccountInfoString(ACCOUNT_CURRENCY));
   json.Write("account_leverage", AccountInfoInteger(ACCOUNT_LEVERAGE));
   json.Write("open_positions", PositionsTotal());
   json.WriteEnd();
   
   // Send data to the API
   string response = SendAPIRequest("POST", "/heartbeat", json.GetData());
   
   // Debug output
   if(StringLen(response) > 0)
   {
      // Process response if needed
      if(StringFind(response, "config") >= 0)
      {
         // Update EA settings from server config
         UpdateEASettings(response);
      }
   }
}

//+------------------------------------------------------------------+
//| Update EA settings from server config                            |
//+------------------------------------------------------------------+
void UpdateEASettings(string jsonResponse)
{
   // Parse JSON and update settings
   // Simple example - production version would use proper JSON parsing
   if(StringFind(jsonResponse, "riskPercent") >= 0)
   {
      // Extract and update risk percent
      string riskStr = ExtractJsonValue(jsonResponse, "riskPercent");
      if(StringLen(riskStr) > 0)
         RiskPercent = StringToDouble(riskStr);
   }
   
   if(StringFind(jsonResponse, "autoSL") >= 0)
   {
      // Extract and update auto SL setting
      string autoSLStr = ExtractJsonValue(jsonResponse, "autoSL");
      if(StringLen(autoSLStr) > 0)
         AutoSL = (StringCompare(autoSLStr, "true") == 0);
   }
   
   if(StringFind(jsonResponse, "autoTP") >= 0)
   {
      // Extract and update auto TP setting
      string autoTPStr = ExtractJsonValue(jsonResponse, "autoTP");
      if(StringLen(autoTPStr) > 0)
         AutoTP = (StringCompare(autoTPStr, "true") == 0);
   }
   
   if(StringFind(jsonResponse, "defaultSLPips") >= 0)
   {
      // Extract and update default SL pips
      string slPipsStr = ExtractJsonValue(jsonResponse, "defaultSLPips");
      if(StringLen(slPipsStr) > 0)
         DefaultSLPips = (int)StringToInteger(slPipsStr);
   }
   
   if(StringFind(jsonResponse, "defaultTPPips") >= 0)
   {
      // Extract and update default TP pips
      string tpPipsStr = ExtractJsonValue(jsonResponse, "defaultTPPips");
      if(StringLen(tpPipsStr) > 0)
         DefaultTPPips = (int)StringToInteger(tpPipsStr);
   }
   
   if(StringFind(jsonResponse, "apiEndpoint") >= 0)
   {
      // Extract and update API endpoint
      string endpointStr = ExtractJsonValue(jsonResponse, "apiEndpoint");
      if(StringLen(endpointStr) > 0)
         APIEndpoint = endpointStr;
   }
   
   if(StringFind(jsonResponse, "apiToken") >= 0)
   {
      // Extract and update API token
      string tokenStr = ExtractJsonValue(jsonResponse, "apiToken");
      if(StringLen(tokenStr) > 0)
         APIToken = tokenStr;
   }
   
   // Log updated settings
   Print("EA settings updated from server");
}

//+------------------------------------------------------------------+
//| Extract JSON value - simple implementation                       |
//+------------------------------------------------------------------+
string ExtractJsonValue(string json, string key)
{
   string searchKey = "\"" + key + "\":\"";
   int pos = StringFind(json, searchKey);
   
   if(pos < 0)
   {
      // Try without quotes for numeric values
      searchKey = "\"" + key + "\":";
      pos = StringFind(json, searchKey);
      
      if(pos < 0)
         return "";
   }
   
   int valueStart = pos + StringLen(searchKey);
   int valueEnd = StringFind(json, "\"", valueStart);
   
   if(valueEnd < 0) // Might be a numeric value without quotes
   {
      valueEnd = StringFind(json, ",", valueStart);
      if(valueEnd < 0)
         valueEnd = StringFind(json, "}", valueStart);
   }
   
   if(valueEnd < 0)
      return "";
      
   return StringSubstr(json, valueStart, valueEnd - valueStart);
}

//+------------------------------------------------------------------+
//| Process pending trade signals                                    |
//+------------------------------------------------------------------+
void ProcessPendingSignals()
{
   // Get pending signals from the API
   string response = SendAPIRequest("GET", "/signals/pending", "");
   
   if(StringLen(response) > 0 && StringFind(response, "signals") >= 0)
   {
      // Process each signal
      // Production version would use proper JSON array parsing
      // Basic implementation for example purposes
      string signalId = ExtractJsonValue(response, "id");
      string symbol = ExtractJsonValue(response, "symbol");
      string action = ExtractJsonValue(response, "action");
      string entryPrice = ExtractJsonValue(response, "entry");
      string stopLoss = ExtractJsonValue(response, "sl");
      string takeProfit = ExtractJsonValue(response, "tp");
      
      if(StringLen(signalId) > 0 && StringLen(symbol) > 0 && StringLen(action) > 0)
      {
         ExecuteTradeSignal(signalId, symbol, action, entryPrice, stopLoss, takeProfit);
      }
   }
}

//+------------------------------------------------------------------+
//| Execute a trade signal                                           |
//+------------------------------------------------------------------+
void ExecuteTradeSignal(string signalId, string symbol, string action,
                       string entryPriceStr, string stopLossStr, string takeProfitStr)
{
   Print("Executing signal: ", signalId, " for ", symbol, " action: ", action);
   
   // Check if symbol exists
   if(!SymbolInfo.SetSymbol(symbol))
   {
      Print("Symbol not found: ", symbol);
      SendSignalUpdate(signalId, "error", "Symbol not found");
      return;
   }
   
   // Determine trade direction
   ENUM_ORDER_TYPE orderType = ORDER_TYPE_BUY;
   if(StringCompare(action, "SELL_NOW") == 0 || StringCompare(action, "ANTICIPATED_SHORT") == 0)
      orderType = ORDER_TYPE_SELL;
   
   // Calculate lot size based on risk
   double lotSize = CalculateLotSize(symbol, RiskPercent, stopLossStr);
   if(lotSize <= 0)
   {
      Print("Invalid lot size calculated");
      SendSignalUpdate(signalId, "error", "Invalid lot size");
      return;
   }
   
   // Set entry price if specified, otherwise use market price
   double entryPrice = 0;
   if(StringLen(entryPriceStr) > 0)
      entryPrice = StringToDouble(entryPriceStr);
   
   // Set stop loss and take profit
   double stopLoss = 0;
   if(StringLen(stopLossStr) > 0)
      stopLoss = StringToDouble(stopLossStr);
   else if(AutoSL)
      stopLoss = CalculateStopLoss(symbol, orderType, DefaultSLPips);
   
   double takeProfit = 0;
   if(StringLen(takeProfitStr) > 0)
      takeProfit = StringToDouble(takeProfitStr);
   else if(AutoTP)
      takeProfit = CalculateTakeProfit(symbol, orderType, DefaultTPPips);
   
   // Execute the trade
   bool result = false;
   string resultMessage = "";
   
   if(entryPrice > 0) // Pending order
   {
      // For anticipated signals - pending orders
      ENUM_ORDER_TYPE orderTypeLimit = (orderType == ORDER_TYPE_BUY) ? ORDER_TYPE_BUY_LIMIT : ORDER_TYPE_SELL_LIMIT;
      
      // Adjust for market price check (implement proper price check in production)
      double currentPrice = SymbolInfo.Ask();
      if(orderType == ORDER_TYPE_SELL)
         currentPrice = SymbolInfo.Bid();
      
      if((orderType == ORDER_TYPE_BUY && entryPrice > currentPrice) ||
         (orderType == ORDER_TYPE_SELL && entryPrice < currentPrice))
      {
         // Switch to stop order instead of limit
         orderTypeLimit = (orderType == ORDER_TYPE_BUY) ? ORDER_TYPE_BUY_STOP : ORDER_TYPE_SELL_STOP;
      }
      
      result = Trade.OrderOpen(symbol, orderTypeLimit, lotSize, entryPrice, stopLoss, takeProfit);
      if(result)
         resultMessage = "Pending order placed: " + IntegerToString((int)Trade.ResultOrder());
      else
         resultMessage = "Error placing pending order: " + IntegerToString((int)Trade.ResultRetcode());
   }
   else // Market order
   {
      // For immediate execution signals
      result = Trade.PositionOpen(symbol, orderType, lotSize, 0, stopLoss, takeProfit);
      if(result)
         resultMessage = "Position opened: " + IntegerToString((int)Trade.ResultDeal());
      else
         resultMessage = "Error opening position: " + IntegerToString((int)Trade.ResultRetcode());
   }
   
   // Update signal status based on execution result
   if(result)
      SendSignalUpdate(signalId, "executed", resultMessage);
   else
      SendSignalUpdate(signalId, "error", resultMessage);
}

//+------------------------------------------------------------------+
//| Calculate appropriate lot size based on risk percentage           |
//+------------------------------------------------------------------+
double CalculateLotSize(string symbol, double riskPercent, string stopLossStr)
{
   // Default to minimum lot size if no SL or risk calculation fails
   double minLot = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
   
   if(StringLen(stopLossStr) == 0 || riskPercent <= 0)
      return minLot;
      
   double stopLoss = StringToDouble(stopLossStr);
   if(stopLoss <= 0)
      return minLot;
      
   // Get current market price
   double entryPrice = SymbolInfoDouble(symbol, SYMBOL_ASK);
   
   // Calculate risk amount
   double accountBalance = AccountInfoDouble(ACCOUNT_BALANCE);
   double riskAmount = accountBalance * (riskPercent / 100.0);
   
   // Calculate pip value
   double pipValue = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_VALUE);
   double point = SymbolInfoDouble(symbol, SYMBOL_POINT);
   double pipPoints = (point * 10); // Standard 5-digit broker
   
   // Calculate distance in pips
   double distance = MathAbs(entryPrice - stopLoss) / pipPoints;
   
   // Calculate lot size based on risk
   double calculatedLot = riskAmount / (distance * pipValue);
   
   // Round to valid lot size
   double lotStep = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
   calculatedLot = MathFloor(calculatedLot / lotStep) * lotStep;
   
   // Apply min/max lot size constraints
   double maxLot = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MAX);
   calculatedLot = MathMax(minLot, MathMin(maxLot, calculatedLot));
   
   return calculatedLot;
}

//+------------------------------------------------------------------+
//| Calculate stop loss based on pips                                |
//+------------------------------------------------------------------+
double CalculateStopLoss(string symbol, ENUM_ORDER_TYPE orderType, int pips)
{
   if(pips <= 0)
      return 0;
      
   double point = SymbolInfoDouble(symbol, SYMBOL_POINT);
   double pipSize = point * 10; // Standard 5-digit broker
   double distance = pips * pipSize;
   
   double price;
   if(orderType == ORDER_TYPE_BUY)
   {
      price = SymbolInfoDouble(symbol, SYMBOL_ASK);
      return NormalizeDouble(price - distance, SymbolInfoInteger(symbol, SYMBOL_DIGITS));
   }
   else
   {
      price = SymbolInfoDouble(symbol, SYMBOL_BID);
      return NormalizeDouble(price + distance, SymbolInfoInteger(symbol, SYMBOL_DIGITS));
   }
}

//+------------------------------------------------------------------+
//| Calculate take profit based on pips                              |
//+------------------------------------------------------------------+
double CalculateTakeProfit(string symbol, ENUM_ORDER_TYPE orderType, int pips)
{
   if(pips <= 0)
      return 0;
      
   double point = SymbolInfoDouble(symbol, SYMBOL_POINT);
   double pipSize = point * 10; // Standard 5-digit broker
   double distance = pips * pipSize;
   
   double price;
   if(orderType == ORDER_TYPE_BUY)
   {
      price = SymbolInfoDouble(symbol, SYMBOL_ASK);
      return NormalizeDouble(price + distance, SymbolInfoInteger(symbol, SYMBOL_DIGITS));
   }
   else
   {
      price = SymbolInfoDouble(symbol, SYMBOL_BID);
      return NormalizeDouble(price - distance, SymbolInfoInteger(symbol, SYMBOL_DIGITS));
   }
}

//+------------------------------------------------------------------+
//| Send signal update to API                                        |
//+------------------------------------------------------------------+
void SendSignalUpdate(string signalId, string status, string message)
{
   // Prepare update data
   CJSONWriter json;
   
   json.WriteStart();
   json.Write("signal_id", signalId);
   json.Write("status", status);
   json.Write("message", message);
   json.Write("terminal_id", TerminalInfoString(TERMINAL_NAME));
   json.Write("account_id", AccountInfoInteger(ACCOUNT_LOGIN));
   json.WriteEnd();
   
   // Send update to API
   SendAPIRequest("POST", "/signals/update", json.GetData());
}

//+------------------------------------------------------------------+
//| Update the status of current trades                              |
//+------------------------------------------------------------------+
void UpdateTradesStatus()
{
   // Get all open positions
   CJSONWriter json;
   json.WriteStart();
   
   json.WriteStart("trades");
   json.WriteStartObject();
   
   for(int i = 0; i < PositionsTotal(); i++)
   {
      if(PositionSelectByTicket(PositionGetTicket(i)))
      {
         json.WriteStart(IntegerToString(PositionGetInteger(POSITION_TICKET)));
         json.WriteStartObject();
         
         json.Write("ticket", IntegerToString(PositionGetInteger(POSITION_TICKET)));
         json.Write("symbol", PositionGetString(POSITION_SYMBOL));
         json.Write("type", PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY ? "BUY" : "SELL");
         json.Write("lot", DoubleToString(PositionGetDouble(POSITION_VOLUME), 2));
         json.Write("open_price", DoubleToString(PositionGetDouble(POSITION_PRICE_OPEN), SymbolInfoInteger(PositionGetString(POSITION_SYMBOL), SYMBOL_DIGITS)));
         json.Write("current_price", DoubleToString(PositionGetDouble(POSITION_PRICE_CURRENT), SymbolInfoInteger(PositionGetString(POSITION_SYMBOL), SYMBOL_DIGITS)));
         json.Write("sl", DoubleToString(PositionGetDouble(POSITION_SL), SymbolInfoInteger(PositionGetString(POSITION_SYMBOL), SYMBOL_DIGITS)));
         json.Write("tp", DoubleToString(PositionGetDouble(POSITION_TP), SymbolInfoInteger(PositionGetString(POSITION_SYMBOL), SYMBOL_DIGITS)));
         json.Write("profit", DoubleToString(PositionGetDouble(POSITION_PROFIT), 2));
         json.Write("swap", DoubleToString(PositionGetDouble(POSITION_SWAP), 2));
         json.Write("commission", DoubleToString(PositionGetDouble(POSITION_COMMISSION), 2));
         json.Write("open_time", TimeToString(PositionGetInteger(POSITION_TIME), TIME_DATE|TIME_SECONDS));
         
         json.WriteEndObject();
         json.WriteEnd();
      }
   }
   
   json.WriteEndObject();
   json.WriteEnd();
   
   json.WriteEnd();
   
   // Send position updates to API
   SendAPIRequest("POST", "/trades/update", json.GetData());
}

//+------------------------------------------------------------------+
//| Send API request and return response                             |
//+------------------------------------------------------------------+
string SendAPIRequest(string method, string endpoint, string data)
{
   string url = APIEndpoint + endpoint;
   string headers = "Content-Type: application/json\r\n";
   
   if(StringLen(APIToken) > 0)
      headers = headers + "Authorization: Bearer " + APIToken + "\r\n";
      
   char data_array[];
   char result_array[];
   string result = "";
   int res = 0;
   
   // Prepare data if provided
   if(StringLen(data) > 0)
      StringToCharArray(data, data_array);
   
   // Send request
   int timeout = 5000; // 5 second timeout
   
   if(method == "GET")
      res = WebRequest("GET", url, headers, timeout, NULL, result_array, 0);
   else if(method == "POST")
      res = WebRequest("POST", url, headers, timeout, data_array, result_array, StringLen(data));
   else if(method == "PUT")
      res = WebRequest("PUT", url, headers, timeout, data_array, result_array, StringLen(data));
   else if(method == "DELETE")
      res = WebRequest("DELETE", url, headers, timeout, NULL, result_array, 0);
   
   // Process response
   if(res == 200) // HTTP OK
   {
      result = CharArrayToString(result_array);
   }
   else if(res > 0) // HTTP error
   {
      Print("HTTP error ", res, " when connecting to ", url);
   }
   else // Connection error
   {
      Print("Connection error ", GetLastError(), " when connecting to ", url);
   }
   
   return result;
}

//+------------------------------------------------------------------+
