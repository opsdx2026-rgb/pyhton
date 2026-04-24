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

CHAT_IDS = [8495972050,-1003931797952]

COINS = {
    "DRX": "drxidr",
    "CST": "cstidr",
    "ANOA": "anoaidr"
}

THRESHOLD = 5  # % alert
last_prices = {}

# =========================
# FORMAT RUPIAH
# =========================
def format_rupiah(value):
    return f"{int(value):,}".replace(",", ".")

# =========================
# GET PRICE
# =========================
def get_price(pair):
    url = f"https://indodax.com/api/ticker/{pair}"
    try:
        r = requests.get(url, timeout=10)

        if r.status_code != 200:
            print("Bad response:", r.status_code)
            return None

        data = r.json()

        if "ticker" not in data:
            print("Invalid data:", data)
            return None

        return float(data["ticker"]["last"])

    except Exception as e:
        print("API error:", e)
        return None

# =========================
# GET SELL WALL DATA
# =========================
def get_sell_wall(pair):
    url = f"https://indodax.com/api/depth/{pair}"
    try:
        r = requests.get(url, timeout=10)

        if r.status_code != 200:
            print("Depth error:", r.status_code)
            return None, None, None, None, None, None

        data = r.json()

        if "sell" not in data or len(data["sell"]) == 0:
            return None, None, None, None, None, None

        total_coin = 0
        total_rp = 0
        top_price = 0

        strongest_price = 0
        strongest_coin = 0
        strongest_value = 0

        for price, amount in data["sell"]:
            price = float(price)
            amount = float(amount)

            value = price * amount

            # total
            total_coin += amount
            total_rp += value

            # highest price
            if price > top_price:
                top_price = price

            # strongest wall (largest value)
            if value > strongest_value:
                strongest_value = value
                strongest_price = price
                strongest_coin = amount

        return (
            top_price,
            total_coin,
            total_rp,
            strongest_price,
            strongest_coin,
            strongest_value
        )

    except Exception as e:
        print("Depth API error:", e)
        return None, None, None, None, None, None

# =========================
# TELEGRAM SEND
# =========================
def send_telegram(message):
    for chat_id in CHAT_IDS:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        try:
            res = requests.post(url, data={
                "chat_id": chat_id,
                "text": message
            }, timeout=10)

            print("Telegram response:", res.text)

        except Exception as e:
            print("Telegram error:", e)

# =========================
# CALCULATE %
# =========================
def calc_change(old, new):
    if old is None:
        return 0
    return ((new - old) / old) * 100

# =========================
# MAIN JOB
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

        if price is None:
            message += f"{coin}: error\n\n"
            continue

        old_price = last_prices.get(coin)
        change = calc_change(old_price, price)

        (
            top_price,
            sell_coin,
            sell_rp,
            strong_price,
            strong_coin,
            strong_value
        ) = get_sell_wall(pair)

        line = f"{coin}: Rp {format_rupiah(price)}"

        if old_price:
            line += f" ({change:.2f}%)"

            if change >= THRESHOLD:
                line += " 🚀 +5%"
                alert_triggered = True

            elif change <= -THRESHOLD:
                line += " 🔻 -5%"
                alert_triggered = True

        # ===== SELL DATA =====
        if sell_coin and sell_rp and top_price:
            line += f"\n   🧱 Top Sell Price: Rp {format_rupiah(top_price)}"
            line += f"\n   🪙 Total Sell: {sell_coin:,.2f}".replace(",", ".")
            line += f"\n   💰 Total Value: Rp {format_rupiah(sell_rp)}"

        # ===== STRONGEST WALL =====
        if strong_price and strong_coin and strong_value:
            line += f"\n   🧱 Strongest Wall:"
            line += f"\n      Price: Rp {format_rupiah(strong_price)}"
            line += f"\n      Vol  : {strong_coin:,.2f}".replace(",", ".")
            line += f"\n      Val  : Rp {format_rupiah(strong_value)}"

        message += line + "\n\n"
        new_prices[coin] = price

    print(message)

    # send normal update
    send_telegram(message)

    # send alert if triggered
    if alert_triggered:
        send_telegram("🚨 PRICE ALERT (±5%) 🚨\n\n" + message)

    last_prices = new_prices

# =========================
# LOOP (30 MIN)
# =========================
if __name__ == "__main__":
    print("Bot started...\n")

    job()

    while True:
        time.sleep(1800)
        job()
