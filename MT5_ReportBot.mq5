//+------------------------------------------------------------------+
//|                    MT5_ReportBot.mq5                             |
//|   Lightweight account/position reporter for MT5 → Flask API      |
//|   Version: 2.0 – Added closed trades reporting                   |
//+------------------------------------------------------------------+
#property copyright "You"
#property version   "2.0"
#property strict

//─- Inputs ----------------------------------------------------------
input string ApiUrl       = "https://4c1f2076-899e-4ced-962a-2903ca4a9bac-00-29hcpk84r1chm.picard.replit.dev";
input string AccountAlias = "";
input int    HistoryDays  = 7;  // How many days of history to check for closed trades

//─- Includes --------------------------------------------------------
#include <JAson.mqh>
#include <Trade\Trade.mqh>
#include <Trade\HistoryOrderInfo.mqh>
#include <Trade\DealInfo.mqh>

//─- Globals ---------------------------------------------------------
CTrade  Trade;
CHistoryOrderInfo HistoryOrder;
CDealInfo Deal;
string  gAccountId;
string  gEndpointTrades, gEndpointStatus;
datetime gLastUpdate = 0;  // Track when we last reported closed trades

//+------------------------------------------------------------------+
//| Helper: convert string → char[] (exact type expected by WebRequest)
//+------------------------------------------------------------------+
void StrToBytes(const string src, char &dst[])
{
   int len = StringLen(src);
   ArrayResize(dst, len);
   for(int i = 0; i < len; i++)
      dst[i] = (char)StringGetCharacter(src, i);
}

//+------------------------------------------------------------------+
//| Expert initialization                                            |
//+------------------------------------------------------------------+
int OnInit()
{
   if(StringLen(ApiUrl) == 0)
   {
      Print("❌ ApiUrl input is empty.");
      return(INIT_FAILED);
   }

   gAccountId = (StringLen(AccountAlias) > 0)
                ? AccountAlias
                : IntegerToString((int)AccountInfoInteger(ACCOUNT_LOGIN));

   gEndpointTrades  = ApiUrl + "/mt5/update_trades";
   gEndpointStatus  = ApiUrl + "/mt5/account_status";

   EventSetTimer(60);
   PrintFormat("🟢 ReportBot started  account_id=%s", gAccountId);
   PrintFormat("API URL: %s", ApiUrl);
   PrintFormat("Close Queue URL: %s", ApiUrl + "/mt5/poll_close_queue?account_id=" + gAccountId);
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   EventKillTimer();
   Print("🔴 ReportBot stopped.");
}

//+------------------------------------------------------------------+
//| Timer event                                                      |
//+------------------------------------------------------------------+
void OnTimer()
{
   Print("⏰ Timer triggered - starting API calls");
   Print("Sending open positions...");   SendOpenPositions();
   Print("Sending closed trades...");    SendRecentlyClosedTrades();
   Print("Sending account status...");   SendAccountStatus();
   Print("Checking close requests...");  CheckCloseRequests();
   Print("Checking modify requests..."); CheckModifyRequests();
   Print("✅ All API calls completed");
}

//+------------------------------------------------------------------+
//| Send open‑positions snapshot                                     |
//+------------------------------------------------------------------+
void SendOpenPositions()
{
   // Create JSON using CJAVal to ensure proper formatting
   CJAVal json;
   json["account_id"] = gAccountId;
   
   // Create the trades object
   CJAVal trades;
   int total = PositionsTotal();

   for(int i=0; i<total; i++)
   {
      ulong ticket = PositionGetTicket(i);
      if(!PositionSelectByTicket(ticket)) continue;

      string sym = PositionGetString(POSITION_SYMBOL);
      double lot = PositionGetDouble(POSITION_VOLUME);
      double entry = PositionGetDouble(POSITION_PRICE_OPEN);
      double sl = PositionGetDouble(POSITION_SL);
      double tp = PositionGetDouble(POSITION_TP);
      double pl = PositionGetDouble(POSITION_PROFIT);
      string side = (PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY) ? "BUY":"SELL";
      string open_time = TimeToString(PositionGetInteger(POSITION_TIME), TIME_DATE|TIME_SECONDS);

      // Add position to trades object
      CJAVal position;
      position["symbol"] = sym;
      position["lot"] = lot;
      position["type"] = side;  // Changed key from "side" to "type" to match server expectation
      position["open_price"] = entry;  // Changed key from "entry" to "open_price"
      position["sl"] = sl;
      position["tp"] = tp;
      position["profit"] = pl;
      position["opened_at"] = open_time;
      position["status"] = "OPEN";
      
      // Add position to trades using ticket as key
      trades[IntegerToString(ticket)] = position;
   }
   
   // Add trades object to main json
   json["trades"] = trades;
   
   // Convert to string
   string jsonStr = json.Serialize();
   
   // Debug output
   Print("DEBUG: Sending JSON: ", jsonStr);
   
   char post[];   
   StrToBytes(jsonStr, post);
   char result[]; 
   string resultHdr;
   string headers = "Content-Type: application/json\r\n";

   int code = WebRequest("POST",
                         gEndpointTrades,
                         headers,
                         "", 5000,
                         post, ArraySize(post),
                         result, resultHdr);

   PrintFormat("[ReportBot] /update_trades → HTTP %d  (open=%d)", code, total);
   
   // If error, print the response for debugging
   if(code != 200)
   {
      string response = CharArrayToString(result, 0, ArraySize(result));
      PrintFormat("Error response: %s", response);
   }
}

