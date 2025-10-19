import os
import json
import datetime as dt
import pandas as pd
import pandas_ta as ta
from market_data import fetch_ohlc, btc_hurricane, funding_bias
from models import Session, Signal

# ---------- config ----------
KILL_ZONE_BREAKER = os.getenv('KILL_ZONE_BREAKER', 'true').lower() == 'true'
MIN_CONFLUENCE    = int(os.getenv('MIN_CONFLUENCE', 3))

# ---------- helpers ----------
def daily_bias() -> str:
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

# ---------- confluence ----------
def liq_confluence(price: float) -> bool:
    """True if entry within 0.2 % of a cached liq-cluster"""
    try:
        with open('liq-cache.json') as f:
            data = json.load(f)
        for c in data.get('clusters', []):
            if abs(price - c) / c <= 0.002:
                return True
        return False
    except (FileNotFoundError, json.JSONDecodeError):
        return True   # fail-open

def confluence_score(sig: dict) -> int:
    score = 0
    # 1. daily bias align
    if sig['side'] == daily_bias(): score += 1
    # 2. funding tail-wind
    if funding_bias(sig['side']): score += 1
    # 3. btc hurricane absent
    if not btc_hurricane(): score += 1
    # 4. inside kill-zone
    t = dt.datetime.utcnow().time()
    if dt.time(13,0) <= t <= dt.time(18,0): score += 1
    # 5. liquidation cluster
    if liq_confluence(sig['entry']): score += 1
    return score

# ---------- kill-zone 15 m breaker ----------
def kill_zone_breaker(level: float, side: str):
    """Sweep → BOS → OB retest inside 13-18 UTC"""
    if not (dt.time(13,0) <= dt.datetime.utcnow().time() <= dt.time(18,0)):
        return None
    df = pd.DataFrame(fetch_ohlc(tf='15m', limit=100),
                      columns=['ts','o','h','l','c','v'])
    latest = df.iloc[-2]   # closed candle

    # 1. SWEEP: pierced the level
    swept = (side=='LONG'  and latest.l <= level) or (side=='SHORT' and latest.h >= level)
    if not swept: return None

    # 2. BOS: close beyond level
    bos = (side=='LONG'  and latest.c > level) or (side=='SHORT' and latest.c < level)
    if not bos: return None

    # 3. opposing-body (OB) = candle before the move
    ob = df.iloc[-3]
    ob_top, ob_bottom = ob.h, ob.l
    entry = (ob_top + ob_bottom) / 2
    sl = ob_bottom - 0.002 if side=='LONG' else ob_top + 0.002
    tp = entry + (entry - sl)*3.0
    return dict(side=side, entry=entry, sl=sl, tp=tp, rr=3.0,
                level=level, vol_mult=latest.v / df.v.rolling(20).mean().iloc[-1])

# ---------- classic 15 m bounce ----------
def classic_bounce(level: float, side: str):
    df = pd.DataFrame(fetch_ohlc(tf='15m', limit=200),
                      columns=['ts','o','h','l','c','v'])
    df['rsi'] = ta.rsi(df.c, 14)
    macd = ta.macd(df.c)
    df['macd'], df['signal'] = macd['MACD_12_26_9'], macd['MACDs_12_26_9']
    df['vol_avg'] = df.v.rolling(20).mean()
    latest = df.iloc[-2]

    vol_mult = 1.3 if dt.time(13,0) <= dt.datetime.utcnow().time() <= dt.time(18,0) else 2.0
    if latest.v < df.vol_avg.iloc[-1] * vol_mult: return None

    if side=='LONG':
        touch = latest.l <= level
        candle = latest.c > latest.o and (latest.c-latest.o)/latest.o > 0.4
        rsi_ok = 30 <= latest.rsi <= 40
        macd_x = df.macd.iloc[-2]>df.signal.iloc[-2] and df.macd.iloc[-3]<=df.signal.iloc[-3]
        if touch and candle and rsi_ok and macd_x:
            sl = latest.l - 0.003
            tp = level + (level - sl)*3.2
            return dict(side='LONG', entry=latest.c, sl=sl, tp=tp, rr=3.2,
                        level=level, vol_mult=latest.v/df.vol_avg.iloc[-1])
    else:  # SHORT
        touch = latest.h >= level
        candle = latest.c < latest.o and (latest.o-latest.c)/latest.o > 0.4
        rsi_ok = 60 <= latest.rsi <= 70
        macd_x = df.macd.iloc[-2]<df.signal.iloc[-2] and df.macd.iloc[-3]>=df.signal.iloc[-3]
        if touch and candle and rsi_ok and macd_x:
            sl = latest.h + 0.003
            tp = level - (sl - level)*3.2
            return dict(side='SHORT', entry=latest.c, sl=sl, tp=tp, rr=3.2,
                        level=level, vol_mult=latest.v/df.vol_avg.iloc[-1])
    return None

# ---------- unified confirm ----------
def confirm(side: str, level: float):
    # 0) global guards
    if btc_hurricane(): return None
    if not funding_bias(side): return None
    with Session() as s:
        last_two = s.query(Signal).order_by(Signal.ts.desc()).limit(2).all()
    if len(last_two)==2 and [t.outcome for t in last_two]==['LOSS','LOSS']:
        if (dt.datetime.utcnow() - last_two[1].ts).total_seconds() < 86400:
            return None

    sig = None
    if KILL_ZONE_BREAKER:
        sig = kill_zone_breaker(level, side)
    if not sig:                       # fallback
        sig = classic_bounce(level, side)

    if sig and confluence_score(sig) >= MIN_CONFLUENCE:
        return sig
    return None
