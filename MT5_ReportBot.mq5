//+------------------------------------------------------------------+
//|                    MT5_ReportBot.mq5                             |
//|   Lightweight account/position reporter for MT5 → Flask API      |
//|   Version: 1.01 (2025-05-13)                                      |
//+------------------------------------------------------------------+
#property copyright "You"
#property link      ""
#property version   "1.01"
#property strict

//─- Inputs
input string ApiUrl       = "https://4c1f2076-899e-4ced-962a-2903ca4a9bac-00-29hcpk84r1chm.picard.replit.dev";
input string AccountAlias = "";

//─- Globals
string gAccountId;
string gEndpointTrades, gEndpointStatus;

//+------------------------------------------------------------------+
//|  Helper: convert string → uchar[] for WebRequest                 |
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

   gAccountId       = (StringLen(AccountAlias) > 0)
                        ? AccountAlias
                        : IntegerToString((int)AccountInfoInteger(ACCOUNT_LOGIN));

   gEndpointTrades  = ApiUrl + "/mt5/update_trades";
   gEndpointStatus  = ApiUrl + "/mt5/account_status";

   EventSetTimer(60);   // 60-second heartbeat
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
}

//+------------------------------------------------------------------+
//| Send open-positions snapshot                                     |
//+------------------------------------------------------------------+
void SendOpenPositions()
{
   //-- Build JSON --------------------------------------------------
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
              "\"symbol\":\""+sym+"\","
              "\"lot\":"+DoubleToString(lot,2)+","
              "\"entry\":"+DoubleToString(entry,_Digits)+","
              "\"sl\":"+DoubleToString(sl,_Digits)+","
              "\"tp\":"+DoubleToString(tp,_Digits)+","
              "\"profit\":"+DoubleToString(pl,2)+"}";

      if(i < total-1) json += ",";
   }
   json += "}}";

   //-- POST --------------------------------------------------------
   uchar post[];
   StrToBytes(json, post);

   uchar   result[];
   string  result_hdr;
   string  headers = "Content-Type: application/json\r\n";
   int     code = WebRequest("POST", gEndpointTrades, "", headers,
                             5000, post, ArraySize(post), result, result_hdr);

   PrintFormat("[ReportBot] /update_trades → HTTP %d  (open=%d)", code, total);
}

//+------------------------------------------------------------------+
//| Send account-status snapshot                                     |
//+------------------------------------------------------------------+
void SendAccountStatus()
{
   double eq      = AccountInfoDouble(ACCOUNT_EQUITY);
   double bal     = AccountInfoDouble(ACCOUNT_BALANCE);
   double margin  = AccountInfoDouble(ACCOUNT_MARGIN);
   double free    = AccountInfoDouble(ACCOUNT_FREEMARGIN);
   double lev     = AccountInfoInteger(ACCOUNT_LEVERAGE);
   int    open    = PositionsTotal();

   string query = gEndpointStatus +
                  "?account_id="     + gAccountId +
                  "&balance="        + DoubleToString(bal, 2) +
                  "&equity="         + DoubleToString(eq, 2) +
                  "&margin="         + DoubleToString(margin, 2) +
                  "&free_margin="    + DoubleToString(free, 2) +
                  "&leverage="       + DoubleToString(lev, 0) +
                  "&open_positions=" + IntegerToString(open);

   Print("📡 Sending account status GET → ", query);

   Print("📡 Sending account status GET → ", query);

   uchar result[];
   string result_headers;
   char dummy[];
   ArrayResize(dummy, 0);
   
   int code = WebRequest("GET", query, "", "", 5000, dummy, 0, result, result_headers);
   PrintFormat("[ReportBot] /account_status (GET) → HTTP %d", code);
}




//+------------------------------------------------------------------+
