# Finnish Investment Research Bot — deploy notes

## What this is
A Streamlit dashboard that monitors a watchlist of Finnish Nasdaq Helsinki
yhtyneet (Nokia, KONE, Kesko, Nordea, Sampo, UPM, Neste, Fortum, Outokumpu,
Orion, Wärtsilä) showing **quote (EUR)** + **news headlines** per ticker.

## Data sources (free, no API key)
- Yahoo Finance via `yfinance` with Helsinki (.HE) symbols.
  - Quote (price, day change, market cap, currency = EUR).
  - News headlines with links back to the original publisher.
- Yahoo quotes for free users are delayed ~15 min and update during the
  Helsinki session (~09:00-16:30 EET/EEST).

## Why no filings
Finnish companies disclose via Nasdaq Helsinki / FIN-FSA (pörssitiedotteet),
which has no free public bulk API comparable to US SEC EDGAR. This version is
news-only per the spec. To add exchange announcements later, the STT Info
Pörssitiedotteet API (via parse.bot; free tier 200 credits/mo) is the most
direct Finnish equivalent.

## Local run
    pip install -r requirements.txt
    streamlit run app_fi.py

## Deploy to Streamlit Community Cloud (free, public URL)
1. Push this repo to GitHub (public or private).
2. Sign in at https://share.streamlit.io with GitHub.
3. "Create app" -> select your repo, branch (main), entrypoint (app_fi.py).
4. Click "Deploy". Your app is live at
   https://<your-github-handle>-invest-bot-fi-app-<hash>.streamlit.app

   You can pick a custom subdomain in App settings (e.g.
   https://fi-invest.streamlit.app).

## Files
- app_fi.py      entrypoint (Streamlit dashboard)
- fetch_fi.py    data layer (yfinance Helsinki quotes + news)
- requirements.txt  Python deps for Streamlit Cloud
- watchlist_fi.json  persisted watchlist (created/updated at runtime)
