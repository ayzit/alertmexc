import os
import sys
import time
import atexit
import pandas as pd
import requests
from flask import Flask
from threading import Thread
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv


# .env dosyasını yükle
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
            # 429 veya başka hata kodunda diğer anahtara geç
        except Exception:
            continue
    return None

def update_coin_list_from_mexc_and_cmc():
    print("Coin listesi güncelleniyor...")
    try:
        # 1. MEXC'den ilk 300 en yüksek hacimli coin
        resp = requests.get("https://api.mexc.com/api/v3/ticker/24hr", timeout=15)
        mexc_data = resp.json()
        sorted_coins = sorted(mexc_data, key=lambda x: float(x.get("quoteVolume", 0)), reverse=True)
        top_300 = sorted_coins[:300]
        symbols = [coin['symbol'] for coin in top_300]
        
        coin_list = []
        with open("coin_list.txt", "w", encoding="utf-8") as f:
            for i in range(0, len(symbols), 100):  # CMC API batch limit
                batch = symbols[i:i+100]
                cmc_data = get_marketcap_with_keys(batch)
                if not cmc_data or "data" not in cmc_data:
                    continue
                for sym in batch:
                    cmc_info = cmc_data["data"].get(sym)
                    if not cmc_info:
                        continue
                    try:
                        marketcap = float(cmc_info["quote"]["USD"]["market_cap"])
                        mexc_coin = next((c for c in top_300 if c["symbol"] == sym), None)
                        volume = float(mexc_coin["quoteVolume"]) if mexc_coin else 0
                        if marketcap > 0 and (volume / marketcap) > 0.05:
                            coin_list.append(sym)
                            f.write(f"{sym},{volume},{marketcap}\n")
                    except Exception:
                        continue
                time.sleep(1)  # CMC API rate limit için
        print(f"Filtrelenmiş coin sayısı: {len(coin_list)}")
        globals()["coin_list"] = coin_list
    except Exception as e:
        print(f"Coin listesi güncellenirken hata: {e}")

# Kendi kodunun kalanını (Flask, Telegram, vs.) olduğu gibi bırakabilirsin, coin_list artık güncel olacak.

# Scheduler ile her saat başı güncelle
scheduler = BackgroundScheduler(daemon=True)
scheduler.add_job(update_coin_list_from_mexc_and_cmc, 'interval', hours=1, max_instances=1)
update_coin_list_from_mexc_and_cmc()  # Script başında da çalışsın
scheduler.start()

# Eğer Flask vs. kullanıyorsan aşağıdaki gibi devam edebilirsin
# ... (diğer kodlar)
# 2. coin_list.txt'den hacim/marketcap > 0.05 olan ilk 100 coini oku
coin_list = []
try:
    with open('coin_list.txt', 'r', encoding='utf-8') as f:
        for line in f:
            parts = line.strip().split(',')
            if len(parts) < 3:
                continue
            coin, volume, marketcap = parts[0], float(parts[1]), float(parts[2])
            if marketcap == 0:
                continue
            ratio = volume / marketcap
            if ratio > 0.05:
                coin_list.append(coin)
            if len(coin_list) == 100:
                break
except Exception as e:
    print(f"coin_list.txt okunurken hata oluştu: {e}")

# Artık coin_list değişkenin güncel ve filtrelenmiş durumda!
# Gerekli diğer importlar ve değişkenler burada yer almalı
# Örnek: TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, coin_list, TZ, vb.

# --- ENCODING HATASI ÇÖZÜMÜ ---
# Terminal ve dosya işlemleri için UTF-8 kullanılır
sys.stdout.reconfigure(encoding="utf-8")

def check_ma_condition_changes(ma_condition_coins):
    # Bu fonksiyonun içeriği projenizde mevcut olmalı
    # Örnek: MA koşulunda değişiklik olup olmadığını kontrol eder
    pass

def send_telegram_alert(msg):
    # Telegram'a mesaj gönderen fonksiyon
    pass

def update_coin_list_from_mexc():
    # MEXC'den coin listesini günceller
    pass

def check_ma_signals():
    try:
        alert_list = []  # Uygun şekilde doldurulmalı
        ma_condition_coins = []  # Uygun şekilde doldurulmalı

        if check_ma_condition_changes(ma_condition_coins):
            if alert_list:
                alert_list.sort(key=lambda x: x[0] or pd.Timestamp.now(tz=TZ))

                msg = "🔺 MA(7)>MA(25) 1H:\n" + '\n'.join(alert for _, alert in alert_list)
                send_telegram_alert(msg)
                # HATA DÜZELTİLDİ: encoding="utf-8" eklendi
                with open("alerts_log.csv", "a", encoding="utf-8") as f:
                    for _, alert in alert_list:
                        f.write(f"{pd.Timestamp.now(tz=TZ)}, {alert}\n")
            else:
                print("ℹ️ Hiçbir coin'de MA(7) > MA(25) koşulu sağlanmıyor")
        else:
            print("ℹ️ Alert listesi değişmedi, mesaj gönderilmedi")

    except Exception as e:
        error_msg = f"Bot hatası: {e}"
        print(f"❌ {error_msg}")
        send_telegram_alert(error_msg)

# Flask ve scheduler kısımları

app = Flask('')

@app.route('/')
def home():
    return "MEXC MA Alert Bot is running!"

@app.route('/test')
def manual_test():
    print("🧪 Manuel test başlatıldı")
    check_ma_signals()
    return "Manuel test tamamlandı! Konsol loglarını kontrol edin."

@app.route('/status')
def status():
    return f"""
    <h2>Bot Durumu</h2>
    <p>Token: {'✓' if TELEGRAM_TOKEN else '✗'}</p>
    <p>Chat ID: {'✓' if TELEGRAM_CHAT_ID else '✗'}</p>
    <p>Kontrol edilen coinler: {len(coin_list)}</p>
    <p>Kontrol aralığı: {os.getenv('CHECK_INTERVAL_MINUTES', 15)} dakika</p>
    <a href="/test">Manuel Test Çalıştır</a>
    """

def run_web():
    port = int(os.getenv('FLASK_PORT', 8080))
    app.run(host='0.0.0.0', port=port)

scheduler = None

def start_bot():
    global scheduler
    print("Bot başlatılıyor...")

    if scheduler and scheduler and getattr(scheduler, "running", False):
        try:
            scheduler.shutdown(wait=False)
        except:
            pass

    # Başlangıçta coin listesini güncelle
    update_coin_list_from_mexc()
    check_ma_signals()

    scheduler = BackgroundScheduler(daemon=True)
    # MA kontrolü her 1 dakikada bir, coin listesi güncellemesi her saat
    scheduler.add_job(check_ma_signals, 'interval', minutes=1, max_instances=1)
    scheduler.add_job(update_coin_list_from_mexc, 'interval', hours=1, max_instances=1)
    scheduler.start()
    print(f"✅ Bot başarıyla başlatıldı. Her 1 dakikada bir kontrol, saat başı coin listesi güncellemesi yapılacak.")

    atexit.register(lambda: scheduler.shutdown() if scheduler and getattr(scheduler, "running", False) else None)

if __name__ == "__main__":
    try:
        Thread(target=run_web, daemon=True).start()
        start_bot()

        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        if scheduler and getattr(scheduler, "running", False):
            scheduler.shutdown()
        print("Bot durduruldu.")
