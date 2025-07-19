import os
import sys
import time
import atexit
import pandas as pd
from flask import Flask
from threading import Thread
from apscheduler.schedulers.background import BackgroundScheduler

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