//+------------------------------------------------------------------+
//| Send recently closed trades                                      |
//+------------------------------------------------------------------+
void SendRecentlyClosedTrades()
{
   // Create JSON using CJAVal to ensure proper formatting
   CJAVal json;
   json["account_id"] = gAccountId;
   
   // Get history within date range
   datetime fromDate = gLastUpdate > 0 ? gLastUpdate : TimeCurrent() - HistoryDays * 86400;
   datetime toDate = TimeCurrent();
   
   // Update our last update timestamp for next time
   gLastUpdate = TimeCurrent();
   
   // Create the trades object for closed positions
   CJAVal closedTrades;
   int total = 0;
   
   // Select history range
   if(HistorySelect(fromDate, toDate))
   {
      // Process all deals in the selected history
      int totalDeals = HistoryDealsTotal();
      
      for(int i=0; i<totalDeals; i++)
      {
         ulong dealTicket = HistoryDealGetTicket(i);
         if(dealTicket == 0) continue;
         
         // Only interested in DEAL_ENTRY_OUT deals (position close)
         if(HistoryDealGetInteger(dealTicket, DEAL_ENTRY) != DEAL_ENTRY_OUT) continue;
         
         ulong positionTicket = HistoryDealGetInteger(dealTicket, DEAL_POSITION_ID);
         string sym = HistoryDealGetString(dealTicket, DEAL_SYMBOL);
         double lot = HistoryDealGetDouble(dealTicket, DEAL_VOLUME);
         double entryPrice = 0;
         double closePrice = HistoryDealGetDouble(dealTicket, DEAL_PRICE);
         double pl = HistoryDealGetDouble(dealTicket, DEAL_PROFIT);
         string side = (HistoryDealGetInteger(dealTicket, DEAL_TYPE) == DEAL_TYPE_SELL) ? "BUY" : "SELL";
         string closeTime = TimeToString(HistoryDealGetInteger(dealTicket, DEAL_TIME), TIME_DATE|TIME_SECONDS);
         
         // Try to find the entry price from history orders
         ulong orderTicket = HistoryDealGetInteger(dealTicket, DEAL_ORDER);
         if(OrderSelect(orderTicket))
         {
            entryPrice = OrderGetDouble(ORDER_PRICE_OPEN);
         }
         
         // Add position to closed trades object
         CJAVal closedPosition;
         closedPosition["symbol"] = sym;
         closedPosition["lot"] = lot;
         closedPosition["type"] = side;
         closedPosition["open_price"] = entryPrice;
         closedPosition["close_price"] = closePrice;
         closedPosition["profit"] = pl;
         closedPosition["closed_at"] = closeTime;
         closedPosition["status"] = "CLOSED";
         
         // Add closed position to trades using position ticket as key
         closedTrades[IntegerToString(positionTicket)] = closedPosition;
         total++;
      }
   }
   
   // Only send if we have closed trades to report
   if(total > 0)
   {
      // Add closed trades object to main json
      json["closed_trades"] = closedTrades;
      
      // Convert to string
      string jsonStr = json.Serialize();
      
      // Debug output
      PrintFormat("DEBUG: Sending %d closed trades: %s", total, jsonStr);
      
      char post[];   
      StrToBytes(jsonStr, post);
      char result[]; 
      string resultHdr;
      string headers = "Content-Type: application/json\r\n";
   
      int code = WebRequest("POST",
                           gEndpointTrades + "/closed",
                           headers,
                           "", 5000,
                           post, ArraySize(post),
                           result, resultHdr);
   
      PrintFormat("[ReportBot] /update_trades/closed → HTTP %d  (closed=%d)", code, total);
      
      // If error, print the response for debugging
      if(code != 200)
      {
         string response = CharArrayToString(result, 0, ArraySize(result));
         PrintFormat("Error response: %s", response);
      }
   }
   else
   {
      PrintFormat("No closed trades found since %s", TimeToString(fromDate));
   }
}

