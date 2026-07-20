import os
import time
import requests
import pandas as pd
from datetime import datetime
from threading import Thread
from flask import Flask

app = Flask(__name__)

DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1527005996201939168/1_x_r20GPpTKdV4l9YsU_-qsdqaZnBneNSzDWpYo9zzz6aKUWYlKens-tnUqZjMm1Coz"

# OANDA Credentials (Cleaned)
OANDA_API_KEY = "333c26463f780224a2861d9fea171bf0-57ecca2eaecf84d074a389e01344c39dc6".strip()
OANDA_ACCOUNT_ID = "101-001-39759925-001".strip()

@app.route('/')
def home():
    return "OANDA Direct Gold Spot (XAU_USD) Bot is Live on Railway!"

def get_oanda_gold_data():
    try:
        # 401 ERROR FIX: Naye accounts ke liye direct v20 trade endpoint use hota hai
        url = "https://api-fxtrade.oanda.com/v3/instruments/XAU_USD/candles"
        
        headers = {
            "Authorization": f"Bearer {OANDA_API_KEY}",
            "Content-Type": "application/json"
        }
        
        params = {
            "granularity": "M5",
            "count": 50
        }
        
        response = requests.get(url, headers=headers, params=params, timeout=10)
        
        # Fallback: Agar upar wala accept na kare to practice sub-server check karein
        if response.status_code == 401:
            fallback_url = "https://api-fxpractice.oanda.com/v3/instruments/XAU_USD/candles"
            response = requests.get(fallback_url, headers=headers, params=params, timeout=10)
            
        if response.status_code != 200:
            print(f"OANDA API Error: Status {response.status_code} - {response.text}")
            return None
            
        data = response.json()
        candles = data.get('candles', [])
        
        if not candles:
            return None
            
        parsed_data = []
        for c in candles:
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
            
        return pd.DataFrame(parsed_data)
        
    except Exception as e:
        print(f"Error fetching data from OANDA: {e}")
        return None

def monitor_volume():
    print("Background Volume Monitor Started using DIRECT OANDA CLOUD API...")
    last_checked_time = None
    
    lengthInput = 20          
    thresholdInput = 2.0      
    enableCombo = True        
    priceChangeThresh = 1.5   
    
    while True:
        try:
            df = get_oanda_gold_data()
            if df is not None and len(df) > lengthInput:
                # Candle close hone par accurate analysis (Index -2 closed candle hoti hai)
                last_candle = df.iloc[-2] 
                previous_candles = df.iloc[-(lengthInput + 2):-2] 
                
                volMA = previous_candles['volume'].mean()
                spikeLevel = volMA * thresholdInput
                
                current_volume = last_candle['volume']
                current_open = last_candle['open']
                current_close = last_candle['close']
                
                if current_volume >= spikeLevel and volMA > 0:
                    isBullish = current_close >= current_open
                    spikeRatio = current_volume / volMA
                    price_change_percent = (abs(current_close - current_open) / current_open) * 100
                    isCombo = enableCombo and price_change_percent >= priceChangeThresh
                    
                    candle_time = last_candle['time'].strftime('%Y-%m-%d %H:%M:%S')
                    
                    if candle_time != last_checked_time:
                        last_checked_time = candle_time
                        
                        if isCombo:
                            status_emoji = "🔥 **OANDA CLOUD: COMBO SPIKE DETECTED (5M)!** 🔥"
                            color_marker = "Combo Spike (High Vol & High Move) ⚡"
                        elif isBullish:
                            status_emoji = "🟢 **OANDA CLOUD: BULLISH VOLUME SPIKE (5M)!** 📈"
                            color_marker = "Bullish (Green) 🟢"
                        else:
                            status_emoji = "🔴 **OANDA CLOUD: BEARISH VOLUME SPIKE (5M)!** 📉"
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
                        
                        try:
                            requests.post(DISCORD_WEBHOOK_URL, json={"content": message}, timeout=5)
                            print(f"OANDA Cloud Alert sent for {candle_time}!")
                        except Exception as discord_err:
                            print(f"Discord error: {discord_err}")
        except Exception as loop_err:
            print(f"Loop error: {loop_err}")
            
        time.sleep(30) # Har 30 seconds baad loop data fresh karega

def run_background_tasks():
    monitor_thread = Thread(target=monitor_volume)
    monitor_thread.daemon = True
    monitor_thread.start()

if __name__ == "__main__":
    run_background_tasks()
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
