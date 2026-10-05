"""All data collection. Everything here is scraped/fetched live from public web sources."""
import io, re
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from urllib.parse import urljoin
from bs4 import BeautifulSoup

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}


def get(url, **kw):
    r = requests.get(url, headers=H, timeout=15, **kw)
    r.raise_for_status()
    return r


def resolve(query):
    """Company name / keyword -> best matching listed equity (NSE/BSE preferred)."""
    j = get("https://query2.finance.yahoo.com/v1/finance/search",
            params={"q": query, "quotesCount": 8, "newsCount": 0}).json()
    eq = [x for x in j.get("quotes", []) if x.get("quoteType") == "EQUITY"]
    eq.sort(key=lambda x: not x["symbol"].endswith((".NS", ".BO")))
    return eq[0] if eq else None


def prices(symbol, rng="1y"):
    """Daily OHLCV history from Yahoo Finance's chart endpoint."""
    r = get(f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
            params={"range": rng, "interval": "1d"}).json()["chart"]["result"][0]
    q, rows = r["indicators"]["quote"][0], []
    for i, t in enumerate(r["timestamp"]):
        if q["close"][i] is None:
            continue
        rows.append({"date": datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%d"),
                     "open": q["open"][i], "high": q["high"][i], "low": q["low"][i],
                     "close": q["close"][i], "volume": q["volume"][i]})
    return r["meta"], rows


def news(name, n=12):
    """Latest headlines from Google News RSS."""
    root = ET.fromstring(get("https://news.google.com/rss/search",
                             params={"q": f"{name} stock", "hl": "en-IN", "gl": "IN", "ceid": "IN:en"}).content)
    return [{"title": i.findtext("title"), "link": i.findtext("link"),
             "date": i.findtext("pubDate"), "source": i.findtext("source")}
            for i in root.iter("item")][:n]


def _num(x):
    try:
        return float(x.replace(",", "").replace("%", ""))
    except ValueError:
        return None


def _table(t):
    if not t:
        return {}
    out = {"periods": [th.get_text(strip=True) for th in t.select("thead th")][1:]}
    for tr in t.select("tbody tr"):
        c = [td.get_text(strip=True) for td in tr.select("td")]
        if len(c) > 1:
            out[re.sub(r"[\s+]+$", "", c[0])] = [_num(x) for x in c[1:]]
    return out


def screener(ticker):
    """Key ratios, quarterly results, filings and the official website (Indian listings)."""
    html = None
    for path in ("consolidated/", ""):
        try:
            html = get(f"https://www.screener.in/company/{ticker}/{path}").text
            break
        except requests.RequestException:
            continue
    if not html:
        return {}
    s = BeautifulSoup(html, "html.parser")
    ratios = {li.select_one(".name").get_text(strip=True): " ".join(li.select_one(".value").get_text().split())
              for li in s.select("#top-ratios li") if li.select_one(".name") and li.select_one(".value")}
    links = [a["href"] for a in s.select(".company-links a[href]")]
    site = next((l for l in links if not re.search(r"bseindia|nseindia|screener", l)), None)
    docs = [{"title": a.get_text(" ", strip=True), "url": urljoin("https://www.screener.in", a["href"])}
            for a in s.select("#documents a[href]")][:12]
    shp = _table(s.select_one("#quarterly-shp table") or s.select_one("#shareholding table"))
    holders = {k: v[-1] for k, v in shp.items() if k != "periods" and v and v[-1] is not None}
    about = s.select_one(".company-profile .about")
    return {"ratios": ratios, "website": site, "docs": docs, "quarters": _table(s.select_one("#quarters table")),
            "sector": [a.get_text(strip=True) for a in s.select("#peers p.sub a")][:3],
            "about": about.get_text(" ", strip=True)[:500] if about else "", "holders": holders,
            "holders_period": (shp.get("periods") or [""])[-1],
            "pros": [li.get_text(strip=True) for li in s.select(".pros li")][:4],
            "cons": [li.get_text(strip=True) for li in s.select(".cons li")][:4]}


KW = re.compile(r"investor|result|financial|quarter|earning|annual", re.I)


def ir_links(site):
    """Scrape the company's own website for investor / results pages."""
    if not site:
        return []
    try:
        s = BeautifulSoup(get(site).text, "html.parser")
    except requests.RequestException:
        return []
    seen, out = set(), []
    for a in s.find_all("a", href=True):
        t = a.get_text(" ", strip=True)
        u = urljoin(site, a["href"])
        if KW.search(t + a["href"]) and u not in seen:
            seen.add(u)
            out.append({"title": t[:80] or u, "url": u})
    return out[:10]


def wiki_profile(name):
    """Founder / owner / key people / HQ from the company's Wikipedia infobox."""
    try:
        base = re.sub(r"\b(limited|ltd\.?|inc\.?|corp(oration)?)\b", "", name, flags=re.I).strip()
        j = get("https://en.wikipedia.org/w/api.php",
                params={"action": "opensearch", "search": base, "limit": 1, "format": "json"}).json()
        if not j[3]:
            return {}
        s = BeautifulSoup(get(j[3][0]).text, "html.parser")
        want = {"founder", "founders", "key people", "owner", "owners", "parent", "headquarters", "founded", "number of employees"}
        info = {}
        for tr in s.select("table.infobox tr"):
            th, td = tr.find("th"), tr.find("td")
            if th and td and th.get_text(" ", strip=True).lower() in want:
                info[th.get_text(" ", strip=True)] = re.sub(r"\[\d+\]", "", td.get_text(" ", strip=True))[:160]
        return {"url": j[3][0], "info": info}
    except Exception:
        return {}


def pdf_text(url, pages=40):
    """Download a report PDF and return the text of its first pages."""
    from pypdf import PdfReader
    r = get(url)
    if not r.content.startswith(b"%PDF") or len(r.content) > 15_000_000:
        return ""
    rd = PdfReader(io.BytesIO(r.content))
    return " ".join((p.extract_text() or "") for p in rd.pages[:pages])
