"""
Finnish Investment Research Bot — data layer.

Free sources (no API key):
  - Yahoo Finance (yfinance) with Helsinki (.HE) symbols -> quote (EUR) + news headlines.

Finnish "filings" equivalent (OPTIONAL — requires a free STT Info API key from parse.bot):
  - STT Info Pörssitiedotteet API -> Finnish stock exchange announcements per company.
  - Sign up at https://parse.bot -> marketplace -> STT Info Pörssitiedotteet API
  - Free tier: 200 credits/month, 1 credit per call, key starts with pmx_.
  - Provide the key in Streamlit secrets as STT_INFO_API_KEY.
"""
import json
import os
import time

import requests
import yfinance as yf

_HERE = os.path.dirname(os.path.abspath(__file__))
WATCHLIST_FILE = os.path.join(_HERE, "watchlist_fi.json")

MARKET_NOTE = (
    "Helsinki quotes via Yahoo Finance are delayed (~15 min) for free users and "
    "update during the Nasdaq Helsinki session (EET/EEST, ~09:00-16:30 local)."
)

# Finnish yhtyneet on Nasdaq Helsinki mapped to the correct Yahoo Finance symbol.
# Many trade under exchange-specific codes on Yahoo (see notes below).
DEFAULT_WATCHLIST = {
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

# STT Info Pörssitiedotteet API (optional — set STT_INFO_API_KEY in secrets)
STT_BASE = "https://api.parse.bot"
STT_ENDPOINT = "scraper/4e1df81b-92fa-41c6-bbcb-0a27e45b9343"  # STT Info scraper id
STT_GET_URI = f"{STT_BASE}/api/{STT_ENDPOINT}/get_porssitiedotteet"
STT_SEARCH_URI = f"{STT_BASE}/api/{STT_ENDPOINT}/search_announcements"


# ---------------------------------------------------------------------------
# Watchlist persistence
# ---------------------------------------------------------------------------

def load_watchlist():
    if os.path.exists(WATCHLIST_FILE):
        try:
            with open(WATCHLIST_FILE) as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
            if isinstance(data, list):
                return {s: s for s in data}
        except Exception:
            pass
    return dict(DEFAULT_WATCHLIST)


def save_watchlist(watchlist):
    tmp = WATCHLIST_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(watchlist, f, indent=2, ensure_ascii=False)
    os.replace(tmp, WATCHLIST_FILE)


def get_stt_key():
    """Return an STT Info API key if available (Streamlit secrets, then env)."""
    try:
        from streamlit import secrets as st_secrets
        key = (getattr(st_secrets, "STT_INFO_API_KEY", None)
               or os.environ.get("STT_INFO_API_KEY"))
        if key:
            return key
    except Exception:
        pass
    return os.environ.get("STT_INFO_API_KEY")


# ---------------------------------------------------------------------------
# Yahoo Finance (Helsinki) — quote + news
# ---------------------------------------------------------------------------

def quote_for(yf_symbol):
    """Current quote for a Helsinki ticker (yfinance symbol, e.g. NOKIA.HE)."""
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
        "yf_symbol": None,
    }


def news_for(yf_symbol):
    """Recent news items for a Helsinki ticker from Yahoo Finance."""
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


def _fmt_mcap(v):
    """Human-readable market cap:  €50Bn / €27Mn / €1,234."""
    if v is None:
        return "—"
    try:
        v = float(v)
    except (TypeError, ValueError):
        return str(v)
    if v >= 1e9:
        return f"€{v/1e9:.0f}Bn"
    if v >= 1e6:
        return f"€{v/1e6:.0f}Mn"
    return f"€{v:,.0f}"


# ---------------------------------------------------------------------------
# STT Info Pörssitiedotteet (Finnish stock exchange announcements)
# ---------------------------------------------------------------------------

def stt_search(query, api_key, limit=15):
    """Search STT Info for announcements matching *query* (company name / keyword).

    Returns list of dicts: title, publisher, date, category, url, error
    """
    if not api_key:
        return [{"error": "STT_INFO_API_KEY not configured. Add it in Streamlit secrets or app."}]
    headers = {"X-API-Key": api_key, "Content-Type": "application/json"}
    params = {"query": query, "size": limit, "language": "fi"}
    try:
        r = requests.get(STT_SEARCH_URI, headers=headers, params=params, timeout=30)
        if r.status_code == 429:
            return [{"error": "STT Info rate limit (429). Wait and retry."}]
        if r.status_code != 200:
            return [{"error": f"STT Info API error {r.status_code}: {r.text[:200]}"}]
        data = r.json()
        items = data.get("announcements") or []
        out = []
        for it in items[:limit]:
            pub_date = it.get("publication_date", "")
            if isinstance(pub_date, str) and "T" in pub_date:
                pub_date = pub_date[:10]
            out.append({
                "title": it.get("title", "(no title)"),
                "publisher": it.get("publisher", ""),
                "date": pub_date,
                "category": it.get("category", ""),
                "url": it.get("url", ""),
            })
        return out
    except requests.RequestException as exc:
        return [{"error": f"STT Info request failed: {exc}"}]


def stt_recent(api_key, limit=20):
    """Most recent Pörssitiedotteet (global, not per-company)."""
    if not api_key:
        return [{"error": "STT_INFO_API_KEY not configured."}]
    get_uri = f"{STT_BASE}/api/{STT_ENDPOINT}/get_porssitiedotteet"
    headers = {"X-API-Key": api_key, "Content-Type": "application/json"}
    params = {"page": 0, "size": limit, "language": "fi"}
    try:
        r = requests.get(get_uri, headers=headers, params=params, timeout=30)
        if r.status_code != 200:
            return [{"error": f"STT Info API error {r.status_code}: {r.text[:200]}"}]
        data = r.json()
        items = data.get("announcements") or []
        out = []
        for it in items[:limit]:
            pub_date = it.get("publication_date", "")
            if isinstance(pub_date, str) and "T" in pub_date:
                pub_date = pub_date[:10]
            out.append({
                "title": it.get("title", "(no title)"),
                "publisher": it.get("publisher", ""),
                "date": pub_date,
                "category": it.get("category", ""),
                "url": it.get("url", ""),
            })
        return out
    except requests.RequestException as exc:
        return [{"error": f"STT Info request failed: {exc}"}]
