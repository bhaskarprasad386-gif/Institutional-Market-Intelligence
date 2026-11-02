import { useMemo, useState } from "react";

type Leg = { id:number; optionType:"CE"|"PE"; side:"BUY"|"SELL"; strike:string; premium:string; quantity:string };
type Point = { spot:number; pnl:number };
const blankLeg=(id:number):Leg=>({id,optionType:"CE",side:"BUY",strike:"",premium:"",quantity:"1"});
function payoffAt(spot:number,legs:Leg[]):number {
 return legs.reduce((total,leg)=>{
  const strike=Number(leg.strike),premium=Number(leg.premium),quantity=Number(leg.quantity);
  const intrinsic=leg.optionType==="CE"?Math.max(0,spot-strike):Math.max(0,strike-spot);
  const perUnit=leg.side==="BUY"?intrinsic-premium:premium-intrinsic;
  return total+perUnit*quantity;
 },0);
}
function money(value:number):string{return value.toLocaleString("en-IN",{maximumFractionDigits:2});}
export default function StrategyPayoff() {
 const [spotInput,setSpotInput]=useState("");
 const [rangeInput,setRangeInput]=useState("10");
 const [legs,setLegs]=useState<Leg[]>([blankLeg(1)]);
 const [nextId,setNextId]=useState(2);
 const spot=Number(spotInput),range=Number(rangeInput);
 const validSpot=Number.isFinite(spot)&&spot>0;
 const validRange=Number.isFinite(range)&&range>=1&&range<=50;
 const completeLegs=legs.filter(l=>Number(l.strike)>0&&Number(l.premium)>=0&&Number(l.quantity)>0&&[l.strike,l.premium,l.quantity].every(v=>v.trim()!=="")&&[l.strike,l.premium,l.quantity].every(v=>Number.isFinite(Number(v))));
 const incomplete=legs.length-completeLegs.length;
 const points=useMemo<Point[]>(()=>{
  if(!validSpot||!validRange||!completeLegs.length)return [];
  const low=spot*(1-range/100),high=spot*(1+range/100);
  return Array.from({length:81},(_,i)=>{const price=low+(high-low)*i/80;return {spot:price,pnl:payoffAt(price,completeLegs)};});
 },[spot,range,validSpot,validRange,completeLegs]);
 const chart=useMemo(()=>{
  if(points.length<2)return null;
  const width=760,height=320,left=76,right=20,top=20,bottom=48,plotW=width-left-right,plotH=height-top-bottom;
  const min=Math.min(0,...points.map(p=>p.pnl)),max=Math.max(0,...points.map(p=>p.pnl)),pad=Math.max(1,(max-min)*0.12);
  const yMin=min-pad,yMax=max+pad;
  const x=(v:number)=>left+(v-points[0].spot)/(points[points.length-1].spot-points[0].spot)*plotW;
  const y=(v:number)=>top+(yMax-v)/(yMax-yMin)*plotH;
  const path=points.map((p,i)=>`${i===0?"M":"L"} ${x(p.spot).toFixed(2)} ${y(p.pnl).toFixed(2)}`).join(" ");
  const breakevens:number[]=[];
  for(let i=1;i<points.length;i++){const a=points[i-1],b=points[i];if(a.pnl===0)breakevens.push(a.spot);else if((a.pnl<0&&b.pnl>0)||(a.pnl>0&&b.pnl<0)){const ratio=-a.pnl/(b.pnl-a.pnl);breakevens.push(a.spot+(b.spot-a.spot)*ratio);}}
  const uniqueBreakEvens=[...new Set(breakevens.map(v=>Math.round(v*100)/100))];
  const maxProfit=Math.max(...points.map(p=>p.pnl)),maxLoss=Math.min(...points.map(p=>p.pnl));
  return {width,height,left,right,top,bottom,plotW,plotH,x,y,path,yMin,yMax,uniqueBreakEvens,maxProfit,maxLoss,zeroY:y(0)};
 },[points]);
 function updateLeg(id:number,field:keyof Omit<Leg,"id">,value:string){setLegs(current=>current.map(l=>l.id===id?{...l,[field]:value}:l));}
 return <div className="strategy-payoff">
  <p className="eyebrow">OPTIONS STRATEGY WORKBENCH</p><h3>Expiry Payoff Calculator</h3>
  <p className="muted">Manually add CE/PE buy/sell legs. Chart shows combined expiry P&amp;L across the selected underlying-price range. This is a payoff calculator, not a trade recommendation.</p>
  <div className="payoff-controls">
   <label>Current underlying spot<input type="number" min="0.01" step="any" value={spotInput} onChange={e=>setSpotInput(e.target.value)} placeholder="e.g. 24500"/></label>
   <label>Scenario range ± %<input type="number" min="1" max="50" step="1" value={rangeInput} onChange={e=>setRangeInput(e.target.value)}/></label>
  </div>
  <div className="payoff-leg-list">
   {legs.map((leg,index)=><div className="payoff-leg" key={leg.id}>
    <strong>Leg {index+1}</strong>
    <label>Option<select value={leg.optionType} onChange={e=>updateLeg(leg.id,"optionType",e.target.value as Leg["optionType"])}><option value="CE">CE</option><option value="PE">PE</option></select></label>
    <label>Side<select value={leg.side} onChange={e=>updateLeg(leg.id,"side",e.target.value as Leg["side"])}><option value="BUY">BUY</option><option value="SELL">SELL</option></select></label>
    <label>Strike<input type="number" min="0.01" step="any" value={leg.strike} onChange={e=>updateLeg(leg.id,"strike",e.target.value)} placeholder="Strike"/></label>
    <label>Premium<input type="number" min="0" step="any" value={leg.premium} onChange={e=>updateLeg(leg.id,"premium",e.target.value)} placeholder="Premium"/></label>
    <label>Quantity<input type="number" min="1" step="1" value={leg.quantity} onChange={e=>updateLeg(leg.id,"quantity",e.target.value)} placeholder="Units"/></label>
    <button type="button" className="payoff-remove" disabled={legs.length===1} onClick={()=>setLegs(current=>current.filter(l=>l.id!==leg.id))}>Remove</button>
   </div>)}
  </div>
  <button type="button" onClick={()=>{setLegs(current=>[...current,blankLeg(nextId)]);setNextId(id=>id+1);}}>+ Add option leg</button>
  {incomplete>0&&<p className="muted">{incomplete} incomplete leg(s) ignored until strike, premium and quantity are entered.</p>}
  {chart&&<><div className="payoff-summary">
   <div><span>Max profit in range</span><strong>₹{money(chart.maxProfit)}</strong></div>
   <div><span>Max loss in range</span><strong>₹{money(chart.maxLoss)}</strong></div>
   <div><span>Break-even(s) in range</span><strong>{chart.uniqueBreakEvens.length?chart.uniqueBreakEvens.map(money).join(", "):"None"}</strong></div>
  </div>
  <div className="payoff-chart"><svg viewBox={`0 0 ${chart.width} ${chart.height}`} role="img" aria-label="Combined option strategy expiry payoff chart">
   {[0,1,2,3,4].map(i=>{const value=chart.yMin+(chart.yMax-chart.yMin)*i/4,yy=chart.y(value);return <g key={i}><line x1={chart.left} x2={chart.width-chart.right} y1={yy} y2={yy} stroke="#40516a" strokeDasharray="4 4"/><text x={chart.left-10} y={yy+4} fill="#c2cfdf" fontSize="11" textAnchor="end">{money(value)}</text></g>;})}
   <line x1={chart.left} x2={chart.width-chart.right} y1={chart.zeroY} y2={chart.zeroY} stroke="#f2c46d" strokeWidth="2"/>
   <line x1={chart.left} x2={chart.left} y1={chart.top} y2={chart.height-chart.bottom} stroke="#8fa3ba"/>
   <path d={chart.path} fill="none" stroke="#70b7ff" strokeWidth="3" strokeLinejoin="round" strokeLinecap="round"/>
   {[points[0].spot,spot,points[points.length-1].spot].map((v,i)=><text key={i} x={chart.x(v)} y={chart.height-16} fill="#d2deec" fontSize="11" textAnchor="middle">{money(v)}</text>)}
   <text x={chart.width/2} y={chart.height-2} fill="#c2cfdf" fontSize="10" textAnchor="middle">Underlying price at expiry</text>
  </svg></div>
  </>}
  {validSpot&&validRange&&completeLegs.length===0&&<p className="muted">At least one complete option leg is required to calculate payoff.</p>}
  {!validSpot&&<p className="muted">Enter a valid underlying spot price to view payoff scenarios.</p>}
  <p className="muted">P&amp;L = intrinsic value minus premium for BUY, premium minus intrinsic value for SELL, multiplied by entered quantity. Max profit/loss and break-even are calculated only inside the displayed price range; brokerage, taxes, slippage, margin and early exercise are excluded.</p>
 </div>;
}
