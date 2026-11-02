import type { BrokerRecommendation, CompanyResult, CompanyResultMetric, RecommendationEvaluation } from "./types";

function growth(current?: number, previous?: number): number | undefined {
  if (current === undefined || previous === undefined || previous === 0) return undefined;
  return (current / previous - 1) * 100;
}
function versusGuidance(actual?: number, guidance?: number): number | undefined {
  if (actual === undefined || guidance === undefined || guidance === 0) return undefined;
  return (actual / guidance - 1) * 100;
}

/** Reports return against a published entry only when an explicitly dated observed price is supplied.
 * A single observation cannot prove that a target or stop-loss was touched historically.
 */
export function evaluateRecommendation(row: BrokerRecommendation): RecommendationEvaluation {
  const observedReturnPct = row.observedPrice !== undefined && row.publishedEntry !== undefined && row.publishedEntry > 0
    ? (row.observedPrice / row.publishedEntry - 1) * 100 : undefined;
  const targetReturnPct = row.targetPrice !== undefined && row.publishedEntry !== undefined && row.publishedEntry > 0
    ? (row.targetPrice / row.publishedEntry - 1) * 100 : undefined;
  const stopLossReturnPct = row.publishedStopLoss !== undefined && row.publishedEntry !== undefined && row.publishedEntry > 0
    ? (row.publishedStopLoss / row.publishedEntry - 1) * 100 : undefined;
  return { ...row, targetReturnPct, stopLossReturnPct, observedReturnPct,
    evaluationStatus: observedReturnPct !== undefined ? "observed_price_only" : "not_evaluated" };
}

export function calculateCompanyResultMetrics(row: CompanyResult): CompanyResultMetric {
  return {
    ...row,
    revenueGrowthPct: growth(row.revenue, row.previousRevenue),
    ebitdaGrowthPct: growth(row.ebitda, row.previousEbitda),
    patGrowthPct: growth(row.pat, row.previousPat),
    epsGrowthPct: growth(row.eps, row.previousEps),
    revenueVsGuidancePct: versusGuidance(row.revenue, row.guidanceRevenue),
    ebitdaVsGuidancePct: versusGuidance(row.ebitda, row.guidanceEbitda),
    patVsGuidancePct: versusGuidance(row.pat, row.guidancePat)
  };
}
