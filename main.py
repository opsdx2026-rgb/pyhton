import requests
from datetime import datetime
import time

# =========================
# CONFIG
# =========================
import os
BOT_TOKEN = os.getenv('BOT_TOKEN', '8730580443:AAEIp0lVVUItXN_4smxKdUqWT9UT3M1hOW4')

CHAT_IDS = [
    8495972050,-5280540812
]

COINS = {
    "DRX": "drxidr",
    "CST": "cstidr",
    "ANOA": "anoaidr"
}

THRESHOLD = 5  # percent alert

last_prices = {}

# =========================
# TELEGRAM SEND
# =========================
def send_telegram(message):
    for chat_id in CHAT_IDS:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        data = {
            "chat_id": chat_id,
            "text": message
        }
        try:
            requests.post(url, data=data)
        except Exception as e:
            print("Telegram error:", e)

# =========================
# GET PRICE
# =========================
def get_price(pair):
    try:
        url = f"https://indodax.com/api/ticker/{pair}"
        r = requests.get(url, timeout=5)
        data = r.json()

        if "ticker" in data:
            return float(data["ticker"]["last"])
        return None

    except Exception as e:
        print("Error:", e)
        return None

# =========================
# FORMAT
# =========================
def format_price(price):
    return f"{int(price):,}".replace(",", ".")

# =========================
# CHANGE %
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

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    message = f"📊 Indodax Update\n⏰ {now}\n\n"

    new_prices = {}
    alert_triggered = False

    for coin, pair in COINS.items():
        price = get_price(pair)

        if price is None:
            message += f"{coin}: error\n"
            continue

        old_price = last_prices.get(coin)
        change = calc_change(old_price, price)

        line = f"{coin}: Rp {format_price(price)}"

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

    # ALWAYS send update every 30 min
    send_telegram(message)

    # EXTRA alert if threshold hit
    if alert_triggered:
        send_telegram("🚨 PRICE ALERT (±5%) 🚨\n\n" + message)

    last_prices = new_prices


# =========================
# LOOP (30 MIN)
# =========================
if __name__ == "__main__":
    print("Bot started...\n")

    while True:
        job()
        time.sleep(1800)  # 30 minutes