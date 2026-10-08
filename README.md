# Stock analyst chat

    pip install -r requirements.txt
    python app.py        # open http://127.0.0.1:5000

Optional: set ANTHROPIC_API_KEY to get a written narrative on top of the rule-based analysis.

Sources: Yahoo Finance (search, prices, volume), Screener.in (ratios, quarterly results, filings, company site),
the company's own website (investor/results links), Google News RSS (headlines).

## UI notes
- Price chart: TradingView `lightweight-charts` (vendored in `static/`, no CDN needed). Y axis auto-fits the visible range, so long ranges are no longer flattened.
- Ranges: 1D, 5D, 1M, 6M, YTD, 1Y, 5Y, MAX. Bar size grows with the range (1m, 15m, 1h, 1d, 1wk, 1mo) to keep payloads small.
- The chart and quote stats load first; ranges are prefetched in the background so switching is instant.
- Forecast (ML) and News load only when their tab is opened; report PDF parsing runs as its own request (`/api/report`).
- Light/dark theme toggle (follows system by default).
