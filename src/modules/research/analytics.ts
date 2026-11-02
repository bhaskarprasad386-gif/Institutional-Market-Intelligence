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

import type { HistoricalPriceBar, HistoricalRecommendationEvaluation } from "./types";

/** Uses daily OHLC after publication. If target and stop are both crossed in one bar,
 * ordering is unknowable from daily OHLC, so it is explicitly marked ambiguous.
 */
export function evaluateRecommendationPath(
  recommendation: BrokerRecommendation,
  bars: HistoricalPriceBar[]
): HistoricalRecommendationEvaluation {
  const ordered = bars.filter(bar => bar.symbol.toUpperCase() === recommendation.symbol.toUpperCase() &&
    bar.tradeDate > recommendation.publishedDate)
    .sort((left, right) => left.tradeDate.localeCompare(right.tradeDate));
  const base = { broker: recommendation.broker, symbol: recommendation.symbol, rating: recommendation.rating,
    publishedDate: recommendation.publishedDate, barsChecked: ordered.length, entryPrice: recommendation.publishedEntry };
  if (recommendation.publishedEntry === undefined || recommendation.targetPrice === undefined && recommendation.publishedStopLoss === undefined)
    return { ...base, evaluation: "missing_entry_or_levels" };
  if (!ordered.length) return { ...base, evaluation: "insufficient_price_history" };
  for (const bar of ordered) {
    const targetTouched = recommendation.targetPrice !== undefined &&
      (recommendation.rating === "SELL" ? bar.low <= recommendation.targetPrice : bar.high >= recommendation.targetPrice);
    const stopTouched = recommendation.publishedStopLoss !== undefined &&
      (recommendation.rating === "SELL" ? bar.high >= recommendation.publishedStopLoss : bar.low <= recommendation.publishedStopLoss);
    if (targetTouched && stopTouched) return { ...base, evaluation: "both_same_day_ambiguous", firstEventDate: bar.tradeDate };
    if (targetTouched) return { ...base, evaluation: "target_hit", firstEventDate: bar.tradeDate };
    if (stopTouched) return { ...base, evaluation: "stop_loss_hit", firstEventDate: bar.tradeDate };
  }
  return { ...base, evaluation: "open_no_hit" };
}
