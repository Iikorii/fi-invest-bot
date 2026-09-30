"""Finnish Investment Research Bot — Nasdaq Helsinki watchlist monitor.

Free data: Yahoo Finance (yfinance, Helsinki .HE symbols) -> quote (EUR) +
news headlines. Optional: STT Info Pörssitiedotteet API (free key from
parse.bot) -> Finnish stock-exchange announcements (the "filings" equivalent).

Deployment: Streamlit Community Cloud (free). See DEPLOY.md.
"""
import streamlit as st
from datetime import datetime, timezone

from fetch_fi import (
    load_watchlist,
    save_watchlist,
    quote_for,
    news_for,
    stt_search,
    _fmt_mcap,
    get_stt_key,
    DEFAULT_WATCHLIST,
    MARKET_NOTE,
)


# ---------------------------------------------------------------------------
# Page setup
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Finnish Investment Research Bot",
    page_icon="🇫🇮",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.title("🇫🇮 Finnish Investment Research Bot — Nasdaq Helsinki Watchlist")
st.caption(
    "Free data: **Yahoo Finance** (yfinance, Helsinki .HE symbols) -> quote "
    "in **EUR** + news headlines. **Optional:** STT Info Pörssitiedotteet API "
    "(free key from parse.bot) for Finnish stock-exchange announcements — the "
    "closest thing Finland has to SEC filings. Data refreshes on demand — hit "
    "**Refresh** in the sidebar."
)
st.caption(MARKET_NOTE)


# ---------------------------------------------------------------------------
# Sidebar — watchlist management
# ---------------------------------------------------------------------------
st.sidebar.header("Watchlist")

if "watchlist" not in st.session_state:
    st.session_state.watchlist = load_watchlist()

wl = st.session_state.watchlist  # dict: display_name -> yf_symbol


# --- add ticker ---
st.sidebar.subheader("Add ticker")
add_symbol = st.sidebar.text_input(
    "Yahoo symbol (Helsinki, with .HE)",
    placeholder="e.g. FORTUM.HE",
    help=(
        "Helsinki ticker in Yahoo Finance format, ending in .HE. Examples: "
        "NOKIA.HE, KONE trades as KNEBV.HE, Nordea as NDA-FI.HE, "
        "Kesko as KESKOB.HE, Outokumpu as OUT1V.HE, Orion as ORNBV.HE, "
        "Wärtsilä as WRT1V.HE."
    ),
).strip().upper()

if st.sidebar.button("Add"):
    if not add_symbol:
        st.sidebar.warning("Enter a Yahoo symbol (e.g. FORTUM.HE).")
    elif add_symbol in wl.values():
        st.sidebar.warning(f"{add_symbol} is already in the watchlist.")
    else:
        # best-effort company name lookup
        try:
            import yfinance as yf
            info = yf.Ticker(add_symbol).info or {}
            name = info.get("longName") or info.get("shortName") or ""
        except Exception:
            name = ""
        if not name or name == add_symbol:
            st.sidebar.error(
                f"❌ '{add_symbol}' not recognised by Yahoo Finance. "
                "Check the symbol (must end in .HE for Helsinki)."
            )
        else:
            display = name.split()[0] if name else add_symbol.replace(".HE", "")
            wl[display] = add_symbol
            save_watchlist(wl)
            st.session_state.watchlist = wl
            st.sidebar.success(f"Added {display} ({add_symbol}) — {name}")

st.sidebar.divider()

# --- remove ---
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

# --- reset ---
if st.sidebar.button("Reset to defaults (11 yhtyneet)"):
    st.session_state.watchlist = dict(DEFAULT_WATCHLIST)
    save_watchlist(DEFAULT_WATCHLIST)
    st.sidebar.success("Watchlist reset to the 11 default Finnish yhtyneet.")

st.sidebar.divider()
st.sidebar.caption(
    f"{len(wl)} ticker{'s' if len(wl) != 1 else ''} in watchlist · "
    "Source: Yahoo Finance (yfinance) · Helsinki (.HE) · EUR · "
    "Filings: STT Info Pörssitiedotteet (optional)"
)

# --- STT Info API key (optional) ---
st.sidebar.subheader("STT Info Pörssitiedotteet key (optional)")
stt_key_input = st.sidebar.text_input(
    "API key",
    type="password",
    placeholder="pmx_... (free key from parse.bot)",
    help=(
        "Get a free key at https://parse.bot → marketplace → STT Info "
        "Pörssitiedotteet API. Free tier: 200 credits/month. Without a key, "
        "only Yahoo Finance news is shown (no Finnish filings)."
    ),
)
if stt_key_input:
    st.session_state.stt_key = stt_key_input
else:
    st.session_state.stt_key = get_stt_key()

st.sidebar.divider()

# --- refresh ---
refresh = st.sidebar.button("🔄 Refresh all data")

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Ticker cards
# ---------------------------------------------------------------------------
for display_name in sorted(data.keys()):
    d = data.get(display_name, {})
    q = d.get("quote", {})
    news = d.get("news", [])
    yf_symbol = d.get("yf_symbol", "")

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
                "code (must end in .HE)."
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

        # --- news ---
        st.subheader("📰 Recent News")
        st.markdown(_news_list(news))
        st.caption(
            "News headlines via Yahoo Finance. Some Finnish-market news is in "
            "English; some items may be in Finnish. Click a headline to read the "
            "original source."
        )

        # --- filings (STT Info Pörssitiedotteet, optional) ---
        key = st.session_state.get("stt_key", "") or get_stt_key()
        if key:
            with st.spinner("Fetching Finnish stock-exchange announcements (STT Info) …"):
                filings = stt_search(display_name, key, limit=8)
            st.divider()
            st.subheader("📄 Recent Finnish Announcements (Pörssitiedotteet)")
            if filings and filings[0].get("error"):
                st.warning(filings[0]["error"])
            elif filings:
                for f in filings:
                    fdate = f.get("date", "")
                    fcat = f.get("category", "")
                    ftitle = f.get("title", "(no title)")
                    fpub = f.get("publisher", "")
                    furl = f.get("url", "")
                    cat_str = f"[{fcat}] " if fcat else ""
                    if furl:
                        st.link_button(f"{cat_str}{ftitle}", furl, help=f"{fpub} · {fdate}")
                    else:
                        st.markdown(f"**{cat_str}{ftitle}** — _{fpub}_ · {fdate}")
                st.caption(
                    "Finnish stock-exchange announcements via STT Info "
                    "(https://parse.bot). These are the closest thing Finland has to "
                    "SEC filings — material events disclosed to the market."
                )
            else:
                st.info("No recent Finnish announcements found for this company.")
        elif st.session_state.get("stt_key"):
            # key was set but is now empty
            st.divider()
            st.subheader("📄 Recent Finnish Announcements (Pörssitiedotteet)")
            st.info("STT Info key cleared. Re-enter it in the sidebar to see Finnish filings.")

st.divider()
st.caption(
    "Data sources & limitations: Quotes and news come from Yahoo Finance "
    "(via the yfinance library) using Helsinki (.HE) symbols. Free-user quotes "
    "are delayed (~15 min) and update during the Nasdaq Helsinki session. "
    "Finnish stock-exchange announcements (Pörssitiedotteet) come from STT Info "
    "via https://parse.bot — a free API key is required (see sidebar). This is "
    "not financial advice."
)
