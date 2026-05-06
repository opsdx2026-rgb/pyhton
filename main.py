import os
import requests
from datetime import datetime, timedelta
import pytz
import time
import websocket
import threading
import json

# =========================
# CONFIG
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN", "8726552111:AAGPZ-DlKsfF4uP57OIK3k7mpWO8QjOCjbs")
ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY", "XFW92CINH8KKEVXWQUCVFNTNSJ21HHMRXA")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN is missing!")

CHAT_IDS = [-1003931797952]

COINS = {
    "DRX": "drxidr",
    "CST": "cstidr",
    "ANOA": "anoaidr"
}

# =========================
# REKU CONFIG
# =========================
REKU_CONFIG = {
    "DRX": {
        "symbol": "DRX_IDR",
        "code": 220
    },
    "CST": {
        "symbol": "CST_IDR",
        "code": 366
    },
    "ANOA": {
        "symbol": "ANOA_IDR",
        "code": 365
    }
}
# ✅ ADD THIS RIGHT HERE
last_reku_price = {k: None for k in REKU_CONFIG}
last_reku_alert = {k: None for k in REKU_CONFIG}

# =========================
# TOKOCRYPTO CONFIG
# =========================

TOKO_DATA = {
    "DRX": {
        "price": 0,
        "high": 0,
        "low": 0,
        "vol_coin": 0,
        "vol_idr": 0,

        "buy_total_coin": 0,
        "buy_total_value": 0,
        "buy_bottom_price": 0,
        "buy_strong_price": 0,
        "buy_strong_coin": 0,
        "buy_strong_value": 0,

        "sell_total_coin": 0,
        "sell_total_value": 0,
        "sell_top_price": 0,
        "sell_strong_price": 0,
        "sell_strong_coin": 0,
        "sell_strong_value": 0
    }
}
        

# =========================
# ETHERSCAN CONFIG
# =========================
TOKENS = {
    "DRX": {
        "contract": "0x83f4389ccCe1CC044dD7441Add33c4F28b967434",
        "min": 1_000_000
    },
    "ANOA": {
        "contract": "0x44A8701fb5c8c22B90d839363e6C2B2C1a58A525",
        "min": 150
    },
    "CST": {
        "contract": "0x3c41C80B966b92d345Dc8FC91e5508BC7248da6E",
        "min": 50
    }
}

TIMEZONE = pytz.timezone("Asia/Jakarta")
BOT_START_TIME = datetime.now(TIMEZONE)

seen_tx = set()
tx_log = []
last_chain_report = {"am": None, "pm": None}

# =========================
# MEMORY (FIXED - REQUIRED)
# =========================
trade_store = {pair: [] for pair in COINS.values()}
price_history = {pair: [] for pair in COINS.values()}
last_report_time = 0
last_report_price = {pair: None for pair in COINS.values()}
last_alert_price = {pair: None for pair in COINS.values()}

# =========================
# FORMAT RUPIAH
# =========================
def format_rupiah(value):
    try:
        return f"{int(value):,}".replace(",", ".")
    except:
        return value

# =========================
# TELEGRAM (ONLY ONE)
# =========================
def send_telegram(message):
    for chat_id in CHAT_IDS:
        try:
            r = requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                data={"chat_id": chat_id, "text": message, "parse_mode": "HTML"},
                timeout=10
            )
            print("Telegram:", r.text)
        except Exception as e:
            print("Telegram error:", e)

# =========================
# ETHERSCAN FETCH
# =========================
def get_token_tx(contract):
    try:
        url = "https://api.etherscan.io/v2/api"

        params = {
            "chainid": 1,
            "module": "account",   # ✅ THIS FIXES YOUR ERROR
            "action": "tokentx",
            "contractaddress": contract,
            "page": 1,
            "offset": 200,
            "sort": "desc",
            "apikey": ETHERSCAN_API_KEY
        }

        res = requests.get(url, params=params, timeout=10).json()

        if res.get("status") != "1":
            print(f"Etherscan error: {res.get('message')} | {res.get('result')}")
            return []

        result = res.get("result", [])

        if isinstance(result, list):
            return result
        else:
            print(f"Etherscan unexpected response: {result}")
            return []

    except Exception as e:
        print("Etherscan fetch error:", e)
        return []


def fetch_report_data(start, end):
    report_data = []

    for token, data in TOKENS.items():
        txs = get_token_tx(data["contract"])

        for tx in txs:

            try:
                decimals = int(tx["tokenDecimal"])
                amount = int(tx["value"]) / (10 ** decimals)
                tx_time = datetime.fromtimestamp(int(tx["timeStamp"]), TIMEZONE)
            except:
                continue

            # ❌ NO MIN FILTER HERE (IMPORTANT)

            if start <= tx_time <= end:
                report_data.append({
                    "token": token,
                    "from": tx["from"],
                    "to": tx["to"],
                    "hash": tx["hash"],
                    "time": tx_time,
                    "amount": amount
                })

    return report_data


