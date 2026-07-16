import os
import time
import requests
import pandas as pd
from datetime import datetime
from threading import Thread
from flask import Flask

# Flask App setup (Railway ko active rakhne ke liye)
app = Flask(__name__)

# Discord Webhook URL (Aapka bilkul sahi webhook set kar diya hai)
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1527005996201939168/1_x_r20GPpTKdV4l9YsU_-qsdqaZnBneNSzDWpYo9zzz6aKUWYlKens-tnUqZjMm1Coz"

@app.route('/')
def home():
    return "Gold Volume Monitor Live! Server is running."

# Yahoo Finance se Gold (XAUUSD / GC=F) ka data fetch karne ka function
def get_gold_data():
    try:
        # Last 1 day ka data 5-minute interval par
        url = "https://query1.finance.yahoo.com/v8/finance/chart/GC=F?interval=5m&range=1d"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers)
        data = response.json()
        
        timestamps = data['chart']['result'][0]['timestamp']
        indicators = data['chart']['result'][0]['indicators']['quote'][0]
        
        volumes = indicators['volume']
        closes = indicators['close']
        
        df = pd.DataFrame({
            'time': [datetime.fromtimestamp(t) for t in timestamps],
            'close': closes,
            'volume': volumes
        })
        df = df.dropna().reset_index(drop=True)
        return df
    except Exception as e:
        print(f"Error fetching data from Yahoo Finance: {e}")
        return None

# Spike check karne ka loop (Har 1 minute baad chalega)
def monitor_volume():
    print("Background Volume Monitor Started...")
    last_checked_time = None
    
    while True:
        df = get_gold_data()
        if df is not None and len(df) > 20:
            last_candle = df.iloc[-1]
            previous_candles = df.iloc[-21:-1] # Pichli 20 candles ka average
            avg_volume = previous_candles['volume'].mean()
            current_volume = last_candle['volume']
            
            if avg_volume > 0:
                ratio = current_volume / avg_volume
                candle_time = last_candle['time'].strftime('%Y-%m-%d %H:%M:%S')
                
                # Agar volume 2x ya us se zyada ho aur alert pehle na gaya ho
                if ratio >= 2.0 and candle_time != last_checked_time:
                    last_checked_time = candle_time
                    message = (
                        f"⚠️ **GOLD (XAUUSD) VOLUME SPIKE DETECTED!** ⚠️\n"
                        f"🕒 **Time (5M):** {candle_time}\n"
                        f"📊 **Current Volume:** {int(current_volume):,}\n"
                        f"📈 **Average Volume (20 periods):** {int(avg_volume):,}\n"
                        f"🚀 **Spike Ratio:** {ratio:.2f}x (More than 2x!)\n"
                        f"💰 **Close Price:** ${last_candle['close']:.2f}"
                    )
                    # Send alert to Discord
                    try:
                        requests.post(DISCORD_WEBHOOK_URL, json={"content": message})
                        print(f"Alert sent successfully for {candle_time}!")
                    except Exception as discord_err:
                        print(f"Failed to send Discord alert: {discord_err}")
        
        time.sleep(60)

# Background Thread start karne ka function
def run_background_tasks():
    monitor_thread = Thread(target=monitor_volume)
    monitor_thread.daemon = True
    monitor_thread.start()

if __name__ == "__main__":
    run_background_tasks()
    
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
