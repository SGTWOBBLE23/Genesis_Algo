//+------------------------------------------------------------------+
//|                                      MT5_GENESIS_EA_fixed_v10.mq5 |
//|                                       Replit GENESIS Trading System |
//|                                                                  |
//+------------------------------------------------------------------+
#property copyright "Replit GENESIS Trading System"
#property link      "https://genesis.replit.app"
#property version   "1.00"

#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>
#include <Trade\OrderInfo.mqh>
#include <Trade\HistoryOrderInfo.mqh>
#include <Trade\DealInfo.mqh>
#include <Trade\SymbolInfo.mqh>
#include <Web\Json.mqh>

// Input parameters
input string   ServerURL = "https://genesis.replit.app";  // Server URL
input string   AccountID = "";                       // Unique account identifier (leave empty to use account number)
input int      SignalCheckInterval = 60;             // Signal checking interval in seconds
input int      TradeUpdateInterval = 30;             // Trade update interval in seconds
input int      HeartbeatInterval = 60;               // Heartbeat interval in seconds
input bool     EnableDebugLog = true;                // Enable detailed debug logs

// Global variables
CTrade         Trade;                                 // Trading operations object
string         g_account_id = "";                     // Actual account ID to be used
ulong          g_terminal_id = 0;                     // Unique terminal identifier
datetime       g_last_signal_check = 0;               // Last signal check time
datetime       g_last_trade_update = 0;               // Last trade update time
datetime       g_last_heartbeat = 0;                  // Last heartbeat time
int            g_last_signal_id = 0;                  // Last received signal ID
int            g_current_trading_symbol = 0;          // Current trading symbol index
string         g_supported_symbols[];                 // Array of supported symbols

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   // Set up account ID
   if(AccountID == "")
   {
      g_account_id = IntegerToString(AccountInfoInteger(ACCOUNT_LOGIN));
   }
   else
   {
      g_account_id = AccountID;
   }
   
   // Generate a unique terminal ID
   g_terminal_id = GetTickCount64() % 10000;
   
   // Add supported symbols
   int total_symbols = SymbolsTotal(false);
   ArrayResize(g_supported_symbols, total_symbols);
   for(int i=0; i<total_symbols; i++)
   {
      g_supported_symbols[i] = SymbolName(i, false);
   }
   
   // Send initial heartbeat
   SendHeartbeat();
   
   // Send initial trade update
   SendTradeUpdate();
   
   // Log initialization
   if(EnableDebugLog) 
      Print("GENESIS EA initialized for account ", g_account_id, ", terminal ", g_terminal_id);
   
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   // Log deinitialization
   if(EnableDebugLog) 
      Print("GENESIS EA deinitialized, reason: ", reason);
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   // Check for new trading signals
   if(TimeCurrent() - g_last_signal_check > SignalCheckInterval)
   {
      CheckForSignals();
      g_last_signal_check = TimeCurrent();
   }
   
   // Send trade updates
   if(TimeCurrent() - g_last_trade_update > TradeUpdateInterval)
   {
      SendTradeUpdate();
      g_last_trade_update = TimeCurrent();
   }
   
   // Send heartbeat
   if(TimeCurrent() - g_last_heartbeat > HeartbeatInterval)
   {
      SendHeartbeat();
      g_last_heartbeat = TimeCurrent();
   }
}

//+------------------------------------------------------------------+
//| Check for new trading signals                                     |
//+------------------------------------------------------------------+
void CheckForSignals()
{
   if(EnableDebugLog) Print("Checking for new trading signals...");
   
   // Prepare a list of symbol indices to send to the server
   string json_symbols = "[";
   for(int i=0; i<ArraySize(g_supported_symbols); i++)
   {
      if(i > 0) json_symbols += ",";
      json_symbols += IntegerToString(i);
   }
   json_symbols += "]";
   
   // Create JSON payload
   string payload = "{"
      + "\"account_id\":\"" + g_account_id + "\","
      + "\"last_signal_id\":" + IntegerToString(g_last_signal_id) + ","
      + "\"symbols\":" + json_symbols
      + "}";
   
   // Send request to server
   string endpoint = ServerURL + "/mt5/get-signals";
   string response = SendHttpRequest(endpoint, payload);
   
   if(response != "")
   {
      // Parse JSON response
      JSONParser parser;
      JSONValue json_response;
      
      if(!parser.Parse(response, json_response))
      {
         Print("Error parsing JSON response: ", parser.GetLastError());
         return;
      }
      
      // Check status
      string status = json_response["status"].GetString();
      if(status != "success")
      {
         Print("Error in signal response: ", json_response["message"].GetString());
         return;
      }
      
      // Process signals
      JSONValue signals = json_response["signals"];
      if(signals.IsArray())
      {
         int signal_count = signals.Size();
         if(EnableDebugLog) Print("Received ", signal_count, " signals");
         
         for(int i=0; i<signal_count; i++)
         {
            ProcessSignal(signals[i]);
         }
      }
   }
}