def get_fixed_window(now, label):
    if label == "08:00 AM":
        start = now.replace(hour=20, minute=0, second=0, microsecond=0) - timedelta(days=1)
        end = now.replace(hour=8, minute=0, second=0, microsecond=0)
    else:
        start = now.replace(hour=8, minute=0, second=0, microsecond=0)
        end = now.replace(hour=20, minute=0, second=0, microsecond=0)

    return start, end


# =========================
# ETHERSCAN PROCESS
# =========================
def process_chain():
    for token, data in TOKENS.items():

        txs = get_token_tx(data["contract"])

        for tx in txs:
            tx_hash = tx.get("hash")

            if not tx_hash or tx_hash in seen_tx:
                continue

            try:
                decimals = int(tx["tokenDecimal"])
                amount = int(tx["value"]) / (10 ** decimals)
            except:
                continue

            if amount < data["min"]:
                continue

            tx_time = datetime.fromtimestamp(int(tx["timeStamp"]), TIMEZONE)

            # 🚨 IGNORE OLD TRANSACTIONS (BEFORE BOT START)
            if tx_time < BOT_START_TIME:
                continue

            # ✅ mark as seen ONLY after passing filter
            seen_tx.add(tx_hash)

            tx_log.append({
                "token": token,
                "from": tx["from"],
                "to": tx["to"],
                "hash": tx_hash,
                "time": tx_time,
                "amount": amount
            })

            msg = f"""🚨 <b>{token} ON-CHAIN MOVEMENT</b>
Amount : {amount:,.2f}
From   : {tx["from"]}
To     : {tx["to"]}
Hash   : {tx_hash}
Time   : {tx_time.strftime('%Y-%m-%d %H:%M:%S')}"""

            send_telegram(msg)

        time.sleep(0.3)

# =========================
# ETHERSCAN REPORT
# =========================
def chain_report():
    global last_chain_report
    now = datetime.now(TIMEZONE)

    # 08:00 AM report
    if now.hour >= 8 and last_chain_report["am"] != now.date():
        start, end = get_fixed_window(now, "08:00 AM")
        generate_chain_report(start, end, "08:00 AM")
        last_chain_report["am"] = now.date()

    # 08:00 PM report
    if now.hour >= 20 and last_chain_report["pm"] != now.date():
        start, end = get_fixed_window(now, "08:00 PM")
        generate_chain_report(start, end, "08:00 PM")
        last_chain_report["pm"] = now.date()

def generate_chain_report(start, end, label):
    data = fetch_report_data(start, end)

    msg = f"📊 <b>On-chain Report {label}</b>\n\n"

    if not data:
        msg += "No transaction"
        send_telegram(msg)
        return

    totals = {}
    counts = {}

    for tx in data:
        token = tx["token"]

        totals[token] = totals.get(token, 0) + tx["amount"]
        counts[token] = counts.get(token, 0) + 1

    for k, v in totals.items():
        count = counts.get(k, 0)
        msg += f"{k}: {v:,.2f} ({count} tx)\n"

    msg += "\n🏆 <b>Top Transactions (Per Coin)</b>\n"

    for token in TOKENS.keys():
        token_txs = [tx for tx in data if tx["token"] == token]

        msg += f"\n<b>{token}</b>\n"

        if not token_txs:
            msg += "No transaction\n"
            continue

        top5 = sorted(token_txs, key=lambda x: x["amount"], reverse=True)[:5]

        for tx in top5:
            msg += f"""\n{tx["amount"]:,.2f}
From: {tx["from"]}
To: {tx["to"]}
Time: {tx["time"].strftime('%H:%M')}
"""

    send_telegram(msg)

# =========================
# REKU FUNCTION
# =========================

REKU_PRICE_CACHE = []
REKU_LAST_UPDATE = 0

def get_reku_market(coin):

    try:

        url = "https://api.reku.id/v3/market?mode=trade&enable=0&delisted=0"

        r = requests.get(url, timeout=10)

        data = r.json()

        if not isinstance(data, list):
            print("REKU INVALID RESPONSE:", data)
            return None

        # find by cd
        target = None

        for item in data:

            if item.get("cd") == coin:
                target = item
                break

        if not target:
            print("REKU COIN NOT FOUND:", coin)
            return None

        return {
            "last": float(target.get("c", 0)),
            "high": float(target.get("h", 0)),
            "low": float(target.get("l", 0)),
            "vol_idr": float(target.get("v", 0))
        }

    except Exception as e:

        print("REKU PRICE ERROR:", coin, e)
        return None

