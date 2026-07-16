import os
import time
import requests
import pandas as pd
from datetime import datetime
from threading import Thread
from flask import Flask

# Flask App setup (Railway ko active rakhne ke liye)
app = Flask(__name__)

# Discord Webhook URL (Aapka URL bilkul sahi set hai)
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1527005996201939168/1_x_r20GPpTKdV4l9YsU_-qsdqaZnBneNSzDWpYo9zzz6aKUWYlKens-tnUqZjMm1Coz"

@app.route('/')
def home():
    return "Gold Volume Monitor Live! Only 5-Minute (5M) timeframe is active."

# Yahoo Finance se Gold (GC=F) 5M data fetch karne ka function
def get_gold_5m_data():
    try:
        # 5m interval aur 2d range (taake data points hamesha 20 se zyada rahein)
        url = "https://query1.finance.yahoo.com/v8/finance/chart/GC=F?interval=5m&range=2d"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code != 200:
            print(f"API Error: Status code {response.status_code}")
            return None
            
        data = response.json()
        
        if 'chart' in data and data['chart']['result'] and 'timestamp' in data['chart']['result'][0]:
            timestamps = data['chart']['result'][0]['timestamp']
            indicators = data['chart']['result'][0]['indicators']['quote'][0]
            
            volumes = indicators.get('volume', [])
            closes = indicators.get('close', [])
            opens = indicators.get('open', [])
            
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

# Spike check karne ka loop (Har 1 minute baad check karega)
def monitor_volume():
    print("Background Volume Monitor Started for 5-Minute Timeframe...")
    last_checked_time = None
    
    # --- Input Parameters (Exactly like Pine Script) ---
    lengthInput = 20          # Average Volume Period (Pichli 20 candles)
    thresholdInput = 2.0      # Spike Threshold Multiplier (2x)
    enableCombo = True        # Enable Combo Detection
    priceChangeThresh = 1.5   # Price Change Threshold (%) for Combo
    
    while True:
        try:
            df = get_gold_5m_data()
            if df is not None and len(df) > lengthInput:
                last_candle = df.iloc[-1]
                previous_candles = df.iloc[-(lengthInput + 1):-1] # Pichli 20 candles
                
                # Volume SMA (volMA)
                volMA = previous_candles['volume'].mean()
                spikeLevel = volMA * thresholdInput
                
                current_volume = last_candle['volume']
                current_open = last_candle['open']
                current_close = last_candle['close']
                
                # Spike Logic (isSpike = volume >= spikeLevel)
                isSpike = current_volume >= spikeLevel
                
                if isSpike and volMA > 0:
                    isBullish = current_close >= current_open
                    spikeRatio = current_volume / volMA
                    
                    # Price Change %: math.abs(close - open) / open * 100
                    price_change_percent = (abs(current_close - current_open) / current_open) * 100
                    
                    # Combo Logic: enableCombo and isSpike and priceChangePercent >= priceChangeThresh
                    isCombo = enableCombo and price_change_percent >= priceChangeThresh
                    
                    candle_time = last_candle['time'].strftime('%Y-%m-%d %H:%M:%S')
                    
                    # Prevent duplicate alerts for the same candle
                    if candle_time != last_checked_time:
                        last_checked_time = candle_time
                        
                        # Formatting Emojis and Alerts
                        if isCombo:
                            status_emoji = "🔥 **COMBO SPIKE DETECTED (5M)!** 🔥"
                            color_marker = "Combo Spike (High Vol & High Move) ⚡"
                        elif isBullish:
                            status_emoji = "🟢 **BULLISH VOLUME SPIKE (5M)!** 📈"
                            color_marker = "Bullish (Green) 🟢"
                        else:
                            status_emoji = "🔴 **BEARISH VOLUME SPIKE (5M)!** 📉"
                            color_marker = "Bearish (Red) 🔴"
                            
                        message = (
                            f"{status_emoji}\n"
                            f"⏰ **Timeframe:** 5-Minute (5M)\n"
                            f"🕒 **Candle Time:** {candle_time}\n"
                            f"📊 **Current Volume:** {int(current_volume):,}\n"
                            f"📈 **Volume SMA (20):** {int(volMA):,}\n"
                            f"🚀 **Spike Ratio:** {spikeRatio:.2f}x (Threshold: {thresholdInput}x)\n"
                            f"💵 **Candle Type:** {color_marker}\n"
                            f"⚡ **Price Change:** {price_change_percent:.3f}%\n"
                            f"💰 **Close Price:** ${current_close:.2f}"
                        )
                        
                        # Send to Discord
                        try:
                            requests.post(DISCORD_WEBHOOK_URL, json={"content": message}, timeout=5)
                            print(f"Alert sent successfully for {candle_time}!")
                        except Exception as discord_err:
                            print(f"Failed to send Discord alert: {discord_err}")
            else:
                if df is None:
                    pass
                else:
                    print(f"Not enough data points. Needed {lengthInput}, got {len(df)}")
        except Exception as loop_err:
            print(f"Error in monitor loop: {loop_err}")
            
        # Har 60 seconds baad checks repeat karega
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
