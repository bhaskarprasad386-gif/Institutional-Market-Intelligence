export type BrokerRating = "BUY" | "HOLD" | "SELL";
export interface BrokerRecommendation {
  broker: string;
  symbol: string;
  rating: BrokerRating;
  publishedDate: string;
  targetPrice?: number;
  publishedEntry?: number;
  publishedStopLoss?: number;
  sourceUrl?: string;
  sourceTitle?: string;
  observedPrice?: number;
  observedDate?: string;
}
export interface RecommendationEvaluation extends BrokerRecommendation {
  targetReturnPct?: number;
  stopLossReturnPct?: number;
  observedReturnPct?: number;
  targetHit?: boolean;
  stopLossHit?: boolean;
  evaluationStatus: "not_evaluated" | "observed_price_only";
}
export interface CompanyResult {
  symbol: string;
  companyName?: string;
  period: string;
  publishedDate: string;
  revenue?: number;
  ebitda?: number;
  pat?: number;
  eps?: number;
  operatingMarginPct?: number;
  netMarginPct?: number;
  debt?: number;
  operatingCashFlow?: number;
  freeCashFlow?: number;
  previousRevenue?: number;
  previousEbitda?: number;
  previousPat?: number;
  previousEps?: number;
  guidanceRevenue?: number;
  guidanceEbitda?: number;
  guidancePat?: number;
  guidanceText?: string;
  managementCommentary?: string;
  sourceUrl?: string;
  sourceTitle?: string;
}
export interface CompanyResultMetric extends CompanyResult {
  revenueGrowthPct?: number;
  ebitdaGrowthPct?: number;
  patGrowthPct?: number;
  epsGrowthPct?: number;
  revenueVsGuidancePct?: number;
  ebitdaVsGuidancePct?: number;
  patVsGuidancePct?: number;
}
