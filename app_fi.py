"""Finnish Investment Research Bot - watchlist monitor dashboard.

Free data: Yahoo Finance (yfinance) with Helsinki (.HE) suffix -> quote (EUR)
           + news headlines per ticker. No API key required.

Finnish companies file with Nasdaq Helsinki / FIN-FSA rather than SEC EDGAR,
and there is no free public bulk API equivalent to EDGAR, so this version is
news-only per ticker (matching the spec). A "Pörssitiedotteet" source (STT Info
via parse.bot) can be added later if you want exchange-announcement listings.

Deployment (Streamlit Community Cloud, free):
    1. Push this repo to GitHub (public or private).
    2. Go to https://share.streamlit.io -> "Create app".
    3. Pick your repo / branch / entrypoint (app_fi.py) -> Deploy.
    4. Your app lives at https://<subdomain>.streamlit.app .

Local dev:
    pip install -r requirements.txt
    streamlit run app_fi.py
"""
import streamlit as st
from datetime import datetime, timezone

from fetch_fi import (
    load_watchlist,
    save_watchlist,
    quote_for,
    news_for,
    company_display_name,
    MARKET_NOTE,
    DEFAULT_WATCHLIST,
)

st.set_page_config(
    page_title="Finnish Investment Research Bot",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.title("📈 Finnish Investment Research Bot — Nasdaq Helsinki Watchlist")
st.caption(
    "Free data: **Yahoo Finance** (via yfinance) with Helsinki (.HE) symbols -> "
    "**quote in EUR** + **news headlines** per ticker. No API key required. "
    "Data refreshes on demand — hit **Refresh** in the sidebar."
)
st.caption(MARKET_NOTE)


# ---------------------------------------------------------------- sidebar
st.sidebar.header("Watchlist")

# initialise session state from disk
if "watchlist" not in st.session_state:
    st.session_state.watchlist = load_watchlist()

wl = st.session_state.watchlist  # dict: display_name -> yf_symbol


# -- add ticker
st.sidebar.subheader("Add ticker")
add_symbol = st.sidebar.text_input(
    "Yahoo symbol (with .HE)",
    placeholder="e.g. FORTUM.HE",
    help="Helsinki ticker in Yahoo Finance format, e.g. NOKIA.HE, KONE is KNEBV.HE, Nordea is NDA-FI.HE",
).strip().upper()

if st.sidebar.button("Add"):
    if not add_symbol:
        st.sidebar.warning("Enter a Yahoo symbol (e.g. FORTUM.HE).")
    elif add_symbol in wl.values():
        # already in watchlist — find its display name for the message
        existing_name = next((k for k, v in wl.items() if v == add_symbol), None)
        st.sidebar.warning(f"{add_symbol} is already in the watchlist.")
    else:
        name = company_display_name(add_symbol)
        if not name or name == add_symbol:
            # try a best-effort lookup; if Yahoo doesn't recognise it, warn
            st.sidebar.error(
                f"❌ '{add_symbol}' not recognised by Yahoo Finance. "
                "Check the symbol (Helsinki uses .HE suffix; some trade under "
                "exchange-specific codes, e.g. KONE→KNEBV.HE, Nordea→NDA-FI.HE)."
            )
        else:
            # use a friendly display key derived from the Yahoo name
            display = name.split()[0] if name else add_symbol.replace(".HE", "")
            wl[display] = add_symbol
            save_watchlist(wl)
            st.session_state.watchlist = wl
            st.sidebar.success(f"Added {display} ({add_symbol}) — {name}")

st.sidebar.divider()

# -- remove
remove_names = st.sidebar.multiselect(
    "Remove tickers",
    options=sorted(wl.keys()),
    default=[],
    format_func=lambda k: f"{k} ({wl[k]})",
)
if st.sidebar.button("Remove selected"):
    if not remove_names:
        st.sidebar.warning("Select at least one ticker.")
    else:
        for k in remove_names:
            del wl[k]
        save_watchlist(wl)
        st.session_state.watchlist = wl
        st.sidebar.success(f"Removed {', '.join(sorted(remove_names))}.")

st.sidebar.divider()

# -- reset
if st.sidebar.button("Reset to defaults (11 yhtyneet)"):
    st.session_state.watchlist = dict(DEFAULT_WATCHLIST)
    save_watchlist(DEFAULT_WATCHLIST)
    st.sidebar.success("Watchlist reset to the 11 default Finnish yhtyneet.")

st.sidebar.divider()
st.sidebar.caption(
    f"{len(wl)} ticker{'s' if len(wl) != 1 else ''} in watchlist · "
    "Source: Yahoo Finance (yfinance) · Helsinki (.HE) symbols · EUR"
)

# -- refresh
refresh = st.sidebar.button("🔄 Refresh all data")

# ---------------------------------------------------------------- main
if not wl:
    st.info("Add Helsinki tickers from the sidebar to populate the watchlist.")
    st.stop()

# fetch on refresh or first load
if refresh or "data" not in st.session_state:
    with st.spinner("Fetching quotes and news from Yahoo Finance …"):
        data = {}
        for display_name, yf_symbol in wl.items():
            q = quote_for(yf_symbol)
            q["yf_symbol"] = yf_symbol
            n = news_for(yf_symbol)
            data[display_name] = {
                "quote": q,
                "news": n,
                "yf_symbol": yf_symbol,
            }
    st.session_state.data = data
    st.session_state.fetch_time = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
else:
    data = st.session_state.data

st.sidebar.caption(f"Last refresh: {st.session_state.get('fetch_time', '—')}")

st.divider()


# ---------------------------------------------------------------- cards
def _fmt_mcap(v):
    if v is None:
        return "—"
    try:
        v = float(v)
    except (TypeError, ValueError):
        return str(v)
    if v >= 1e12:
        return f"€{v/1e12:.2f}Bn"  # Finland: billions
    if v >= 1e9:
        return f"€{v/1e9:.0f}Bn"
    if v >= 1e6:
        return f"€{v/1e6:.0f}Mn"
    return f"€{v:,.0f}"


def _news_list(news):
    if not news:
        return "_No recent news._"
    if news[0].get("error"):
        return f"_⚠ {news[0]['error']}_"
    lines = []
    for n in news[:12]:
        title = n.get("title", "(no title)")
        pub = n.get("publisher") or n.get("source", "")
        dt = n.get("date", "")
        url = n.get("url", "")
        meta = f" — _{pub}_" + (f" · {dt}" if dt else "")
        if url:
            lines.append(f"- [{title}]({url}){meta}")
        else:
            lines.append(f"- **{title}**{meta}")
    return "\n".join(lines)


for display_name in sorted(data.keys()):
    d = data[display_name]
    q = d["quote"]
    news = d["news"]
    yf_symbol = d["yf_symbol"]

    price = q.get("price")
    prev = q.get("previous_close")
    change = q.get("change")
    change_pct = q.get("change_pct")
    mcap = q.get("market_cap")
    currency = q.get("currency", "EUR")
    name = q.get("name") or display_name

    with st.expander(f"**{display_name}**  —  {name}  [Yahoo: {yf_symbol}]", expanded=True):
        if price is None and not news:
            st.warning(
                f"'{yf_symbol}' returned no quote or news from Yahoo Finance. "
                "The symbol may be wrong — remove it and try the correct Helsinki "
                "code (see the Add-ticker help text)."
            )
            continue

        # quote row
        c1, c2, c3, c4 = st.columns(4)
        if price is not None:
            c1.metric("Price", f"{price:,.2f} {currency}")
        else:
            c1.metric("Price", "—")

        if change is not None and prev:
            c2.metric("Day Change", f"{change:+,.2f} {currency}", delta=f"{change_pct:+.2f}%")
        else:
            c2.metric("Day Change", "—")

        c3.metric("Market Cap", _fmt_mcap(mcap))
        c4.metric("Currency", currency)

        st.divider()

        # news
        st.subheader("📰 Recent News")
        st.markdown(_news_list(news))
        st.caption(
            "News headlines via Yahoo Finance. Some Finnish-market news is in "
            "English; some items may be in Finnish. Click a headline to read the "
            "original source."
        )

st.divider()
st.caption(
    "Data sources & limitations: Quotes and news come from Yahoo Finance "
    "(via the yfinance library) using Helsinki (.HE) symbols. Free-user quotes "
    "are delayed (~15 min) and update during the Nasdaq Helsinki session. "
    "This is not financial advice."
)
