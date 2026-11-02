import type { OptionObservation, OptionType } from "./types";
type Raw=Record<string,unknown>;
type Rejection={rowNumber:number;reason:string};
const aliases:Record<string,string[]>={underlying:["underlying","underlying_symbol","underlyingsymbol","underlyingname"],symbol:["symbol","tradingsymbol","ticker"],tradeDate:["date","trade_date","tradedate","trad_dt"],expiryDate:["expiry","expiry_date","expirydate","xprydt"],strike:["strike","strike_price","strikeprice"],optionType:["option_type","instrument_type","type","opttype"],spotPrice:["spot","spot_price","underlying_value","undrlygpric"],openInterest:["oi","open_interest","openinterest","opnintrst"],previousOpenInterest:["previous_oi","prev_oi","previous_open_interest"],previousLtp:["previous_ltp","prev_ltp","previous_close","prev_close"],volume:["volume","traded_volume","ttltradgvol"],ltp:["ltp","last_price","close","clspric"],bid:["bid","best_bid","bid_price"],ask:["ask","best_ask","ask_price"],ivPct:["iv","iv_pct","implied_volatility","impliedvolatility"]};
const norm=(s:string)=>s.toLowerCase().replace(/[ _-]/g,"");
function get(r:Raw,k:keyof typeof aliases):unknown{return Object.entries(r).find(([h])=>aliases[k].some(a=>norm(a)===norm(h)))?.[1];}
function num(v:unknown):number|undefined{if(v===undefined||v===null||String(v).trim()==="")return undefined;const n=Number(String(v).replace(/,/g,""));return Number.isFinite(n)?n:undefined;}
function date(v:unknown):string|undefined{if(v instanceof Date&&!Number.isNaN(v.getTime()))return v.toISOString().slice(0,10);const s=String(v??"").trim();if(/^\d{4}-\d{2}-\d{2}$/.test(s))return s;const m=s.match(/^(\d{1,2})[-/]([A-Za-z]{3})[-/](\d{4})$/);if(m){const d=new Date(`${m[2]} ${m[1]}, ${m[3]} UTC`);if(!Number.isNaN(d.getTime()))return d.toISOString().slice(0,10);}return undefined;}
export function mapOptionRows(input:Raw[]):{rows:OptionObservation[];rejected:Rejection[]}{
 const rows:OptionObservation[]=[],rejected:Rejection[]=[];
 input.forEach((raw,index)=>{
  const underlying=String(get(raw,"underlying")??"").trim(),symbol=String(get(raw,"symbol")??"").trim();
  const tradeDate=date(get(raw,"tradeDate")),expiryDate=date(get(raw,"expiryDate")),strike=num(get(raw,"strike"));
  const rawType=String(get(raw,"optionType")??"").trim().toUpperCase();
  const optionType=(rawType==="CE"||rawType==="CALL"?"CE":rawType==="PE"||rawType==="PUT"?"PE":undefined) as OptionType|undefined;
  const spotPrice=num(get(raw,"spotPrice")),openInterest=num(get(raw,"openInterest"));
  const previousOpenInterest=num(get(raw,"previousOpenInterest")),previousLtp=num(get(raw,"previousLtp")),volume=num(get(raw,"volume")),ltp=num(get(raw,"ltp")),bid=num(get(raw,"bid")),ask=num(get(raw,"ask")),ivPct=num(get(raw,"ivPct"));
  if(!underlying||!tradeDate||!expiryDate||strike===undefined||strike<=0||!optionType||spotPrice===undefined||spotPrice<=0||openInterest===undefined||openInterest<0||
    [previousOpenInterest,previousLtp,volume,ltp,bid,ask,ivPct].some(x=>x!==undefined&&x<0)||ivPct!==undefined&&ivPct>1000||
    (ltp!==undefined&&ltp<=0)||(bid!==undefined&&bid<=0)||(ask!==undefined&&ask<=0)||(bid!==undefined&&ask!==undefined&&bid>ask)){
   rejected.push({rowNumber:index+2,reason:"Required underlying/date/expiry/strike/CE-PE/spot/OI missing or invalid; check optional prices and IV"});return;
  }
  if(expiryDate<tradeDate){rejected.push({rowNumber:index+2,reason:"Expiry date is before trade date"});return;}
  rows.push({underlying,symbol,tradeDate,expiryDate,strike,optionType,spotPrice,openInterest,previousOpenInterest,previousLtp,volume,ltp,bid,ask,ivPct});
 });
 return {rows,rejected};
}
