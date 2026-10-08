"""NLP on full article text: FinBERT sentence-level sentiment (VADER fallback) + TF-IDF extractive summary."""
import re
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

_pipe, _method = None, None


def score(texts):
    """-> list of sentiment scores in [-1, 1] (positive minus negative probability)."""
    global _pipe, _method
    if _method != "VADER":
        try:
            if _pipe is None:
                from transformers import pipeline
                _pipe = pipeline("text-classification", model="ProsusAI/finbert", top_k=None, truncation=True, max_length=256)
                _method = "FinBERT"
            out = _pipe(texts, batch_size=16)
            return [{d["label"].lower(): d["score"] for d in o}.get("positive", 0) -
                    {d["label"].lower(): d["score"] for d in o}.get("negative", 0) for o in out]
        except Exception:
            _method = "VADER"
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    a = SentimentIntensityAnalyzer()
    return [a.polarity_scores(t)["compound"] for t in texts]


def sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if 40 < len(s.strip()) < 350]


def summarize(arts, k=5):
    pool = [s for a in arts for s in sentences(a["text"][:4000])] or [a["title"] for a in arts]
    if len(pool) <= k:
        return pool
    X = TfidfVectorizer(stop_words="english").fit_transform(pool)
    rank, chosen = np.asarray(X.sum(axis=1)).ravel().argsort()[::-1], []
    for i in rank:  # greedy pick, skipping near-duplicates
        if all(cosine_similarity(X[i], X[j])[0, 0] < .5 for j in chosen):
            chosen.append(i)
        if len(chosen) == k:
            break
    return [pool[i] for i in chosen]


def analyze_news(arts):
    heads = score([a["title"] for a in arts]) if arts else []
    counts, total = {"Positive": 0, "Neutral": 0, "Negative": 0}, []
    for a, h in zip(arts, heads):
        body = sentences(a["text"])[:12]
        s = 0.3 * h + 0.7 * float(np.mean(score(body))) if body else h
        a["score"], a["label"] = round(s, 3), "Positive" if s > .1 else "Negative" if s < -.1 else "Neutral"
        a["snippet"] = (body[0] if body else "")[:200]
        counts[a["label"]] += 1
        total.append(s)
    m = float(np.mean(total)) if total else 0
    keep = ("title", "url", "site", "source", "date", "image", "snippet", "score", "label")
    return {"articles": [{k: a.get(k) for k in keep} for a in arts], "summary": summarize(arts) if arts else [],
            "sentiment": {"score": round(m, 3), "label": "Bullish" if m > .1 else "Bearish" if m < -.1 else "Neutral",
                          "method": _method or "VADER", "counts": counts, "full_text": sum(bool(a["text"]) for a in arts)}}
