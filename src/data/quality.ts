import type { DataProvenance, DataStatus } from "../core/domain";
export function assessDataStatus(p:Pick<DataProvenance,"marketDate"|"sourceName"|"retrievedAt">,expectedMarketDate:string):DataStatus { if(!p.sourceName||!p.marketDate||!p.retrievedAt)return "unverified"; if(p.marketDate!==expectedMarketDate)return "stale"; return "verified"; }
