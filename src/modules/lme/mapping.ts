import type { BaseMetal,LmeObservation } from "./types";
const aliases:Record<string,string[]>={
 metal:["metal","commodity","base_metal","product"],reportDate:["date","report_date","trade_date","as_of_date"],
 warehouseRegion:["region","warehouse_region","location"],
 totalInventoryTonnes:["total_inventory","inventory","stock_tonnes","total_stock","closing_stock"],
 onWarrantTonnes:["on_warrant","on_warrant_tonnes","live_warrants"],
 cancelledWarrantsTonnes:["cancelled_warrants","cancelled_warrants_tonnes","cancelled"],
 dailyChangeTonnes:["daily_change","change","net_change","stock_change"],
 productionTonnes:["production","production_tonnes"],importsTonnes:["imports","imports_tonnes"],exportsTonnes:["exports","exports_tonnes"]
};
function norm(v:unknown):string{return String(v??"").trim().toLowerCase().replace(/[\s\-()%]/g,"_").replace(/_+/g,"_");}
function get(row:Record<string,unknown>,key:string):unknown{const keys=Object.keys(row);for(const alias of aliases[key]??[]){const found=keys.find(k=>norm(k)===norm(alias));if(found!==undefined)return row[found];}return undefined;}
function num(v:unknown):number|undefined{if(v===undefined||v===null||String(v).trim()==="")return undefined;const n=Number(String(v).replace(/,/g,""));return Number.isFinite(n)?n:undefined;}
function date(v:unknown):string|undefined{if(v instanceof Date&&!Number.isNaN(v.getTime()))return v.toISOString().slice(0,10);const s=String(v??"").trim();if(/^\d{4}-\d{2}-\d{2}$/.test(s))return s;const m=s.match(/^(\d{1,2})[-/ ]([A-Za-z]{3})[-/ ](\d{4})$/);if(m){const d=new Date(`${m[2]} 1, ${m[3]}`);if(!Number.isNaN(d.getTime()))return `${m[3]}-${String(d.getMonth()+1).padStart(2,"0")}-${m[1].padStart(2,"0")}`;}return undefined;}
const metalMap:Record<string,BaseMetal>={aluminium:"ALUMINIUM",aluminum:"ALUMINIUM",copper:"COPPER",zinc:"ZINC",nickel:"NICKEL",lead:"LEAD",tin:"TIN"};
export function mapLmeRows(input:Record<string,unknown>[]):{rows:LmeObservation[];rejected:{row:number;reason:string}[]}{
 const rows:LmeObservation[]=[],rejected:{row:number;reason:string}[]=[];
 input.forEach((raw,i)=>{const rawMetal=norm(get(raw,"metal")).replace(/_/g,"");const metal=metalMap[rawMetal];const reportDate=date(get(raw,"reportDate"));const totalInventoryTonnes=num(get(raw,"totalInventoryTonnes"));const onWarrantTonnes=num(get(raw,"onWarrantTonnes"));const cancelledWarrantsTonnes=num(get(raw,"cancelledWarrantsTonnes"));const dailyChangeTonnes=num(get(raw,"dailyChangeTonnes"));const productionTonnes=num(get(raw,"productionTonnes"));const importsTonnes=num(get(raw,"importsTonnes"));const exportsTonnes=num(get(raw,"exportsTonnes"));
  if(!metal){rejected.push({row:i+2,reason:"Unsupported or missing metal"});return;}
  if(!reportDate){rejected.push({row:i+2,reason:"Invalid or missing report date"});return;}
  if(totalInventoryTonnes===undefined||totalInventoryTonnes<0){rejected.push({row:i+2,reason:"Total inventory must be a non-negative number"});return;}
  if([onWarrantTonnes,cancelledWarrantsTonnes,productionTonnes,importsTonnes,exportsTonnes].some(v=>v!==undefined&&v<0)){rejected.push({row:i+2,reason:"Inventory components and flow values cannot be negative"});return;}
  if(onWarrantTonnes!==undefined&&onWarrantTonnes>totalInventoryTonnes){rejected.push({row:i+2,reason:"On-warrant exceeds total inventory"});return;}
  if(cancelledWarrantsTonnes!==undefined&&cancelledWarrantsTonnes>totalInventoryTonnes){rejected.push({row:i+2,reason:"Cancelled warrants exceed total inventory"});return;}
  rows.push({metal,reportDate,totalInventoryTonnes,onWarrantTonnes,cancelledWarrantsTonnes,dailyChangeTonnes,productionTonnes,importsTonnes,exportsTonnes,warehouseRegion:String(get(raw,"warehouseRegion")??"").trim()||undefined});
 });return {rows,rejected};
}
