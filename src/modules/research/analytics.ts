import type { BrokerRecommendation, CompanyResult, CompanyResultMetric, RecommendationEvaluation } from "./types";

function growth(current?: number, previous?: number): number | undefined {
  if (current === undefined || previous === undefined || previous === 0) return undefined;
  return (current / previous - 1) * 100;
}
function versusGuidance(actual?: number, guidance?: number): number | undefined {
  if (actual === undefined || guidance === undefined || guidance === 0) return undefined;
  return (actual / guidance - 1) * 100;
}

/** Evaluates only explicitly supplied observations; no price history is inferred. */
export function evaluateRecommendation(row: BrokerRecommendation): RecommendationEvaluation {
  const observedReturnPct = row.observedPrice !== undefined && row.publishedEntry !== undefined && row.publishedEntry > 0
    ? (row.observedPrice / row.publishedEntry - 1) * 100 : undefined;
  const targetReturnPct = row.targetPrice !== undefined && row.publishedEntry !== undefined && row.publishedEntry > 0
    ? (row.targetPrice / row.publishedEntry - 1) * 100 : undefined;
  const stopLossReturnPct = row.publishedStopLoss !== undefined && row.publishedEntry !== undefined && row.publishedEntry > 0
    ? (row.publishedStopLoss / row.publishedEntry - 1) * 100 : undefined;
  const targetHit = row.observedPrice !== undefined && row.targetPrice !== undefined &&
    (row.rating === "SELL" ? row.observedPrice <= row.targetPrice : row.observedPrice >= row.targetPrice);
  const stopLossHit = row.observedPrice !== undefined && row.publishedStopLoss !== undefined &&
    (row.rating === "SELL" ? row.observedPrice >= row.publishedStopLoss : row.observedPrice <= row.publishedStopLoss);
  const evaluationStatus = targetHit ? "target_hit" : stopLossHit ? "stop_loss_hit" :
    observedReturnPct !== undefined ? "observed_price_only" : "not_evaluated";
  return { ...row, targetReturnPct, stopLossReturnPct, observedReturnPct, targetHit, stopLossHit, evaluationStatus };
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
