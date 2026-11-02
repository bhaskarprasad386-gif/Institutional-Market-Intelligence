import type { OptionObservation, OptionMetric, OptionExpirySummary, OptionType } from "./types";
const DAY_MS = 86400000;
const SQRT_2PI = Math.sqrt(2 * Math.PI);
function normalPdf(x:number):number{return Math.exp(-0.5*x*x)/SQRT_2PI;}
function normalCdf(x:number):number {
 const sign=x<0?-1:1,z=Math.abs(x)/Math.sqrt(2),t=1/(1+0.3275911*z);
 const erf=1-(((((1.061405429*t-1.453152027)*t)+1.421413741)*t-0.284496736)*t+0.254829592)*t*Math.exp(-z*z);
 return 0.5*(1+sign*erf);
}
function greeks(spot:number,strike:number,days:number,ivPct:number,type:OptionType,ratePct:number) {
 const time=days/365, sigma=ivPct/100, rate=ratePct/100;
 if(time<=0||sigma<=0)return {};
 const root=Math.sqrt(time),d1=(Math.log(spot/strike)+(rate+0.5*sigma*sigma)*time)/(sigma*root),d2=d1-sigma*root;
 const pdf=normalPdf(d1),discount=Math.exp(-rate*time);
 const delta=type==="CE"?normalCdf(d1):normalCdf(d1)-1;
 const gamma=pdf/(spot*sigma*root);
 const vega=spot*pdf*root/100;
 const thetaAnnual=type==="CE"?-(spot*pdf*sigma)/(2*root)-rate*strike*discount*normalCdf(d2):-(spot*pdf*sigma)/(2*root)+rate*strike*discount*normalCdf(-d2);
 return {delta,gamma,thetaPerDay:thetaAnnual/365,vegaPerVolPoint:vega};
}
export function calculateOptionMetrics(rows:OptionObservation[],ratePct=0):{metrics:OptionMetric[];summaries:OptionExpirySummary[]} {
 const metrics=rows.map(row=>{
  const daysToExpiry=Math.max(0,Math.ceil((Date.parse(row.expiryDate+"T00:00:00Z")-Date.parse(row.tradeDate+"T00:00:00Z"))/DAY_MS));
  const moneynessPct=(row.spotPrice-row.strike)/row.spotPrice*100;
  const intrinsicValue=row.ltp===undefined?undefined:Math.max(0,row.optionType==="CE"?row.spotPrice-row.strike:row.strike-row.spotPrice);
  const timeValue=row.ltp===undefined||intrinsicValue===undefined?undefined:Math.max(0,row.ltp-intrinsicValue);
  const oiChange=row.previousOpenInterest===undefined?undefined:row.openInterest-row.previousOpenInterest;
  const oiChangePct=row.previousOpenInterest!==undefined&&row.previousOpenInterest>0&&oiChange!==undefined?oiChange/row.previousOpenInterest*100:undefined;
  const volumeOiRatio=row.volume===undefined||row.openInterest<=0?undefined:row.volume/row.openInterest;
  const greek=row.ivPct!==undefined?greeks(row.spotPrice,row.strike,daysToExpiry,row.ivPct,row.optionType,ratePct):{};
  return {...row,daysToExpiry,moneynessPct,intrinsicValue,timeValue,oiChange,oiChangePct,volumeOiRatio,...greek,
   unusualActivity:(oiChangePct!==undefined&&Math.abs(oiChangePct)>=50)||(volumeOiRatio!==undefined&&volumeOiRatio>=2)};
 });
 const groups=new Map<string,OptionObservation[]>();
 for(const row of rows){const key=row.underlying+"|"+row.tradeDate+"|"+row.expiryDate;const group=groups.get(key)??[];group.push(row);groups.set(key,group);}
 const summaries:OptionExpirySummary[]=[];
 for(const [key,group] of groups){
  const [underlying,tradeDate,expiryDate]=key.split("|");
  const callOi=group.filter(x=>x.optionType==="CE").reduce((a,x)=>a+x.openInterest,0);
  const putOi=group.filter(x=>x.optionType==="PE").reduce((a,x)=>a+x.openInterest,0);
  const callVolume=group.filter(x=>x.optionType==="CE").reduce((a,x)=>a+(x.volume??0),0);
  const putVolume=group.filter(x=>x.optionType==="PE").reduce((a,x)=>a+(x.volume??0),0);
  const strikes=[...new Set(group.map(x=>x.strike))].sort((a,b)=>a-b);
  let maxPainStrike:number|undefined,maxPainPayout:number|undefined;
  for(const candidate of strikes){
   const payout=group.reduce((sum,x)=>sum+x.openInterest*(x.optionType==="CE"?Math.max(0,candidate-x.strike):Math.max(0,x.strike-candidate)),0);
   if(maxPainPayout===undefined||payout<maxPainPayout){maxPainPayout=payout;maxPainStrike=candidate;}
  }
  const spot=group[0]?.spotPrice;
  const near=group.filter(x=>Math.abs(x.strike-spot)<=Math.max(1,spot*0.01));
  const ceIv=near.filter(x=>x.optionType==="CE"&&x.ivPct!==undefined).sort((a,b)=>Math.abs(a.strike-spot)-Math.abs(b.strike-spot))[0]?.ivPct;
  const peIv=near.filter(x=>x.optionType==="PE"&&x.ivPct!==undefined).sort((a,b)=>Math.abs(a.strike-spot)-Math.abs(b.strike-spot))[0]?.ivPct;
  summaries.push({underlying,tradeDate,expiryDate,callOi,putOi,pcrOi:callOi>0?putOi/callOi:undefined,callVolume,putVolume,pcrVolume:callVolume>0?putVolume/callVolume:undefined,maxPainStrike,maxPainPayout,atmIvSkewPct:ceIv!==undefined&&peIv!==undefined?peIv-ceIv:undefined});
 }
 return {metrics,summaries};
}
