import re
import time
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
from flask import Flask, jsonify, request, send_from_directory
import analysis as an
import ml
import nlp
import scraper as sc

app = Flask(__name__)
CACHE, RES = {}, {}


def ok(f, default):
    try:
        return f()
    except Exception:
        return default


def resolve(q):
    if q.lower() not in RES:
        h = sc.resolve(q)
        RES[q.lower()] = (h["symbol"], h.get("longname") or h.get("shortname") or q) if h else None
    return RES[q.lower()]


def screener_cached(sym):  # profile + report jobs both need it; scrape once
    key = ("scr", sym)
    if key not in CACHE or time.time() - CACHE[key][0] > 900:
        CACHE[key] = (time.time(), ok(lambda: sc.screener(sym.split(".")[0]), {}))
    return CACHE[key][1]


def read_report(docs):
    low = lambda d: d["title"].lower()
    for d in ([x for x in docs if "transcript" in low(x)] + [x for x in docs if "financial year" in low(x)])[:3]:
        text = ok(lambda: sc.pdf_text(d["url"]), "")
        if len(text) > 2000:
            return {"source": d, **an.report_insights(text)}


def job_ml(sym, name):
    meta, rows = sc.prices(sym, "5y")
    return {"name": name, "symbol": sym, "currency": meta.get("currency", ""), "last": rows[-1]["close"],
            "prev": rows[-2]["close"], **ml.run(rows)}


def job_news(sym, name):
    return nlp.analyze_news(sc.news_full(name))


def job_profile(sym, name):
    with ThreadPoolExecutor(3) as ex:
        px, fin, wiki = ex.submit(sc.prices, sym, "1y"), ex.submit(screener_cached, sym), ex.submit(sc.wiki_profile, name)
        meta, rows = px.result()
        fin, wiki = ok(fin.result, {}), ok(wiki.result, {})
    return {"name": name, "symbol": sym, "currency": meta.get("currency", ""), "prices": rows, "tech": an.technicals(rows),
            "ratios": fin.get("ratios", {}), "quarters": fin.get("quarters", {}), "sector": fin.get("sector", []),
            "about": fin.get("about", ""), "holders": fin.get("holders", {}), "holders_period": fin.get("holders_period", ""),
            "pros": fin.get("pros", []), "cons": fin.get("cons", []), "wiki": wiki, "docs": fin.get("docs", [])}


def job_report(sym, name):  # downloads and parses PDFs, so it runs on its own and never blocks the overview
    fin = screener_cached(sym)
    return {"report": read_report(fin.get("docs", []))}


JOBS, TTL = {"ml": job_ml, "news": job_news, "profile": job_profile, "report": job_report}, 900


@app.get("/")
def index():
    return send_from_directory("templates", "index.html", max_age=0)


@app.get("/api/indices")
def indices():
    if "idx" not in CACHE or time.time() - CACHE["idx"][0] > 60:
        CACHE["idx"] = (time.time(), sc.indices())
    return jsonify(CACHE["idx"][1])


# range -> (Yahoo range, interval, cache seconds). Coarser bars for long ranges keep payloads small and charts fast.
RANGES = {"1d": ("1d", "1m", 60), "5d": ("5d", "15m", 300), "1mo": ("1mo", "60m", 300), "6mo": ("6mo", "1d", 900),
          "ytd": ("ytd", "1d", 900), "1y": ("1y", "1d", 900), "5y": ("5y", "1wk", 3600), "max": ("max", "1mo", 3600)}
INTRADAY = {"1d", "5d", "1mo"}


@app.post("/api/resolve")
def resolve_api():
    q = (request.json or {}).get("query", "").strip()
    if not q:
        return jsonify(error="Type a company name or ticker."), 400
    try:
        r = resolve(q)
    except Exception:
        return jsonify(error="Search failed. Check your connection."), 502
    return (jsonify(symbol=r[0], name=r[1]) if r else (jsonify(error=f"No listed company found for '{q}'."), 404))


def chart_payload(sym, rg):
    yr, iv, _ = RANGES[rg]
    meta, rows = sc.prices(sym, yr, iv)
    if not rows:
        raise ValueError("empty")
    out, seen = [], set()
    for r in rows:
        k = r["t"] if rg in INTRADAY else datetime.fromtimestamp(r["t"], timezone.utc).strftime("%Y-%m-%d")
        if k in seen:  # Yahoo can repeat the current bar on weekly/monthly series; the chart needs unique times
            out[-1] = (k, r)
            continue
        seen.add(k)
        out.append((k, r))
    reg = (meta.get("currentTradingPeriod") or {}).get("regular") or {}
    rd = lambda v: round(v, 4) if v is not None else None
    d = {"t": [k for k, _ in out], "c": [rd(r["close"]) for _, r in out], "v": [r["volume"] or 0 for _, r in out],
         "meta": {"currency": meta.get("currency", ""), "tz": meta.get("exchangeTimezoneName"), "exchange": meta.get("fullExchangeName") or meta.get("exchangeName"),
                  "last": meta.get("regularMarketPrice"), "time": meta.get("regularMarketTime"), "prev": meta.get("chartPreviousClose"),
                  "open_at": reg.get("start"), "close_at": reg.get("end"), "hi52": meta.get("fiftyTwoWeekHigh"), "lo52": meta.get("fiftyTwoWeekLow")}}
    if rg == "1d":  # day stats for the quote panel
        o = [r for _, r in out]
        d["quote"] = {"open": rd(o[0]["open"] or o[0]["close"]), "high": rd(max(r["high"] or r["close"] for r in o)),
                      "low": rd(min(r["low"] or r["close"] for r in o)), "volume": sum(r["volume"] or 0 for r in o)}
    return d


@app.post("/api/chart")
def chart():
    j = request.json or {}
    sym, rg = str(j.get("symbol", "")), j.get("range")
    if rg not in RANGES or not re.fullmatch(r"[\w.^&-]{1,20}", sym):
        return jsonify(error="Bad chart request."), 400
    key = ("chart", sym, rg)
    if key not in CACHE or time.time() - CACHE[key][0] > RANGES[rg][2]:
        try:
            CACHE[key] = (time.time(), chart_payload(sym, rg))
        except Exception:
            return jsonify(error="Could not load chart data."), 502
    return jsonify(CACHE[key][1])


@app.post("/api/<kind>")
def api(kind):
    q = (request.json or {}).get("query", "").strip()
    if kind not in JOBS or not q:
        return jsonify(error="Type a company name or ticker."), 400
    try:
        r = resolve(q)
    except Exception:
        return jsonify(error="Search failed. Check your connection."), 502
    if not r:
        return jsonify(error=f"No listed company found for '{q}'."), 404
    key = (kind, r[0])
    if key not in CACHE or time.time() - CACHE[key][0] > TTL:
        try:
            CACHE[key] = (time.time(), JOBS[kind](*r))
        except Exception as e:
            return jsonify(error=f"{kind} analysis failed: {e}"), 500
    return jsonify(CACHE[key][1])


if __name__ == "__main__":
    app.run(debug=False, threaded=True)
