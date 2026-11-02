import type { BrokerRating, BrokerRecommendation, CompanyResult } from "./types";
type Raw = Record<string, unknown>;
type Rejection = { rowNumber: number; reason: string };
const aliases: Record<string, string[]> = {
 broker:["broker","broker_name","research_house","analyst"],symbol:["symbol","ticker","scrip","tckrsymb"],
 rating:["rating","recommendation","call","action"],publishedDate:["published_date","recommendation_date","report_date","date"],
 targetPrice:["target_price","target","price_target"],publishedEntry:["entry","entry_price","published_entry"],
 publishedStopLoss:["stop_loss","stoploss","sl","published_stop_loss"],sourceUrl:["source_url","url","report_url"],
 sourceTitle:["source_title","report_title","title"],observedPrice:["observed_price","evaluation_price","latest_price"],
 observedDate:["observed_date","evaluation_date","price_date"],companyName:["company","company_name","name"],
 period:["period","quarter","financial_period"],revenue:["revenue","total_income","net_sales"],
 ebitda:["ebitda","operating_ebitda"],pat:["pat","net_profit","profit_after_tax"],eps:["eps","basic_eps"],
 operatingMarginPct:["operating_margin","operating_margin_pct"],netMarginPct:["net_margin","net_margin_pct"],
 debt:["debt","total_debt","borrowings"],operatingCashFlow:["operating_cash_flow","cash_from_operations"],
 freeCashFlow:["free_cash_flow"],previousRevenue:["previous_revenue","prior_revenue"],
 previousEbitda:["previous_ebitda","prior_ebitda"],previousPat:["previous_pat","prior_pat"],
 previousEps:["previous_eps","prior_eps"],guidanceRevenue:["guidance_revenue","revenue_guidance"],
 guidanceEbitda:["guidance_ebitda","ebitda_guidance"],guidancePat:["guidance_pat","pat_guidance"],
 guidanceText:["guidance_text","management_guidance"],managementCommentary:["management_commentary","commentary","management_notes"],open:["open","opening_price","opnpric"],high:["high","high_price","hghpric"],low:["low","low_price","lwpric"],close:["close","close_price","clspric"]
};
const norm=(s:string)=>s.toLowerCase().replace(/[ _-]/g,"");
function get(row:Raw,key:keyof typeof aliases):unknown {
 return Object.entries(row).find(([header])=>aliases[key].some(alias=>norm(alias)===norm(header)))?.[1];
}
function num(value:unknown):number|undefined {
 if(value===undefined||value===null||String(value).trim()==="")return undefined;
 const parsed=Number(String(value).replace(/,/g,""));return Number.isFinite(parsed)?parsed:undefined;
}
function date(value:unknown):string|undefined {
 if(value instanceof Date&&!Number.isNaN(value.getTime()))return value.toISOString().slice(0,10);
 const s=String(value??"").trim();
 if(/^\d{4}-\d{2}-\d{2}$/.test(s))return s;
 const m=s.match(/^(\d{1,2})[-/]([A-Za-z]{3})[-/](\d{4})$/);
 if(m){const d=new Date(`${m[2]} ${m[1]}, ${m[3]} UTC`);if(!Number.isNaN(d.getTime()))return d.toISOString().slice(0,10);}
 return undefined;
}
function optionalText(value:unknown):string|undefined {const s=String(value??"").trim();return s||undefined;}

export function mapRecommendationRows(input:Raw[]):{rows:BrokerRecommendation[];rejected:Rejection[]} {
 const rows:BrokerRecommendation[]=[],rejected:Rejection[]=[];
 input.forEach((raw,index)=>{
  const broker=String(get(raw,"broker")??"").trim(),symbol=String(get(raw,"symbol")??"").trim();
  const rating=String(get(raw,"rating")??"").trim().toUpperCase() as BrokerRating;
  const publishedDate=date(get(raw,"publishedDate"));
  const targetPrice=num(get(raw,"targetPrice")),publishedEntry=num(get(raw,"publishedEntry")),publishedStopLoss=num(get(raw,"publishedStopLoss"));
  if(!broker||!symbol||!publishedDate||!["BUY","HOLD","SELL"].includes(rating)||
    [targetPrice,publishedEntry,publishedStopLoss].some(v=>v!==undefined&&v<=0)){
    rejected.push({rowNumber:index+2,reason:"Broker, symbol, date, BUY/HOLD/SELL rating or valid positive price missing"});return;
  }
  rows.push({broker,symbol,rating,publishedDate,targetPrice,publishedEntry,publishedStopLoss,
   sourceUrl:optionalText(get(raw,"sourceUrl")),sourceTitle:optionalText(get(raw,"sourceTitle")),
   observedPrice:num(get(raw,"observedPrice")),observedDate:date(get(raw,"observedDate"))});
 });
 return {rows,rejected};
}

export function mapCompanyResultRows(input:Raw[]):{rows:CompanyResult[];rejected:Rejection[]} {
 const rows:CompanyResult[]=[],rejected:Rejection[]=[];
 input.forEach((raw,index)=>{
  const symbol=String(get(raw,"symbol")??"").trim(),period=String(get(raw,"period")??"").trim();
  const publishedDate=date(get(raw,"publishedDate"));
  if(!symbol||!period||!publishedDate){rejected.push({rowNumber:index+2,reason:"Symbol, financial period and published date are required"});return;}
  const numericKeys=["revenue","ebitda","pat","eps","operatingMarginPct","netMarginPct","debt","operatingCashFlow","freeCashFlow","previousRevenue","previousEbitda","previousPat","previousEps","guidanceRevenue","guidanceEbitda","guidancePat"] as const;
  const values:Partial<CompanyResult>={};
  for(const key of numericKeys){const value=num(get(raw,key));if(value!==undefined)values[key]=value;}
  rows.push({symbol,period,publishedDate,companyName:optionalText(get(raw,"companyName")),
   sourceUrl:optionalText(get(raw,"sourceUrl")),sourceTitle:optionalText(get(raw,"sourceTitle")),
   guidanceText:optionalText(get(raw,"guidanceText")),managementCommentary:optionalText(get(raw,"managementCommentary")),
   ...values});
 });
 return {rows,rejected};
}

import type { HistoricalPriceBar } from "./types";

export function mapHistoricalPriceRows(input: Raw[], expectedSymbol?: string): { rows: HistoricalPriceBar[]; rejected: Rejection[] } {
 const rows: HistoricalPriceBar[] = [], rejected: Rejection[] = [];
 input.forEach((raw,index) => {
  const symbol=String(get(raw,"symbol")??"").trim(),tradeDate=date(get(raw,"publishedDate"));
  const open=num(get(raw,"open")),high=num(get(raw,"high")),low=num(get(raw,"low")),close=num(get(raw,"close"));
  if(!symbol||!tradeDate||open===undefined||high===undefined||low===undefined||close===undefined||
    Math.min(open,high,low,close)<=0||high<Math.max(open,close,low)||low>Math.min(open,close,high)||
    (expectedSymbol&&symbol.toUpperCase()!==expectedSymbol.toUpperCase())){
    rejected.push({rowNumber:index+2,reason:"Invalid symbol/date/OHLC values or symbol mismatch"});return;
  }
  rows.push({symbol,tradeDate,open,high,low,close});
 });
 return {rows,rejected};
}
