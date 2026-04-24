import os
import requests
from datetime import datetime
import pytz
import time

# =========================
# CONFIG
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN", "8726552111:AAGPZ-DlKsfF4uP57OIK3k7mpWO8QjOCjbs")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN is missing!")

CHAT_IDS = [-1003931797952]

COINS = {
    "DRX": "drxidr",
    "CST": "cstidr",
    "ANOA": "anoaidr"
}

# =========================
# FORMAT
# =========================
def format_rupiah(value):
    try:
        return f"{int(value):,}".replace(",", ".")
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

        # SELL
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

        # BUY
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
            requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                data={
                    "chat_id": chat_id,
                    "text": message,
                    "parse_mode": "HTML"
                },
                timeout=10
            )
        except Exception as e:
            print("Telegram error:", e)

# =========================
# MAIN
# =========================
def job():
    wib = pytz.timezone("Asia/Jakarta")
    timestamp = datetime.now(wib).strftime("%Y-%m-%d %H:%M")

    message = f"📊 <b>Indodax Update</b>\n⏰ {timestamp}\n\n"

    for coin, pair in COINS.items():
        price = get_price(pair)

        if not price:
            continue

        depth = get_market_depth(pair, price)

        line = f"🔷 <b>{coin}</b>\n"
        line += f"💰 <b>Rp {format_rupiah(price)}</b>\n"

        if depth:
            # SELL
            line += f"\n🟥 SELL"
            line += f"\n   🧱 Top Price: Rp {format_rupiah(depth['sell_top_price'])}"
            line += f"\n   🪙 Total Sell: {depth['sell_total_coin']:,.2f}".replace(",", ".")
            line += f"\n   💰 Total Value: Rp {format_rupiah(depth['sell_total_value'])}"

            line += f"\n   🧱 Strongest Wall:"
            line += f"\n      Price: Rp {format_rupiah(depth['sell_strong_price'])}"
            line += f"\n      Volume: {depth['sell_strong_coin']:,.2f}".replace(",", ".")
            line += f"\n      Value: Rp {format_rupiah(depth['sell_strong_value'])}"

            # BUY (FIXED INDENTATION)
            line += f"\n\n🟩 BUY"
            line += f"\n   🔻 Bottom Price: Rp {format_rupiah(depth['buy_bottom_price'])}"
            line += f"\n   🪙 Total Buy: {depth['buy_total_coin']:,.2f}".replace(",", ".")
            line += f"\n   💰 Total Value: Rp {format_rupiah(depth['buy_total_value'])}"

            line += f"\n   🧱 Strongest Wall:"
            line += f"\n      Price: Rp {format_rupiah(depth['buy_strong_price'])}"
            line += f"\n      Volume: {depth['buy_strong_coin']:,.2f}".replace(",", ".")
            line += f"\n      Value: Rp {format_rupiah(depth['buy_strong_value'])}"

            # RESISTANCE / SUPPORT
            if depth["res"]:
                p, v, val = depth["res"]
                line += f"\n\n🚧 Nearest Resistance"
                line += f"\n   Price: Rp {format_rupiah(p)}"
                line += f"\n   Volume: {v:,.2f}".replace(",", ".")
                line += f"\n   Value: Rp {format_rupiah(val)}"

            if depth["sup"]:
                p, v, val = depth["sup"]
                line += f"\n\n🛡️ Nearest Support"
                line += f"\n   Price: Rp {format_rupiah(p)}"
                line += f"\n   Volume: {v:,.2f}".replace(",", ".")
                line += f"\n   Value: Rp {format_rupiah(val)}"

            signal = get_signal(depth['buy_total_value'], depth['sell_total_value'])
            line += f"\n\n📈 Signal: {signal}"

        message += line + "\n\n"

    send_telegram(message)

# =========================
# LOOP
# =========================
if __name__ == "__main__":
    job()
    while True:
        time.sleep(1800)
        job()