//+------------------------------------------------------------------+
//| Process a trading signal                                          |
//+------------------------------------------------------------------+
void ProcessSignal(JSONValue signal)
{
   // Extract signal properties
   int id = (int)signal["id"].GetInteger();
   string symbol = signal["symbol"].GetString();
   string action = signal["action"].GetString();
   double entry_price = signal["entry_price"].GetDouble();
   double stop_loss = signal["stop_loss"].GetDouble();
   double take_profit = signal["take_profit"].GetDouble();
   double position_size = signal["position_size"].GetDouble();
   bool force_execution = signal["force_execution"].GetBoolean();
   
   // Update the last signal ID
   if(id > g_last_signal_id) g_last_signal_id = id;
   
   if(EnableDebugLog)
   {
      Print("Processing signal #", id, ": ", action, " ", symbol, 
            ", Entry: ", entry_price, ", SL: ", stop_loss, ", TP: ", take_profit,
            ", Size: ", position_size);
   }
   
   // Execute the trading signal
   ExecuteSignal(id, symbol, action, entry_price, stop_loss, take_profit, position_size, force_execution);
}

//+------------------------------------------------------------------+
//| Execute a trading signal                                          |
//+------------------------------------------------------------------+
void ExecuteSignal(int signal_id, string symbol, string action, double entry_price, 
                   double stop_loss, double take_profit, double position_size, bool force_execution)
{
   // Convert lot size from position_size (which is the preferred option from the server)
   // or calculate based on risk if not specified
   double lot_size = position_size;
   if(lot_size <= 0) lot_size = 0.01; // Default minimal lot size
   
   // Normalize lot size to symbol minimum
   double min_lot = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
   double max_lot = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MAX);
   double step_lot = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
   
   lot_size = MathMax(min_lot, MathMin(max_lot, lot_size));
   lot_size = MathFloor(lot_size / step_lot) * step_lot;
   
   // Get symbol digits for price normalization
   int digits = (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS);
   
   // Normalize prices
   entry_price = NormalizeDouble(entry_price, digits);
   stop_loss = NormalizeDouble(stop_loss, digits);
   take_profit = NormalizeDouble(take_profit, digits);
   
   bool trade_success = false;
   string trade_message = "";
   ulong ticket = 0;
   
   // Process signal based on action
   if(action == "BUY_NOW")
   {
      // Execute market buy order
      Trade.SetExpertMagicNumber(signal_id);
      Trade.SetDeviationInPoints(10);
      
      if(Trade.Buy(lot_size, symbol, 0, stop_loss, take_profit, "GENESIS_SIGNAL_" + IntegerToString(signal_id)))
      {
         ticket = Trade.ResultOrder();
         trade_success = true;
         trade_message = "Buy order executed successfully";
      }
      else
      {
         trade_message = "Failed to execute buy order: " + IntegerToString(Trade.ResultRetcode()) + ": " + Trade.ResultComment();
      }
   }
   else if(action == "SELL_NOW")
   {
      // Execute market sell order
      Trade.SetExpertMagicNumber(signal_id);
      Trade.SetDeviationInPoints(10);
      
      if(Trade.Sell(lot_size, symbol, 0, stop_loss, take_profit, "GENESIS_SIGNAL_" + IntegerToString(signal_id)))
      {
         ticket = Trade.ResultOrder();
         trade_success = true;
         trade_message = "Sell order executed successfully";
      }
      else
      {
         trade_message = "Failed to execute sell order: " + IntegerToString(Trade.ResultRetcode()) + ": " + Trade.ResultComment();
      }
   }
   else if(action == "ANTICIPATED_LONG" || action == "ANTICIPATED_SHORT")
   {
      // Set up a pending order
      ENUM_ORDER_TYPE order_type = (action == "ANTICIPATED_LONG") ? ORDER_TYPE_BUY_LIMIT : ORDER_TYPE_SELL_LIMIT;
      
      Trade.SetExpertMagicNumber(signal_id);
      
      if(Trade.OrderOpen(symbol, order_type, lot_size, 0, entry_price, stop_loss, take_profit, 0, 0, "GENESIS_SIGNAL_" + IntegerToString(signal_id)))
      {
         ticket = Trade.ResultOrder();
         trade_success = true;
         trade_message = "Pending order placed successfully";
      }
      else
      {
         trade_message = "Failed to place pending order: " + IntegerToString(Trade.ResultRetcode()) + ": " + Trade.ResultComment();
      }
   }
   
   // Report trade execution back to the server
   ReportTradeExecution(signal_id, symbol, action, lot_size, entry_price, stop_loss, take_profit, ticket, trade_success, trade_message);
}

