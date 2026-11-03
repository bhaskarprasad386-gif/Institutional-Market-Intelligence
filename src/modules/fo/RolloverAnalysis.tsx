import type { RolloverMetric } from "./types";
function flagLabel(flag:RolloverMetric["rolloverPctFlag"]):string {
  return flag==="HIGH"?"HIGH":flag==="NORMAL"?"Normal":flag==="ROLL_CREDIT"?"Credit":"Need ≥5 symbols";
}
export default function RolloverAnalysis({rows}:{rows:RolloverMetric[]}) {
  if(!rows.length)return null;
  const highPct=rows.filter(row=>row.rolloverPctFlag==="HIGH").length;
  const highCost=rows.filter(row=>row.rolloverCostFlag==="HIGH").length;
  const combined=rows.filter(row=>row.rolloverPctFlag==="HIGH"&&row.rolloverCostFlag==="HIGH");
  return <section className="rollover-analysis">
    <div className="rollover-heading"><div><p className="eyebrow">F&O ROLLOVER INTELLIGENCE</p><h3>High Rollover % + High Rollover Cost</h3></div><span>{rows[0].tradeDate}</span></div>
    <div className="rollover-kpis"><article><span>High rollover %</span><strong>{highPct}</strong></article><article><span>High rollover cost</span><strong>{highCost}</strong></article><article><span>Both conditions</span><strong>{combined.length}</strong></article><article><span>Symbols compared</span><strong>{rows.length}</strong></article></div>
    <div className="table-wrap"><table><thead><tr><th>Symbol</th><th>Near → Next expiry</th><th>Rollover %</th><th>Rollover % status</th><th>Near / Next future</th><th>Cost points</th><th>Cost %</th><th>Cost / lot</th><th>Cost status</th></tr></thead><tbody>
      {[...rows].sort((a,b)=>Number((b.rolloverPctFlag==="HIGH"&&b.rolloverCostFlag==="HIGH"))-Number((a.rolloverPctFlag==="HIGH"&&a.rolloverCostFlag==="HIGH"))||b.rolloverPct-a.rolloverPct).map((row,i)=><tr key={row.symbol+row.tradeDate+i}><td><strong>{row.symbol}</strong></td><td>{row.nearExpiry} → {row.nextExpiry}</td><td>{row.rolloverPct.toFixed(2)}%</td><td><span className={row.rolloverPctFlag==="HIGH"?"rollover-high":"rollover-neutral"}>{flagLabel(row.rolloverPctFlag)}</span></td><td>{row.nearFuturesClose.toFixed(2)} / {row.nextFuturesClose.toFixed(2)}</td><td>{row.rolloverCostPoints.toFixed(2)}</td><td>{row.rolloverCostPct.toFixed(3)}%</td><td>{row.rolloverCostPerLot===undefined?"Lot size unavailable":row.rolloverCostPerLot.toFixed(2)}</td><td><span className={row.rolloverCostFlag==="HIGH"?"rollover-high":"rollover-neutral"}>{row.rolloverCostFlag==="ROLL_CREDIT"?"Credit":flagLabel(row.rolloverCostFlag)}</span></td></tr>)}
    </tbody></table></div>
    <p className="muted">Rollover % = next-expiry OI ÷ (near + next expiry OI) × 100. Rollover cost = next-expiry futures price − near-expiry futures price; cost % is relative to near futures price. Cost per lot is shown only when the source file supplies a consistent lot size. HIGH means top quartile versus same-date symbols, requiring at least five symbols; otherwise status remains unclassified. Positive cost is contango; negative cost is a rollover credit. These are screening metrics, not standalone buy/sell signals.</p>
  </section>;
}
