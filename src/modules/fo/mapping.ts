import type { FuturesObservation } from "./types";
type Raw=Record<string,unknown>;
const aliases:Record<string,string[]>={symbol:["symbol","ticker","tckrsymb"],tradeDate:["date","trade_date","trddt","trad_dt"],expiryDate:["expiry","expiry_date","xprydt"],futuresClose:["close","close_price","clspric","settle_pr","sttlmpric"],spotClose:["spot","spot_close","underlying_value","undrlygpric"],openInterest:["oi","open_interest","opn_interest","openinterest","opnintrst"],previousOpenInterest:["prev_oi","previous_oi","prev_open_interest"],changeOpenInterest:["change_oi","chnginopnintrst"],previousFuturesClose:["prev_close","previous_close","prev_fut_close","prvsclsgpric"],volume:["volume","contracts","ttl_trd_qnty","ttltradgvol"],lotSize:["lot_size","market_lot","market_lot_size","marketlot","contract_size"]};
const norm=(s:string)=>s.toLowerCase().replace(/[ _-]/g,"");
function get(r:Raw,k:keyof typeof aliases){const entry=Object.entries(r).find(([h])=>aliases[k].some(a=>norm(a)===norm(h)));return entry?.[1];}
function num(v:unknown):number|undefined {if(v===undefined||v===null||String(v).trim()==="")return undefined;const n=Number(String(v).replace(/,/g,""));return Number.isFinite(n)?n:undefined;}
function date(v:unknown):string|undefined {if(v instanceof Date&&!Number.isNaN(v.getTime()))return v.toISOString().slice(0,10);const s=String(v??"").trim();if(/^\d{4}-\d{2}-\d{2}$/.test(s))return s;const m=s.match(/^(\d{1,2})[-/]([A-Za-z]{3})[-/](\d{4})$/);if(m){const d=new Date(`${m[2]} ${m[1]}, ${m[3]} UTC`);if(!Number.isNaN(d.getTime()))return d.toISOString().slice(0,10);}return undefined;}
export function mapFuturesRows(rawRows:Raw[]):{rows:FuturesObservation[];rejected:{rowNumber:number;reason:string}[]} {
 const rows:FuturesObservation[]=[],rejected:{rowNumber:number;reason:string}[]=[];
 rawRows.forEach((r,i)=>{const symbol=String(get(r,"symbol")??"").trim(),tradeDate=date(get(r,"tradeDate")),expiryDate=date(get(r,"expiryDate")),futuresClose=num(get(r,"futuresClose")),spotClose=num(get(r,"spotClose")),openInterest=num(get(r,"openInterest"));
 if(!symbol||!tradeDate||!expiryDate||futuresClose===undefined||spotClose===undefined||openInterest===undefined||futuresClose<=0||spotClose<=0||openInterest<0){rejected.push({rowNumber:i+2,reason:"Required symbol/date/expiry/price/OI field missing or invalid"});return;}
 const explicitPreviousOi=num(get(r,"previousOpenInterest")),changeOi=num(get(r,"changeOpenInterest")),previousOpenInterest=explicitPreviousOi??(changeOi===undefined?undefined:openInterest-changeOi),previousFuturesClose=num(get(r,"previousFuturesClose")),volume=num(get(r,"volume"));
 rows.push({symbol,tradeDate,expiryDate,futuresClose,spotClose,openInterest,previousOpenInterest,previousFuturesClose,volume,lotSize:lotSize!==undefined&&lotSize>0?lotSize:undefined});
 });return {rows,rejected};
}