REKU_ORDERBOOK_CACHE = []
REKU_ORDERBOOK_UPDATE = 0
def get_reku_depth(coin, current_price):
    try:
        pair = REKU_CONFIG[coin]["symbol"]
        url = f"https://api.reku.id/v2/orderbook?symbol={pair}"

        r = requests.get(url, timeout=10)
        raw = r.json()

        # =========================
        # VALIDATION
        # =========================
        if not isinstance(raw, dict):
            print("INVALID FORMAT:", raw)
            return None

        bids = raw.get("b")
        asks = raw.get("s")

        if bids is None or asks is None:
            print("MISSING BID/ASK:", raw)
            return None

        if not bids and not asks:
            print("EMPTY ORDERBOOK:", coin)
            return None

        # =========================
        # INIT
        # =========================
        buy_total_idr = buy_total_coin = 0
        sell_total_idr = sell_total_coin = 0

        buy_strong_val = buy_strong_price = buy_strong_coin = 0
        sell_strong_val = sell_strong_price = sell_strong_coin = 0

        # =========================
        # BUY SIDE
        # =========================
        for item in bids:
            try:
                value = float(item[0])   # IDR
                price = float(item[1])
                coin_amt = float(item[2])
            except:
                continue

            buy_total_idr += value
            buy_total_coin += coin_amt

            if value > buy_strong_val:
                buy_strong_val = value
                buy_strong_price = price
                buy_strong_coin = coin_amt

        # =========================
        # SELL SIDE
        # =========================
        for item in asks:
            try:
                value = float(item[0])
                price = float(item[1])
                coin_amt = float(item[2])
            except:
                continue

            sell_total_idr += value
            sell_total_coin += coin_amt

            if value > sell_strong_val:
                sell_strong_val = value
                sell_strong_price = price
                sell_strong_coin = coin_amt

        # =========================
        # LAST LEVEL (IMPORTANT FIX)
        # =========================
        last_buy_price = float(bids[-1][1]) if bids else 0
        last_sell_price = float(asks[-1][1]) if asks else 0

        return {
            # TOTALS
            "buy_total_value": buy_total_idr,
            "buy_total_coin": buy_total_coin,
            "sell_total_value": sell_total_idr,
            "sell_total_coin": sell_total_coin,

            # LAST LEVEL (your requirement)
            "buy_bottom_price": last_buy_price,
            "sell_top_price": last_sell_price,

            # STRONG WALLS
            "buy_strong_price": buy_strong_price,
            "buy_strong_value": buy_strong_val,
            "buy_strong_coin": buy_strong_coin,

            "sell_strong_price": sell_strong_price,
            "sell_strong_value": sell_strong_val,
            "sell_strong_coin": sell_strong_coin
        }

    except Exception as e:
        print("REKU DEPTH ERROR:", coin, e)
        return None

def get_reku_bidask(symbol):
    try:
        url = "https://api.reku.id/v2/bidaskpercoin"
        r = requests.post(url, json={"accountcode": symbol}, timeout=10).json()

        return r.get("data", {})
    except Exception as e:
        print("REKU BIDASK ERROR:", e)
        return None

def detect_reku_whale(depth, current_price):
    if not depth:
        return None

    threshold = 100_000_000

    if depth["buy_strong_value"] >= threshold:
        return f"🟢 Whale BUY @ Rp {format_rupiah(depth['buy_strong_price'])} (Rp {format_rupiah(depth['buy_strong_value'])})"

    if depth["sell_strong_value"] >= threshold:
        return f"🔴 Whale SELL @ Rp {format_rupiah(depth['sell_strong_price'])} (Rp {format_rupiah(depth['sell_strong_value'])})"

    return None

def check_reku_alert(coin, price):
    prev = last_reku_alert[coin]

    if prev is None:
        last_reku_alert[coin] = price
        return None

    change = ((price - prev) / prev) * 100

    if change >= 10:
        last_reku_alert[coin] = price
        return f"🚨🚨 <b>{coin} REKU +{change:.2f}%</b>\n💰 Rp {format_rupiah(price)}"

    elif change <= -10:
        last_reku_alert[coin] = price
        return f"🚨🚨 <b>{coin} REKU {change:.2f}%</b>\n💰 Rp {format_rupiah(price)}"

    elif change >= 5:
        last_reku_alert[coin] = price
        return f"🚀 <b>{coin} REKU +{change:.2f}%</b>\n💰 Rp {format_rupiah(price)}"

    elif change <= -5:
        last_reku_alert[coin] = price
        return f"⚠️ <b>{coin} REKU {change:.2f}%</b>\n💰 Rp {format_rupiah(price)}"

    return None

