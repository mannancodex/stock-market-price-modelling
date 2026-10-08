"""Next-day price modelling: LSTM + Random Forest + SVM, tuned, then combined in a validation-weighted ensemble."""
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import GridSearchCV, TimeSeriesSplit
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVR

W = 20  # LSTM look-back window (trading days)


def build(rows):
    df = pd.DataFrame(rows)
    c, f = df.close, pd.DataFrame(index=df.index)
    for k in (1, 2, 3, 5, 10, 20):
        f[f"r{k}"] = c.pct_change(k)
    f["sma10"], f["sma50"] = c / c.rolling(10).mean() - 1, c / c.rolling(50).mean() - 1
    d = c.diff()
    g, l = d.clip(lower=0).rolling(14).mean(), (-d.clip(upper=0)).rolling(14).mean()
    f["rsi"] = 100 - 100 / (1 + g / (l + 1e-9))
    f["macd"] = (c.ewm(span=12).mean() - c.ewm(span=26).mean()) / c
    f["vol20"], f["range"] = c.pct_change().rolling(20).std(), (df.high - df.low) / c
    v = df.volume.replace(0, np.nan)
    f["vchg"] = (v / v.rolling(20).mean() - 1).fillna(0)
    f["target"] = c.shift(-1) / c - 1  # next-day return
    return df, f


def metrics(close, ret, pred):
    act, hat = close * (1 + ret), close * (1 + pred)
    mape = float(np.mean(np.abs(act - hat) / act) * 100)
    return {"accuracy": round(100 - mape, 2), "mape": round(mape, 3),
            "rmse": round(float(np.sqrt(np.mean((act - hat) ** 2))), 3),
            "r2": round(float(1 - np.sum((act - hat) ** 2) / np.sum((act - act.mean()) ** 2)), 4),
            "direction": round(float((np.sign(pred) == np.sign(ret)).mean() * 100), 1)}


def fit_rf(X, y):
    g = GridSearchCV(RandomForestRegressor(random_state=0, n_jobs=-1),
                     {"n_estimators": [200], "max_depth": [4, 8], "min_samples_leaf": [5, 20]},
                     cv=TimeSeriesSplit(3), scoring="neg_mean_squared_error").fit(X, y)
    return g.best_estimator_.predict, g.best_params_


def fit_svr(X, y):
    g = GridSearchCV(make_pipeline(StandardScaler(), SVR(kernel="rbf")),
                     {"svr__C": [0.1, 1, 10], "svr__epsilon": [0.01, 0.1], "svr__gamma": ["scale", 0.01]},
                     cv=TimeSeriesSplit(3), scoring="neg_mean_squared_error").fit(X, y * 100)
    return (lambda Z: g.best_estimator_.predict(Z) / 100), {k.split("__")[1]: v for k, v in g.best_params_.items()}


def fit_lstm(Xs, yy, start, tr, va):
    import torch
    import torch.nn as nn
    torch.manual_seed(0)
    seq = torch.tensor(np.stack([Xs[i - W + 1:i + 1] for i in range(start, len(Xs))]), dtype=torch.float32)
    tgt = torch.tensor(yy[start:] * 100, dtype=torch.float32)

    class Net(nn.Module):
        def __init__(s):
            super().__init__()
            s.l, s.d, s.f = nn.LSTM(Xs.shape[1], 32, batch_first=True), nn.Dropout(0.2), nn.Linear(32, 1)

        def forward(s, x):
            o, _ = s.l(x)
            return s.f(s.d(o[:, -1])).squeeze(-1)
    m, lossf = Net(), nn.MSELoss()
    opt = torch.optim.Adam(m.parameters(), 1e-3, weight_decay=1e-4)
    a, b, best, state, wait = tr - start, va - start, 1e9, None, 0
    for _ in range(60):  # early stopping on the validation block
        m.train()
        perm = torch.randperm(a)
        for k in range(0, a, 64):
            ix = perm[k:k + 64]
            opt.zero_grad()
            lossf(m(seq[ix]), tgt[ix]).backward()
            opt.step()
        m.eval()
        with torch.no_grad():
            v = lossf(m(seq[a:b]), tgt[a:b]).item()
        if v < best:
            best, state, wait = v, {k: x.clone() for k, x in m.state_dict().items()}, 0
        else:
            wait += 1
            if wait >= 8:
                break
    m.load_state_dict(state)
    m.eval()
    with torch.no_grad():
        out = np.full(len(Xs), np.nan)
        out[start:] = m(seq).numpy() / 100
    return out


def run(rows):
    df, f = build(rows)
    fc = [c for c in f.columns if c != "target"]
    data = f.dropna(subset=fc)
    n = len(data) - 1  # last row is "today": features only, no target yet
    if n < 300:
        raise ValueError("not enough price history to model")
    X, y = data[fc].values, data["target"].values
    pos, close, dates = data.index.values, df.close.loc[data.index].values, df.date.values
    start, tr, va = W - 1, int(n * .7), int(n * .85)
    preds, params = {}, {}
    for name, fn in (("Random Forest", fit_rf), ("SVM", fit_svr)):
        p, par = fn(X[start:tr], y[start:tr])
        preds[name], params[name] = p(X), par
    try:
        Xs = StandardScaler().fit(X[start:tr]).transform(X)
        preds["LSTM"], params["LSTM"] = fit_lstm(Xs, np.r_[y[:-1], 0.0], start, tr, va), {"units": 32, "window": W}
    except ImportError:
        pass
    inv = {m: 1 / np.sqrt(np.mean((preds[m][tr:va] - y[tr:va]) ** 2)) for m in preds}
    w = {m: v / sum(inv.values()) for m, v in inv.items()}
    preds["Ensemble"] = sum(w[m] * preds[m] for m in w)
    sl_tr, sl_te = slice(start, tr), slice(va, n)
    models = {}
    for m, p in preds.items():
        models[m] = {"params": params.get(m, {}), "weight": round(w.get(m, 1), 3),
                     "train": metrics(close[sl_tr], y[sl_tr], p[sl_tr]), "test": metrics(close[sl_te], y[sl_te], p[sl_te]),
                     "next_ret": float(p[n]) * 100, "next_price": float(close[n] * (1 + p[n]))}
    base = metrics(close[sl_te], y[sl_te], np.zeros(n - va))
    ups = sum(preds[m][n] > 0 for m in preds if m != "Ensemble")
    return {"models": models, "baseline": base, "votes": {"up": int(ups), "total": len(preds) - 1},
            "split": {"train": [dates[pos[start]], dates[pos[tr - 1]]], "test": [dates[pos[va]], dates[pos[n - 1] + 1]]},
            "test": {"dates": [dates[i + 1] for i in pos[sl_te]], "actual": (close[sl_te] * (1 + y[sl_te])).tolist(),
                     **{m: (close[sl_te] * (1 + p[sl_te])).tolist() for m, p in preds.items()}},
            "skipped": [] if "LSTM" in preds else ["LSTM (install torch)"]}
