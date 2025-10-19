#!/usr/bin/env python3
import requests, pandas as pd, os, datetime as dt

TOKEN   = os.getenv('TELEGRAM_TOKEN')
CHAT    = os.getenv('TELEGRAM_CHAT')
TG_URL  = f'https://api.telegram.org/bot{TOKEN}/sendMessage'

# ---- paste the fresh URL you copied here ----
JSON_URL = 'https://capi.coinglass.com/api/index/v2/liqHeatMap?merge=true&symbol=Binance_HIFIUSDT&interval=5&limit=288&data=k7Ia9l0WibIdOajxZZ02N%2FLlPpoT3luXJlsuJxJJIYg%3D'

def send(text):
    requests.post(TG_URL, data={'chat_id': CHAT, 'text': text, 'parse_mode': 'Markdown'})

def main():
    r = requests.get(JSON_URL, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
    r.raise_for_status()
    data = r.json()['data']
    df = pd.DataFrame({
        'price':   [float(p) for p in data['price']],
        'longUsd': [float(l) for l in data['longUsd']],
        'shortUsd':[float(s) for p in data['shortUsd']]
    })

    price   = df['price'].iloc[-1]
    top_long  = df.loc[df['longUsd'].idxmax()]
    top_short = df.loc[df['shortUsd'].idxmax()]
    dist_l  = (top_long['price']  - price) / price
    dist_s  = (price - top_short['price']) / price

    summary = (f"📊 HIFI scan {dt.datetime.utcnow():%H:%M} UTC\n"
               f"Price: `{price:.5f}`\n"
               f"Long wall: `{top_long['price']:.5f}`  (dist `{dist_l*100:.2f}%`)\n"
               f"Short wall: `{top_short['price']:.5f}`  (dist `{dist_s*100:.2f}%`)")
    send(summary)
    if dist_l < 0.0025:
        send(f"🟢 LONG Entry `{top_long['price']:.5f}`  Stop `{price*0.99:.5f}`  TP `{price*1.016:.5f}`")
    if dist_s < 0.0025:
        send(f"🔴 SHORT Entry `{top_short['price']:.5f}`  Stop `{price*1.01:.5f}`  TP `{price*0.984:.5f}`")

if __name__ == '__main__':
    main()