TOKO_PRODUCTS_URL = (
    "https://www.tokocrypto.com/bapi/asset/v2/public/"
    "asset-service/product/get-products?includeEtf=true"
)

TOKO_FALLBACK_URL = (
    "https://cloudme-toko.2meta.app/api/v1/ticker/24hr?symbol=DRXIDR"
)


class TokocryptoMarketError(RuntimeError):
    pass


def fetch_tokocrypto_market(symbol="DRX_IDR"):

    headers = {
        "accept": "application/json",
        "user-agent": "Mozilla/5.0",
        "referer": f"https://www.tokocrypto.com/id/trade/{symbol}",
    }

    try:

        # =========================
        # FRONTEND API
        # =========================
        response = requests.get(
            TOKO_PRODUCTS_URL,
            headers=headers,
            timeout=20
        )

        print("TOKO STATUS:", response.status_code)

        content_type = response.headers.get("content-type", "")

        if response.status_code == 200 and "json" in content_type.lower():

            payload = response.json()

            products = payload.get("data", {}).get("data", [])

            row = next(
                (item for item in products if item.get("s") == symbol),
                None
            )

            if row:

                return {
                    "symbol": row["s"],
                    "last_price": float(row["c"]),
                    "high_24h": float(row["h"]),
                    "low_24h": float(row["l"]),
                    "volume_24h_drx": float(row["v"]),
                    "volume_24h_idr": float(row["qv"]),
                }

        # =========================
        # FALLBACK API
        # =========================
        print("TOKO FRONTEND BLOCKED -> USING FALLBACK")

        r = requests.get(
            TOKO_FALLBACK_URL,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=20
        )

        data = r.json()

        return {
            "symbol": symbol,
            "last_price": float(data.get("c", 0)),
            "high_24h": float(data.get("h", 0)),
            "low_24h": float(data.get("l", 0)),
            "volume_24h_drx": float(data.get("v", 0)),
            "volume_24h_idr": float(data.get("q", 0)),
        }

    except Exception as e:

        raise TokocryptoMarketError(str(e))

# =========================
# TOKOCRYPTO DEPTH
# =========================

def update_tokocrypto_depth():
    try:
        url = "https://cloudme-toko.2meta.app/api/v1/depth?symbol=DRXIDR&limit=1000"

        headers = {
            "User-Agent": "Mozilla/5.0"
        }

        r = requests.get(url, headers=headers, timeout=10)
        data = r.json()

        raw = data.get("data", data)
        bids = raw.get("bids", [])
        asks = raw.get("asks", [])

        # =========================
        # BUY
        # =========================
        buy_total_coin = 0
        buy_total_value = 0

        buy_bottom_price = float("inf")

        buy_strong_price = 0
        buy_strong_coin = 0
        buy_strong_value = 0

        for item in bids:

            try:
                price = float(item[0])
                coin = float(item[1])
            except:
                continue

            value = price * coin

            buy_total_coin += coin
            buy_total_value += value

            if price < buy_bottom_price:
                buy_bottom_price = price

            if value > buy_strong_value:
                buy_strong_value = value
                buy_strong_price = price
                buy_strong_coin = coin

        # =========================
        # SELL
        # =========================
        sell_total_coin = 0
        sell_total_value = 0

        sell_top_price = 0

        sell_strong_price = 0
        sell_strong_coin = 0
        sell_strong_value = 0

        for item in asks:

            try:
                price = float(item[0])
                coin = float(item[1])
            except:
                continue

            value = price * coin

            sell_total_coin += coin
            sell_total_value += value

            if price > sell_top_price:
                sell_top_price = price

            if value > sell_strong_value:
                sell_strong_value = value
                sell_strong_price = price
                sell_strong_coin = coin

        TOKO_DATA["DRX"].update({
            "buy_total_coin": buy_total_coin,
            "buy_total_value": buy_total_value,
            "buy_bottom_price": buy_bottom_price,
            "buy_strong_price": buy_strong_price,
            "buy_strong_coin": buy_strong_coin,
            "buy_strong_value": buy_strong_value,

            "sell_total_coin": sell_total_coin,
            "sell_total_value": sell_total_value,
            "sell_top_price": sell_top_price,
            "sell_strong_price": sell_strong_price,
            "sell_strong_coin": sell_strong_coin,
            "sell_strong_value": sell_strong_value
        })

    except Exception as e:
        print("TOKOCRYPTO DEPTH ERROR:", e)
        
def update_tokocrypto_market():

    try:

        data = fetch_tokocrypto_market("DRX_IDR")

        TOKO_DATA["DRX"]["price"] = data["last_price"]
        TOKO_DATA["DRX"]["high"] = data["high_24h"]
        TOKO_DATA["DRX"]["low"] = data["low_24h"]
        TOKO_DATA["DRX"]["vol_coin"] = data["volume_24h_drx"]
        TOKO_DATA["DRX"]["vol_idr"] = data["volume_24h_idr"]

        print("TOKO MARKET UPDATED:", TOKO_DATA["DRX"])

    except Exception as e:

        print("TOKOCRYPTO MARKET ERROR:", e)

   
