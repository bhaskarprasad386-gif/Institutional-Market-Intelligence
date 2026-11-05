import type {HistoricalRolloverContext,RolloverMetric} from "./types";
type Props={rows:RolloverMetric[];historical?:Map<string,HistoricalRolloverContext>;historyStatus?:string};
function historyLabel(status:HistoricalRolloverContext["rolloverPctStatus"]):string{return status==="INSUFFICIENT_HISTORY"?"Need 5 cycles":status;}
function buildLabel(value:RolloverMetric["nearBuildUp"]):string{return value?value.replaceAll("_"," "):"—";}
const key=(r:RolloverMetric)=>r.symbol+"|"+r.nearExpiry+"|"+r.nextExpiry;
function signed(value:number|undefined|null,digits=2,suffix=""):string{return value===undefined||value===null?"—":(value>0?"+":"")+value.toFixed(digits)+suffix;}
export default function RolloverAnalysis({rows,historical,historyStatus}:Props){
 if(!rows.length)return null;
 const highPct=rows.filter(r=>r.rolloverPctFlag==="HIGH").length,highCost=rows.filter(r=>r.rolloverCostFlag==="HIGH").length,combined=rows.filter(r=>r.rolloverPctFlag==="HIGH"&&r.rolloverCostFlag==="HIGH");
 const longBuild=rows.filter(r=>r.nearBuildUp==="LONG_BUILD_UP"||r.nextBuildUp==="LONG_BUILD_UP").length;
 const shortBuild=rows.filter(r=>r.nearBuildUp==="SHORT_BUILD_UP"||r.nextBuildUp==="SHORT_BUILD_UP").length;
 return <section className="rollover-analysis">
  <div className="rollover-heading"><div><p className="eyebrow">F&O ROLLOVER INTELLIGENCE</p><h3>Advanced Positional Rollover Intelligence</h3></div><span>{rows[0].tradeDate}</span></div>
  <div className="rollover-kpis"><article><span>High rollover %</span><strong>{highPct}</strong></article><article><span>High rollover cost</span><strong>{highCost}</strong></article><article><span>Both conditions</span><strong>{combined.length}</strong></article><article><span>Long / Short build-up</span><strong>{longBuild} / {shortBuild}</strong></article></div>
  <p className="muted">Historical archive: {historyStatus??"Loading…"} · Momentum uses only prior archived trading sessions; missing sessions remain unavailable.</p>
  <div className="table-wrap"><table><thead><tr><th>Symbol</th><th>Near → Next expiry</th><th>Rollover %</th><th>Extended rollover %</th><th>Far share %</th><th>Near OI Δ</th><th>Next OI Δ</th><th>Total OI Δ % · 3D / 5D</th><th>Next share momentum · 3D / 5D</th><th>Near build-up</th><th>Next build-up</th><th>Historical cycles</th><th>Historical rollover %</th><th>Cost points</th><th>Cost %</th><th>Cost / lot</th></tr></thead><tbody>
   {[...rows].sort((a,b)=>Number((b.rolloverPctFlag==="HIGH"&&b.rolloverCostFlag==="HIGH"))-Number((a.rolloverPctFlag==="HIGH"&&a.rolloverCostFlag==="HIGH"))||b.rolloverPct-a.rolloverPct).map((r,i)=>{const h=historical?.get(key(r));return <tr key={r.symbol+r.tradeDate+i}><td><strong>{r.symbol}</strong></td><td>{r.nearExpiry} → {r.nextExpiry}</td><td>{r.rolloverPct.toFixed(2)}%</td><td>{r.extendedRolloverPct===undefined?"—":r.extendedRolloverPct.toFixed(2)+"%"}</td><td>{r.farSharePct===undefined?"—":r.farSharePct.toFixed(2)+"%"}</td><td>{signed(r.nearOiChange,0)}</td><td>{signed(r.nextOiChange,0)}</td><td>{signed(r.totalOiMomentum3dPct)+ " / "+signed(r.totalOiMomentum5dPct)+"%"}</td><td>{signed(r.nextShareMomentum3d)+" / "+signed(r.nextShareMomentum5d)+" pp"}</td><td>{buildLabel(r.nearBuildUp)}</td><td>{buildLabel(r.nextBuildUp)}</td><td>{h?.sampleCount??"—"}</td><td>{h?.rolloverPctPercentile===undefined?historyLabel(h?.rolloverPctStatus??"INSUFFICIENT_HISTORY"):h.rolloverPctPercentile.toFixed(0)+"th · "+h.rolloverPctStatus}</td><td>{r.rolloverCostPoints.toFixed(2)}</td><td>{r.rolloverCostPct.toFixed(3)}%</td><td>{r.rolloverCostPerLot===undefined?"Lot size unavailable":r.rolloverCostPerLot.toFixed(2)}</td></tr>;})}
  </tbody></table></div>
  <p className="muted">Next rollover % = Next OI ÷ (Near + Next OI). Extended rollover % = (Next + Far OI) ÷ (Near + Next + Far OI). Daily build-up uses contract price change and contract OI change. Momentum is the change versus 3 or 5 archived trading sessions earlier. Build-up labels are descriptive, not proof of directional ownership. This is an EOD research screen, not a standalone buy/sell recommendation. Historical outcome accuracy is not yet measured.</p>
 </section>;
}
