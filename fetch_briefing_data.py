"""Market data for Luke's Daily Briefing.

Runs in the same GitHub Action as fetch_prices.py (and on demand from the briefing
task via workflow_dispatch) and writes briefing-prices.json.

Per symbol:
  price        latest trade, INCLUDING pre-market / after-hours (1-minute bars, prepost)
  priceTime    ET timestamp of that trade;  priceDate = its ET date (YYYY-MM-DD)
  session      "pre" | "regular" | "post" | "closed" | "24h" (crypto)
  prevClose    the last regular-session close BEFORE priceDate (computed from daily
               history — yfinance's fast_info.previous_close is unreliable)
  changePct    (price - prevClose) / prevClose * 100
  history      last 10 regular-session daily closes [[date, close], ...]
  low52/high52, marketCap (when available)
Prices only — no holdings or share counts.
"""
import json
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import yfinance as yf

ET = ZoneInfo('America/New_York')

SYMBOLS = [
    '^GSPC', '^IXIC', '^DJI', 'BTC-USD', 'ETH-USD', '^VIX', 'HUBS',
    'NVDA', 'SPCX', 'NET', 'HODL', 'JOBY', 'AMZN', 'COIN', 'TSLA',
    'SNAP', 'ZM', 'NFLX', 'DIS', 'MRNA',
    # index futures: the only live read on the indices before 9:30am ET
    'ES=F', 'NQ=F', 'YM=F',
]


def session_for(ts_et, sym):
    if sym.endswith('-USD'):
        return '24h'
    if sym.endswith('=F'):
        return 'futures'
    if ts_et.weekday() >= 5:
        return 'closed'
    hm = ts_et.hour * 60 + ts_et.minute
    if 4 * 60 <= hm < 9 * 60 + 30:
        return 'pre'
    if 9 * 60 + 30 <= hm < 16 * 60:
        return 'regular'
    if 16 * 60 <= hm < 20 * 60:
        return 'post'
    return 'closed'


def describe(sym):
    t = yf.Ticker(sym)
    daily = t.history(period='1y', interval='1d', auto_adjust=False)
    closes = []
    for idx, c in zip(daily.index, daily['Close']):
        if c == c:
            d = idx.tz_convert(ET) if idx.tzinfo else idx
            closes.append((d.strftime('%Y-%m-%d'), round(float(c), 4)))

    price, ts = None, None
    try:
        intra = t.history(period='5d', interval='1m', prepost=True, auto_adjust=False)
        intra = intra[intra['Close'] == intra['Close']]
        if len(intra):
            price = float(intra['Close'].iloc[-1])
            ts = intra.index[-1]
            ts = ts.tz_convert(ET) if ts.tzinfo else ts.replace(tzinfo=ET)
    except Exception as e:
        print(f'  {sym} intraday error: {e}')

    if price is None and closes:  # fall back to last daily close
        price = closes[-1][1]
        ts = datetime.strptime(closes[-1][0], '%Y-%m-%d').replace(hour=16, tzinfo=ET)

    price_date = ts.strftime('%Y-%m-%d') if ts else None
    before = [c for d, c in closes if price_date and d < price_date]
    prev = before[-1] if before else None
    if sym.endswith('-USD') and ts is not None:
        # crypto trades 24h: compare with the price 24 hours earlier
        try:
            ago = intra[intra.index <= intra.index[-1] - __import__('pandas').Timedelta(hours=24)]
            if len(ago):
                prev = float(ago['Close'].iloc[-1])
        except Exception:
            pass
    # If the latest trade is from a day with no completed bar yet, history ends on the prior day.
    out = {
        'price': round(price, 4) if price else None,
        'priceTime': ts.isoformat() if ts else None,
        'priceDate': price_date,
        'session': session_for(ts, sym) if ts else None,
        'prevClose': round(prev, 4) if prev else None,
        'prevCloseDate': None if sym.endswith('-USD') else next((d for d, c in reversed(closes) if price_date and d < price_date), None),
        'changePct': round((price - prev) / prev * 100, 4) if price and prev else None,
        'history': closes[-10:],
        'low52': min(c for _, c in closes) if closes else None,
        'high52': max(c for _, c in closes) if closes else None,
    }
    try:
        mc = t.fast_info.market_cap
        if mc:
            out['marketCap'] = int(mc)
    except Exception:
        pass
    return out


data = {}
for sym in SYMBOLS:
    try:
        data[sym] = describe(sym)
        s = data[sym]
        print(f"  {sym}: {s['price']} ({s['session']} {s['priceTime']}) vs {s['prevClose']} {s['prevCloseDate']} -> {s['changePct']}%")
    except Exception as e:
        print(f'  {sym} error: {e}')
        data[sym] = None

with open('briefing-prices.json', 'w') as f:
    json.dump({'updated': datetime.now(timezone.utc).isoformat(), 'symbols': data}, f, indent=1)
print('Done. briefing-prices.json written.')
