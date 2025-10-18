```python
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
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent='Mozilla/5.0')
        page.goto(URL, wait_until='networkidle')
        for _ in range(30):
            data = page.evaluate('() => window.__NUXT__?.state?.liquidationMap?.data || null')
            if data: break
            page.wait_for_timeout(1000)
        browser.close()
    return pd.DataFrame(data) if data else pd.DataFrame()

def main():
    df = scrape()
    if df.empty:
        print('no data')
        return
    price   = df['price'].iloc[-1]
    top_long  = df.loc[df['longUsd'].idxmax()]
    top_short = df.loc[df['shortUsd'].idxmax()]
    dist_l  = (top_long['price']  - price) / price
    dist_s  = (price - top_short['price']) / price

    alerts = []
    if dist_l < 0.0025:
        alerts.append(f"🟢 *HIFI LONG*\\nEntry `{top_long['price']:.5f}`\\nStop `{price*0.99:.5f}`\\nTP `{price*1.016:.5f}`\\nDist {dist_l*100:.2f}%")
    if dist_s < 0.0025:
        alerts.append(f"🔴 *HIFI SHORT*\\nEntry `{top_short['price']:.5f}`\\nStop `{price*1.01:.5f}`\\nTP `{price*0.984:.5f}`\\nDist {dist_s*100:.2f}%")

    for msg in alerts: send(msg)

if __name__ == '__main__':
    main()
```
