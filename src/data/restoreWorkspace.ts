import { calculateFoMetrics, calculateRolloverFromRows } from "../modules/fo/analytics";
import { calculateSectorMetrics, calculateInstitutionalFlow, validateDeliveryObservation } from "../modules/flows/analytics";
import { evaluateRecommendation, calculateCompanyResultMetrics, evaluateRecommendationPath } from "../modules/research/analytics";
import { calculateOptionMetrics } from "../modules/options/analytics";
import { calculateLmeMetrics } from "../modules/lme/analytics";
import type { FuturesObservation } from "../modules/fo/types";
import type { SectorObservation, DeliveryObservation, InstitutionalFlowObservation } from "../modules/flows/types";
import type { BrokerRecommendation, CompanyResult, HistoricalPriceBar } from "../modules/research/types";
import type { OptionObservation } from "../modules/options/types";
import type { LmeObservation } from "../modules/lme/types";

type Row = Record<string, unknown>;
const has = (row: Row, ...keys: string[]) => keys.every(key => key in row);
const str = (row: Row, key: string) => typeof row[key] === "string";
const num = (row: Row, key: string) => typeof row[key] === "number" && Number.isFinite(row[key]);

export function restoreWorkspace(rows: Row[]) {
  const futures = rows.filter(row => has(row,"symbol","tradeDate","expiryDate","futuresClose","spotClose","openInterest") && str(row,"symbol") && num(row,"futuresClose")) as unknown as FuturesObservation[];
  const sectors = rows.filter(row => has(row,"symbol","sector","tradeDate","close","previousClose") && str(row,"sector")) as unknown as SectorObservation[];
  const deliveries = rows.filter(row => has(row,"symbol","tradeDate","close","volume","deliveryQuantity","deliveryPct") && num(row,"deliveryQuantity")) as unknown as DeliveryObservation[];
  const flows = rows.filter(row => has(row,"tradeDate","fiiNet","diiNet","unit") && num(row,"fiiNet")) as unknown as InstitutionalFlowObservation[];
  const brokerRows = rows.filter(row => has(row,"broker","symbol","rating","publishedDate") && str(row,"broker")) as unknown as BrokerRecommendation[];
  const companyRows = rows.filter(row => has(row,"symbol","period","publishedDate") && str(row,"period")) as unknown as CompanyResult[];
  const priceBars = rows.filter(row => has(row,"symbol","tradeDate","open","high","low","close") && num(row,"high") && num(row,"low")) as unknown as HistoricalPriceBar[];
  const optionRows = rows.filter(row => has(row,"underlying","tradeDate","expiryDate","strike","optionType","spotPrice","openInterest") && num(row,"strike")) as unknown as OptionObservation[];
  const lmeRows = rows.filter(row => has(row,"metal","reportDate","totalInventoryTonnes") && num(row,"totalInventoryTonnes")) as unknown as LmeObservation[];

  const latestDate = futures.reduce((latest,row) => row.tradeDate > latest ? row.tradeDate : latest, "");
  const latestFutures = latestDate ? futures.filter(row => row.tradeDate === latestDate) : [];
  const latestOptionDate = optionRows.reduce((latest,row) => row.tradeDate > latest ? row.tradeDate : latest, "");
  const latestOptions = latestOptionDate ? optionRows.filter(row => row.tradeDate === latestOptionDate) : [];
  const calculatedOptions = calculateOptionMetrics(latestOptions,0,optionRows);

  const recommendations = brokerRows.map(evaluateRecommendation);
  const historicalEvaluations = recommendations.map(row => evaluateRecommendationPath(row,priceBars));
  return {
    futures: latestFutures.map(calculateFoMetrics),
    rollovers: calculateRolloverFromRows(latestFutures),
    sectors: calculateSectorMetrics(sectors),
    deliveries: deliveries.map(row => validateDeliveryObservation(row)),
    flows: flows.map(calculateInstitutionalFlow),
    recommendations,
    companyResults: companyRows.map(calculateCompanyResultMetrics),
    historicalEvaluations,
    optionHistoryRows: optionRows,
    optionMetrics: calculatedOptions.metrics,
    optionSummaries: calculatedOptions.summaries,
    lmeMetrics: calculateLmeMetrics(lmeRows),
    counts: { futures:futures.length, sectors:sectors.length, deliveries:deliveries.length, flows:flows.length,
      recommendations:brokerRows.length, companyResults:companyRows.length, priceBars:priceBars.length,
      optionRows:optionRows.length, lmeRows:lmeRows.length }
  };
}
