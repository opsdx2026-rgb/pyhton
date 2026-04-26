import os
import requests
from datetime import datetime
import pytz
import time

# =========================
# CONFIG
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN","8726552111:AAGPZ-DlKsfF4uP57OIK3k7mpWO8QjOCjbs")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN is missing!")

CHAT_IDS = [-1003931797952]

COINS = {
    "DRX": "drxidr",
    "CST": "cstidr",
    "ANOA": "anoaidr"
}

# =========================
# MEMORY
# =========================
trade_store = {pair: [] for pair in COINS.values()}
price_history = {pair: [] for pair in COINS.values()}
last_report_time = 0
last_report_price = {pair: None for pair in COINS.values()}

# =========================
# FORMAT
# =========================
def format_rupiah(value):
    try:
        return f"{int(value):,}".replace(",", ".")
    except:
        return "0"

def format_coin(value):
    try:
        return "{:,.2f}".format(value).replace(",", ".")
    except:
        return "0"

# =========================
# GET PRICE
# =========================
def get_price(pair):
    try:
        r = requests.get(f"https://indodax.com/api/ticker/{pair}", timeout=10)
        return float(r.json()["ticker"]["last"])
    except:
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
# TELEGRAM
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
# REPORT
# =========================
def send_report():
    wib = pytz.timezone("Asia/Jakarta")
    timestamp = datetime.now(wib).strftime("%Y-%m-%d %H:%M:%S")

    message = f"📊 <b>Indodax 6H Full Report</b>\n⏰ {timestamp}\n\n"

    for coin, pair in COINS.items():
        price = get_price(pair)
        if not price:
            continue

        prev_price = last_report_price[pair]

        if prev_price is None:
            change = None
        else:
            change = ((price - prev_price) / prev_price) * 100

        alert = ""
        if change is not None:
            if change >= 5:
                alert = "🚀 +5% BREAKOUT"
            elif change <= -5:
                alert = "⚠️ -5% DROP"

        most_price, most_volume = get_most_traded_6h(pair)
        depth = get_market_depth(pair, price)
        whale = detect_whale(pair, price)

        line = f"🔷 <b>{coin}</b>\n"
        line += f"💰 <b>Rp {format_rupiah(price)}</b>\n"
        line += f"📊 Change: {f'{change:+.2f}%' if change is not None else 'first data'}\n"

        if alert:
            line += f"{alert}\n"

        if most_price:
            line += f"📍 Most Traded: Rp {format_rupiah(most_price)} (Rp {format_rupiah(most_volume)})\n"

        if whale:
            line += f"\n🐋 {whale}\n"

        if depth:
            line += f"\n🟥 SELL"
            line += f"\n   🧱 Top Price: Rp {format_rupiah(depth['sell_top_price'])}"
            line += f"\n   🪙 Total Offer Coin: {depth['sell_total_coin']:,.2f}".replace(",", ".")
            line += f"\n   💰 Total Value: Rp {format_rupiah(depth['sell_total_value'])}"

            line += f"\n   🧱 Strongest Wall:"
            line += f"\n      Price: Rp {format_rupiah(depth['sell_strong_price'])}"
            line += f"\n      Coin: {depth['sell_strong_coin']:,.2f}".replace(",", ".")
            line += f"\n      Value: Rp {format_rupiah(depth['sell_strong_value'])}"

            line += f"\n\n🟩 BUY"
            line += f"\n   🔻 Bottom Price: Rp {format_rupiah(depth['buy_bottom_price'])}"
            line += f"\n   🪙 Total Bid Coin: {depth['buy_total_coin']:,.2f}".replace(",", ".")
            line += f"\n   💰 Total Value: Rp {format_rupiah(depth['buy_total_value'])}"

            line += f"\n   🧱 Strongest Wall:"
            line += f"\n      Price: Rp {format_rupiah(depth['buy_strong_price'])}"
            line += f"\n      Coin: {depth['buy_strong_coin']:,.2f}".replace(",", ".")
            line += f"\n      Value: Rp {format_rupiah(depth['buy_strong_value'])}"

            if depth["res"]:
                p, v, val = depth["res"]
                line += f"\n\n🚧 Resistance"
                line += f"\n   Price: Rp {format_rupiah(p)}"
                line += f"\n   Coin: {v:,.2f}".replace(",", ".")
                line += f"\n   Value: Rp {format_rupiah(val)}"

            if depth["sup"]:
                p, v, val = depth["sup"]
                line += f"\n\n🛡️ Support"
                line += f"\n   Price: Rp {format_rupiah(p)}"
                line += f"\n   Coin: {v:,.2f}".replace(",", ".")
                line += f"\n   Value: Rp {format_rupiah(val)}"

            signal = get_signal(depth['buy_total_value'], depth['sell_total_value'])
            line += f"\n\n📈 Signal: {signal}"

        message += line + "\n\n"
        last_report_price[pair] = price

    send_telegram(message)

# =========================
# LOOP
# =========================
def loop():
    global last_report_time

    while True:
        now = time.time()

        for pair in COINS.values():
            update_trade_store(pair)

        if now - last_report_time >= 21600:
            send_report()
            last_report_time = now

        time.sleep(300)

# =========================
# START
# =========================
if __name__ == "__main__":
    print("Bot started...")
    loop()
