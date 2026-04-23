import httpx
import asyncio

async def run(): 
    res = await httpx.AsyncClient().post('http://localhost:8001/api/v1/market/test/ping', json={'symbol':'BTCUSDT','interval':'1m','limit':100,'start_date':'2024-04-10','end_date':'2024-04-11'}, timeout=60.0)
    print(res.status_code)
    print(res.text)

asyncio.run(run())
