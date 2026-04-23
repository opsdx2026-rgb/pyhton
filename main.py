import os
import requests
from datetime import datetime
import schedule
import time

# =========================
# CONFIG
# =========================
BOT_TOKEN = os.getenv('BOT_TOKEN', '8730580443:AAEIp0lVVUItXN_4smxKdUqWT9UT3M1hOW4')

CHAT_IDS = [
    8495972050,-5280540812
]

# =========================
# INDODAX API
# =========================
def get_indodax_price():
    url = "https://indodax.com/api/ticker/drxidr"
    
    try:
        response = requests.get(url, timeout=10)

        if response.status_code != 200:
            print("Bad response:", response.status_code)
            return None

        data = response.json()

        if "ticker" not in data:
            print("Invalid data:", data)
            return None

        return data

    except Exception as e:
        print("API error:", e)
        return None

# =========================
# TELEGRAM
# =========================
def send_telegram(message):
    for chat_id in CHAT_IDS:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        data = {
            "chat_id": chat_id,
            "text": message
        }
        requests.post(url, data=data)

# =========================
# JOB
# =========================
def job():
    data = get_indodax_price()

    if not data:
        print("Skip (no data)")
        return

    price = float(data['ticker']['last'])

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    message = f"""
📊 Indodax Update
⏰ {timestamp}

DRX: Rp {price:,.0f}
CST: Rp {price * 39.25:,.0f}
ANOA: Rp {price * 8.13:,.0f}
"""

    send_telegram(message)

schedule.every(1).minutes.do(job)

if __name__ == "__main__":
    print("Bot started...")
    while True:
        schedule.run_pending()
        time.sleep(1)
