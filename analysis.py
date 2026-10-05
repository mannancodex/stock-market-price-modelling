"""Turns raw scraped data into metrics, sentiment and a plain-language view."""
import os
import requests

POS = {"surge", "beat", "growth", "profit", "gain", "record", "upgrade", "rally", "strong", "wins", "buy", "rises", "jumps", "dividend"}
NEG = {"fall", "falls", "loss", "miss", "downgrade", "probe", "fraud", "plunge", "weak", "sell", "cuts", "drops", "slump", "lawsuit", "default"}


def _sma(v, n):
    return sum(v[-n:]) / n if len(v) >= n else None


def _ret(c, n):
    return (c[-1] / c[-n - 1] - 1) * 100 if len(c) > n else None


def _rsi(c, n=14):
    d = [c[i] - c[i - 1] for i in range(1, len(c))][-n:]
    g, l = sum(x for x in d if x > 0) / n, -sum(x for x in d if x < 0) / n
    return 100.0 if l == 0 else 100 - 100 / (1 + g / l)


def technicals(rows):
    c, v = [r["close"] for r in rows], [r["volume"] or 0 for r in rows]
    hi, lo = max(r["high"] for r in rows), min(r["low"] for r in rows)
    return {"last": c[-1], "sma50": _sma(c, 50), "sma200": _sma(c, 200), "rsi": _rsi(c),
            "ret_1m": _ret(c, 21), "ret_6m": _ret(c, 126), "ret_1y": _ret(c, len(c) - 1),
            "high_52w": hi, "low_52w": lo, "pos_52w": (c[-1] - lo) / (hi - lo) * 100 if hi > lo else None,
            "avg_vol_20": _sma(v, 20), "avg_vol_100": _sma(v, 100)}


def sentiment(items):
    total = 0
    for it in items:
        w = set(it["title"].lower().replace(",", " ").split())
        it["tone"] = (len(w & POS) > len(w & NEG)) - (len(w & POS) < len(w & NEG))
        total += it["tone"]
    return total / len(items) if items else 0


def fundamentals(q):
    rev = q.get("Sales") or q.get("Revenue") or []
    pat = q.get("Net Profit") or []

    def g(s, k):
        return (s[-1] / s[-1 - k] - 1) * 100 if len(s) > k and s[-1] is not None and s[-1 - k] else None
    return {"rev_yoy": g(rev, 4), "rev_qoq": g(rev, 1), "pat_yoy": g(pat, 4), "pat_qoq": g(pat, 1)}


def analyze(name, tech, sent, fund):
    pts, score = [], 0

    def add(cond, delta, text):
        nonlocal score
        if cond:
            score += delta
            pts.append(text)
    if tech["sma200"]:
        add(tech["last"] > tech["sma200"], 1, "Trading above its 200-day average (long-term uptrend).")
        add(tech["last"] < tech["sma200"], -1, "Trading below its 200-day average (long-term downtrend).")
    add(tech["rsi"] > 70, -1, f"RSI {tech['rsi']:.0f}: overbought, a pullback is more likely.")
    add(tech["rsi"] < 30, 1, f"RSI {tech['rsi']:.0f}: oversold, a bounce is more likely.")
    if tech["ret_1y"] is not None:
        add(True, 1 if tech["ret_1y"] > 0 else -1, f"{tech['ret_1y']:+.1f}% over the past year.")
    if tech["avg_vol_20"] and tech["avg_vol_100"]:
        add(tech["avg_vol_20"] > 1.3 * tech["avg_vol_100"], 0, "Recent volume is well above normal, so moves carry more weight.")
    add(sent > 0.15, 1, "Recent headlines lean positive.")
    add(sent < -0.15, -1, "Recent headlines lean negative.")
    if fund.get("rev_yoy") is not None:
        add(True, 1 if fund["rev_yoy"] > 10 else -1 if fund["rev_yoy"] < 0 else 0, f"Revenue {fund['rev_yoy']:+.1f}% vs same quarter last year.")
    if fund.get("pat_yoy") is not None:
        add(True, 1 if fund["pat_yoy"] > 10 else -1 if fund["pat_yoy"] < 0 else 0, f"Net profit {fund['pat_yoy']:+.1f}% vs same quarter last year.")
    verdict = "Positive" if score >= 3 else "Negative" if score <= -2 else "Mixed"
    out = {"score": score, "verdict": verdict, "points": pts, "llm": None}
    key = os.getenv("ANTHROPIC_API_KEY")
    if key:  # optional: have Claude write the narrative from the scraped facts
        try:
            r = requests.post("https://api.anthropic.com/v1/messages", timeout=40,
                              headers={"x-api-key": key, "anthropic-version": "2023-06-01"},
                              json={"model": "claude-sonnet-4-6", "max_tokens": 500, "messages": [{"role": "user", "content":
                                    f"Write a balanced 120-word analysis of {name} for a retail investor using only these facts. "
                                    f"No advice.\nTechnicals: {tech}\nFundamentals: {fund}\nHeadline sentiment: {sent:.2f}\nSignals: {pts}"}]})
            out["llm"] = r.json()["content"][0]["text"]
        except Exception:
            pass
    return out


