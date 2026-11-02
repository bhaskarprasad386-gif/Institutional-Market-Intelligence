import type { BaseMetal, LmeObservation } from "./types";
const aliases: Record<string,string[]> = {
 exchange:["exchange","exchange_code","market","venue"],
 metal:["metal","commodity","base_metal","product","metal_name"], reportDate:["date","report_date","trade_date","as_of_date","stock_date","reporting_date"],
 warehouseRegion:["region","warehouse_region","location","warehouse","warehouse_location","country","warehouse_country"],
 totalInventoryTonnes:["total_inventory_tonnes","total_inventory","inventory","stock_tonnes","total_stock","total_stock_tonnes","closing_stock","closing_stock_tonnes","closing_stocks","stocks","stock"],
 onWarrantTonnes:["on_warrant","on_warrant_tonnes","live_warrants","live_warrants_t","live_warrants_tonnes","warrants_live"],
 cancelledWarrantsTonnes:["cancelled_warrants","cancelled_warrants_t","cancelled_warrants_tonnes","cancelled","cancelled_warrant","cancelled_warrants_stock"],
 dailyChangeTonnes:["daily_change","daily_change_tonnes","change","net_change","stock_change","stock_change_tonnes","daily_stock_change","daily_stock_change_tonnes","change_in_stocks"],
 openingStockTonnes:["opening_stock","opening_stock_tonnes","opening_stocks","opening_inventory"],
 deliveredInTonnes:["delivered_in","delivered_in_tonnes","deliveries_in","arrivals","inbound"],
 deliveredOutTonnes:["delivered_out","delivered_out_tonnes","deliveries_out","withdrawals","outbound"],
 productionTonnes:["production","production_tonnes","mine_production"],importsTonnes:["imports","imports_tonnes","import_tonnes"],exportsTonnes:["exports","exports_tonnes","export_tonnes"],cashPrice:["cash_price","cash","cash_settlement","cash_official","cash_usd_tonne"],threeMonthPrice:["3m","3_month","three_month","3m_price","three_month_price","3_month_price","three_month_settlement","3m_official","3m_usd_tonne"]
};
function norm(value:unknown):string{return String(value??"").replace(/^\uFEFF/,"").trim().toLowerCase().replace(/&/g,"and").replace(/[\s\-()%./]+/g,"_").replace(/_+/g,"_").replace(/^_|_$/g,"");}
function get(row:Record<string,unknown>,key:string):unknown{const names=Object.keys(row);for(const alias of aliases[key]??[]){const found=names.find(name=>norm(name)===norm(alias));if(found!==undefined)return row[found];}return undefined;}
function numeric(value:unknown):{value?:number;invalid:boolean}{
 if(value===undefined||value===null||String(value).trim()===""||["-","—"].includes(String(value).trim()))return {invalid:false};
 if(typeof value==="number")return Number.isFinite(value)?{value,invalid:false}:{invalid:true};
 const raw=String(value).trim().replace(/\u00a0/g," ").replace(/,/g,"").replace(/\s/g,"");
 const accounting=raw.startsWith("(")&&raw.endsWith(")"),cleaned=accounting?raw.slice(1,-1):raw;
 if(!/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$/.test(cleaned))return {invalid:true};
 const parsed=Number(cleaned)*(accounting?-1:1);return Number.isFinite(parsed)?{value:parsed,invalid:false}:{invalid:true};
}
function isoDate(year:number,month:number,day:number):string|undefined{const d=new Date(Date.UTC(year,month-1,day));if(d.getUTCFullYear()!==year||d.getUTCMonth()!==month-1||d.getUTCDate()!==day)return undefined;return `${year.toString().padStart(4,"0")}-${month.toString().padStart(2,"0")}-${day.toString().padStart(2,"0")}`;}
function parseDate(value:unknown):string|undefined{
 if(value instanceof Date&&!Number.isNaN(value.getTime()))return isoDate(value.getFullYear(),value.getMonth()+1,value.getDate());
 if(typeof value==="number"&&Number.isFinite(value)&&value>0&&value<100000){const d=new Date(Date.UTC(1899,11,30)+Math.floor(value)*86400000);return isoDate(d.getUTCFullYear(),d.getUTCMonth()+1,d.getUTCDate());}
 const s=String(value??"").trim();let m=s.match(/^(\d{4})-(\d{1,2})-(\d{1,2})$/);if(m)return isoDate(Number(m[1]),Number(m[2]),Number(m[3]));
 m=s.match(/^(\d{1,2})[/-](\d{1,2})[/-](\d{4})$/);if(m)return isoDate(Number(m[3]),Number(m[2]),Number(m[1]));
 m=s.match(/^(\d{1,2})[-/ ]([A-Za-z]{3,9})[-/ ](\d{4})$/);if(m){const month=new Date(`${m[2]} 1, 2000`).getMonth()+1;return isoDate(Number(m[3]),month,Number(m[1]));}return undefined;
}
const metalMap:Record<string,BaseMetal>={aluminium:"ALUMINIUM",aluminum:"ALUMINIUM",copper:"COPPER",zinc:"ZINC",nickel:"NICKEL",lead:"LEAD",tin:"TIN"};
export function mapLmeRows(input:Record<string,unknown>[],defaultExchange:"LME"|"COMEX"|"SHFE"|"MCX"|"OTHER"="LME"):{rows:LmeObservation[];rejected:{row:number;reason:string}[]}{
 const rows:LmeObservation[]=[],rejected:{row:number;reason:string}[]=[];
 input.forEach((raw,index)=>{
  const metal=metalMap[norm(get(raw,"metal")).replace(/_/g,"")],reportDate=parseDate(get(raw,"reportDate"));
  const exchangeRaw=norm(get(raw,"exchange")??defaultExchange).replace(/_/g,"");
  const exchangeMap:Record<string,"LME"|"COMEX"|"SHFE"|"MCX"|"OTHER">={lme:"LME",comex:"COMEX",cme:"COMEX",cmecomex:"COMEX",shfe:"SHFE",shanghai:"SHFE",shanghaifutures:"SHFE",mcx:"MCX",other:"OTHER"};
  const exchange=exchangeMap[exchangeRaw];
  const fields=["totalInventoryTonnes","onWarrantTonnes","cancelledWarrantsTonnes","dailyChangeTonnes","openingStockTonnes","deliveredInTonnes","deliveredOutTonnes","productionTonnes","importsTonnes","exportsTonnes","cashPrice","threeMonthPrice"] as const;
  const parsed=Object.fromEntries(fields.map(key=>[key,numeric(get(raw,key))])) as Record<typeof fields[number],{value?:number;invalid:boolean}>;
  const reject=(reason:string)=>rejected.push({row:index+2,reason});
  if(!exchange){reject("Unsupported exchange; use LME, COMEX, SHFE, MCX or OTHER");return;}
  if(!metal){reject("Unsupported or missing metal (Aluminium, Copper, Zinc, Nickel, Lead, Tin)");return;}
  if(!reportDate){reject("Invalid report date; use YYYY-MM-DD, DD/MM/YYYY, DD-MMM-YYYY or an Excel date");return;}
  const total=parsed.totalInventoryTonnes.value;
  if(parsed.totalInventoryTonnes.invalid||total===undefined||total<0){reject("Total / closing inventory must be a valid non-negative number");return;}
  const invalidField=fields.find(key=>parsed[key].invalid);if(invalidField){reject(`Invalid numeric value in ${invalidField}`);return;}
  const nonNegative:typeof fields[number][]=["onWarrantTonnes","cancelledWarrantsTonnes","openingStockTonnes","deliveredInTonnes","deliveredOutTonnes","productionTonnes","importsTonnes","exportsTonnes"];
  if(nonNegative.some(key=>parsed[key].value!==undefined&&parsed[key].value!<0)){reject("Inventory and flow quantities cannot be negative (daily change may be negative)");return;}
  const live=parsed.onWarrantTonnes.value,cancelled=parsed.cancelledWarrantsTonnes.value;
  if(live!==undefined&&live>total){reject("Live / on-warrant stock exceeds total inventory");return;}
  if(cancelled!==undefined&&cancelled>total){reject("Cancelled warrants exceed total inventory");return;}
  if(live!==undefined&&cancelled!==undefined&&live+cancelled>total+1e-8){reject("Live plus cancelled warrants exceed total inventory");return;}
  if(parsed.cashPrice.value!==undefined&&parsed.cashPrice.value<=0||parsed.threeMonthPrice.value!==undefined&&parsed.threeMonthPrice.value<=0){reject("Cash and 3M prices must be positive when supplied");return;}
  rows.push({exchange,metal,reportDate,warehouseRegion:String(get(raw,"warehouseRegion")??"").trim()||undefined,totalInventoryTonnes:total,onWarrantTonnes:live,cancelledWarrantsTonnes:cancelled,dailyChangeTonnes:parsed.dailyChangeTonnes.value,openingStockTonnes:parsed.openingStockTonnes.value,deliveredInTonnes:parsed.deliveredInTonnes.value,deliveredOutTonnes:parsed.deliveredOutTonnes.value,productionTonnes:parsed.productionTonnes.value,importsTonnes:parsed.importsTonnes.value,exportsTonnes:parsed.exportsTonnes.value,cashPrice:parsed.cashPrice.value,threeMonthPrice:parsed.threeMonthPrice.value});
 });return {rows,rejected};
}
