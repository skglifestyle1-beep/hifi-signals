import requests, pandas as pd, datetime as dt, os

SYMBOL = 'HIFIUSDT'
INTERVAL = '4h'          # binance uses 5-min slices → we resample
URL = 'https://fapi.binance.com/futures/data/topTraderLiquidation'

def fetch_binance_liq():
    """
    Returns DataFrame[price, longLiq, shortLiq, total]  newest-first
    Binance gives 5-min data for last 4 days → we resample to 4h
    """
    params = {'symbol': SYMBOL, 'period': '5m', 'limit': 500}
    r = requests.get(URL, params=params, timeout=10)
    r.raise_for_status()
    df = pd.DataFrame(r.json())
    df = df.astype({'price': float, 'longLiq': float, 'shortLiq': float})
    df['total'] = df['longLiq'] + df['shortLiq']
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('timestamp', inplace=True)
    # resample 5m → 4h  (sum liquidations, last price)
    df = df.resample('4h').agg({'price': 'last', 'longLiq': 'sum',
                                  'shortLiq': 'sum', 'total': 'sum'})
    df.dropna(inplace=True)
    df['price'] = df['price'].ffill()
    return df.sort_values('timestamp', ascending=False)

def liq_clusters(df, thresh_usd=1_000_000, merge_pips=0.25/100):
    """Return list of mid-prices where total liq > thresh within merge band"""
    big = df[df.total >= thresh_usd].copy()
    clusters, cur = [], None
    for _, row in big.iterrows():
        if cur is None:
            cur = {'p0': row.price, 'p1': row.price, 'vol': row.total}
            continue
        if abs(row.price - cur['p1'])/cur['p1'] <= merge_pips:
            cur['p1'] = row.price
            cur['vol'] += row.total
        else:
            clusters.append(cur)
            cur = {'p0': row.price, 'p1': row.price, 'vol': row.total}
    if cur: clusters.append(cur)
    return [(c['p0']+c['p1'])/2 for c in clusters if c['vol'] >= thresh_usd]

def update_liq_cache():
    df = fetch_binance_liq()
    clusters = liq_clusters(df)
    # save tiny json for bot
    out = {'clusters': clusters, 'updated': dt.datetime.utcnow().isoformat()}
    with open('liq-cache.json', 'w') as f:
        import json
        json.dump(out, f)
    return clusters
