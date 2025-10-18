#!/usr/bin/env python3
from playwright.sync_api import sync_playwright
import pandas as pd, os, requests, datetime as dt, base64

TOKEN   = os.getenv('TELEGRAM_TOKEN')
CHAT    = os.getenv('TELEGRAM_CHAT')
TG_URL  = f'https://api.telegram.org/bot{TOKEN}/sendMessage'

URL = 'https://www.coinglass.com/pro/futures/LiquidationHeatMap?coin=HIFI'

def send(text):
    requests.post(TG_URL, data={'chat_id': CHAT, 'text': text, 'parse_mode': 'Markdown'})

def scrape():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent='Mozilla/5.0')
        page.goto(URL, wait_until='networkidle')

        # 1. screenshot for debugging (upload as artifact)
        png = page.screenshot()
        with open('page.png','wb') as f: f.write(png)

        # 2. try multiple global names
        for _ in range(40):   # 40 s max
            data = page.evaluate('''() => {
                const win = window || {};
                return  win.__NUXT__?.state?.liquidationMap?.data ||
                        win.liquidationData ||
                        win.heatmapData ||
                        null;
            }''')
            if data: break
            page.wait_for_timeout(1000)

        browser.close()
    return pd.DataFrame(data) if data else pd.DataFrame()

def main():
    df = scrape()
    if df.empty:
        # upload screenshot so we can see what’s rendered
        with open('page.png','rb') as f:
            img = base64.b64encode(f.read()).decode()
        send(f"⚠️ HIFI empty – debug pic\n<img src='data:image/png;base64,{img}'>")
        return

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