# =========================
# GET PRICE
# =========================
def get_price_data(pair):
    try:
        r = requests.get(f"https://indodax.com/api/ticker/{pair}", timeout=10)
        t = r.json()["ticker"]

        return {
            "last": float(t["last"]),
            "high": float(t["high"]),
            "low": float(t["low"]),
            "vol_coin": float(t[f"vol_{pair[:-3]}"]),
            "vol_idr": float(t["vol_idr"])
        }
    except:
        return None
def get_price(pair):
    data = get_price_data(pair)
    return data["last"] if data else None
# =========================
# 🚨 PRICE ALERT
# =========================
def check_price_alert(pair, coin, price):
    prev = last_alert_price[pair]

    if prev is None:
        last_alert_price[pair] = price
        return None

    change = ((price - prev) / prev) * 100

    # 🚨🚨 BIG ALERT ±10%
    if change >= 10:
        last_alert_price[pair] = price
        return f"🚨🚨 <b>{coin} BIG BREAKOUT +{change:.2f}%</b>\n💰 Rp {format_rupiah(price)}"

    elif change <= -10:
        last_alert_price[pair] = price
        return f"🚨🚨 <b>{coin} BIG DROP {change:.2f}%</b>\n💰 Rp {format_rupiah(price)}"

    # 🚨 NORMAL ALERT ±5%
    elif change >= 5:
        last_alert_price[pair] = price
        return f"🚀 <b>{coin}</b> BREAKOUT +{change:.2f}%\n💰 Rp {format_rupiah(price)}"

    elif change <= -5:
        last_alert_price[pair] = price
        return f"⚠️ <b>{coin}</b> DROP {change:.2f}%\n💰 Rp {format_rupiah(price)}"

    return None

# =========================
# PRICE HISTORY (6H) (unused for change now, kept as-is)
# =========================
def update_price_history(pair, price):
    now = time.time()
    price_history[pair].append((now, price))
    cutoff = now - 21600
    price_history[pair] = [p for p in price_history[pair] if p[0] >= cutoff]

def get_6h_change(pair, current_price):
    history = price_history.get(pair, [])

    if len(history) < 2:
        return None

    oldest_time, oldest_price = history[0]

    if time.time() - oldest_time < 21600:
        return None

    if oldest_price == 0:
        return None

    return ((current_price - oldest_price) / oldest_price) * 100

# =========================
# TRADE STORE (6H)
# =========================
last_trade_id = {pair: 0 for pair in COINS.values()}

def update_trade_store(pair):
    global last_trade_id

    try:
        r = requests.get(f"https://indodax.com/api/trades/{pair}", timeout=10)
        trades = r.json()
        now = time.time()

        for t in trades:
            trade_id = int(t["tid"])

            if trade_id <= last_trade_id[pair]:
                continue

            trade_time = int(t["date"])
            price = float(t["price"])
            amount = float(t["amount"])

            trade_store[pair].append((trade_time, price, amount))

            if trade_id > last_trade_id[pair]:
                last_trade_id[pair] = trade_id

        cutoff = now - 21600
        trade_store[pair] = [t for t in trade_store[pair] if t[0] >= cutoff]

    except Exception as e:
        print("Trade error:", e)

# =========================
# MOST TRADED (6H)
# =========================
def get_most_traded_6h(pair):
    trades = trade_store.get(pair, [])
    volume_map = {}

    for _, price, amount in trades:
        value = price * amount
        volume_map[price] = volume_map.get(price, 0) + value

    if not volume_map:
        return None, None

    best_price = max(volume_map, key=volume_map.get)
    return best_price, volume_map[best_price]

# =========================
# WHALE DETECTION
# =========================
def detect_whale(pair, current_price):
    trades = trade_store.get(pair, [])
    now = time.time()

    recent = [t for t in trades if t[0] >= now - 300]

    volume_map = {}

    for _, price, amount in recent:
        value = price * amount
        volume_map[price] = volume_map.get(price, 0) + value

    if not volume_map:
        return None

    whale_price = max(volume_map, key=volume_map.get)
    whale_value = volume_map[whale_price]

    if whale_value < 100_000_000:
        return None

    if whale_price <= current_price:
        return f"🟢 Whale BUY @ Rp {format_rupiah(whale_price)} (Rp {format_rupiah(whale_value)})"
    else:
        return f"🔴 Whale SELL @ Rp {format_rupiah(whale_price)} (Rp {format_rupiah(whale_value)})"

