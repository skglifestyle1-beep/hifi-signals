#!/usr/bin/env python3
import os, requests, pandas as pd, datetime as dt

TOKEN   = '8486551379:AAGCvTrIHqkfMVuFc6DTkCcJyfPbt1LQkAA'
CHAT    = '7143200137'
TG_URL  = f'https://api.telegram.org/bot{TOKEN}/sendMessage'
HEADERS = {'User-Agent': 'Mozilla/5.0'}
API     = 'https://www.coinglass.com/pro/v2/futures'

def get(path, params=None):
    r = requests.get(API + path, params=params, headers=HEADERS, timeout=15)
    r.raise_for_status()
    return r.json()

def send(text):
    payload = {'chat_id': CHAT, 'text': text, 'parse_mode': 'Markdown'}
    print(requests.post(TG_URL, data=payload).json())

def main():
    # 1. liquidation clusters
    cl  = pd.DataFrame(get('/liquidation/heatmap?symbol=HIFIUSDT&exchange=all&range=1d')['data'])
    cl  = cl.astype({'price': float, 'longUsd': float, 'shortUsd': float})
    # 2. current price & OI
    oi   = get('/openInterest?symbol=HIFIUSDT&exchange=all')
    price = float(oi['data'][-1]['price'])
    # 3. levels
    top_long  = cl.loc[cl['longUsd'].idxmax()]
    top_short = cl.loc[cl['shortUsd'].idxmax()]
    dist_l  = (top_long['price']  - price) / price
    dist_s  = (price - top_short['price']) / price
    # 4. signals
    alerts = []
    if dist_l < 0.0025:
        alerts.append(
            f"🟢 *HIFI LONG BREAK*\\n"
            f"Entry: `{top_long['price']:.5f}`\\n"
            f"Stop:  `{price*0.99:.5f}`\\n"
            f"TP:    `{price*1.016:.5f}`\\n"
            f"Dist:  {dist_l*100:.2f} %"
        )
    if dist_s < 0.0025:
        alerts.append(
            f"🔴 *HIFI SHORT BREAK*\\n"
            f"Entry: `{top_short['price']:.5f}`\\n"
            f"Stop:  `{price*1.01:.5f}`\\n"
            f"TP:    `{price*0.984:.5f}`\\n"
            f"Dist:  {dist_s*100:.2f} %"
        )
    # 5. send
    for msg in alerts:
        send(msg)

if __name__ == '__main__':
    main()