//+------------------------------------------------------------------+
//| Report trade execution back to the server                         |
//+------------------------------------------------------------------+
void ReportTradeExecution(int signal_id, string symbol, string action, double lot_size, 
                          double entry_price, double stop_loss, double take_profit, 
                          ulong ticket, bool success, string message)
{
   // Create JSON payload
   string status = success ? "success" : "error";
   string execution_time = TimeToString(TimeCurrent(), TIME_DATE|TIME_SECONDS);
   
   string payload = "{"
      + "\"account_id\":\"" + g_account_id + "\","
      + "\"signal_id\":" + IntegerToString(signal_id) + ","
      + "\"symbol\":\"" + symbol + "\","
      + "\"action\":\"" + action + "\","
      + "\"ticket\":\"" + IntegerToString(ticket) + "\","
      + "\"lot_size\":" + DoubleToString(lot_size, 2) + ","
      + "\"entry_price\":" + DoubleToString(entry_price, SymbolInfoInteger(symbol, SYMBOL_DIGITS)) + ","
      + "\"stop_loss\":" + DoubleToString(stop_loss, SymbolInfoInteger(symbol, SYMBOL_DIGITS)) + ","
      + "\"take_profit\":" + DoubleToString(take_profit, SymbolInfoInteger(symbol, SYMBOL_DIGITS)) + ","
      + "\"execution_time\":\"" + execution_time + "\","
      + "\"status\":\"" + status + "\","
      + "\"message\":\"" + message + "\""
      + "}";
   
   // Send request to server
   string endpoint = ServerURL + "/mt5/trade_report";
   string response = SendHttpRequest(endpoint, payload);
   
   if(EnableDebugLog)
   {
      Print("Trade execution report sent for signal #", signal_id, ", status: ", status, ", message: ", message);
      if(response != "") Print("Server response: ", response);
   }
}

