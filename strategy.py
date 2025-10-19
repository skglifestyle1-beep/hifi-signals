import pandas as pd, pandas_ta as ta, datetime as dt
from market_data import fetch_ohlc, btc_hurricane, funding_bias
from models import Session, Signal

VOL_MULT = 1.5

def daily_bias():
    df = pd.DataFrame(fetch_ohlc(tf='1d', limit=100),
                      columns=['ts','o','h','l','c','v'])
    df['ema'] = ta.ema(df.c, length=50)
    macd = ta.macd(df.c)
    df['macd'], df['signal'] = macd['MACD_12_26_9'], macd['MACDs_12_26_9']
    last = df.iloc[-1]
    if last.c > last.ema and last.macd > last.signal: return 'LONG'
    if last.c < last.ema and last.macd < last.signal: return 'SHORT'
    return 'NONE'

def key_levels():
    df = pd.DataFrame(fetch_ohlc(tf='1d', limit=100),
                      columns=['ts','o','h','l','c','v'])
    df['avg_vol'] = df.v.rolling(20).mean()
    # swing 8 % + vol spike
    df['sh'] = (df.h == df.h.rolling(20).max()) & (df.v > df.avg_vol*2) & (df.h.rolling(10).max()/df.l.rolling(10).min() > 1.08)
    df['sl'] = (df.l == df.l.rolling(20).min()) & (df.v > df.avg_vol*2) & (df.h.rolling(10).max()/df.l.rolling(10).min() > 1.08)
    resist = df[df.sh].h.tail(5).tolist()
    support= df[df.sl].l.tail(5).tolist()
    return support, resist

def confirm(signal_side:str, level:float):
    # 0) session filter
    utc_t = dt.datetime.utcnow().time()
    prime = dt.time(13,0) <= utc_t <= dt.time(18,0)
    if not prime: return None

    # 1) BTC hurricane
    if btc_hurricane(): return None

    # 2) funding
    if not funding_bias(signal_side): return None

    # 3) loss cool-down
    with Session() as s:
        last_two = s.query(Signal).order_by(Signal.ts.desc()).limit(2).all()
    if len(last_two)==2 and [t.outcome for t in last_two]==['LOSS','LOSS']:
        if (dt.datetime.utcnow() - last_two[1].ts).total_seconds() < 86400:
            return None

    # 4) 15 m confirmation
    df = pd.DataFrame(fetch_ohlc(tf='15m', limit=200),
                      columns=['ts','o','h','l','c','v'])
    df['rsi'] = ta.rsi(df.c, 14)
    macd = ta.macd(df.c)
    df['macd'], df['signal'] = macd['MACD_12_26_9'], macd['MACDs_12_26_9']
    df['vol_avg'] = df.v.rolling(20).mean()
    latest = df.iloc[-2]   # closed candle

    vol_mult = 1.3 if prime else 2.0
    if latest.v < latest.vol_avg * vol_mult: return None

    if signal_side=='LONG':
        touch = latest.l <= level
        candle = latest.c > latest.o and (latest.c-latest.o)/latest.o > 0.4
        rsi_ok = 30 <= latest.rsi <= 40
        macd_x = df.macd.iloc[-2]>df.signal.iloc[-2] and df.macd.iloc[-3]<=df.signal.iloc[-3]
        if touch and candle and rsi_ok and macd_x:
            sl = latest.l - 0.003
            tp = level + (level - sl)*3.2
            return dict(side='LONG', entry=latest.c, sl=sl, tp=tp, rr=3.2, level=level)
    else:  # SHORT
        touch = latest.h >= level
        candle = latest.c < latest.o and (latest.o-latest.c)/latest.o > 0.4
        rsi_ok = 60 <= latest.rsi <= 70
        macd_x = df.macd.iloc[-2]<df.signal.iloc[-2] and df.macd.iloc[-3]>=df.signal.iloc[-3]
        if touch and candle and rsi_ok and macd_x:
            sl = latest.h + 0.003
            tp = level - (sl - level)*3.2
            return dict(side='SHORT', entry=latest.c, sl=sl, tp=tp, rr=3.2, level=level)
    return None
