import os
import requests
from datetime import datetime
import pytz
import time

# =========================
# CONFIG
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN", "8730580443:AAEIp0lVVUItXN_4smxKdUqWT9UT3M1hOW4")

CHAT_IDS = [8495972050, -5280540812]

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
# TELEGRAM SEND
# =========================
def send_telegram(message):
    for chat_id in CHAT_IDS:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        try:
            print(f"Sending to {chat_id}...")
            response = requests.post(url, data={"chat_id": chat_id, "text": message})
            print(f"Response status: {response.status_code}")
            print(f"Response: {response.text}")
        except Exception as e:
            print(f"Telegram error: {e}")


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
            message += f"{coin}: error\n"
            continue

        old_price = last_prices.get(coin)
        change = calc_change(old_price, price)

        line = f"{coin}: Rp {format_rupiah(price)}"

        if old_price:
            line += f" ({change:.2f}%)"

            if change >= THRESHOLD:
                line += " 🚀 +5%"
                alert_triggered = True

            elif change <= -THRESHOLD:
                line += " 🔻 -5%"
                alert_triggered = True

        message += line + "\n"
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

    job()  # run immediately

    while True:
        time.sleep(1800)  # 30 minutes
        job()
