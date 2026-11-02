import type { HistoricalRecommendationEvaluation } from "./types";

export default function BrokerScorecard({evaluations}:{evaluations:HistoricalRecommendationEvaluation[]}) {
  if (!evaluations.length) return null;
  const groups = new Map<string,{broker:string;rating:string;target:number;stop:number;ambiguous:number;open:number;insufficient:number;missing:number}>();
  for (const item of evaluations) {
    const key = item.broker + "|" + item.rating;
    const group = groups.get(key) ?? {broker:item.broker,rating:item.rating,target:0,stop:0,ambiguous:0,open:0,insufficient:0,missing:0};
    if (item.evaluation === "target_hit") group.target++;
    else if (item.evaluation === "stop_loss_hit") group.stop++;
    else if (item.evaluation === "both_same_day_ambiguous") group.ambiguous++;
    else if (item.evaluation === "open_no_hit") group.open++;
    else if (item.evaluation === "insufficient_price_history") group.insufficient++;
    else group.missing++;
    groups.set(key,group);
  }
  return <section className="scorecard-block"><h3>Broker / rating performance summary</h3>
    <p className="muted">Target-hit share is calculated only among outcomes where target or stop-loss was first observed. Ambiguous, open/no-hit, insufficient-history and missing-level cases are excluded. This is historical price-path evidence, not realized returns or a statistically validated broker ranking.</p>
    <div className="table-wrap"><table><thead><tr><th>Broker</th><th>Rating</th><th>Target first</th><th>Stop-loss first</th><th>Ambiguous</th><th>Open / no hit</th><th>Insufficient history</th><th>Missing levels</th><th>Target-hit share*</th></tr></thead>
      <tbody>{[...groups.values()].map((g,i)=>{const resolved=g.target+g.stop;return <tr key={g.broker+g.rating+i}><td>{g.broker}</td><td>{g.rating}</td><td>{g.target}</td><td>{g.stop}</td><td>{g.ambiguous}</td><td>{g.open}</td><td>{g.insufficient}</td><td>{g.missing}</td><td>{resolved?(g.target/resolved*100).toFixed(1)+"%":"—"}</td></tr>;})}</tbody></table></div>
    <p className="muted">* Target-hit share = target-first / (target-first + stop-loss-first). Open/no-hit cases may simply reflect the end of imported price history.</p>
  </section>;
}
