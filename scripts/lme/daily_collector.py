#!/usr/bin/env python3
"""Daily, access-respecting LME raw-report collector."""
from __future__ import annotations
import hashlib, json, re, sys, urllib.error, urllib.request, zipfile, io
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

UA="InstitutionalMarketIntelligence/1.0 (official LME public report collector)"
MAX_BYTES=40*1024*1024
OUT=Path("lme-raw-output")
ALLOWED={"lme.com","www.lme.com"}
SOURCES=[
 {"id":"daily-stocks-breakdown","name":"Daily Stocks Breakdown","cadence":"daily T+2","url":"https://www.lme.com/Market-data/Reports-and-data/Warehouse-and-stocks-reports/Stock-breakdown-report","terms":("stock","breakdown","warehouse")},
 {"id":"daily-off-warrant","name":"Daily Off-Warrant Stocks","cadence":"daily T+3","url":"https://www.lme.com/market-data/reports-and-data/warehouse-and-stocks-reports/off-warrant-stock-reporting","terms":("off-warrant","off warrant","stock")},
 {"id":"warehouse-queue","name":"Warehouse & Queue","cadence":"monthly T+10","url":"https://www.lme.com/Market-data/Reports-and-data/Warehouse-and-stocks-reports/Warehouse-and-queue-data","terms":("warehouse company stocks and queue","warehouse","queue")},
 {"id":"prices-volume-oi","name":"Prices, Volumes & Open Interest","cadence":"daily / report-specific","url":"https://www.lme.com/market-data/reports-and-data","terms":("price","volume","open interest","monthly overview")},
 {"id":"cotr","name":"Commitments of Traders","cadence":"weekly T+2","url":"https://www.lme.com/market-data/reports-and-data","terms":("commitments of traders","cotr","trader positioning")},
]
EXTS=(".xlsx",".xls",".csv",".zip",".pdf")
class Links(HTMLParser):
 def __init__(self): super().__init__(); self.href=None; self.parts=[]; self.items=[]
 def handle_starttag(self,tag,attrs):
  if tag.lower()=="a": self.href=dict(attrs).get("href"); self.parts=[]
 def handle_data(self,data):
  if self.href is not None: self.parts.append(data)
 def handle_endtag(self,tag):
  if tag.lower()=="a" and self.href is not None:
   self.items.append((self.href," ".join(" ".join(self.parts).split()))); self.href=None; self.parts=[]
def request(url):
 req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"*/*"})
 try:
  with urllib.request.urlopen(req,timeout=45) as response:
   final=response.geturl()
   if urlparse(final).hostname not in ALLOWED: raise RuntimeError("Refusing redirect outside official LME host.")
   data=response.read(MAX_BYTES+1)
   if len(data)>MAX_BYTES: raise RuntimeError("Response exceeded 40 MB safety limit.")
   return data,response.headers.get("Content-Type",""),final
 except urllib.error.HTTPError as exc:
  if exc.code in (401,403): raise PermissionError("HTTP_"+str(exc.code)) from exc
  raise
def candidates(page,base,terms):
 parser=Links(); parser.feed(page.decode("utf-8",errors="replace")); found=[]
 for href,label in parser.items:
  url=urljoin(base,href); parsed=urlparse(url); searchable=(label+" "+parsed.path).lower()
  if parsed.hostname not in ALLOWED or not parsed.path.lower().endswith(EXTS): continue
  if any(term in searchable for term in terms): found.append((url,label or Path(parsed.path).name))
 return found[:1]
def main():
 OUT.mkdir(parents=True,exist_ok=True); folder=OUT/"files"; folder.mkdir(exist_ok=True)
 checked=datetime.now(timezone.utc).isoformat(); results=[]
 for source in SOURCES:
  row={"id":source["id"],"name":source["name"],"cadence":source["cadence"],"source_page":source["url"],"checked_at_utc":checked}
  try:
   page,_,page_url=request(source["url"]); links=candidates(page,page_url,source["terms"])
   if not links: row.update(status="PAGE_FETCHED_NO_REPORT_LINK",raw_file_fetched=False,note="Official page reachable; no matching downloadable file link found.")
   else:
    url,label=links[0]; raw,mime,final=request(url); suffix=Path(urlparse(final).path).suffix.lower()
    if suffix==".xlsx" and not zipfile.is_zipfile(io.BytesIO(raw)): raise RuntimeError("Downloaded XLSX failed container validation.")
    digest=hashlib.sha256(raw).hexdigest(); name=re.sub(r"[^A-Za-z0-9._-]+","-",Path(urlparse(final).path).name)[:120] or source["id"]+suffix
    dest=folder/(source["id"]+"-"+name); dest.write_bytes(raw)
    row.update(status="DOWNLOADED",report_label=label,download_url=final,raw_file_fetched=True,raw_file_name=str(dest.relative_to(OUT)),raw_file_size_bytes=len(raw),raw_file_sha256=digest,content_type=mime,note="Raw report downloaded and processed temporarily on the runner; this workflow retains only the non-sensitive manifest. No market values/signals are inferred by the collector.")
  except PermissionError as exc: row.update(status="ACCESS_REQUIRED",raw_file_fetched=False,http_status=str(exc),note="LME requires authorized session or licensed access; no access control bypassed.")
  except Exception as exc: row.update(status="FETCH_ERROR",raw_file_fetched=False,error=str(exc))
  results.append(row); print(json.dumps(row,ensure_ascii=False))
 downloaded=sum(1 for row in results if row["status"]=="DOWNLOADED")
 manifest={"source":"London Metal Exchange","checked_at_utc":checked,"collector_status":"DOWNLOADED" if downloaded else "NO_AUTHORIZED_FILES_DOWNLOADED","downloaded_count":downloaded,"sources":results,"important":"Workflow success means checks completed, not that every source supplied a file. Restricted data requires LME-authorized access."}
 (OUT/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8"); print(json.dumps(manifest,indent=2))
 return 0 if all(row["status"]!="FETCH_ERROR" for row in results) else 1
if __name__=="__main__":
 try: raise SystemExit(main())
 except Exception as exc: print("LME collector fatal error: "+str(exc),file=sys.stderr); raise SystemExit(1)
