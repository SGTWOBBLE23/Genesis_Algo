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

   EventSetTimer(60);   // 60‑second heartbeat
   PrintFormat("🟢 ReportBot started  account_id=%s  url=%s", gAccountId, ApiUrl);
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
   SendOpenPositions();
   SendAccountStatus();
   CheckCloseRequests();
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

      json += "\""+IntegerToString((long)ticket)+"\":{"
              "\"symbol\":\""+sym+"\","                     +
              "\"lot\":"+DoubleToString(lot,2)+","          +
              "\"entry\":"+DoubleToString(entry,_Digits)+","+
              "\"sl\":"+DoubleToString(sl,_Digits)+","      +
              "\"tp\":"+DoubleToString(tp,_Digits)+","      +
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
                  "?account_id="     + gAccountId +
                  "&balance="        + DoubleToString(bal, 2) +
                  "&equity="         + DoubleToString(eq, 2) +
                  "&margin="         + DoubleToString(margin, 2) +
                  "&free_margin="    + DoubleToString(free, 2) +
                  "&leverage="       + DoubleToString(lev_dbl, 0) +
                  "&open_positions=" + IntegerToString(open);

   uchar dummy[];
   uchar result[];
   string hdr;
   int code = WebRequest("GET", query, "", "", 5000, dummy, 0, result, hdr);
   PrintFormat("[ReportBot] /account_status → HTTP %d", code);
}

//─────────────────────────────────────────────────────────────
//  Close‑ticket queue – expects array of ticket numbers
//─────────────────────────────────────────────────────────────
void CheckCloseRequests()
{
   string loginStr = IntegerToString((int)AccountInfoInteger(ACCOUNT_LOGIN));
   string url      = ApiUrl + "/mt5/poll_close_queue?account_id=" + loginStr;

   uchar res[], dummy[];  string hdr;
   if(WebRequest("GET", url, "", "", 5000, dummy, 0, res, hdr) != 200)
      return;

   CJAVal root;
   if(!root.Deserialize(CharArrayToString(res,0,ArraySize(res))))
      return;

   int n = root["tickets"].Size();
   if(n == 0) return;

   for(int i = 0; i < n; i++)
   {
      ulong tk = (ulong)root["tickets"][i].ToInt();
      if(Trade.PositionClose(tk))
         PrintFormat("ReportBot: closed %llu (ExitNet)", tk);
   }
}

//─────────────────────────────────────────────────────────────
//  Modify‑SL/TP queue – expects array of objects:
//  [{ticket:123, sl:..., tp:...}, … ]
//─────────────────────────────────────────────────────────────
void CheckModifyRequests()
{
   string loginStr = IntegerToString((int)AccountInfoInteger(ACCOUNT_LOGIN));
   string url      = ApiUrl + "/mt5/poll_modify_queue?account_id=" + loginStr;

   uchar res[], dummy[];  string hdr;
   if(WebRequest("GET", url, "", "", 5000, dummy, 0, res, hdr) != 200)
      return;

   CJAVal root;
   if(!root.Deserialize(CharArrayToString(res,0,ArraySize(res))))
      return;

   int objCnt = root["mods"].Size();
   if(objCnt == 0) return;

   CJAVal mods = root["mods"];

   for(int idx = 0; idx < objCnt; idx++)
   {
      ulong  tk = (ulong)mods[idx]["ticket"].ToInt();

      double sl = mods[idx]["sl"].ToDbl();
      double tp = mods[idx]["tp"].ToDbl();

      if(sl == 0) sl = EMPTY_VALUE;
      if(tp == 0) tp = EMPTY_VALUE;

      if(Trade.PositionModify(tk, sl, tp))
         PrintFormat("ReportBot: modified %llu  SL=%.5f  TP=%.5f", tk, sl, tp);
   }
}