# =========================
# FILTER LEVEL
# =========================
def filter_levels(levels, current_price, is_resistance=True):
    candidates_50 = []
    candidates_20 = []

    for price, amount in levels:
        price = float(price)
        amount = float(amount)
        value = price * amount

        if is_resistance and price <= current_price:
            continue
        if not is_resistance and price >= current_price:
            continue

        if value >= 50_000_000:
            candidates_50.append((price, amount, value))
        elif value >= 20_000_000:
            candidates_20.append((price, amount, value))

    if candidates_50:
        return min(candidates_50, key=lambda x: x[0]) if is_resistance else max(candidates_50, key=lambda x: x[0])

    if candidates_20:
        return min(candidates_20, key=lambda x: x[0]) if is_resistance else max(candidates_20, key=lambda x: x[0])

    # fallback: pick strongest even if small
    if levels:
        valid = []
        for price, amount in levels:
            price = float(price)
            amount = float(amount)

            if not is_resistance and price < current_price:
                valid.append((price, amount, price * amount))

            if is_resistance and price > current_price:
                valid.append((price, amount, price * amount))

        if valid:
            return max(valid, key=lambda x: x[2])

    return None
 

# =========================
# MARKET DEPTH
# =========================
def get_market_depth(pair, current_price):
    try:
        r = requests.get(f"https://indodax.com/api/depth/{pair}", timeout=10)
        data = r.json()

        sell = data.get("sell", [])
        buy = data.get("buy", [])

        sell_total_coin = sell_total_value = 0
        sell_top_price = 0
        sell_strong_price = sell_strong_coin = sell_strong_value = 0

        for price, amount in sell:
            price = float(price)
            amount = float(amount)
            value = price * amount

            sell_total_coin += amount
            sell_total_value += value

            if price > sell_top_price:
                sell_top_price = price

            if value > sell_strong_value:
                sell_strong_value = value
                sell_strong_price = price
                sell_strong_coin = amount

        buy_total_coin = buy_total_value = 0
        buy_bottom_price = float("inf")
        buy_strong_price = buy_strong_coin = buy_strong_value = 0

        for price, amount in buy:
            price = float(price)
            amount = float(amount)
            value = price * amount

            buy_total_coin += amount
            buy_total_value += value

            if price < buy_bottom_price:
                buy_bottom_price = price

            if value > buy_strong_value:
                buy_strong_value = value
                buy_strong_price = price
                buy_strong_coin = amount

        res = filter_levels(sell, current_price, True)
        sup = filter_levels(buy, current_price, False)

        return {
            "sell_total_coin": sell_total_coin,
            "sell_total_value": sell_total_value,
            "sell_top_price": sell_top_price,
            "sell_strong_price": sell_strong_price,
            "sell_strong_coin": sell_strong_coin,
            "sell_strong_value": sell_strong_value,
            "buy_total_coin": buy_total_coin,
            "buy_total_value": buy_total_value,
            "buy_bottom_price": buy_bottom_price,
            "buy_strong_price": buy_strong_price,
            "buy_strong_coin": buy_strong_coin,
            "buy_strong_value": buy_strong_value,
            "res": res,
            "sup": sup
        }

    except Exception as e:
        print("Depth error:", e)
        return None

# =========================
# SIGNAL
# =========================
def get_signal(buy_value, sell_value):
    if buy_value > sell_value * 1.2:
        return "🟢 BULLISH"
    elif sell_value > buy_value * 1.2:
        return "🔴 BEARISH"
    else:
        return "⚖️ NEUTRAL"