//+------------------------------------------------------------------+
//| Send trade updates to the server                                  |
//+------------------------------------------------------------------+
void SendTradeUpdate()
{
   if(EnableDebugLog) Print("Sending trade updates to the server...");
   
   // Create JSON object for all open trades
   string trades_json = "{"; // Start JSON object
   
   // Add all open positions
   bool has_trades = false;
   for(int i=0; i<PositionsTotal(); i++)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket <= 0) continue;
      
      if(PositionSelectByTicket(ticket))
      {
         if(has_trades) trades_json += ",";
         has_trades = true;
         
         string symbol = PositionGetString(POSITION_SYMBOL);
         double open_price = PositionGetDouble(POSITION_PRICE_OPEN);
         double current_price = PositionGetDouble(POSITION_PRICE_CURRENT);
         double sl = PositionGetDouble(POSITION_SL);
         double tp = PositionGetDouble(POSITION_TP);
         double profit = PositionGetDouble(POSITION_PROFIT);
         double lot = PositionGetDouble(POSITION_VOLUME);
         datetime opened_at = (datetime)PositionGetInteger(POSITION_TIME);
         ENUM_POSITION_TYPE pos_type = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
         
         string type_str = (pos_type == POSITION_TYPE_BUY) ? "BUY" : "SELL";
         
         trades_json += "\"" + IntegerToString(ticket) + "\":{"
            + "\"symbol\":\"" + symbol + "\","
            + "\"type\":\"" + type_str + "\","
            + "\"lot\":" + DoubleToString(lot, 2) + ","
            + "\"open_price\":" + DoubleToString(open_price, (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS)) + ","
            + "\"current_price\":" + DoubleToString(current_price, (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS)) + ","
            + "\"sl\":" + DoubleToString(sl, (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS)) + ","
            + "\"tp\":" + DoubleToString(tp, (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS)) + ","
            + "\"profit\":" + DoubleToString(profit, 2) + ","
            + "\"opened_at\":\"" + TimeToString(opened_at, TIME_DATE|TIME_SECONDS) + "\","
            + "\"status\":\"OPEN\""
            + "}";
      }
   }
   
   // Get closed trades from history
   HistorySelect(0, TimeCurrent());
   int deals_total = HistoryDealsTotal();
   
   for(int i=0; i<deals_total; i++)
   {
      ulong deal_ticket = HistoryDealGetTicket(i);
      if(deal_ticket <= 0) continue;
      
      if(HistoryDealGetInteger(deal_ticket, DEAL_TYPE) == DEAL_TYPE_BUY || 
         HistoryDealGetInteger(deal_ticket, DEAL_TYPE) == DEAL_TYPE_SELL)
      {
         // Only complete deals that closed a position
         if(HistoryDealGetInteger(deal_ticket, DEAL_ENTRY) == DEAL_ENTRY_OUT)
         {
            ulong position_ticket = HistoryDealGetInteger(deal_ticket, DEAL_POSITION_ID);
            // Check if we've already added this position (to avoid duplicates)
            if(StringFind(trades_json, "\"" + IntegerToString(position_ticket) + "\":{")==-1) 
            {
               if(has_trades) trades_json += ",";
               has_trades = true;
               
               string symbol = HistoryDealGetString(deal_ticket, DEAL_SYMBOL);
               double entry_price = 0;
               double exit_price = HistoryDealGetDouble(deal_ticket, DEAL_PRICE);
               double profit = HistoryDealGetDouble(deal_ticket, DEAL_PROFIT);
               double lot = HistoryDealGetDouble(deal_ticket, DEAL_VOLUME);
               datetime closed_at = (datetime)HistoryDealGetInteger(deal_ticket, DEAL_TIME);
               
               // Try to find the entry deal
               double sl = 0, tp = 0;
               datetime opened_at = 0;
               ENUM_DEAL_TYPE deal_type = (ENUM_DEAL_TYPE)HistoryDealGetInteger(deal_ticket, DEAL_TYPE);
               string type_str = (deal_type == DEAL_TYPE_BUY) ? "BUY" : "SELL";
               
               // Look for the opposing IN entry for this position
               for(int j=0; j<deals_total; j++)
               {
                  ulong entry_ticket = HistoryDealGetTicket(j);
                  if(entry_ticket <= 0) continue;
                  
                  if(HistoryDealGetInteger(entry_ticket, DEAL_POSITION_ID) == position_ticket && 
                     HistoryDealGetInteger(entry_ticket, DEAL_ENTRY) == DEAL_ENTRY_IN)
                  {
                     entry_price = HistoryDealGetDouble(entry_ticket, DEAL_PRICE);
                     opened_at = (datetime)HistoryDealGetInteger(entry_ticket, DEAL_TIME);
                     break;
                  }
               }
               
               trades_json += "\"" + IntegerToString(position_ticket) + "\":{"
                  + "\"symbol\":\"" + symbol + "\","
                  + "\"type\":\"" + type_str + "\","
                  + "\"lot\":" + DoubleToString(lot, 2) + ","
                  + "\"open_price\":" + DoubleToString(entry_price, (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS)) + ","
                  + "\"exit_price\":" + DoubleToString(exit_price, (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS)) + ","
                  + "\"sl\":" + DoubleToString(sl, (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS)) + ","
                  + "\"tp\":" + DoubleToString(tp, (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS)) + ","
                  + "\"profit\":" + DoubleToString(profit, 2) + ","
                  + "\"opened_at\":\"" + TimeToString(opened_at, TIME_DATE|TIME_SECONDS) + "\","
                  + "\"closed_at\":\"" + TimeToString(closed_at, TIME_DATE|TIME_SECONDS) + "\","
                  + "\"status\":\"CLOSED\""
                  + "}";
            }
         }
      }
   }
   
   trades_json += "}"; // End JSON object
   
   // Create the payload to send to the server
   string payload = "{"
      + "\"account_id\":\"" + g_account_id + "\","
      + "\"trades\":" + trades_json
      + "}";
   
   // Send request to server
   string endpoint = ServerURL + "/mt5/update_trades";
   string response = SendHttpRequest(endpoint, payload);
   
   if(EnableDebugLog && has_trades)
   {
      Print("Trade updates sent to server");
      if(response != "") Print("Server response: ", response);
   }
}

