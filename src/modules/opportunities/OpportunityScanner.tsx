import {useMemo,useState} from "react";
import type {FoMetrics} from "../fo/types";
import type {OptionMetric} from "../options/types";
import type {RecommendationEvaluation,CompanyResultMetric} from "../research/types";
import type {InstitutionalFlowMetric} from "../flows/types";
type Props={futures:FoMetrics[];options:OptionMetric[];recommendations:RecommendationEvaluation[];results:CompanyResultMetric[];flows:InstitutionalFlowMetric[]};
type Signal={symbol:string;score:number;coverage:number;reasons:string[];risk:string};
const clamp=(v:number)=>Math.max(0,Math.min(100,v));
function add(map:Map<string,{points:number;coverage:number;reasons:string[]}>,symbol:string,points:number,reason:string){const key=symbol.trim().toUpperCase();if(!key)return;const v=map.get(key)??{points:0,coverage:0,reasons:[]};v.points+=points;v.coverage++;v.reasons.push(reason);map.set(key,v);}
export default function OpportunityScanner({futures,options,recommendations,results,flows}:Props){
 const [filter,setFilter]=useState("ALL");
 const rows=useMemo(()=>{
  const map=new Map<string,{points:number;coverage:number;reasons:string[]}>();
  for(const f of futures){if(f.priceChangePct===undefined||f.oiChangePct===undefined)continue;const p=f.priceChangePct>0&&f.oiChangePct>0?14:f.priceChangePct<0&&f.oiChangePct>0?-14:f.priceChangePct>0&&f.oiChangePct<0?6:f.priceChangePct<0&&f.oiChangePct<0?-6:0;if(p)add(map,f.symbol,p,`F&O ${p>0?"positive":"negative"} price/OI build-up`);}
  for(const o of options){if(o.priceOiSignal==="INSUFFICIENT_DATA"||o.priceOiSignal==="MIXED")continue;const bullish=(o.optionType==="CE"&&["LONG_BUILD_UP","SHORT_COVERING"].includes(o.priceOiSignal))||(o.optionType==="PE"&&["SHORT_BUILD_UP","LONG_UNWINDING"].includes(o.priceOiSignal));const pts=bullish?7:-7;add(map,o.underlying,pts,`${o.optionType} ${o.priceOiSignal.toLowerCase().replaceAll("_"," ")}`);}
  for(const r of recommendations){const pts=r.rating==="BUY"?12:r.rating==="SELL"?-12:0;if(pts)add(map,r.symbol,pts,`Broker research: ${r.rating}`);}
  for(const r of results){const growth=[r.revenueGrowthPct,r.ebitdaGrowthPct,r.patGrowthPct].filter((v):v is number=>v!==undefined);if(!growth.length)continue;const avg=growth.reduce((a,b)=>a+b,0)/growth.length;const pts=Math.max(-12,Math.min(12,avg/5));if(Math.abs(pts)>=1)add(map,r.symbol,pts,`Financial growth average ${avg.toFixed(1)}%`);}
  return [...map.entries()].map(([symbol,v]):Signal=>({symbol,score:clamp(50+v.points),coverage:v.coverage,reasons:v.reasons,risk:v.coverage===1?"LOW DATA COVERAGE":v.coverage===2?"PARTIAL COVERAGE":"MULTI-SOURCE COVERAGE"})).sort((a,b)=>b.score-a.score);
 },[futures,options,recommendations,results]);
 const macro=flows.length?flows.slice().sort((a,b)=>b.tradeDate.localeCompare(a.tradeDate))[0]:undefined;
 const filtered=rows.filter(r=>filter==="ALL"||(filter==="BULLISH"&&r.score>=60)||(filter==="BEARISH"&&r.score<=40)||(filter==="NEUTRAL"&&r.score>40&&r.score<60));
 return <section className="panel opportunity-panel"><p className="eyebrow">BATCH 8 · CROSS-MODULE ANALYTICS</p><h2>Combined Opportunity Scanner</h2>
 <p className="muted">A transparent research ranking from currently loaded imports. It is not a live scanner, investment advice, or an execution signal. Missing inputs are not treated as neutral evidence.</p>
 {macro&&<div className="notice">Latest institutional flow context · {macro.tradeDate} · FII {macro.fiiNet.toLocaleString()} / DII {macro.diiNet.toLocaleString()} {macro.unit} · Combined {macro.combinedNet.toLocaleString()} {macro.unit}. Market-wide context only; not assigned to individual stocks.</div>}
 <div className="opportunity-toolbar"><div><strong>{rows.length} symbols scored</strong><span className="muted"> · {futures.length} F&amp;O · {options.length} option contracts · {recommendations.length} broker reports · {results.length} results</span></div><label>View<select value={filter} onChange={e=>setFilter(e.target.value)}><option value="ALL">All</option><option value="BULLISH">Bullish ≥60</option><option value="NEUTRAL">Neutral 41–59</option><option value="BEARISH">Bearish ≤40</option></select></label></div>
 {filtered.length?<div className="table-wrap"><table><thead><tr><th>Symbol</th><th>Research score / 100</th><th>Coverage</th><th>Evidence / reasons</th><th>Confidence note</th></tr></thead><tbody>{filtered.map(r=><tr key={r.symbol}><td><strong>{r.symbol}</strong></td><td><div className="score-cell"><strong>{r.score.toFixed(0)}</strong><div className="score-track"><span style={{width:`${r.score}%`}}/></div><small>{r.score>=60?"Bullish bias":r.score<=40?"Bearish bias":"Neutral / mixed"}</small></div></td><td>{r.coverage} signals</td><td>{r.reasons.map((x,i)=><div key={i}>• {x}</div>)}</td><td>{r.risk}</td></tr>)}</tbody></table></div>:<p className="muted">इस filter के लिए पर्याप्त loaded evidence नहीं है। पहले संबंधित modules में source-attributed CSV/Excel imports करें।</p>}
 <p className="muted">Score starts at 50 and adds capped evidence contributions: F&amp;O price/OI ±14, option contract ±7, broker BUY/SELL ±12, financial growth ±12. Option CE/PE signals are direction-adjusted. Sector and delivery data are not assigned to a stock without a verified constituent mapping. No backtest, probability, or future return is implied. Imported data remains unverified.</p>
 </section>;
}