# =========================
# REPORT
# =========================
def send_report():
    wib = pytz.timezone("Asia/Jakarta")
    timestamp = datetime.now(wib).strftime("%Y-%m-%d %H:%M:%S")

    message = f"📊 <b>Multi-Exchange Report</b>\n⏰ {timestamp}\n\n"

    for coin, pair in COINS.items():

        # =========================
        # INDODAX
        # =========================
        data = get_price_data(pair)
        if not data:
            continue

        price = data["last"]
        high_24h = data["high"]
        low_24h = data["low"]
        vol_coin = data["vol_coin"]
        vol_idr = data["vol_idr"]

        prev_price = last_report_price[pair]
        change = ((price - prev_price) / prev_price) * 100 if prev_price else None

        most_price, most_volume = get_most_traded_6h(pair)
        depth = get_market_depth(pair, price)
        whale = detect_whale(pair, price)

        line = f"🔷 <b>{coin}</b>\n"

        # =========================
        # 🏦 INDODAX
        # =========================
        line += f"\n🏦 <b>INDODAX</b>"
        line += f"\n💰 Price: Rp {format_rupiah(price)}"
        line += f"\n📊 Change: {f'{change:+.2f}%' if change else 'first data'}"

        if most_price:
            line += f"\n🔥 Most Traded: Rp {format_rupiah(most_price)} (Rp {format_rupiah(most_volume)})"

        line += f"\n\n📊 <b>24H Stats</b>"
        line += f"\n⬆️ High: Rp {format_rupiah(high_24h)}"
        line += f"\n⬇️ Low : Rp {format_rupiah(low_24h)}"
        line += f"\n🪙 Volume Coin: {vol_coin:,.2f}".replace(",", ".")
        line += f"\n💰 Volume IDR: Rp {format_rupiah(vol_idr)}"

        # =========================
        # DEPTH
        # =========================
        if depth:

            # SELL
            line += f"\n\n🟥 SELL"
            line += f"\n   🔺 Top Price: Rp {format_rupiah(depth['sell_top_price'])}"
            line += f"\n   🪙 Total Coin: {depth['sell_total_coin']:,.2f}".replace(",", ".")
            line += f"\n   💰 Total Value: Rp {format_rupiah(depth['sell_total_value'])}"

            line += f"\n   🧱 Strongest Wall:"
            line += f"\n      Price: Rp {format_rupiah(depth['sell_strong_price'])}"
            line += f"\n      Coin: {depth['sell_strong_coin']:,.2f}".replace(",", ".")
            line += f"\n      Value: Rp {format_rupiah(depth['sell_strong_value'])}"

            # BUY
            line += f"\n\n🟩 BUY"
            line += f"\n   🔻 Bottom Price: Rp {format_rupiah(depth['buy_bottom_price'])}"
            line += f"\n   🪙 Total Coin: {depth['buy_total_coin']:,.2f}".replace(",", ".")
            line += f"\n   💰 Total Value: Rp {format_rupiah(depth['buy_total_value'])}"

            line += f"\n   🧱 Strongest Wall:"
            line += f"\n      Price: Rp {format_rupiah(depth['buy_strong_price'])}"
            line += f"\n      Coin: {depth['buy_strong_coin']:,.2f}".replace(",", ".")
            line += f"\n      Value: Rp {format_rupiah(depth['buy_strong_value'])}"

            # SUPPORT / RESISTANCE
            if depth["res"]:
                p, _, _ = depth["res"]
                line += f"\n\n🚧 Resistance"
                line += f"\n   Price: Rp {format_rupiah(p)}"

            if depth["sup"]:
                p, _, _ = depth["sup"]
                line += f"\n\n🛡️ Support"
                line += f"\n   Price: Rp {format_rupiah(p)}"

            # SIGNAL
            signal = get_signal(depth['buy_total_value'], depth['sell_total_value'])
            line += f"\n\n📈 Signal: {signal}"

            if whale:
                line += f"\n🐋 {whale}"

        # =========================
        # 🔥 REKU SECTION (FIXED)
        # =========================
        line += f"\n\n🏦 <b>REKU</b>"

        reku_market = get_reku_market(coin)

        # =========================
        # PRICE (OPTIONAL)
        # =========================
        if reku_market:
            reku_price = reku_market["last"]

            prev = last_reku_price.get(coin)
            change = ((reku_price - prev) / prev) * 100 if prev else None

            line += f"\n💰 Price: Rp {format_rupiah(reku_price)}"
            line += f"\n📊 Change: {f'{change:+.2f}%' if change else 'first data'}"

            line += f"\n\n📊 <b>24H Stats</b>"
            line += f"\n⬆️ High: Rp {format_rupiah(reku_market['high'])}"
            line += f"\n⬇️ Low : Rp {format_rupiah(reku_market['low'])}"
            line += f"\n💰 Volume IDR: Rp {format_rupiah(reku_market['vol_idr'])}"

            last_reku_price[coin] = reku_price
        else:
            print("REKU PRICE FAILED:", coin)
            line += "\n⚠️ Price not available"

        # =========================
        # ORDERBOOK (ALWAYS RUN)
        # =========================
        reku_depth = get_reku_depth(coin, 0)

        if reku_depth:
            line += f"\n\n🟥 SELL"
            line += f"\n   🔺 Highest Offer: Rp {format_rupiah(reku_depth['sell_top_price'])}"
            line += f"\n   🪙 Total Offer Coin: {reku_depth['sell_total_coin']:,.2f}".replace(",", ".")
            line += f"\n   💰 Total Offer Value: Rp {format_rupiah(reku_depth['sell_total_value'])}"
            
            line += f"\n   🧱 Strongest Wall:"
            line += f"\n      Price: Rp {format_rupiah(reku_depth['sell_strong_price'])}"
            line += f"\n      Coin: {reku_depth['sell_strong_coin']:,.2f}".replace(",", ".")
            line += f"\n      Value: Rp {format_rupiah(reku_depth['sell_strong_value'])}"
            
            line += f"\n\n🟩 BUY"
            line += f"\n   🔻 Lowest Bid: Rp {format_rupiah(reku_depth['buy_bottom_price'])}"
            line += f"\n   🪙 Total Bid Coin: {reku_depth['buy_total_coin']:,.2f}".replace(",", ".")
            line += f"\n   💰 Total Bid Value: Rp {format_rupiah(reku_depth['buy_total_value'])}"
            
            line += f"\n   🧱 Strongest Wall:"
            line += f"\n      Price: Rp {format_rupiah(reku_depth['buy_strong_price'])}"
            line += f"\n      Coin: {reku_depth['buy_strong_coin']:,.2f}".replace(",", ".")
            line += f"\n      Value: Rp {format_rupiah(reku_depth['buy_strong_value'])}"
        else:
            print("REKU ORDERBOOK FAILED:", coin)
            line += "\n⚠️ Orderbook not available"

   
        # =========================
        # TOKOCRYPTO
        # =========================
        if coin == "DRX":

            update_tokocrypto_market()
            update_tokocrypto_depth()

            toko = TOKO_DATA["DRX"]
        
            line += f"\n\n🏦 <b>TOKOCRYPTO</b>"
        
            line += f"\n💰 Price: Rp {format_rupiah(toko['price'])}"
        
            line += f"\n\n📊 <b>24H Stats</b>"
            line += f"\n⬆️ High: Rp {format_rupiah(toko['high'])}"
            line += f"\n⬇️ Low : Rp {format_rupiah(toko['low'])}"
            line += f"\n🪙 Volume Coin: {toko['vol_coin']:,.2f}".replace(",", ".")
            line += f"\n💰 Volume IDR: Rp {format_rupiah(toko['vol_idr'])}"


            # SELL
            line += f"\n\n🟥 SELL"
            line += f"\n   🔺 Highest Offer: Rp {format_rupiah(toko['sell_top_price'])}"
            line += f"\n   🪙 Total Offer Coin: {toko['sell_total_coin']:,.2f}".replace(",", ".")
            line += f"\n   💰 Total Offer Value: Rp {format_rupiah(toko['sell_total_value'])}"

            line += f"\n   🧱 Strongest Wall:"
            line += f"\n      Price: Rp {format_rupiah(toko['sell_strong_price'])}"
            line += f"\n      Coin: {toko['sell_strong_coin']:,.2f}".replace(",", ".")
            line += f"\n      Value: Rp {format_rupiah(toko['sell_strong_value'])}"

            # BUY
            line += f"\n\n🟩 BUY"
            line += f"\n   🔻 Lowest Bid: Rp {format_rupiah(toko['buy_bottom_price'])}"
            line += f"\n   🪙 Total Bid Coin: {toko['buy_total_coin']:,.2f}".replace(",", ".")
            line += f"\n   💰 Total Bid Value: Rp {format_rupiah(toko['buy_total_value'])}"

            line += f"\n   🧱 Strongest Wall:"
            line += f"\n      Price: Rp {format_rupiah(toko['buy_strong_price'])}"
            line += f"\n      Coin: {toko['buy_strong_coin']:,.2f}".replace(",", ".")
            line += f"\n      Value: Rp {format_rupiah(toko['buy_strong_value'])}"

        # ✅ ALWAYS APPEND
        message += line + "\n\n"

        # ✅ update last report price
        last_report_price[pair] = price

    # ✅ SEND TELEGRAM ONCE
    send_telegram(message)

# =========================
# MAIN LOOP
# =========================
def loop():
    global last_report_time

    while True:
        current_time = datetime.now(TIMEZONE)

        for coin, pair in COINS.items():

            # =========================
            # INDODAX REALTIME
            # =========================
            update_trade_store(pair)

            price = get_price(pair)
            if price:
                alert = check_price_alert(pair, coin, price)
                if alert:
                    send_telegram(alert)

            # =========================
            # REKU REALTIME ALERT
            # =========================
            reku_market = get_reku_market(coin)
            if reku_market:
                reku_price = reku_market["last"]
                alert_r = check_reku_alert(coin, reku_price)

                if alert_r:
                    send_telegram(alert_r)

        # =========================
        # REPORT SCHEDULE (FIXED)
        # =========================
        if current_time.hour in [0, 6, 16] and current_time.minute < 5:
            if last_report_time != current_time.hour:
                send_report()
                last_report_time = current_time.hour

        # =========================
        # ON-CHAIN + REPORT
        # =========================
        process_chain()
        chain_report()

        time.sleep(60)
# =========================
# START
# =========================
if __name__ == "__main__":

    print("🚀 Multi-Engine Bot Started")

    send_report()

    loop()
