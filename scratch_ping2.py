import urllib.request
import json
data = json.dumps({'symbol':'BTCUSDT','interval':'1m','limit':100,'start_date':'2024-04-10','end_date':'2024-04-11'}).encode()
req = urllib.request.Request('http://localhost:8001/api/v1/market/test/ping', data=data, headers={'Content-Type': 'application/json'})
try:
    resp = urllib.request.urlopen(req)
    print(resp.read().decode())
except urllib.error.HTTPError as e:
    print(e.code)
    print(e.read().decode())
