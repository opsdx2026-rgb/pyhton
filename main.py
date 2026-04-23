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
    url = "https://api.indodax.com/api/ticker/drx_idr"
    response = requests.get(url)
    return response.json()

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
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    message = f"""
📊 Indodax Update
⏰ {timestamp}

DRX: Rp {data['ticker']['last']:,.0f}
CST: Rp {data['ticker']['last'] * 39.25:,.0f}
ANOA: Rp {data['ticker']['last'] * 8.13:,.0f}
"""
    
    send_telegram(message)

schedule.every(1).minutes.do(job)

if __name__ == "__main__":
    print("Bot started...")
    while True:
        schedule.run_pending()
        time.sleep(1)
