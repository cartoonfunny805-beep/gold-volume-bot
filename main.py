import os
import time
import requests
import pandas as pd
from datetime import datetime
from threading import Thread
from flask import Flask

app = Flask(__name__)

DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1527005996201939168/1_x_r20GPpTKdV4l9YsU_-qsdqaZnBneNSzDWpYo9zzz6aKUWYlKens-tnUqZjMm1Coz"

# OANDA Credentials
OANDA_API_KEY = "333c26463f780224a2861d9fea171bf0-57ecca2eaecf84d074a389e01344c39dc6".strip()
OANDA_ACCOUNT_ID = "101-001-39759925-001".strip()

@app.route('/')
def home():
    return "OANDA Multi-Endpoint Gold Bot is Live!"

def get_oanda_gold_data():
    # 3 different URLs jo OANDA use karta hai naye aur purane accounts ke liye
    endpoints = [
        f"https://api-fxpractice.oanda.com/v3/accounts/{OANDA_ACCOUNT_ID}/instruments/XAU_USD/candles",
        "https://api-fxpractice.oanda.com/v3/instruments/XAU_USD/candles",
        "https://api-fxtrade.oanda.com/v3/instruments/XAU_USD/candles"
    ]
    
    headers = {
        "Authorization": f"Bearer {OANDA_API_KEY}",
        "Content-Type": "application/json"
    }
    
    params = {
        "granularity": "M5",
        "count": 50
    }
    
    response = None
    for url in endpoints:
        try:
            print(f"Trying endpoint: {url}")
            res = requests.get(url, headers=headers, params=params, timeout=7)
            if res.status_code == 200:
                response = res
                print("Successfully connected to OANDA!")
                break
            else:
                print(f"Failed with status {res.status_code}")
        except Exception as e:
            print(f"Connection error on URL: {e}")
            
    if response is None or response.status_code != 200:
        print("All OANDA endpoints rejected the API Key. Status 401 remains.")
        return None
        
    try:
        data = response.json()
        candles = data.get('candles', [])
        if not candles:
            return None
            
        parsed_data = []
        for c in candles:
            volume = float(c.get('volume', 0))
            candle_time = datetime.strptime(c['time'][:19], "%Y-%m-%dT%H:%M:%S")
            mid = c.get('mid', {})
            parsed_data.append({
                'time': candle_time,
                'open': float(mid.get('o', 0)),
                'close': float(mid.get('c', 0)),
                'volume': volume
            })
        return pd.DataFrame(parsed_data)
    except Exception as parse_err:
        print(f"Parsing error: {parse_err}")
        return None

def monitor_volume():
    print("Background Multi-Endpoint Monitor Started...")
    last_checked_time = None
    lengthInput = 20          
    thresholdInput = 2.0      
    
    while True:
        try:
            df = get_oanda_gold_data()
            if df is not None and len(df) > lengthInput:
                last_candle = df.iloc[-2] 
                previous_candles = df.iloc[-(lengthInput + 2):-2] 
                
                volMA = previous_candles['volume'].mean()
                spikeLevel = volMA * thresholdInput
                
                current_volume = last_candle['volume']
                current_open = last_candle['open']
                current_close = last_candle['close']
                
                if current_volume >= spikeLevel and volMA > 0:
                    spikeRatio = current_volume / volMA
                    candle_time = last_candle['time'].strftime('%Y-%m-%d %H:%M:%S')
                    
                    if candle_time != last_checked_time:
                        last_checked_time = candle_time
                        
                        isBullish = current_close >= current_open
                        status_emoji = "🟢 **OANDA: BULLISH SPIKE!** 📈" if isBullish else "🔴 **OANDA: BEARISH SPIKE!** 📉"
                        
                        message = (
                            f"{status_emoji}\n"
                            f"⏰ **Timeframe:** 5M\n"
                            f"🕒 **Time:** {candle_time} (GMT)\n"
                            f"📊 **Volume:** {int(current_volume):,}\n"
                            f"🚀 **Ratio:** {spikeRatio:.2f}x\n"
                            f"💰 **Close:** ${current_close:.2f}"
                        )
                        requests.post(DISCORD_WEBHOOK_URL, json={"content": message}, timeout=5)
        except Exception as e:
            print(f"Loop error: {e}")
        time.sleep(30)

if __name__ == "__main__":
    monitor_thread = Thread(target=monitor_volume)
    monitor_thread.daemon = True
    monitor_thread.start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