//+------------------------------------------------------------------+
//| Send heartbeat to the server                                      |
//+------------------------------------------------------------------+
void SendHeartbeat()
{
   if(EnableDebugLog) Print("Sending heartbeat...");
   
   // Create JSON payload
   string payload = "{"
      + "\"account_id\":\"" + g_account_id + "\","
      + "\"terminal_id\":\"" + IntegerToString(g_terminal_id) + "\","
      + "\"connection_time\":\"" + TimeToString(TimeCurrent(), TIME_DATE|TIME_SECONDS) + "\""
      + "}";
   
   // Send request to server
   string endpoint = ServerURL + "/mt5/heartbeat";
   string response = SendHttpRequest(endpoint, payload);
   
   if(EnableDebugLog)
   {
      Print("Heartbeat sent to server");
      if(response != "") Print("Server response: ", response);
   }
   
   // Send account status update as well
   SendAccountStatus();
}

//+------------------------------------------------------------------+
//| Send account status to the server                                 |
//+------------------------------------------------------------------+
void SendAccountStatus()
{
   if(EnableDebugLog) Print("Sending account status...");
   
   // Get account info
   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   double margin = AccountInfoDouble(ACCOUNT_MARGIN);
   double free_margin = AccountInfoDouble(ACCOUNT_MARGIN_FREE);
   double leverage = AccountInfoInteger(ACCOUNT_LEVERAGE);
   int open_positions = PositionsTotal();
   
   // Create JSON payload
   string payload = "{"
      + "\"account_id\":\"" + g_account_id + "\","
      + "\"balance\":" + DoubleToString(balance, 8) + ","
      + "\"equity\":" + DoubleToString(equity, 8) + ","
      + "\"margin\":" + DoubleToString(margin, 8) + ","
      + "\"free_margin\":" + DoubleToString(free_margin, 8) + ","
      + "\"leverage\":" + IntegerToString(leverage) + ","
      + "\"open_positions\":" + IntegerToString(open_positions) + ""
      + "}";
   
   // Send request to server
   string endpoint = ServerURL + "/mt5/account_status";
   string response = SendHttpRequest(endpoint, payload);
   
   if(EnableDebugLog)
   {
      Print("Account status sent to server");
      if(response != "") Print("Server response: ", response);
   }
}

//+------------------------------------------------------------------+
//| Send HTTP request to the server                                   |
//+------------------------------------------------------------------+
string SendHttpRequest(string endpoint, string payload)
{
   if(EnableDebugLog) Print("Sending HTTP request to ", endpoint);
   
   char payload_arr[];      // Array for the request body
   char result_arr[];       // Array for the result
   string result = "";      // The result as a string
   string headers;          // Headers for the request
   
   // Convert the payload to a char array
   StringToCharArray(payload, payload_arr, 0, StringLen(payload), CP_UTF8);
   
   int res = WebRequest("POST", endpoint, "Content-Type: application/json\r\n", 10000, payload_arr, result_arr, headers);
   
   // Check the result
   if(res != -1)
   {
      // Convert the received data to a string
      result = CharArrayToString(result_arr, 0, -1, CP_UTF8);
      
      if(EnableDebugLog) Print("HTTP request successful, response code: ", res);
   }
   else
   {
      Print("HTTP request failed: ", GetLastError());
      Print("Make sure to add the URL ", endpoint, " to the list of allowed URLs in Tools -> Options -> Expert Advisors");
   }
   
   return result;
}
