import os
import time
import requests
import pandas as pd
from datetime import datetime
from threading import Thread
from flask import Flask

# Flask App setup (Railway ko active rakhne ke liye)
app = Flask(__name__)

# Discord Webhook URL (Aapka bilkul sahi webhook set hai)
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1527005996201939168/1_x_r20GPpTKdV4l9YsU_-qsdqaZnBneNSzDWpYo9zzz6aKUWYlKens-tnUqZjMm1Coz"

@app.route('/')
def home():
    return "Gold Volume Monitor Live! Server is running."

# Yahoo Finance se Gold (GC=F) ka real-time data fetch karne ka function (With Error Handling)
def get_gold_data():
    try:
        # GC=F Gold Futures hai jiska volume OANDA se boht close match karta hai
        url = "https://query1.finance.yahoo.com/v8/finance/chart/GC=F?interval=5m&range=1d"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code != 200:
            print(f"API Error: Status code {response.status_code}")
            return None
            
        data = response.json()
        
        # Check if proper data structure exists (to avoid 'timestamp' error)
        if 'chart' in data and data['chart']['result'] and 'timestamp' in data['chart']['result'][0]:
            timestamps = data['chart']['result'][0]['timestamp']
            indicators = data['chart']['result'][0]['indicators']['quote'][0]
            
            volumes = indicators.get('volume', [])
            closes = indicators.get('close', [])
            opens = indicators.get('open', [])
            
            # Agar data khali hai to skip karein
            if not timestamps or not volumes or not closes:
                return None
                
            df = pd.DataFrame({
                'time': [datetime.fromtimestamp(t) for t in timestamps],
                'open': opens,
                'close': closes,
                'volume': volumes
            })
            df = df.dropna().reset_index(drop=True)
            return df
        else:
            print("Required fields missing in API response.")
            return None
    except Exception as e:
        print(f"Error fetching data: {e}")
        return None

# Spike check karne ka loop (Har 1 minute baad chalega)
def monitor_volume():
    print("Background Volume Monitor Started...")
    last_checked_time = None
    
    lengthInput = 20          # Average Volume Period (Pichli 20 candles)
    thresholdInput = 2.0      # Spike Threshold Multiplier (2x)
    
    while True:
        try:
            df = get_gold_data()
            if df is not None and len(df) > lengthInput:
                last_candle = df.iloc[-1]
                previous_candles = df.iloc[-(lengthInput + 1):-1] # Pichli 20 candles
                
                # Simple Moving Average (SMA) of Volume
                volMA = previous_candles['volume'].mean()
                spikeLevel = volMA * thresholdInput
                
                current_volume = last_candle['volume']
                current_open = last_candle['open']
                current_close = last_candle['close']
                
                # Check Spike (isSpike = volume >= spikeLevel)
                isSpike = current_volume >= spikeLevel
                
                if isSpike and volMA > 0:
                    # Bullish or Bearish check
                    isBullish = current_close >= current_open
                    spikeRatio = current_volume / volMA
                    
                    # Price Change %
                    price_change_percent = (abs(current_close - current_open) / current_open) * 100
                    candle_time = last_candle['time'].strftime('%Y-%m-%d %H:%M:%S')
                    
                    # Prevent duplicate alerts
                    if candle_time != last_checked_time:
                        last_checked_time = candle_time
                        
                        if isBullish:
                            status_emoji = "🟢 **BULLISH VOLUME SPIKE!** 📈"
                            color_marker = "Bullish (Green) 🟢"
                        else:
                            status_emoji = "🔴 **BEARISH VOLUME SPIKE!** 📉"
                            color_marker = "Bearish (Red) 🔴"
                            
                        message = (
                            f"{status_emoji}\n"
                            f"🕒 **Time (5M):** {candle_time}\n"
                            f"📊 **Current Volume:** {int(current_volume):,}\n"
                            f"📈 **Volume SMA (20):** {int(volMA):,}\n"
                            f"🚀 **Spike Ratio:** {spikeRatio:.2f}x (Threshold: {thresholdInput}x)\n"
                            f"💵 **Candle Type:** {color_marker}\n"
                            f"⚡ **Price Change:** {price_change_percent:.3f}%\n"
                            f"💰 **Close Price (GC=F):** ${current_close:.2f}"
                        )
                        
                        # Discord Webhook Send
                        try:
                            requests.post(DISCORD_WEBHOOK_URL, json={"content": message}, timeout=5)
                            print(f"Alert sent successfully for {candle_time}!")
                        except Exception as discord_err:
                            print(f"Failed to send Discord alert: {discord_err}")
            else:
                if df is None:
                    print("Skipping check as data was None.")
                else:
                    print(f"Not enough data points. Needed {lengthInput}, got {len(df)}")
        except Exception as loop_err:
            print(f"Error in monitor loop: {loop_err}")
            
        # Har 60 seconds baad check karega (1 minute)
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
