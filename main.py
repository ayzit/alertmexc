import os
import sys
import time
import atexit
import pandas as pd
import requests
import BackgroundScheduler
import load_dotenv
import Flask
import Thread
from flask 
from threading 
from apscheduler.schedulers.background 
from dotenv 

load_dotenv()

CMC_API_KEYS = [
    os.getenv("CMC_API_KEY1"),
    os.getenv("CMC_API_KEY2"),
    os.getenv("CMC_API_KEY3"),
]
CMC_QUOTE_URL = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"


def get_marketcap_with_keys(symbols):
    for api_key in CMC_API_KEYS:
        if not api_key:
            continue
        headers = {"X-CMC_PRO_API_KEY": api_key}
        params = {"symbol": ",".join(symbols)}
        try:
            resp = requests.get(CMC_QUOTE_URL, headers=headers, params=params, timeout=15)
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            continue
    return None


def update_coin_list_from_mexc_and_cmc():
    print("Coin listesi güncelleniyor...")
    try:
        resp = requests.get("https://api.mexc.com/api/v3/ticker/24hr", timeout=15)
        mexc_data = resp.json()
        sorted_coins = sorted(mexc_data, key=lambda x: float(x.get("quoteVolume", 0)), reverse=True)
        top_300 = sorted_coins[:300]

        symbols = []
        symbol_volume_map = {}

        for coin in top_300:
            symbol = coin['symbol']
            if symbol.endswith('USDT'):
                base = symbol.replace('USDT', '')
                volume = float(coin.get('quoteVolume', 0))
                symbols.append(base)
                symbol_volume_map[base] = volume

        coin_list = []
        with open("coin_list.txt", "w", encoding="utf-8") as f:
            for i in range(0, len(symbols), 100):
                batch = symbols[i:i+100]
                print(f"\n--- CMC sorgu: {batch} ---")
                cmc_data = get_marketcap_with_keys(batch)
                if not cmc_data or "data" not in cmc_data:
                    print("CMC API'den veri alınamadı veya 'data' alanı yok.")
                    continue

                for sym in batch:
                    cmc_info = cmc_data["data"].get(sym)
                    if not cmc_info:
                        print(f"⛔ {sym}: CoinMarketCap'te bulunamadı (sembol uyuşmazlığı olabilir).")
                        continue
                    try:
                        marketcap = float(cmc_info["quote"]["USD"]["market_cap"])
                        volume = symbol_volume_map.get(sym, 0)
                        oran = volume / marketcap if marketcap else 0

                        print(f"🔎 {sym}: Volume={volume:.2f}, MarketCap={marketcap:.2f}, Oran={oran:.4f}")

                        if marketcap > 0 and oran > 0.01:
                            coin_list.append(sym)
                            f.write(f"{sym},{volume},{marketcap}\n")
                            print(f"✅ {sym} eklendi (oran={oran:.4f})")
                        else:
                            print(f"⚠️ {sym} elendi: oran çok düşük ({oran:.4f})")

                    except Exception as e:
                        print(f"🚨 {sym}: hesaplama hatası: {e}")
                        continue
                time.sleep(1)
        print(f"Filtrelenmiş coin sayısı: {len(coin_list)}")
        globals()["coin_list"] = coin_list
    except Exception as e:
        print(f"Coin listesi güncellenirken hata: {e}")

def send_telegram_alert(msg):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram ayarları eksik!")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"}
    try:
        requests.post(url, data=data, timeout=10)
    except Exception as e:
        print(f"Telegram mesaj hatası: {e}")

def check_ma_condition_changes(ma_condition_coins):
    # Bu örnekte sadece True dönüyor
    return True

def check_ma_signals():
    try:
        alert_list = []
        ma_condition_coins = []

        for coin in coin_list:
            df = pd.DataFrame(requests.get(
                f"https://api.mexc.com/api/v3/klines?symbol={coin}&interval=1h&limit=100"
            ).json(), columns=["time", "open", "high", "low", "close", "volume", "close_time", "qav", "trades", "tbv", "tbq", "ignore"])
            df["close"] = pd.to_numeric(df["close"])
            df["open"] = pd.to_numeric(df["open"])
            df["ma7"] = df["close"].rolling(window=7).mean()
            df["ma25"] = df["close"].rolling(window=25).mean()
            if df["ma7"].iloc[-1] > df["ma25"].iloc[-1]:
                rsi_value = 70  # Örnek sabit RSI
                consecutive_hours = 1
                consecutive_count = 1
                direction_emoji = "🟢" if df["close"].iloc[-1] > df["open"].iloc[-1] else "🔴"
                pct_diff = (df["close"].iloc[-1] - df["open"].iloc[-1]) / df["open"].iloc[-1] * 100
                pct_diff_str = f"{pct_diff:+.1f}%"
                rsi_arrow = "🔺"
                up_long = sum(df["close"].iloc[-5:] > df["open"].iloc[-5:])
                down_long = 5 - up_long
                alert_text = f"{coin}-{consecutive_hours}h-R{int(rsi_value)}-{consecutive_count}{direction_emoji} {pct_diff_str} {rsi_arrow} L{up_long}/S{down_long}"
                alert_list.append((datetime.now(tz=TZ), alert_text))

        if check_ma_condition_changes(ma_condition_coins):
            if alert_list:
                alert_list.sort(key=lambda x: x[0])
                msg = "🔺 MA(7)>MA(25) 1H:\n" + '\n'.join(alert for _, alert in alert_list)
                send_telegram_alert(msg)
                with open("alerts_log.csv", "a", encoding="utf-8") as f:
                    for _, alert in alert_list:
                        f.write(f"{datetime.now(tz=TZ)}, {alert}\n")
            else:
                print("Hiçbir coin'de MA(7)>MA(25) sinyali yok.")
        else:
            print("Koşullar değişmedi, mesaj gönderilmedi.")

    except Exception as e:
        error_msg = f"Bot hatası: {e}"
        print(f"❌ {error_msg}")
        send_telegram_alert(error_msg)

app = Flask('')

@app.route('/')
def home():
    return "MEXC MA Alert Bot is running!"

@app.route('/test')
def manual_test():
    check_ma_signals()
    return "Manuel test tamamlandı."

@app.route('/status')
def status():
    return f"""
    <h2>Bot Durumu</h2>
    <p>Token: {'✓' if TELEGRAM_TOKEN else '✗'}</p>
    <p>Chat ID: {'✓' if TELEGRAM_CHAT_ID else '✗'}</p>
    <p>Kontrol edilen coinler: {len(coin_list)}</p>
    <a href="/test">Manuel Test Çalıştır</a>
    """

def run_web():
    port = int(os.getenv('FLASK_PORT', 8080))
    app.run(host='0.0.0.0', port=port)

scheduler = None

def start_bot():
    global scheduler
    print("Bot başlatılıyor...")

    if scheduler and getattr(scheduler, "running", False):
        try:
            scheduler.shutdown(wait=False)
        except:
            pass

    update_coin_list_from_mexc_and_cmc()
    check_ma_signals()

    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(check_ma_signals, 'interval', minutes=1, max_instances=1)
    scheduler.add_job(update_coin_list_from_mexc_and_cmc, 'interval', hours=1, max_instances=1)
    scheduler.start()

    atexit.register(lambda: scheduler.shutdown() if scheduler and getattr(scheduler, "running", False) else None)

if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        Thread(target=run_web, daemon=True).start()
        start_bot()
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        if scheduler and getattr(scheduler, "running", False):
            scheduler.shutdown()
        print("Bot durduruldu.")
