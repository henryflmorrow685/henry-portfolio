import os
from datetime import date, timedelta
from io import StringIO

import pandas as pd
import plotly.express as px
import streamlit as st
import yfinance as yf
from streamlit_autorefresh import st_autorefresh

st.set_page_config(page_title="Henry Morrow | Portfolio Lab", layout="wide")
st_autorefresh(interval=15 * 60 * 1000, key="portfolio_auto_refresh")

INITIAL_CAD = 10000.0
START = "2026-08-31"
COLUMNS = ["Date", "Ticker", "Side", "Quantity", "Price", "Currency", "FX_Rate", "Fee_CAD"]

st.markdown("""<style>
.stApp {background-color: #080E17; color:#F2F6FC;}
[data-testid="stMetric"] {background:#121E2D; border:1px solid #243448; padding:14px; border-radius:9px;}
h1,h2,h3 {color:#F2F6FC;}
</style>""", unsafe_allow_html=True)


def sheet_url():
    url = os.environ.get("SHEET_CSV_URL", "")
    try:
        url = st.secrets.get("SHEET_CSV_URL", url)
    except Exception:
        pass
    return str(url).strip()


@st.cache_data(ttl=300, show_spinner=False)
def read_transactions(csv_url: str) -> pd.DataFrame:
    if csv_url:
        if not csv_url.startswith("https://"):
            raise ValueError("SHEET_CSV_URL must begin with https://")
        df = pd.read_csv(csv_url)
    else:
        df = pd.read_csv("transactions.csv")
    missing = set(COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(f"Missing spreadsheet columns: {', '.join(sorted(missing))}")
    df = df.loc[:, COLUMNS].copy()
    df["Date"] = pd.to_datetime(df["Date"], errors="raise").dt.normalize()
    df["Ticker"] = df["Ticker"].astype(str).str.strip().str.upper()
    df["Side"] = df["Side"].astype(str).str.strip().str.upper()
    df["Currency"] = df["Currency"].astype(str).str.strip().str.upper()
    for key in ["Quantity", "Price", "FX_Rate", "Fee_CAD"]:
        df[key] = pd.to_numeric(df[key], errors="raise")
    if df.empty:
        raise ValueError("The transaction log is empty.")
    if not df["Side"].isin(["BUY", "SELL"]).all():
        raise ValueError("Side must be BUY or SELL.")
    if not df["Currency"].isin(["USD", "CAD"]).all():
        raise ValueError("Currency must be CAD or USD.")
    if (df[["Quantity", "Price", "FX_Rate"]] <= 0).any().any() or (df["Fee_CAD"] < 0).any():
        raise ValueError("Quantity, Price and FX_Rate must be positive; fees must be nonnegative.")
    if df["Date"].min() < pd.Timestamp(START):
        raise ValueError(f"Transactions before inception {START} are not supported.")
    if df["Date"].max() > pd.Timestamp(date.today()):
        raise ValueError("Future dated transactions are not supported.")
    if (df.loc[df["Currency"] == "CAD", "FX_Rate"] != 1).any():
        raise ValueError("For CAD stocks, FX_Rate must be 1.")
    if df.groupby("Ticker")["Currency"].nunique().max() > 1:
        raise ValueError("A ticker cannot use more than one currency.")
    # Validate sequential trades (within a day, rows in spreadsheet order).
    shares = {}
    cash = INITIAL_CAD
    for t in df.sort_values("Date", kind="stable").itertuples(index=False):
        shares.setdefault(t.Ticker, 0.0)
        cost_cad = float(t.Quantity) * float(t.Price) * float(t.FX_Rate)
        if t.Side == "BUY":
            cash -= cost_cad + float(t.Fee_CAD)
            shares[t.Ticker] += float(t.Quantity)
        else:
            if t.Quantity > shares[t.Ticker] + 1e-7:
                raise ValueError(f"Sale exceeds holdings for {t.Ticker} on {t.Date.date()}.")
            cash += cost_cad - float(t.Fee_CAD)
            shares[t.Ticker] -= float(t.Quantity)
        if cash < -0.02:
            raise ValueError(f"Insufficient CAD cash on {t.Date.date()}. Enter a smaller BUY or sell another holding first.")
    return df.sort_values("Date", kind="stable")


@st.cache_data(ttl=1800, show_spinner=False)
def fetch_close(tickers: tuple[str, ...]) -> pd.DataFrame:
    all_tickers = list(tickers) + ["CAD=X"]
    raw = yf.download(
        all_tickers, start=START, end=(date.today() + timedelta(days=1)).isoformat(),
        auto_adjust=False, progress=False, threads=False, group_by="column"
    )
    if raw.empty:
        raise ValueError("The market-data provider returned no prices.")
    close = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw[["Close"]].rename(columns={"Close": all_tickers[0]})
    close.index = pd.to_datetime(close.index).tz_localize(None).normalize()
    close = close.sort_index().ffill()
    absent = [t for t in all_tickers if t not in close.columns or close[t].isna().all()]
    if absent:
        raise ValueError(f"Missing market prices: {', '.join(absent)}. Check ticker symbols or try again later.")
    return close


def compute_history(transactions: pd.DataFrame, close: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, float]:
    currencies = transactions.drop_duplicates("Ticker").set_index("Ticker")["Currency"].to_dict()
    position = {t: 0.0 for t in currencies}
    cash = INITIAL_CAD
    records = []
    daily = []
    ix = 0
    trades = list(transactions.itertuples(index=False))
    for day, row in close.iterrows():
        while ix < len(trades) and trades[ix].Date <= day:
            tr = trades[ix]
            amount = tr.Quantity * tr.Price * tr.FX_Rate
            if tr.Side == "BUY":
                cash -= amount + tr.Fee_CAD
                position[tr.Ticker] += tr.Quantity
            else:
                cash += amount - tr.Fee_CAD
                position[tr.Ticker] -= tr.Quantity
            ix += 1
        total = cash
        for ticker, qty in position.items():
            if abs(qty) < 1e-10:
                continue
            px = row.get(ticker, float("nan"))
            fx = row["CAD=X"] if currencies[ticker] == "USD" else 1.0
            if pd.isna(px) or pd.isna(fx):
                raise ValueError(f"Missing {ticker} or FX close on {day.date()}.")
            value = float(qty * px * fx)
            total += value
        daily.append({"Date": day, "Value CAD": total, "Return %": (total / INITIAL_CAD - 1) * 100})
    if ix != len(trades):
        st.warning("Some very recent trades are not yet reflected because the market has not published a closing price for their date.")
    if not daily:
        raise ValueError("No daily valuation dates were retrieved.")
    last = close.iloc[-1]
    for ticker, qty in position.items():
        if qty <= 1e-9:
            continue
        fx = float(last["CAD=X"]) if currencies[ticker] == "USD" else 1.0
        px = float(last[ticker])
        records.append({"Ticker": ticker, "Shares": qty, "Currency": currencies[ticker],
                        "Latest Close": px, "FX (CAD/unit)": fx, "Market Value CAD": qty * px * fx})
    return pd.DataFrame(daily), pd.DataFrame(records), cash


st.caption("HM / MARKETS / EQUITY PORTFOLIO")
st.title("Portfolio Lab")
st.caption("SIMULATED · CAD BASE CURRENCY · DAILY CLOSING PRICES · PRICE RETURN ONLY")
url = sheet_url()
if not url:
    st.warning("DEMO DATA SOURCE: reading the initial transaction file. To enable edits from Google Sheets, add the published sheet CSV URL to your Streamlit app secrets as SHEET_CSV_URL.")

try:
    tx = read_transactions(url)
    prices = fetch_close(tuple(sorted(tx["Ticker"].unique())))
    hist, holdings, cad_cash = compute_history(tx, prices)
    latest_value = float(hist["Value CAD"].iloc[-1])
    daily_change = latest_value - float(hist["Value CAD"].iloc[-2]) if len(hist) > 1 else 0.0
    a, b, c, d = st.columns(4)
    a.metric("Market Value", f"C${latest_value:,.2f}")
    b.metric("Since Inception", f"{(latest_value / INITIAL_CAD - 1) * 100:+.2f}%")
    c.metric("Change vs Previous Close", f"C${daily_change:+,.2f}")
    d.metric("Cash", f"C${cad_cash:,.2f}")
    st.caption(f"Latest closing-price date: {hist['Date'].iloc[-1].date()} · Sheet changes typically appear within approximately 5–20 minutes while the app is open; market-price updates depend on the data source.")
    st.subheader("Portfolio performance")
    st.line_chart(hist.set_index("Date")["Value CAD"], x_label="Date", y_label="Portfolio value (CAD)")
    left, right = st.columns([2, 1])
    with left:
        st.subheader("Current holdings")
        if holdings.empty:
            st.info("No stock holdings. Portfolio is all cash.")
        else:
            st.dataframe(holdings, hide_index=True, use_container_width=True, column_config={
                "Shares": st.column_config.NumberColumn(format="%.6f"),
                "Latest Close": st.column_config.NumberColumn(format="%.2f"),
                "FX (CAD/unit)": st.column_config.NumberColumn(format="%.4f"),
                "Market Value CAD": st.column_config.NumberColumn(format="$%.2f"),
            })
    with right:
        st.subheader("Allocation")
        if not holdings.empty:
            fig = px.pie(holdings, names="Ticker", values="Market Value CAD", hole=0.58)
            fig.update_layout(paper_bgcolor="#080E17", plot_bgcolor="#080E17", font_color="#F2F6FC", showlegend=True, margin=dict(l=0,r=0,t=10,b=0))
            st.plotly_chart(fig, use_container_width=True)
    with st.expander("Transaction history"):
        st.dataframe(tx, hide_index=True, use_container_width=True)
    st.caption("Educational simulated portfolio. Figures use provider closing prices and recorded trade prices; dividends, taxes, corporate actions (including splits), and external cash flows are not automatically modeled. Validate all prices before relying on the results. Not investment advice.")
except Exception as exc:
    st.error(f"Unable to calculate portfolio: {exc}")
    st.info("Check the public CSV link, ticker symbols, transaction amounts, and available market-data history.")
