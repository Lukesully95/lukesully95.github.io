import yfinance as yf
import json
from datetime import datetime, timezone

SYMBOLS = ['AMZN', 'COIN', 'DIS', 'HODL', 'JOBY', 'MRNA', 'NET', 'NFLX', 'NVDA', 'SNAP', 'TSLA', 'ZM']

data = {}
try:
    tickers = yf.Tickers(' '.join(SYMBOLS))
    for sym in SYMBOLS:
        try:
            t = tickers.tickers[sym]
            fi = t.fast_info
            price = fi.last_price
            prev  = fi.previous_close
            chg   = round(price - prev, 4) if price and prev else None
            chgPct= round((price - prev) / prev * 100, 4) if price and prev else None
            data[sym] = {
                'price':     round(price, 4) if price else None,
                'change':    chg,
                'changePct': chgPct,
                'prevClose': round(prev, 4) if prev else None,
            }
            print(f"  {sym}: ${price}")
        except Exception as e:
            print(f"  {sym} error: {e}")
            data[sym] = {'price': None, 'change': None, 'changePct': None, 'prevClose': None}
except Exception as e:
    print(f"Tickers error: {e}")

output = {
    'updated': datetime.now(timezone.utc).isoformat(),
    'prices': data
}
with open('prices.json', 'w') as f:
    json.dump(output, f, indent=2)
print("Done. prices.json written.")
