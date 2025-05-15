//+------------------------------------------------------------------+
//|                    MT5_ReportBot.mq5                             |
//|   Lightweight account/position reporter for MT5 → Flask API      |
//|   Version: 1.05 (2025‑05‑15) – Added Debug Logging               |
//+------------------------------------------------------------------+
#property copyright "You"
#property version   "1.05"
#property strict

//─- Inputs ----------------------------------------------------------
input string ApiUrl       = "https://4c1f2076-899e-4ced-962a-2903ca4a9bac-00-29hcpk84r1chm.picard.replit.dev";
input string AccountAlias = "";

//─- Includes --------------------------------------------------------
#include <JAson.mqh>          // CJAVal
#include <Trade\Trade.mqh>    // CTrade

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

   EventSetTimer(60);  // 60‑second heartbeat
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
   
   Print("Sending open positions...");
   SendOpenPositions();
   
   Print("Sending account status...");
   SendAccountStatus();
   
   Print("Checking close requests...");
   CheckCloseRequests();
   
   Print("Checking modify requests...");
   CheckModifyRequests();
   
   Print("✅ All API calls completed");
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
      string  side  = (PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY) ? "BUY":"SELL";

      json += "\""+IntegerToString(ticket)+"\":{"
              "\"symbol\":\""+sym+"\","
              "\"lot\":"+DoubleToString(lot,2)+","
              "\"side\":\""+side+"\","
              "\"entry\":"+DoubleToString(entry,_Digits)+","
              "\"sl\":"+DoubleToString(sl,_Digits)+","
              "\"tp\":"+DoubleToString(tp,_Digits)+","
              "\"profit\":"+DoubleToString(pl,2)+"}";

      if(i < total-1) json += ",";
   }
   json += "}}";

   // --- POST ------------------------------------------------------
   uchar post[];
   StrToBytes(json, post);

   uchar result[];
   string headers   = "Content-Type: application/json\r\n";
   string resultHdr;

   /* correct overload:
      WebRequest(method, url, headers, cookie, timeout,
                 postBody[], postSize, result[], resultHeaders)
   */
   int code = WebRequest("POST",
                         gEndpointTrades,
                         headers,
                         "",          // cookie
                         5000,
                         post,
                         ArraySize(post),
                         result,
                         resultHdr);

   PrintFormat("[ReportBot] /update_trades → HTTP %d  (open=%d)", code, total);
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

   uchar dummy[];
   uchar result[];
   string resultHdr;

   /* GET with no body → use overload:
      WebRequest(method,url,headers,cookie,timeout,body[],size,result[],hdr)
      pass empty headers + cookie, body array size 0
   */
   int code = WebRequest("GET",
                         query,
                         "",      // headers
                         "",      // cookie
                         5000,
                         dummy,
                         0,
                         result,
                         resultHdr);

   PrintFormat("[ReportBot] /account_status → HTTP %d", code);
}

//─────────────────────────────────────────────────────────────
//  Close‑ticket queue
//─────────────────────────────────────────────────────────────
void CheckCloseRequests()
{
   string url = ApiUrl + "/mt5/poll_close_queue?account_id=" + gAccountId;
   PrintFormat("DEBUG: Checking close queue with URL: %s", url);

   uchar dummy[];
   uchar res[];
   string hdr;

   int code = WebRequest("GET",
                         url,
                         "", "", 5000,
                         dummy, 0,
                         res, hdr);

   PrintFormat("[ReportBot] /poll_close_queue → HTTP %d", code);
   
   if(code != 200) {
      PrintFormat("ERROR checking close queue: HTTP %d", code);
      return;
   }

   string response = CharArrayToString(res, 0, ArraySize(res));
   PrintFormat("Response from close queue: %s", response);

   CJAVal root;
   if(!root.Deserialize(response)) {
      Print("ERROR: Failed to parse JSON response from close queue");
      return;
   }

   int n = root["tickets"].Size();
   PrintFormat("Found %d tickets in close queue", n);
   
   for(int i=0;i<n;i++)
   {
      ulong tk = (ulong)root["tickets"][i].ToInt();
      PrintFormat("Attempting to close ticket: %llu", tk);
      
      if(Trade.PositionClose(tk))
         PrintFormat("SUCCESS: closed ticket %llu via ExitNet", tk);
      else
         PrintFormat("FAILED to close ticket %llu: error %d", tk, GetLastError());
   }
}

//─────────────────────────────────────────────────────────────
//  Modify‑SL/TP queue
//─────────────────────────────────────────────────────────────
void CheckModifyRequests()
{
   string url = ApiUrl + "/mt5/poll_modify_queue?account_id=" + gAccountId;
   PrintFormat("DEBUG: Checking modify queue with URL: %s", url);

   uchar dummy[];
   uchar res[];
   string hdr;

   int code = WebRequest("GET",
                         url,
                         "", "", 5000,
                         dummy, 0,
                         res, hdr);

   PrintFormat("[ReportBot] /poll_modify_queue → HTTP %d", code);
   
   if(code != 200) {
      PrintFormat("ERROR checking modify queue: HTTP %d", code);
      return;
   }

   string response = CharArrayToString(res, 0, ArraySize(res));
   if(StringLen(response) > 20) {
      // Only print the response if it's interesting (not empty)
      PrintFormat("Response from modify queue: %s", response);
   }

   CJAVal root;
   if(!root.Deserialize(response)) {
      Print("ERROR: Failed to parse JSON response from modify queue");
      return;
   }

   int m = root["mods"].Size();
   PrintFormat("Found %d modifications in queue", m);
   
   for(int j=0;j<m;j++)
   {
      ulong tk  = (ulong)root["mods"][j]["ticket"].ToInt();
      double sl = root["mods"][j]["sl"].ToDbl();
      double tp = root["mods"][j]["tp"].ToDbl();

      if(sl == 0) sl = EMPTY_VALUE;
      if(tp == 0) tp = EMPTY_VALUE;

      PrintFormat("Attempting to modify ticket: %llu SL=%f TP=%f", tk, sl, tp);
      
      if(Trade.PositionModify(tk, sl, tp))
         PrintFormat("SUCCESS: modified ticket %llu", tk);
      else
         PrintFormat("FAILED to modify ticket %llu: error %d", tk, GetLastError());
   }
}