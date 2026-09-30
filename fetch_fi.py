"""Data layer for the Finnish Investment Research Bot.

Free sources:
  - Yahoo Finance (yfinance) with Helsinki (.HE) suffix -> quote (EUR) + news
  - No SEC-EDGAR equivalent for Finnish filings (FIN-FSA / exchange disclosure
    has no free public bulk API like EDGAR), so this version is news-only per
    your spec. STT Info pörssitiedotteet can be added later if you want.

Finnish yhtyneet on Nasdaq Helsinki are referenced by yfinance using the
<BASE>.HE suffix, BUT many tickers use exchange-specific codes (e.g. KONE
trades as KNEBV.HE, Nordea as NDA-FI.HE, Kesko as KESKOB.HE, etc.). The
WATCHLIST below maps a friendly name to the correct Yahoo symbol.

Usage:
    streamlit run app_fi.py
"""
import json
import os
import time

import yfinance as yf

_HERE = os.path.dirname(os.path.abspath(__file__))
WATCHLIST_FILE = os.path.join(_HERE, "watchlist_fi.json")

# Reference date context for the Finnish market:
# Yahoo Finance Helsinki quotes are typically delayed (~15 min) for free users
# and update during the Helsinki session (EET/EEST, roughly 09:00-16:30 local).
MARKET_NOTE = (
    "Helsinki quotes via Yahoo Finance are delayed (~15 min) for free users and "
    "update during the Nasdaq Helsinki session (EET/EEST, ~09:00-16:30 local)."
)

# Friendly Finnish yhtyneet mapped to the correct Yahoo Finance symbol.
# Some trade under exchange-specific codes on Yahoo (see notes above).
DEFAULT_WATCHLIST = {
    # ticker_display : yfinance_symbol
    "NOKIA":      "NOKIA.HE",
    "KONE":       "KNEBV.HE",
    "KESKO":      "KESKOB.HE",
    "NDA":        "NDA-FI.HE",   # Nordea Bank Abp
    "SAMPO":      "SAMPO.HE",
    "UPM":        "UPM.HE",
    "NESTE":      "NESTE.HE",
    "FORTUM":     "FORTUM.HE",
    "OUTOKUMPU":  "OUT1V.HE",
    "ORION":      "ORNBV.HE",
    "WARTSILA":   "WRT1V.HE",
}

# ---------------------------------------------------------------------------
# Watchlist persistence
# ---------------------------------------------------------------------------

def load_watchlist():
    if os.path.exists(WATCHLIST_FILE):
        try:
            with open(WATCHLIST_FILE) as f:
                data = json.load(f)
            # Accept either {name: symbol} or a list of symbols
            if isinstance(data, dict):
                return data
            if isinstance(data, list):
                return {s: s for s in data}
        except Exception:
            pass
    return dict(DEFAULT_WATCHLIST)


def save_watchlist(watchlist):
    """Persist the watchlist (dict: friendly name -> yfinance symbol)."""
    tmp = WATCHLIST_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(watchlist, f, indent=2, ensure_ascii=False)
    os.replace(tmp, WATCHLIST_FILE)


# ---------------------------------------------------------------------------
# Quote + news from Yahoo Finance (Helsinki)
# ---------------------------------------------------------------------------

def quote_for(yf_symbol):
    """Current quote for a Helsinki ticker (yfinance symbol, e.g. NOKIA.HE).

    Returns dict: price, previous_close, change, change_pct, market_cap,
                  currency, name, yf_symbol
    """
    try:
        info = yf.Ticker(yf_symbol).info or {}
    except Exception:
        info = {}

    price = info.get("regularMarketPrice") or info.get("currentPrice")
    prev = info.get("previousClose")
    change = info.get("regularMarketChange")
    change_pct = info.get("regularMarketChangePercent")
    mcap = info.get("marketCap")
    currency = info.get("currency", "EUR")
    name = info.get("longName") or info.get("shortName") or ""

    return {
        "price": price,
        "previous_close": prev,
        "change": change,
        "change_pct": change_pct,
        "market_cap": mcap,
        "currency": currency,
        "name": name,
        "yf_symbol": None,  # set by caller
    }


def news_for(yf_symbol):
    """Recent news items for a Helsinki ticker from Yahoo Finance.

    Returns a list of dicts: title, publisher, url, date, source.
    On failure returns a single dict with an ``error`` key.
    """
    try:
        items = yf.Ticker(yf_symbol).news or []
    except Exception as exc:
        return [{"error": f"yfinance error: {exc}"}]

    out = []
    for it in items:
        c = it.get("content", {})
        title = c.get("title") or "(no title)"
        provider = c.get("provider", {})
        publisher = provider.get("displayName", "")
        ctu = c.get("clickThroughUrl") or c.get("canonicalUrl") or {}
        url = ctu.get("url", "")
        out.append({
            "title": title,
            "publisher": publisher,
            "url": url,
            "date": c.get("pubDate", "")[:10] if c.get("pubDate") else "",
            "source": provider.get("sourceId", ""),
        })
    return out


def company_display_name(yf_symbol):
    """Best-effort company name for a yfinance symbol (for the add-ticker UI)."""
    try:
        info = yf.Ticker(yf_symbol).info or {}
        return info.get("longName") or info.get("shortName") or yf_symbol
    except Exception:
        return yf_symbol
