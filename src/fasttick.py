import certifi
import glob
import json
import os
import pickle
import time
import urllib3


# This will be called in __init__ for GUIfastmarket class, it will
#  delete all old pickle files so we start with a clean dataset.
def delete_ancient_pickles(max_range=0):
    max_range = abs(max_range)
    files = glob.glob('fast_history/*pickle')
    files.sort(key=os.path.getmtime)
    for i in range(len(files)-max_range):
        os.remove(files[i])


def save_pickle(latest_data, cfg):
    date_time = time.strftime('%M%S', time.localtime())
    with open('fast_history/' + date_time + '.pickle', 'wb') as f:
        pickle.dump(latest_data, f, protocol=pickle.HIGHEST_PROTOCOL)
    delete_ancient_pickles(cfg.FASTTICK_LB)


# Getting filenames for last(LOOKBACK) pickle files and
#   removing files that are out of date.
def open_pickles(cfg):
    files = glob.glob('fast_history/*pickle')
    if not files:
        return []
    files.sort(key=os.path.getmtime)
    for file in files[cfg.FASTTICK_LB:]:
        with open(file, 'rb') as f:
            yield pickle.load(f)


def heartbeat(cfg):
    http = urllib3.PoolManager(cert_reqs='CERT_REQUIRED', ca_certs=certifi.where())
    page = http.request('GET', 'https://bittrex.com/api/v2.0/pub/Markets/GetMarketSummaries').data
    data = json.loads(page)

    # Processing for saving latest data from Bittrex API
    latest_data = {}
    for i in data['result']:
        name = i['Market']['MarketCurrencyLong']
        last_price = i['Summary']['Last']
        last_vol = i['Summary']['BaseVolume']
        if i['Market']['BaseCurrency'] == 'BTC' and last_price >= \
                cfg.FASTTICK_MIN_PRICE and last_vol >= cfg.FASTTICK_MIN_VOL:
                    latest_data[name] = {'Market': i['Market'], 'Summary': i['Summary']}

    # Processing all data within 9 ticks + latest and returning
    #  rate for output in GUI
    prev_data = list(open_pickles(cfg))
    prev_data.append(latest_data)
    ticker_data = []
    if prev_data:
        for name in latest_data:
            prev_changes = []
            for i in range(len(prev_data)-1):
                old_price = prev_data[i].get(name, {}).get('Summary', {}).get('Last', 0)
                new_price = prev_data[i+1].get(name, {}).get('Summary', {}).get('Last', 0)
                if old_price != 0 and new_price != 0:
                    prev_changes.append(((new_price - old_price) / old_price) * 100)
            if prev_changes:
                volume = latest_data.get(name, {}).get('Summary', {}).get('BaseVolume', 0)
                average_rate = (sum(prev_changes) / len(prev_changes))
                if average_rate >= cfg.FASTTICK_MIN_RATE:
                    ticker_data.append([name,
                                        float('{:.02f}'.format(average_rate)),
                                        float('{:.02f}'.format(volume))])

    save_pickle(latest_data, cfg)
    return ticker_data