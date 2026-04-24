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

THRESHOLD = 5
last_prices = {}

# =========================
# FORMAT
# =========================
def format_rupiah(value):
    return f"{int(value):,}".replace(",", ".")

# =========================
# GET PRICE
# =========================
def get_price(pair):
    try:
        r = requests.get(f"https://indodax.com/api/ticker/{pair}", timeout=10)
        data = r.json()
        return float(data["ticker"]["last"])
    except:
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

        # ===== SELL =====
        sell_total_coin = 0
        sell_total_value = 0
        sell_top_price = 0

        sell_strong_price = 0
        sell_strong_coin = 0
        sell_strong_value = 0

        nearest_res_price = None
        nearest_res_value = 0
        nearest_res_coin = 0

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

            if price > current_price:
                if nearest_res_price is None or price < nearest_res_price:
                    nearest_res_price = price
                    nearest_res_value = value
                    nearest_res_coin = amount

        # ===== BUY =====
        buy_total_coin = 0
        buy_total_value = 0

        buy_top_price = 0
        buy_bottom_price = float("inf")

        buy_strong_price = 0
        buy_strong_coin = 0
        buy_strong_value = 0

        nearest_sup_price = None
        nearest_sup_value = 0
        nearest_sup_coin = 0

        for price, amount in buy:
            price = float(price)
            amount = float(amount)
            value = price * amount

            buy_total_coin += amount
            buy_total_value += value

            if price > buy_top_price:
                buy_top_price = price

            if price < buy_bottom_price:
                buy_bottom_price = price

            if value > buy_strong_value:
                buy_strong_value = value
                buy_strong_price = price
                buy_strong_coin = amount

            if price < current_price:
                if nearest_sup_price is None or price > nearest_sup_price:
                    nearest_sup_price = price
                    nearest_sup_value = value
                    nearest_sup_coin = amount

        return {
            "sell_total_coin": sell_total_coin,
            "sell_total_value": sell_total_value,
            "sell_top_price": sell_top_price,
            "sell_strong_price": sell_strong_price,
            "sell_strong_coin": sell_strong_coin,
            "sell_strong_value": sell_strong_value,

            "buy_total_coin": buy_total_coin,
            "buy_total_value": buy_total_value,
            "buy_top_price": buy_top_price,
            "buy_bottom_price": buy_bottom_price,
            "buy_strong_price": buy_strong_price,
            "buy_strong_coin": buy_strong_coin,
            "buy_strong_value": buy_strong_value,

            "res_price": nearest_res_price,
            "res_value": nearest_res_value,
            "res_coin": nearest_res_coin,

            "sup_price": nearest_sup_price,
            "sup_value": nearest_sup_value,
            "sup_coin": nearest_sup_coin
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
                data={"chat_id": chat_id, "text": message},
                timeout=10
            )
        except Exception as e:
            print("Telegram error:", e)

# =========================
# CHANGE %
# =========================
def calc_change(old, new):
    if old is None:
        return 0
    return ((new - old) / old) * 100

# =========================
# MAIN
# =========================
def job():
    global last_prices

    wib = pytz.timezone("Asia/Jakarta")
    timestamp = datetime.now(wib).strftime("%Y-%m-%d %H:%M")

    message = f"📊 Indodax Update\n⏰ {timestamp}\n\n"

    new_prices = {}
    alert_triggered = False

    for coin, pair in COINS.items():
        price = get_price(pair)

        if not price:
            message += f"{coin}: error\n\n"
            continue

        old_price = last_prices.get(coin)
        change = calc_change(old_price, price)

        depth = get_market_depth(pair, price)

        line = f"{coin}: Rp {format_rupiah(price)}"

        if old_price:
            line += f" ({change:.2f}%)"

            if change >= THRESHOLD:
                line += " 🚀 +5%"
                alert_triggered = True
            elif change <= -THRESHOLD:
                line += " 🔻 -5%"
                alert_triggered = True

        if depth:
            # SELL
            line += f"\n🟥 SELL"
            line += f"\n   🧱 Top Sell Price: Rp {format_rupiah(depth['sell_top_price'])}"
            line += f"\n   🪙 Total Sell: {depth['sell_total_coin']:,.2f}".replace(",", ".")
            line += f"\n   💰 Total Value: Rp {format_rupiah(depth['sell_total_value'])}"
            line += f"\n   🧱 Strongest Wall:"
            line += f"\n      Price: Rp {format_rupiah(depth['sell_strong_price'])}"
            line += f"\n      Volume  : {depth['sell_strong_coin']:,.2f}".replace(",", ".")
            line += f"\n      Value  : Rp {format_rupiah(depth['sell_strong_value'])}"

            # BUY
            line += f"\n🟩 BUY"
            line += f"\n   🔝 Top Buy (Highest): Rp {format_rupiah(depth['buy_top_price'])}"
            line += f"\n   🔻 Bottom Buy (Lowest): Rp {format_rupiah(depth['buy_bottom_price'])}"
            line += f"\n   🪙 Total Buy: {depth['buy_total_coin']:,.2f}".replace(",", ".")
            line += f"\n   💰 Total Value: Rp {format_rupiah(depth['buy_total_value'])}"
            line += f"\n   🧱 Strongest Wall:"
            line += f"\n      Price: Rp {format_rupiah(depth['buy_strong_price'])}"
            line += f"\n      Volume  : {depth['buy_strong_coin']:,.2f}".replace(",", ".")
            line += f"\n      Value  : Rp {format_rupiah(depth['buy_strong_value'])}"

            # RESISTANCE
            if depth["res_price"]:
                line += f"\n🚧 Resistance (Nearest)"
                line += f"\n   Price: Rp {format_rupiah(depth['res_price'])}"
                line += f"\n   Vol  : {depth['res_coin']:,.2f}".replace(",", ".")
                line += f"\n   Val  : Rp {format_rupiah(depth['res_value'])}"

            # SUPPORT
            if depth["sup_price"]:
                line += f"\n🛡️ Support (Nearest)"
                line += f"\n   Price: Rp {format_rupiah(depth['sup_price'])}"
                line += f"\n   Vol  : {depth['sup_coin']:,.2f}".replace(",", ".")
                line += f"\n   Val  : Rp {format_rupiah(depth['sup_value'])}"

            # SIGNAL
            signal = get_signal(depth['buy_total_value'], depth['sell_total_value'])
            line += f"\n📈 Signal: {signal}"

        message += line + "\n\n"
        new_prices[coin] = price

    print(message)
    send_telegram(message)

    if alert_triggered:
        send_telegram("🚨 PRICE ALERT 🚨\n\n" + message)

    last_prices = new_prices

# =========================
# LOOP
# =========================
if __name__ == "__main__":
    print("Bot started...\n")

    job()

    while True:
        time.sleep(3600)
        job()
