import os
import time
import requests
import pandas as pd
from datetime import datetime
from threading import Thread
from flask import Flask

# Flask App setup (Railway ko active rakhne ke liye)
app = Flask(__name__)

# Discord Webhook URL
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1527005996201939168/1_x_r20GPpTKdV4l9YsU_-qsdqaZnBneNSzDWpYo9zzz6aKUWYlKens-tnUqZjMm1Coz"

# OANDA API Credentials (Demo Account)
OANDA_API_KEY = "333c26463f780224a2861d9fea171bf0-57ecca2eaecf84d074a389e01344c39dc6"
OANDA_ACCOUNT_ID = "101-001-39759925-001"

@app.route('/')
def home():
    return "Gold Spot (XAU/USD) Volume Monitor Live on OANDA API!"

# Direct OANDA API se Gold Spot (XAU_USD) 5M Candles Fetch Karne Ka Function
def get_oanda_gold_data():
    try:
        # OANDA Practice Server Endpoint
        url = "https://api-fxpractice.oanda.com/v3/instruments/XAU_USD/candles"
        
        headers = {
            "Authorization": f"Bearer {OANDA_API_KEY}",
            "Content-Type": "application/json"
        }
        
        # granularity='M5' (5-Minute candles), count=50 (pichli 50 candles average nikalne ke liye)
        params = {
            "granularity": "M5",
            "count": 50
        }
        
        response = requests.get(url, headers=headers, params=params, timeout=10)
        
        if response.status_code != 200:
            print(f"OANDA API Error: Status {response.status_code} - {response.text}")
            return None
            
        data = response.json()
        candles = data.get('candles', [])
        
        if not candles:
            print("No candles returned from OANDA.")
            return None
            
        # Parse Candles Data
        parsed_data = []
        for c in candles:
            # Sirf complete candles ka data uthana hai (c['complete'] == True)
            # Lekin real-time check ke liye hum last candle (chahe incomplete ho) bhi check karenge
            volume = float(c.get('volume', 0))
            candle_time = datetime.strptime(c['time'][:19], "%Y-%m-%dT%H:%M:%S")
            
            mid = c.get('mid', {})
            open_p = float(mid.get('o', 0))
            close_p = float(mid.get('c', 0))
            
            parsed_data.append({
                'time': candle_time,
                'open': open_p,
                'close': close_p,
                'volume': volume
            })
            
        df = pd.DataFrame(parsed_data)
        return df
        
    except Exception as e:
        print(f"Error fetching data from OANDA: {e}")
        return None

# Spike check karne ka loop (Har 1 minute baad check karega)
def monitor_volume():
    print("Background Volume Monitor Started using DIRECT OANDA API...")
    last_checked_time = None
    
    # --- Input Parameters (Exactly like Pine Script) ---
    lengthInput = 20          # Average Volume Period (Pichli 20 candles)
    thresholdInput = 2.0      # Spike Threshold Multiplier (2x)
    enableCombo = True        # Enable Combo Detection
    priceChangeThresh = 1.5   # Price Change Threshold (%) for Combo
    
    while True:
        try:
            df = get_oanda_gold_data()
            if df is not None and len(df) > lengthInput:
                # OANDA dynamic price & volume check
                last_candle = df.iloc[-1]
                previous_candles = df.iloc[-(lengthInput + 1):-1] # Pichli 20 candles
                
                # Volume SMA (volMA)
                volMA = previous_candles['volume'].mean()
                spikeLevel = volMA * thresholdInput
                
                current_volume = last_candle['volume']
                current_open = last_candle['open']
                current_close = last_candle['close']
                
                # Spike Logic
                isSpike = current_volume >= spikeLevel
                
                if isSpike and volMA > 0:
                    isBullish = current_close >= current_open
                    spikeRatio = current_volume / volMA
                    
                    # Price Change %
                    price_change_percent = (abs(current_close - current_open) / current_open) * 100
                    isCombo = enableCombo and price_change_percent >= priceChangeThresh
                    
                    candle_time = last_candle['time'].strftime('%Y-%m-%d %H:%M:%S')
                    
                    # Prevent duplicate alerts
                    if candle_time != last_checked_time:
                        last_checked_time = candle_time
                        
                        # Formatting Emojis based on Pine Script logic
                        if isCombo:
                            status_emoji = "🔥 **OANDA: COMBO SPIKE DETECTED (5M)!** 🔥"
                            color_marker = "Combo Spike (High Vol & High Move) ⚡"
                        elif isBullish:
                            status_emoji = "🟢 **OANDA: BULLISH VOLUME SPIKE (5M)!** 📈"
                            color_marker = "Bullish (Green) 🟢"
                        else:
                            status_emoji = "🔴 **OANDA: BEARISH VOLUME SPIKE (5M)!** 📉"
                            color_marker = "Bearish (Red) 🔴"
                            
                        message = (
                            f"{status_emoji}\n"
                            f"⏰ **Timeframe:** 5-Minute (5M)\n"
                            f"🕒 **Candle Time:** {candle_time} (GMT)\n"
                            f"📊 **Current Volume (Ticks):** {int(current_volume):,}\n"
                            f"📈 **Volume SMA (20):** {int(volMA):,}\n"
                            f"🚀 **Spike Ratio:** {spikeRatio:.2f}x (Threshold: {thresholdInput}x)\n"
                            f"💵 **Candle Type:** {color_marker}\n"
                            f"⚡ **Price Change:** {price_change_percent:.3f}%\n"
                            f"💰 **Close Price:** ${current_close:.2f}"
                        )
                        
                        # Send to Discord
                        try:
                            requests.post(DISCORD_WEBHOOK_URL, json={"content": message}, timeout=5)
                            print(f"OANDA Alert sent successfully for {candle_time}!")
                        except Exception as discord_err:
                            print(f"Failed to send Discord alert: {discord_err}")
            else:
                if df is None:
                    pass
                else:
                    print(f"Not enough data points. Needed {lengthInput}, got {len(df)}")
        except Exception as loop_err:
            print(f"Error in OANDA monitor loop: {loop_err}")
            
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
