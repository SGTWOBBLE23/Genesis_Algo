//+------------------------------------------------------------------+
//|                    MT5_ReportBot.mq5                             |
//|   Lightweight account/position reporter for MT5 → Flask API      |
//|   Version: 1.03 (2025-05-15) – compile‑clean                     |
//+------------------------------------------------------------------+
#property copyright "You"
#property version   "1.03"
#property strict

//─- Inputs ----------------------------------------------------------
input string ApiUrl       = "https://4c1f2076-899e-4ced-962a-2903ca4a9bac-00-29hcpk84r1chm.picard.replit.dev";
input string AccountAlias = "";

//─- Includes --------------------------------------------------------
#include <JAson.mqh>          // CJAVal  ✅ available in Include
#include <Trade\Trade.mqh>    // CTrade ✅ available in Include

//─- Globals ---------------------------------------------------------
CTrade  Trade;                // trade helper
string  gAccountId;
string  gEndpointTrades, gEndpointStatus;

//+------------------------------------------------------------------+
//| Helper: convert string → uchar[]                                 |
//+------------------------------------------------------------------+
void StrToBytes(const string src, uchar &dst[])
{
   int len = StringLen(src);
   ArrayResize(dst, len);
   for(int i = 0; i < len; i++)
      dst[i] = (uchar)StringGetCharacter(src, i);
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

   EventSetTimer(60);  // 60-second heartbeat
   Print("🟢 ReportBot started.");
   Print("• ApiUrl: " + ApiUrl);
   Print("• AccountAlias: " + ((StringLen(AccountAlias) > 0) ? AccountAlias : "—"));
   Print("• AccountId: " + gAccountId);
   
   // DEBUG: Print current URL for checking close queue
   string close_queue_url = ApiUrl + "/mt5/poll_close_queue?account_id=" + gAccountId;
   Print("• CloseQueueURL: " + close_queue_url);
   
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization                                          |
//+------------------------------------------------------------------+
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
   SendOpenPositions();
   SendAccountStatus();
   
   // Add debug prints to verify these functions are being called
   Print("Checking close requests...");
   CheckCloseRequests();
   
   Print("Checking modify requests...");
   CheckModifyRequests();
}

//+------------------------------------------------------------------+
//| Send open‑positions snapshot                                     |
//+------------------------------------------------------------------+
void SendOpenPositions()
{
   string json = "{\"account_id\":\""+gAccountId+"\",\"trades\":{";
   int total   = PositionsTotal();

   for(int i=0; i<total; i++)
   {
      ulong ticket = PositionGetTicket(i);
      if(!PositionSelectByTicket(ticket)) continue;

      string  sym   = PositionGetString(POSITION_SYMBOL);
      double  lot   = PositionGetDouble(POSITION_VOLUME);
      double  entry = PositionGetDouble(POSITION_PRICE_OPEN);
      double  sl    = PositionGetDouble(POSITION_SL);
      double  tp    = PositionGetDouble(POSITION_TP);
      double  pl    = PositionGetDouble(POSITION_PROFIT);
      
      string  side  = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY)
                     ? "BUY" : "SELL";
      
      datetime open_time = (datetime)PositionGetInteger(POSITION_TIME);
      string o_time = TimeToString(open_time, TIME_DATE|TIME_MINUTES|TIME_SECONDS);
      
      json += "\""+IntegerToString(ticket)+"\":{" +
              "\"ticket\":"+IntegerToString(ticket)+"," +
              "\"symbol\":\""+sym+"\"," +
              "\"lot\":"+DoubleToString(lot,2)+"," +
              "\"side\":\""+side+"\"," +
              "\"entry\":"+DoubleToString(entry,5)+"," +
              "\"sl\":"+DoubleToString(sl,5)+"," +
              "\"tp\":"+DoubleToString(tp,5)+"," +
              "\"open_time\":\""+o_time+"\"," +
              "\"profit\":"+DoubleToString(pl,2)+"}";

      if(i < total-1) json += ",";
   }
   json += "}}";

   uchar post[];
   StrToBytes(json, post);

   uchar result[];
   string headers = "Content-Type: application/json\r\n";
   string result_hdr;
   int    code = WebRequest("POST", gEndpointTrades, "", headers,
                            5000, post, ArraySize(post), result, result_hdr);

   PrintFormat("[ReportBot] /update_trades → HTTP %d  (open=%d)", code, total);
}

