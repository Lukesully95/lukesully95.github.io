"""Market data for Luke's Daily Briefing.

Runs in the same GitHub Action as fetch_prices.py and writes briefing-prices.json:
live price, previous close, % change and recent daily closes for every index,
coin and stock the briefing shows. Prices only — no holdings or share counts.
"""
import json
from datetime import datetime, timezone

import yfinance as yf

SYMBOLS = [
    '^GSPC', '^IXIC', '^DJI', 'BTC-USD', 'ETH-USD', '^VIX', 'HUBS',
    'NVDA', 'SPCX', 'NET', 'HODL', 'JOBY', 'AMZN', 'COIN', 'TSLA',
    'SNAP', 'ZM', 'NFLX', 'DIS', 'MRNA',
]


def describe(sym):
    t = yf.Ticker(sym)
    hist = t.history(period='1y', interval='1d', auto_adjust=False)
    closes = [(idx.strftime('%Y-%m-%d'), round(float(c), 4))
              for idx, c in zip(hist.index, hist['Close']) if c == c]
    fi = t.fast_info
    price = fi.last_price
    prev = fi.previous_close
    out = {
        'price': round(float(price), 4) if price else None,
        'prevClose': round(float(prev), 4) if prev else None,
        'changePct': round((price - prev) / prev * 100, 4) if price and prev else None,
        'history': closes[-10:],
        'low52': min(c for _, c in closes) if closes else None,
        'high52': max(c for _, c in closes) if closes else None,
    }
    try:
        mc = fi.market_cap
        if mc:
            out['marketCap'] = int(mc)
    except Exception:
        pass
    return out


data = {}
for sym in SYMBOLS:
    try:
        data[sym] = describe(sym)
        print(f"  {sym}: {data[sym]['price']}")
    except Exception as e:
        print(f"  {sym} error: {e}")
        data[sym] = None

with open('briefing-prices.json', 'w') as f:
    json.dump({'updated': datetime.now(timezone.utc).isoformat(), 'symbols': data}, f, indent=1)
print('Done. briefing-prices.json written.')
