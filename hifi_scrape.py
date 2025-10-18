#!/usr/bin/env python3
from playwright.sync_api import sync_playwright
import pandas as pd, os, requests, datetime as dt

TOKEN   = os.getenv('TELEGRAM_TOKEN')
CHAT    = os.getenv('TELEGRAM_CHAT')
TG_URL  = f'https://api.telegram.org/bot{TOKEN}/sendMessage'

URL = 'https://www.coinglass.com/pro/futures/LiquidationHeatMap?coin=HIFI'

def send(text):
    requests.post(TG_URL, data={'chat_id': CHAT, 'text': text, 'parse_mode': 'Markdown'})

def scrape():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,           # real browser
            args=['--disable-blink-features=AutomationControlled']
        )
        page = browser.new_page(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36'
        )
        page.goto(URL, wait_until='networkidle')

        # wait for canvas + brute-force JS globals
        page.wait_for_selector('canvas', timeout=20_000)
        for _ in range(40):
            data = page.evaluate('''() => {
                const win = window || {};
                return  win.__NUXT__?.state?.liquidationMap?.data ||
                        win.liquidationData ||
                        win.heatmapData ||
                        win.state?.liquidationMap ||
                        null;
            }''')
            if data: break
            page.wait_for_timeout(1000)

        browser.close()
    return pd.DataFrame(data) if data else pd.DataFrame()

def main():
    try:
        df = scrape()
        if df.empty:
            send("⚠️ HIFI scrape returned empty")
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
    except Exception as e:
        send(f"💥 Crash: {e}")
        raise

if __name__ == '__main__':
    main()
