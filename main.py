from fastapi import FastAPI
import requests
import time
from collections import defaultdict

app = FastAPI()

FORGE_REGION_ID = 10000002
JITA_STATION_ID = 60003760
FEE_RATE = 0.037  # 3.7% total fees

CACHE = {"timestamp": 0, "data": []}
CACHE_TTL = 3600  # 1 hour

def fetch_all_orders(order_type):
    page = 1
    all_orders = []

    while True:
        url = f"https://esi.evetech.net/latest/markets/{FORGE_REGION_ID}/orders/?order_type={order_type}&page={page}"
        res = requests.get(url)
        if res.status_code != 200:
            break
        orders = [o for o in res.json() if o["location_id"] == JITA_STATION_ID]
        if not orders:
            break
        all_orders.extend(orders)
        page += 1

    return all_orders

def get_item_name(type_id):
    try:
        url = f"https://esi.evetech.net/latest/universe/types/{type_id}/"
        res = requests.get(url)
        if res.status_code == 200:
            return res.json().get("name", str(type_id))
    except:
        pass
    return str(type_id)

@app.get("/market-data")
def get_market_data():
    now = time.time()
    if now - CACHE["timestamp"] < CACHE_TTL:
        return {"cached": True, "top_items": CACHE["data"]}

    buy_orders = fetch_all_orders("buy")
    sell_orders = fetch_all_orders("sell")

    item_data = defaultdict(lambda: {"buy": 0, "sell": float("inf"), "volume": 0})

    for o in buy_orders:
        tid = o["type_id"]
        item_data[tid]["buy"] = max(item_data[tid]["buy"], o["price"])

    for o in sell_orders:
        tid = o["type_id"]
        item_data[tid]["sell"] = min(item_data[tid]["sell"], o["price"])
        item_data[tid]["volume"] += o["volume_remain"]

    result = []
    for tid, info in item_data.items():
        if info["buy"] > 0 and info["sell"] < float("inf"):
            net_sell = info["sell"] * (1 - FEE_RATE)
            profit = net_sell - info["buy"]
            margin = round((profit / info["buy"]) * 100, 2)

            if margin > 1 and info["volume"] > 50:
                result.append({
                    "type_id": tid,
                    "item_name": get_item_name(tid),
                    "buy_price": round(info["buy"], 2),
                    "sell_price": round(info["sell"], 2),
                    "net_sell_price": round(net_sell, 2),
                    "volume": int(info["volume"]),
                    "profit_per_unit": round(profit, 2),
                    "margin_percent": margin
                })

    result = sorted(result, key=lambda x: x["profit_per_unit"] * x["volume"], reverse=True)[:50]
    CACHE["timestamp"] = now
    CACHE["data"] = result
    return {"cached": False, "top_items": result}
