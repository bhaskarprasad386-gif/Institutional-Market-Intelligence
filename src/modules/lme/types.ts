export type BaseMetal = "ALUMINIUM"|"COPPER"|"ZINC"|"NICKEL"|"LEAD"|"TIN";
export interface LmeObservation {
 metal:BaseMetal; reportDate:string; warehouseRegion?:string;
 totalInventoryTonnes:number; onWarrantTonnes?:number; cancelledWarrantsTonnes?:number;
 dailyChangeTonnes?:number; productionTonnes?:number; importsTonnes?:number; exportsTonnes?:number;
}
export interface LmeMetric extends LmeObservation {
 onWarrantPct?:number; cancelledWarrantPct?:number; dailyChangePct?:number;
 impliedWithdrawalsTonnes?:number; inventoryStatus:"BUILD"|"DRAW"|"FLAT"|"INSUFFICIENT_HISTORY";
}
