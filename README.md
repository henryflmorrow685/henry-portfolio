# Henry Morrow – Portfolio Lab

A free Streamlit portfolio dashboard that reads a public Google Sheets CSV of transactions, values stocks in CAD using Yahoo Finance closing prices, and can be embedded in Framer.

## 1. Create your Google Sheet

Open Google Sheets, create a blank workbook named `HM Portfolio`, rename the first tab `Transactions`, and import or paste the entire `transactions.csv` file. Confirm the header is on row 1.

**Each subsequent trade gets a NEW ROW. Never replace the original purchase row.** For a new buy or sell, enter `Date` (YYYY-MM-DD), `Ticker` (Yahoo symbol; Toronto stocks end in `.TO`), `Side` (`BUY` or `SELL`), `Quantity`, `Price` in security currency, `Currency` (`CAD` or `USD`), `FX_Rate` (CAD per 1 USD for USD transactions, `1` for CAD), `Fee_CAD` (0 if none). Price and FX must be actual trade-day prices; do not use today's FX for a past trade. Purchases must be funded by available simulated CAD cash. There is a C$10,000 starting balance and no added deposit workflow. Rebalance by SELL then BUY.

## 2. Publish ONLY the Transactions tab

In Google Sheets: File → Share → Publish to web → choose the Transactions sheet → Comma-separated values (.csv) → Publish. Copy the provided **published CSV** link. This exposes the transaction history publicly: DO NOT include personal information or real account identifiers. Publishing is not the same as making the entire Google Sheet editable. If Google changes menu names, refer to Google Sheets help.

## 3. Create a GitHub repository

Create a new public repository (e.g. `hm-portfolio-lab`). Upload these three files: `app.py`, `requirements.txt`, `transactions.csv`. Do NOT upload API keys or secrets. The default transactions file is for testing only; the live Google Sheet overrides it when configured.

## 4. Deploy for free with Streamlit

Go to https://share.streamlit.io/ → New app → choose GitHub repo, branch `main`, and file `app.py`. In Advanced settings → Secrets, enter:

```toml
SHEET_CSV_URL = "PASTE_YOUR_PUBLISHED_CSV_URL_HERE"
```

Deploy. You will get a `*.streamlit.app` URL. Update secrets if the link changes.

## 5. Put dashboard on Framer

Open your Framer project → Insert → Embed → paste the Streamlit URL. Give the Embed generous height (~900–1100 px). If iframe is blocked, add a button linking to the Streamlit app instead. Publish your Framer site.

## How updates work

- Every buy/sell is a new spreadsheet row. The app re-reads the CSV on a 5-minute cache.
- An open app refreshes every 15 minutes and prices are cached for 30 minutes.
- After market close, the latest available market close is picked up on a subsequent refresh/visit. No paid scheduling service is necessary for this version.
- Google published CSV propagation, provider outages, and hosted app suspension can delay updates; this is NOT guaranteed instant or live trading data.
- Existing history is based on recorded trades. DO NOT simply overwrite old quantities, or prior history will become inaccurate.

## Important limitations

1. Price-return methodology only: no dividend cash credit or automatic split/corporate-action handling. A split would require a ledger adjustment or code changes.
2. Recorded BUY/SELL prices and FX must match the trade; the daily curve uses closing prices and reflects trades by their dates. Historical same-day intraday cash movements are simplified.
3. This starter supports trading with the existing cash balance only, not deposits/withdrawals; a more advanced version should add cash flows and time-weighted return calculations.
4. If ticker symbols or market prices are missing, it displays an error instead of invented values.
5. Validate prices and exchange rates against your original portfolio. Unofficial Yahoo Finance feeds may have availability, data quality, or usage restrictions.
