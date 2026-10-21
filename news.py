import calendar
from datetime import datetime, timezone
from urllib.parse import quote

import feedparser
import requests
import streamlit as st

st.set_page_config(
    page_title="HM | Macro Newswire",
    page_icon="📈",
    layout="wide"
)

TOPICS = {
    "Bond Yields": "Canada US Treasury bond yields",
    "Central Banks": "Bank of Canada Federal Reserve interest rates",
    "Inflation": "Canada US CPI inflation economy",
    "FX & Credit": "USD CAD foreign exchange credit spreads"
}

@st.cache_data(ttl=1800)
def fetch_news():
    articles = []
    for category, query in TOPICS.items():
        url = (
            "https://news.google.com/rss/search?q="
            + quote(query + " when:2d")
            + "&hl=en-CA&gl=CA&ceid=CA:en"
        )
        try:
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            feed = feedparser.parse(response.content)

            for entry in feed.entries[:8]:
                published = (
                    calendar.timegm(entry.published_parsed)
                    if entry.get("published_parsed")
                    else 0
                )
                articles.append({
                    "title": entry.title,
                    "link": entry.link,
                    "category": category,
                    "published": published,
                    "source": entry.get("source", {}).get("title", "News")
                })
        except (requests.RequestException, ValueError):
            continue

    unique = {}
    for article in articles:
        unique.setdefault(article["link"], article)

    return sorted(
        unique.values(),
        key=lambda x: x["published"],
        reverse=True
    )

st.markdown("### MACRO NEWSWIRE")
st.title("Markets in Focus")
st.caption(
    "External financial news • Automatically refreshed "
    "every 30 minutes while the app is active"
)

category = st.selectbox(
    "Filter headlines",
    ["All News"] + list(TOPICS.keys())
)

articles = fetch_news()
if category != "All News":
    articles = [
        article for article in articles
        if article["category"] == category
    ]

if not articles:
    st.info("No headlines currently available.")
else:
    for article in articles[:8]:
        st.caption(article["category"].upper())
        st.markdown(f"**{article['title']}**")
        date = (
            datetime.fromtimestamp(
                article["published"], timezone.utc
            ).strftime("%b %d, %Y %H:%M UTC")
            if article["published"] else "Date unavailable"
        )
        st.caption(f"{article['source']} • {date}")
        st.link_button(
            "Read original article ↗",
            article["link"]
        )
        st.divider()
