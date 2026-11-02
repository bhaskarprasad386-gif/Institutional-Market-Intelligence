import type { HistoricalPriceBar, HistoricalRecommendationEvaluation, RecommendationEvaluation } from "./types";
type ForwardPoint = { day1?: number; day5?: number; day10?: number };
function forwardReturns(r:RecommendationEvaluation,bars:HistoricalPriceBar[]):ForwardPoint {
 const entry=r.publishedEntry;\n if(entry===undefined||entry<=0)return {};
 const ordered=bars.filter(b=>b.symbol.toUpperCase()===r.symbol.toUpperCase()&&b.tradeDate>r.publishedDate).sort((a,b)=>a.tradeDate.localeCompare(b.tradeDate));
 const direction=r.rating==="SELL"?-1:1;
 const at=(n:number)=>ordered.length>=n&&ordered[n-1].close>0?direction*(ordered[n-1].close/entry-1)*100:undefined;
 return {day1:at(1),day5:at(5),day10:at(10)};
}
type Group={broker:string;rating:string;target:number;stop:number;ambiguous:number;open:number;insufficient:number;missing:number;returns:{day1:number[];day5:number[];day10:number[]}};
export default function BrokerScorecard({evaluations,recommendations,priceBars}:{evaluations:HistoricalRecommendationEvaluation[];recommendations:RecommendationEvaluation[];priceBars:HistoricalPriceBar[]}) {
 const groups=new Map<string,Group>();
 const get=(broker:string,rating:string):Group=>{const key=broker+"|"+rating;let g=groups.get(key);if(!g){g={broker,rating,target:0,stop:0,ambiguous:0,open:0,insufficient:0,missing:0,returns:{day1:[],day5:[],day10:[]}};groups.set(key,g);}return g;};
 for(const item of evaluations){const g=get(item.broker,item.rating);if(item.evaluation==="target_hit")g.target++;else if(item.evaluation==="stop_loss_hit")g.stop++;else if(item.evaluation==="both_same_day_ambiguous")g.ambiguous++;else if(item.evaluation==="open_no_hit")g.open++;else if(item.evaluation==="insufficient_price_history")g.insufficient++;else g.missing++;}
 for(const r of recommendations){const g=get(r.broker,r.rating);const p=forwardReturns(r,priceBars);if(p.day1!==undefined)g.returns.day1.push(p.day1);if(p.day5!==undefined)g.returns.day5.push(p.day5);if(p.day10!==undefined)g.returns.day10.push(p.day10);}
 if(!groups.size)return null;
 const summary=(v:number[])=>v.length?`${(v.reduce((a,b)=>a+b,0)/v.length).toFixed(2)}% avg · ${(v.filter(x=>x>0).length/v.length*100).toFixed(1)}% positive · n=${v.length}`:"—";
 return <section className="scorecard-block"><h3>Broker / rating performance summary</h3>
 <p className="muted">Target-hit share uses only target-first and stop-loss-first outcomes. Forward returns use the explicitly published entry price and closing price after the 1st, 5th or 10th available trading bar. SELL returns are direction-adjusted. Missing entry prices or horizons are excluded, never treated as zero. These are historical price observations, not realized P&amp;L or a statistically validated broker ranking.</p>
 <div className="table-wrap"><table><thead><tr><th>Broker</th><th>Rating</th><th>Target first</th><th>Stop-loss first</th><th>Ambiguous</th><th>Open / no hit</th><th>Insufficient history</th><th>Missing levels</th><th>Target-hit share*</th><th>1D avg / positive</th><th>5D avg / positive</th><th>10D avg / positive</th></tr></thead><tbody>{[...groups.values()].map((g,i)=>{const n=g.target+g.stop;return <tr key={g.broker+g.rating+i}><td>{g.broker}</td><td>{g.rating}</td><td>{g.target}</td><td>{g.stop}</td><td>{g.ambiguous}</td><td>{g.open}</td><td>{g.insufficient}</td><td>{g.missing}</td><td>{n?(g.target/n*100).toFixed(1)+"%":"—"}</td><td>{summary(g.returns.day1)}</td><td>{summary(g.returns.day5)}</td><td>{summary(g.returns.day10)}</td></tr>;})}</tbody></table></div>
 <p className="muted">* Target-hit share = target-first / (target-first + stop-loss-first). Forward return sample sizes are shown separately for each horizon.</p></section>;
}