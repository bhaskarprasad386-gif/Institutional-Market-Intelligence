#!/usr/bin/env python3
"""Fetch the latest three NSE shareholding-pattern XBRL filings for NIFTY 50."""
import datetime as dt
import http.cookiejar
import json
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONSTITUENTS = ROOT / "public/data/nifty50-constituents.json"
OUT = ROOT / "public/data/nifty50-shareholding-latest.json"
BASE = "https://www.nseindia.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
    "Accept": "application/json,text/html,application/xml,*/*",
    "Referer": "https://www.nseindia.com/companies-listing/corporate-filings-shareholding-pattern",
}
MEMBERS = {
    "promoter": "ShareholdingOfPromoterAndPromoterGroupMember",
    "public": "PublicShareholdingMember",
    "fii": "InstitutionsForeignMember",
    "dii": "InstitutionsDomesticMember",
}
PCT_TAG = "ShareholdingAsAPercentageOfTotalNumberOfShares"


def local_name(tag):
    return tag.rsplit("}", 1)[-1].split(":")[-1]


def fetch(url, opener):
    req = urllib.request.Request(url, headers=HEADERS)
    with opener.open(req, timeout=35) as response:
        return response.read()


def parse_date(value):
    for fmt in ("%d-%b-%Y", "%d-%B-%Y", "%d-%b-%y"):
        try:
            return dt.datetime.strptime(str(value).strip(), fmt).date().isoformat()
        except ValueError:
            pass
    return None


def parse_xbrl(payload):
    root = ET.fromstring(payload)
    contexts = {}
    for node in root.iter():
        if local_name(node.tag) != "context":
            continue
        members = set()
        for child in node.iter():
            name = local_name(child.tag)
            if name.endswith("Member"):
                members.add(name)
        contexts[node.attrib.get("id", "")] = members
    facts = {}
    for node in root.iter():
        if local_name(node.tag) != PCT_TAG:
            continue
        context = contexts.get(node.attrib.get("contextRef", ""), set())
        if len(context) > 2:
            continue
        try:
            value = float((node.text or "").strip())
        except ValueError:
            continue
        for category, member in MEMBERS.items():
            if member in context and category not in facts:
                facts[category] = value
                break
    promoter, public = facts.get("promoter"), facts.get("public")
    reference = (promoter or 0) + (public or 0)
    scale = 0.01 if reference > 1000 else (100.0 if 0 < reference < 2 else 1.0)
    return {key: round(value * scale, 4) for key, value in facts.items()}


def main():
    if not CONSTITUENTS.exists():
        raise SystemExit("NIFTY 50 constituent cache missing; build EOD snapshot first.")
    stocks = json.loads(CONSTITUENTS.read_text()).get("stocks", [])
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    fetch(BASE + "/", opener)
    output = {}
    failures = []
    for stock in stocks:
        symbol = stock["symbol"]
        try:
            query = urllib.parse.urlencode({"index": "equities", "symbol": symbol})
            payload = json.loads(fetch(BASE + "/api/corporate-share-holdings-master?" + query, opener))
            filings = payload if isinstance(payload, list) else payload.get("data", [])
            filings = sorted(
                [f for f in filings if f.get("xbrl") and parse_date(f.get("date"))],
                key=lambda f: parse_date(f.get("date")) or "", reverse=True
            )[:3]
            quarters = []
            for filing in filings:
                url = filing["xbrl"]
                if url.startswith("/"):
                    url = "https://nsearchives.nseindia.com" + url
                elif not url.startswith("http"):
                    url = "https://nsearchives.nseindia.com/corporate/xbrl/" + url
                parsed = parse_xbrl(fetch(url, opener))
                if parsed:
                    quarters.append({
                        "quarter": parse_date(filing.get("date")),
                        "value": parsed.get("fii"),
                        "unit": "%",
                        "promoterPct": parsed.get("promoter"),
                        "diiPct": parsed.get("dii"),
                        "source": url,
                    })
            output[symbol] = {
                "fiiPosition": [{"quarter": q["quarter"], "value": q["value"], "unit": "%"} for q in quarters if q.get("value") is not None],
                "diiPosition": [{"quarter": q["quarter"], "value": q["diiPct"], "unit": "%"} for q in quarters if q.get("diiPct") is not None],
                "promoterHolding": [{"quarter": q["quarter"], "value": q["promoterPct"], "unit": "%"} for q in quarters if q.get("promoterPct") is not None],
                "source": "NSE Shareholding Pattern XBRL",
                "latestFilingDate": quarters[0]["quarter"] if quarters else None,
            }
        except Exception as exc:
            failures.append({"symbol": symbol, "error": str(exc)[:240]})
        time.sleep(0.25)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "generatedAt": dt.datetime.now(dt.timezone.utc).isoformat(),
        "source": "NSE Shareholding Pattern XBRL",
        "symbolsProcessed": len(stocks),
        "symbolsWithFilings": sum(bool(v["fiiPosition"] or v["diiPosition"]) for v in output.values()),
        "rows": output,
        "failures": failures,
    }, separators=(",", ":")), encoding="utf-8")
    print(f"NIFTY 50 shareholding: {len(output)} symbols, {len(failures)} failures")


if __name__ == "__main__":
    main()
