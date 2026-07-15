import time
import requests
import pandas as pd
import os

# Web server taake Render isko active rakhe
from flask import Flask
import threading

app = Flask('')

@app.route('/')
def home():
    return "Bot is running 24/7!"

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# Aapka Discord Webhook URL
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1527005996201939168/1_x_r20GPpTKdV4l9YsU_-qsdqaZnBneNSzDWpYo9zzz6aKUWYlKens-tnUqZjMm1Coz"
SYMBOL = "PAXGUSDT"
INTERVALS = ["5m", "30m"]

def send_discord_alert(message):
    payload = {"content": message}
    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json=payload)
    except Exception as e:
        print("Discord send error:", e)

def get_volume_data(interval):
    url = f"https://api.binance.com/api/v3/klines?symbol={SYMBOL}&interval={interval}&limit=50"
    try:
        response = requests.get(url).json()
        df = pd.DataFrame(response, columns=[
            'open_time', 'open', 'high', 'low', 'close', 'volume', 
            'close_time', 'quote_volume', 'count', 'taker_buy_volume', 
            'taker_buy_quote_volume', 'ignore'
        ])
        df['volume'] = df['volume'].astype(float)
        return df
    except Exception as e:
        print(f"Error fetching data: {e}")
        return None

def monitor_volume():
    last_alerted_candle = {"5m": None, "30m": None}
    print("🚀 Gold Volume Monitor Live!")
    send_discord_alert("🚀 **Gold (XAUUSD) 24/7 Cloud Bot Active!**")
    
    while True:
        for interval in INTERVALS:
            df = get_volume_data(interval)
            if df is None or len(df) < 20:
                continue
            
            closed_candle_time = df.iloc[-2]['open_time']
            closed_candle_volume = df.iloc[-2]['volume']
            avg_volume = df.iloc[-22:-2]['volume'].mean()
            
            if avg_volume > 0:
                ratio = closed_candle_volume / avg_volume
                if ratio >= 2.0 and last_alerted_candle[interval] != closed_candle_time:
                    price = df.iloc[-2]['close']
                    message = (
                        f"⚠️ **GOLD (XAUUSD) VOLUME SPIKE!** ⚠️\n"
                        f"⏱️ **Timeframe:** {interval}\n"
                        f"📈 **Current Volume:** {closed_candle_volume:.2f}\n"
                        f"📊 **Average Volume:** {avg_volume:.2f}\n"
                        f"🔥 **Spike Multiplier:** {ratio:.2f}x\n"
                        f"💰 **Approx Price:** ${float(price):.2f}"
                    )
                    send_discord_alert(message)
                    last_alerted_candle[interval] = closed_candle_time
        time.sleep(10)

if __name__ == "__main__":
    t = threading.Thread(target=run_web_server)
    t.start()
    monitor_volume()