//+------------------------------------------------------------------+
//| Send account‑status snapshot                                     |
//+------------------------------------------------------------------+
void SendAccountStatus()
{
   double eq      = AccountInfoDouble(ACCOUNT_EQUITY);
   double bal     = AccountInfoDouble(ACCOUNT_BALANCE);
   double margin  = AccountInfoDouble(ACCOUNT_MARGIN);
   double free    = AccountInfoDouble(ACCOUNT_FREEMARGIN);
   double lev_dbl = (double)AccountInfoInteger(ACCOUNT_LEVERAGE);  // explicit cast
   int    open    = PositionsTotal();

   string query = gEndpointStatus +
                 "?account_id="   + gAccountId +
                 "&equity="       + DoubleToString(eq, 2) +
                 "&balance="      + DoubleToString(bal, 2) +
                 "&margin="       + DoubleToString(margin, 2) +
                 "&free_margin="  + DoubleToString(free, 2) +
                 "&leverage="     + DoubleToString(lev_dbl, 0) +
                 "&positions="    + IntegerToString(open);

   uchar result[];
   string headers, result_hdr;
   int    code = WebRequest("GET", query, "", headers,
                           5000, NULL, 0, result, result_hdr);

   PrintFormat("[ReportBot] /account_status → HTTP %d", code);
}

//─────────────────────────────────────────────────────────────
//  Close‑ticket queue – expects array of ticket numbers
//─────────────────────────────────────────────────────────────
void CheckCloseRequests()
{
   // Debug - print the URL and account ID being used
   string url = ApiUrl + "/mt5/poll_close_queue?account_id=" + gAccountId;
   PrintFormat("Polling close queue with URL: %s", url);
   PrintFormat("Using account ID: %s", gAccountId);

   // Create empty arrays and headers for WebRequest
   char empty[];
   uchar result[];
   string headers = "";
   string result_headers;
   
   // Make the WebRequest call
   int closeCode = WebRequest("GET", url, headers, 5000, empty, result, result_headers);
   
   PrintFormat("[ReportBot] /poll_close_queue → HTTP %d", closeCode);
   
   if(closeCode != 200)
   {
      PrintFormat("Error checking close queue: HTTP %d", closeCode);
      return;
   }

   // Process the response
   string response = CharArrayToString(result, 0, ArraySize(result));
   PrintFormat("Response: %s", response);
   
   CJAVal root;
   if(!root.Deserialize(response))
   {
      Print("Error deserializing close queue response");
      return;
   }

   int n = root["tickets"].Size();
   PrintFormat("Found %d tickets in close queue", n);
   
   if(n == 0) return;

   for(int i = 0; i < n; i++)
   {
      ulong tk = (ulong)root["tickets"][i].ToInt();
      PrintFormat("Attempting to close ticket: %llu", tk);
      
      if(Trade.PositionClose(tk))
         PrintFormat("ReportBot: closed %llu (ExitNet)", tk);
      else
         PrintFormat("Failed to close ticket %llu: %d", tk, GetLastError());
   }
}

//─────────────────────────────────────────────────────────────
//  Modify‑SL/TP queue – expects array of objects:
//  [{ticket:123, sl:..., tp:...}, … ]
//─────────────────────────────────────────────────────────────
void CheckModifyRequests()
{
   // Debug - print the URL and account ID being used
   string url = ApiUrl + "/mt5/poll_modify_queue?account_id=" + gAccountId;
   PrintFormat("Polling modify queue with URL: %s", url);
   
   // Create empty arrays and headers for WebRequest
   char empty[];
   uchar result[];
   string headers = "";
   string result_headers;
   
   // Make the WebRequest call
   int modifyCode = WebRequest("GET", url, headers, 5000, empty, result, result_headers);
   
   PrintFormat("[ReportBot] /poll_modify_queue → HTTP %d", modifyCode);
   
   if(modifyCode != 200)
   {
      PrintFormat("Error checking modify queue: HTTP %d", modifyCode);
      return;
   }

   // Process the response
   string response = CharArrayToString(result, 0, ArraySize(result));
   
   CJAVal root;
   if(!root.Deserialize(response))
   {
      Print("Error deserializing modify queue response");
      return;
   }

   int objCnt = root["mods"].Size();
   PrintFormat("Found %d modifications in queue", objCnt);
   
   if(objCnt == 0) return;

   for(int idx=0; idx < objCnt; idx++)
   {
      ulong ticket = (ulong)root["mods"][idx]["ticket"].ToInt();
      double sl    = root["mods"][idx]["sl"].ToDbl();
      double tp    = root["mods"][idx]["tp"].ToDbl();

      if(sl == 0) sl = EMPTY_VALUE;
      if(tp == 0) tp = EMPTY_VALUE;

      if(Trade.PositionModify(ticket, sl, tp))
         PrintFormat("ReportBot: modified %llu  SL=%.5f  TP=%.5f", ticket, sl, tp);
      else 
         PrintFormat("Failed to modify ticket %llu: %d", ticket, GetLastError());
   }
}