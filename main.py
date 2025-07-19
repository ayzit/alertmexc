import os
import sys
import time
import atexit
import pandas as pd
from flask import Flask
from threading import Thread
from apscheduler.schedulers.background import BackgroundScheduler
import requests

# 1. MEXC API'den coin verilerini çek ve coin_list.txt'ye kaydet
try:
    response = requests.get("https://api.mexc.com/api/v3/ticker/24hr", timeout=10)
    data = response.json()
    with open("coin_list.txt", "w", encoding="utf-8") as f:
        for coin in data:
            # 'symbol', 'quoteVolume', 'marketCap' alanları mevcutsa yaz
            symbol = coin.get("symbol")
            volume = float(coin.get("quoteVolume", 0))
            marketcap = float(coin.get("marketCap", 0))
            # Eğer marketcap yoksa, volume/marketcap oranı hesaplanamayacağı için atla
            if symbol and marketcap > 0:
                f.write(f"{symbol},{volume},{marketcap}\n")
except Exception as e:
    print(f"MEXC verisi çekilirken hata oluştu: {e}")

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
