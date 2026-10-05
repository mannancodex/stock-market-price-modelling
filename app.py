import time
from concurrent.futures import ThreadPoolExecutor
from flask import Flask, jsonify, render_template, request
import scraper as sc
import analysis as an

app = Flask(__name__)
CACHE, TTL = {}, 600


def ok(f, default):
    try:
        return f()
    except Exception:
        return default


def read_report(docs):
    """Read the latest concall transcript or annual report and analyse its text."""
    low = lambda d: d["title"].lower()
    cands = [d for d in docs if "transcript" in low(d)] + [d for d in docs if "financial year" in low(d)]
    for d in cands[:3]:
        text = ok(lambda: sc.pdf_text(d["url"]), "")
        if len(text) > 2000:
            return {"source": d, **an.report_insights(text)}
    return None


@app.get("/")
def index():
    return render_template("index.html")


@app.post("/api/analyze")
def analyze():
    q = (request.json or {}).get("query", "").strip()
    if not q:
        return jsonify(error="Type a company name or ticker."), 400
    if q in CACHE and time.time() - CACHE[q][0] < TTL:
        return jsonify(CACHE[q][1])
    try:
        hit = sc.resolve(q)
    except Exception:
        return jsonify(error="Search failed. Check your connection and try again."), 502
    if not hit:
        return jsonify(error=f"No listed company found for '{q}'. Try the full name or ticker."), 404
    sym, name = hit["symbol"], hit.get("longname") or hit.get("shortname") or q
    with ThreadPoolExecutor(4) as ex:
        f_px, f_news = ex.submit(sc.prices, sym), ex.submit(sc.news, name)
        f_fin, f_wiki = ex.submit(sc.screener, sym.split(".")[0]), ex.submit(sc.wiki_profile, name)
        try:
            meta, rows = f_px.result()
        except Exception:
            return jsonify(error=f"Could not load price history for {sym}."), 502
        news, fin, wiki = ok(f_news.result, []), ok(f_fin.result, {}), ok(f_wiki.result, {})
    tech, sent = an.technicals(rows), an.sentiment(news)
    fund = an.fundamentals(fin.get("quarters", {}))
    report = read_report(fin.get("docs", []))
    out = {"name": name, "symbol": sym, "currency": meta.get("currency", ""), "prices": rows, "tech": tech,
           "ratios": fin.get("ratios", {}), "quarters": fin.get("quarters", {}), "fund": fund, "news": news,
           "news_insights": an.news_insights(news), "report": report, "website": fin.get("website"),
           "ir": sc.ir_links(fin.get("website")), "docs": fin.get("docs", []),
           "profile": {"sector": fin.get("sector", []), "about": fin.get("about", ""), "holders": fin.get("holders", {}),
                       "holders_period": fin.get("holders_period", ""), "pros": fin.get("pros", []),
                       "cons": fin.get("cons", []), "wiki": wiki},
           "scores": an.scores(tech, sent, fund, report), "analysis": an.analyze(name, tech, sent, fund)}
    CACHE[q] = (time.time(), out)
    return jsonify(out)


if __name__ == "__main__":
    app.run(debug=True)