//+------------------------------------------------------------------+
//| Send account‑status snapshot                                     |
//+------------------------------------------------------------------+
void SendAccountStatus()
{
   double eq   = AccountInfoDouble(ACCOUNT_EQUITY);
   double bal  = AccountInfoDouble(ACCOUNT_BALANCE);
   double mar  = AccountInfoDouble(ACCOUNT_MARGIN);
   double free = AccountInfoDouble(ACCOUNT_FREEMARGIN);
   double lev  = (double)AccountInfoInteger(ACCOUNT_LEVERAGE);
   int    open = PositionsTotal();

   string query = gEndpointStatus +
                  "?account_id="     + gAccountId +
                  "&balance="        + DoubleToString(bal, 2) +
                  "&equity="         + DoubleToString(eq, 2) +
                  "&margin="         + DoubleToString(mar, 2) +
                  "&free_margin="    + DoubleToString(free, 2) +
                  "&leverage="       + DoubleToString(lev, 0) +
                  "&open_positions=" + IntegerToString(open);

   char dummy[];
   char result[];
   string resultHdr;

   int code = WebRequest("GET",
                         query,
                         "", "", 5000,
                         dummy, 0,
                         result, resultHdr);

   PrintFormat("[ReportBot] /account_status → HTTP %d", code);
}

//─────────────────────────────────────────────────────────────
void CheckCloseRequests()
{
   string url = ApiUrl + "/mt5/poll_close_queue?account_id=" + gAccountId;
   PrintFormat("DEBUG: Checking close queue with URL: %s", url);

   char dummy[], res[]; string hdr;
   int code = WebRequest("GET",
                         url,
                         "", "", 5000,
                         dummy, 0,
                         res, hdr);

   PrintFormat("[ReportBot] /poll_close_queue → HTTP %d", code);
   if(code!=200) return;

   string response = CharArrayToString(res,0,ArraySize(res));
   PrintFormat("Response from close queue: %s", response);

   CJAVal root;
   if(!root.Deserialize(response)) return;

   int n=root["tickets"].Size();
   for(int i=0;i<n;i++)
   {
      ulong tk=(ulong)root["tickets"][i].ToInt();
      bool ok=Trade.PositionClose(tk);
      PrintFormat("Close %llu → %s (err=%d)",tk,(ok?"OK":"FAIL"),GetLastError());
   }
}

//─────────────────────────────────────────────────────────────
void CheckModifyRequests()
{
   string url = ApiUrl + "/mt5/poll_modify_queue?account_id=" + gAccountId;
   PrintFormat("DEBUG: Checking modify queue with URL: %s", url);

   char dummy[], res[]; string hdr;
   int code = WebRequest("GET",
                         url,
                         "", "", 5000,
                         dummy, 0,
                         res, hdr);

   PrintFormat("[ReportBot] /poll_modify_queue → HTTP %d", code);
   if(code!=200) return;

   string response = CharArrayToString(res,0,ArraySize(res));
   if(StringLen(response)>20) Print("Response from modify queue: "+response);

   CJAVal root;
   if(!root.Deserialize(response)) return;

   int m=root["mods"].Size();
   for(int j=0;j<m;j++)
   {
      ulong tk=(ulong)root["mods"][j]["ticket"].ToInt();
      double sl=root["mods"][j]["sl"].ToDbl();
      double tp=root["mods"][j]["tp"].ToDbl();
      if(sl==0) sl=EMPTY_VALUE;
      if(tp==0) tp=EMPTY_VALUE;
      bool ok=Trade.PositionModify(tk,sl,tp);
      PrintFormat("Modify %llu → %s (err=%d)",tk,(ok?"OK":"FAIL"),GetLastError());
   }
}