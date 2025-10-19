import os, ccxt, pandas as pd, pandas_ta as ta, datetime as dt
from dotenv import load_dotenv
load_dotenv()

SYMBOL = 'HIFI/USDT'
BTC    = 'BTC/USDT'

exchange = ccxt.binance({
    'apiKey': None,   # signal-only
    'secret': None,
    'options': {'defaultType': 'future'}
})

def fetch_ohlc(symbol=SYMBOL, tf='15m', limit=200):
    return exchange.fetch_ohlcv(symbol, timeframe=tf, limit=limit)

def btc_hurricane():
    df = pd.DataFrame(fetch_ohlc(BTC, '1h', 50),
                      columns=['ts','o','h','l','c','v'])
    atr = ta.atr(df.h, df.l, df.c, length=24).iloc[-1]
    price = df.c.iloc[-1]
    return (atr / price) > 0.05

def funding_bias(side:str):
    f = exchange.fetch_funding_rate(SYMBOL)['fundingRate']
    if side=='LONG'  and float(f) >  0.00045: return False
    if side=='SHORT' and float(f) < -0.00045: return False
    return True

def usd_size(sl_dist, capital):
    risk_amt = capital * 0.01          # 1 %
    return round(risk_amt / sl_dist, 2)