TOPICS = {"Earnings": ["results", "profit", "revenue", "quarter", "q1", "q2", "q3", "q4", "earnings"],
          "Deals & expansion": ["acquire", "acquisition", "deal", "stake", "order", "expansion", "merger", "launch", "plant"],
          "Regulation & legal": ["sebi", "court", "probe", "penalty", "tax", "regulator", "lawsuit", "ban"],
          "Analyst views": ["target", "rating", "upgrade", "downgrade", "buy", "sell", "brokerage"],
          "Management": ["ceo", "chairman", "md", "appoints", "resigns", "board"]}


def news_insights(items):
    """Per-headline tone (already set by sentiment()), topic mix and tone counts."""
    tone = {"Positive": 0, "Neutral": 0, "Negative": 0}
    topics = {k: 0 for k in TOPICS}
    for it in items:
        tone["Positive" if it["tone"] > 0 else "Negative" if it["tone"] < 0 else "Neutral"] += 1
        t = it["title"].lower()
        for k, words in TOPICS.items():
            if any(w in t for w in words):
                topics[k] += 1
    return {"tone": tone, "topics": {k: v for k, v in topics.items() if v}}


THEMES = {"Growth": ["growth", "expansion", "demand", "order book", "market share"],
          "Margins": ["margin", "ebitda", "profitability", "cost"],
          "Debt": ["debt", "borrowing", "leverage", "interest cost"],
          "Investment": ["capex", "capital expenditure", "investment", "capacity"],
          "Risk": ["risk", "uncertain", "headwind", "pressure", "litigation", "volatil"],
          "Outlook": ["outlook", "guidance", "expect", "target", "pipeline"]}
R_POS = POS | {"improved", "robust", "momentum", "healthy", "opportunity", "increase", "outperform", "efficient"}
R_NEG = NEG | {"decline", "challenging", "headwinds", "pressure", "uncertainty", "decreased", "impairment", "delay"}


def report_insights(text):
    import re
    low, words = text.lower(), max(len(text.split()), 1)
    themes = {k: round(sum(low.count(w) for w in ws) / words * 1000, 1) for k, ws in THEMES.items()}
    toks = re.findall(r"[a-z]+", low)
    p, n = sum(t in R_POS for t in toks), sum(t in R_NEG for t in toks)
    sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if 70 < len(s) < 300]
    key = [s for s in sents if re.search(r"\b(outlook|guidance|expect|target|plan to|aim)\b", s, re.I) and re.search(r"\d", s)][:4]
    return {"words": words, "themes": themes, "tone": (p - n) / max(p + n, 1), "key_sentences": key,
            "llm": _llm(f"Summarise this company report excerpt in 80 words for an investor: management tone, "
                        f"growth drivers, risks. Excerpt: {text[:6000]}")}


def _llm(prompt):
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        return None
    try:
        r = requests.post("https://api.anthropic.com/v1/messages", timeout=40,
                          headers={"x-api-key": key, "anthropic-version": "2023-06-01"},
                          json={"model": "claude-sonnet-4-6", "max_tokens": 400, "messages": [{"role": "user", "content": prompt}]})
        return r.json()["content"][0]["text"]
    except Exception:
        return None


def scores(tech, sent, fund, report):
    """0-100 sub-scores for the radar chart (50 = neutral)."""
    clip = lambda x: round(max(0, min(100, x)))
    trend = 50 + (20 if tech["sma200"] and tech["last"] > tech["sma200"] else -20 if tech["sma200"] else 0) \
        + (10 if tech["sma50"] and tech["sma200"] and tech["sma50"] > tech["sma200"] else 0) + ((tech["pos_52w"] or 50) - 50) * 0.2
    mom = 50 + (tech["ret_1m"] or 0) * 2 + (tech["ret_6m"] or 0) * 0.5 - max(0, abs(tech["rsi"] - 50) - 20)
    fnd = 50 + (fund.get("rev_yoy") or 0) * 1 + (fund.get("pat_yoy") or 0) * 0.5
    out = {"Trend": clip(trend), "Momentum": clip(mom), "Fundamentals": clip(fnd), "News": clip(50 + sent * 50)}
    if report:
        out["Reports"] = clip(50 + report["tone"] * 50)
    return out
