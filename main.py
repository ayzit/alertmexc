import ccxt
import pandas as pd
import requests
import os
import time
import json
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask
from threading import Thread
import atexit
from dotenv import load_dotenv
import pytz
from datetime import datetime
import sys

# Fix console encoding for Unicode (emojis, Turkish chars)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding='utf-8')

# ENV yükleme
load_dotenv()

# Zaman dilimi
TZ = pytz.timezone('Europe/Istanbul')

# Telegram ayarları
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

print(f"Telegram Token: {'✓ Loaded' if TELEGRAM_TOKEN else '✗ Missing'}")
print(f"Chat ID: {'✓ Loaded' if TELEGRAM_CHAT_ID else '✗ Missing'}")

# MEXC future (eski bot için)
exchange_mexc = ccxt.mexc({
    'enableRateLimit': True,
    'options': {'defaultType': 'future'}
})

coin_list = [
    'PENGU', 'PROM', 'FUN', 'QNT', 'SYRUP', 'HYPE', 'BID', 'SPX',
    'MKR', 'AAVE', 'BNT', 'JST', 'CAKE', 'KAVA', 'CHEEMS', 'NEIROETH',
    'FARTCOIN', 'SUN', 'PENDLE', 'AVA', 'SEI', 'JELLYJELLY', 'BONK', 'MOG', 'VIC', 'FLOKI',
    'BTC', 'ETH', 'DOGE', 'NEIROCTO', 'SHIB', 'PEPE','KNC',
]

symbols_mexc = [f"{coin}/USDT" for coin in coin_list]

def send_telegram_alert(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = {
            'chat_id': TELEGRAM_CHAT_ID,
            'text': message,
            'parse_mode': 'HTML'  # For bold and color formatting
        }
        response = requests.post(url, data=data, timeout=10)
        if response.status_code == 200:
            print(f"✓ Telegram mesajı gönderildi: {message[:50]}...")
        else:
            print(f"✗ Telegram hatası: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"✗ Telegram bağlantı hatası: {e}")

def check_coin_list_changes():
    try:
        previous_coins = set()
        try:
            with open("previous_coin_list.txt", "r", encoding="utf-8") as f:
                previous_coins = set(f.read().strip().split('\n'))
        except FileNotFoundError:
            pass

        current_coins = set(coin_list)

        if previous_coins and previous_coins != current_coins:
            added_coins = current_coins - previous_coins
            removed_coins = previous_coins - current_coins

            if added_coins or removed_coins:
                change_msg = "📝 Coin Listesi:\n"

                if added_coins:
                    change_msg += f"➕ {', '.join(sorted(added_coins))}\n"

                if removed_coins:
                    change_msg += f"➖ {', '.join(sorted(removed_coins))}\n"

                change_msg += f"📊 Toplam: {len(current_coins)}"

                print(f"🔄 {change_msg}")
                send_telegram_alert(change_msg)

        with open("previous_coin_list.txt", "w", encoding="utf-8") as f:
            f.write('\n'.join(sorted(current_coins)))
    except Exception as e:
        print(f"❌ Coin listesi kontrol hatası: {e}")

def check_ma_condition_changes(current_ma_coins):
    try:
        previous_ma_coins = set()
        try:
            with open("previous_ma_coins.txt", "r", encoding="utf-8") as f:
                previous_ma_coins = set(f.read().strip().split('\n'))
        except FileNotFoundError:
            pass

        current_ma_coins_set = set(current_ma_coins)

        list_changed = previous_ma_coins != current_ma_coins_set

        if list_changed:
            new_ma_coins = current_ma_coins_set - previous_ma_coins
            removed_ma_coins = previous_ma_coins - current_ma_coins_set

            if new_ma_coins or removed_ma_coins:
                change_msg = "🔄 MA(7)>MA(25):\n"

                if new_ma_coins:
                    change_msg += f"🟢 {', '.join(sorted(new_ma_coins))}\n"

                if removed_ma_coins:
                    change_msg += f"🔴 {', '.join(sorted(removed_ma_coins))}\n"

                change_msg += f"📊 Toplam: {len(current_ma_coins_set)}"

                print(f"🔄 {change_msg}")
                send_telegram_alert(change_msg)

        with open("previous_ma_coins.txt", "w", encoding="utf-8") as f:
            f.write('\n'.join(sorted(current_ma_coins_set)))

        return list_changed
    except Exception as e:
        print(f"❌ MA şartı kontrol hatası: {e}")
        return False

def check_ma_signals_and_rsi_macd_ema():
    try:
        check_coin_list_changes()

        print(f"🔍 MA ve RSI/MACD/EMA sinyalleri kontrol ediliyor... {pd.Timestamp.now(tz=TZ)}")
        markets = exchange_mexc.load_markets()
        available_symbols = set(markets.keys())
        alert_list = []
        checked_count = 0
        rsi_macd_ema_alert_list = []

        for symbol_mexc in symbols_mexc:
            if symbol_mexc not in available_symbols:
                print(f"⚠️ {symbol_mexc} MEXC'de bulunamadı")
                continue
            try:
                ohlcv = exchange_mexc.fetch_ohlcv(symbol_mexc, '1h', limit=100)
                df = pd.DataFrame(ohlcv, columns=['time', 'open', 'high', 'low', 'close', 'volume'])

                # ------------------------ LIVE RSI ARROW LOGIC ------------------------
                # Get latest ticker for realtime price
                try:
                    ticker = exchange_mexc.fetch_ticker(symbol_mexc)
                    df.at[len(df)-1, 'close'] = ticker['last']
                except Exception as e:
                    print(f"⚠️ Ticker fetch error for {symbol_mexc}: {e}")

                # Recalculate RSI for "live" candle
                delta = df['close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                rs = gain / loss
                df['rsi'] = 100 - (100 / (1 + rs))
                # ----------------------------------------------------------------------

                # Heikin-Ashi hesaplama
                ha_df = pd.DataFrame()
                ha_df['close'] = (df['open'] + df['high'] + df['low'] + df['close']) / 4

                ha_open = [ (df['open'][0] + df['close'][0]) / 2 ]
                for i in range(1, len(df)):
                    ha_open.append( (ha_open[i-1] + ha_df['close'][i-1]) / 2 )
                ha_df['open'] = ha_open

                ha_df['high'] = df[['high', 'open', 'close']].max(axis=1)
                ha_df['low'] = df[['low', 'open', 'close']].min(axis=1)

                # MA ve RSI hesaplama
                df['ma7'] = df['close'].rolling(window=7).mean()
                df['ma25'] = df['close'].rolling(window=25).mean()
                # EMA'lar
                df['ema9'] = df['close'].ewm(span=9, adjust=False).mean()
                df['ema21'] = df['close'].ewm(span=21, adjust=False).mean()
                # MACD ve sinyal çizgisi
                exp12 = df['close'].ewm(span=12, adjust=False).mean()
                exp26 = df['close'].ewm(span=26, adjust=False).mean()
                df['macd'] = exp12 - exp26
                df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()

                condition = df['ma7'] > df['ma25']

                consecutive_hours = 0
                start_date = None
                start_index = None

                for i in range(len(condition) - 1, -1, -1):
                    if condition.iloc[i]:
                        consecutive_hours += 1
                        start_index = i
                    else:
                        break

                if start_index is not None:
                    start_date = pd.to_datetime(df['time'].iloc[start_index], unit='ms').tz_localize('UTC').tz_convert(TZ)

                consecutive_count = 0
                last_color = None

                for i in range(len(ha_df) - 1, -1, -1):
                    if ha_df['close'].iloc[i] > ha_df['open'].iloc[i]:
                        current_color = 'green'
                    else:
                        current_color = 'red'

                    if last_color is None:
                        last_color = current_color
                        consecutive_count = 1
                    elif current_color == last_color:
                        consecutive_count += 1
                    else:
                        break

                direction_emoji = "🟢" if last_color == 'green' else "🔴"

                current_price = df['close'].iloc[-1]
                ma7_current = df['ma7'].iloc[-1]
                ma25_current = df['ma25'].iloc[-1]
                rsi_value = df['rsi'].iloc[-1]

                # Colored arrows (🔺 = up/red, 🔻 = down/red)
                rsi_last = df['rsi'].iloc[-1]
                rsi_prev = df['rsi'].iloc[-2]
                if rsi_last > rsi_prev:
                    rsi_arrow = "🔺"
                else:
                    rsi_arrow = "🔻"

                # -- Calculate L and S for last 72 candles --
                lookback = 72
                up_long = 0
                down_long = 0
                volume = df['volume'][-lookback:]
                avg_vol = volume.mean()
                high_vol_thres = avg_vol * 1.5
                for i in range(-lookback, 0):
                    if i == 0:
                        continue
                    body = df['close'].iloc[i] - df['open'].iloc[i]
                    rng = abs(df['high'].iloc[i] - df['low'].iloc[i])
                    # Define a "long" candle: body at least 60% of range (can tune)
                    is_long = abs(body) > 0.6 * rng and rng > 0
                    is_high_vol = df['volume'].iloc[i] > high_vol_thres
                    if is_long and is_high_vol:
                        if body > 0:
                            up_long += 1
                        elif body < 0:
                            down_long += 1

                # ATH and high volume checks
                day_high = df['high'][-24:].max()
                curr_vol = df['volume'].iloc[-1]
                is_ath = current_price >= day_high
                is_high_vol = curr_vol > avg_vol * 1.5  # 1.5x average volume

                print(f"📊 {symbol_mexc}: Fiyat={current_price:.4f}, MA7={ma7_current:.4f}, MA25={ma25_current:.4f}, RSI={rsi_value:.2f}, H={consecutive_count}{direction_emoji}, L:{up_long}, S:{down_long}")

                # ALERT MESAJI için eski koddaki alert listesine ekle
                if condition.iloc[-1]:
                    pct_diff = round((current_price - ma7_current) / ma7_current * 100, 1)
                    sign = "+" if pct_diff >= 0 else ""
                    pct_diff_str = f"{sign}{pct_diff}%"

                    coin_name = symbol_mexc.replace('/USDT', '')
                    alert_text = f"{coin_name}-{consecutive_hours}h-R{int(rsi_value)}-{consecutive_count}{direction_emoji} {pct_diff_str} {rsi_arrow} L{up_long}/S{down_long}"

                    if is_ath and is_high_vol:
                        alert_text = f"<b>{alert_text}</b>"

                    alert_list.append((rsi_value, alert_text))

                # --- EK KOŞUL: RSI>70 düşüşü, MACD cross down, EMA(9)<EMA(21) ---
                rsi_was_over_70 = rsi_prev > 70 and rsi_last < rsi_prev
                rsi_now_under_70 = rsi_last < 70

                macd_last = df['macd'].iloc[-1]
                macd_prev = df['macd'].iloc[-2]
                macd_signal_last = df['macd_signal'].iloc[-1]
                macd_signal_prev = df['macd_signal'].iloc[-2]
                macd_cross_down = (macd_prev > macd_signal_prev) and (macd_last < macd_signal_last)

                ema9_last = df['ema9'].iloc[-1]
                ema21_last = df['ema21'].iloc[-1]
                ema_condition = ema9_last < ema21_last

                if rsi_was_over_70 and rsi_now_under_70 and macd_cross_down and ema_condition:
                    coin_name = symbol_mexc.replace('/USDT', '')
                    rsi_macd_ema_alert_list.append(f"{coin_name} RSI düşüşü, MACD kesişim, EMA(9)<EMA(21)")

                checked_count += 1
                time.sleep(1.5)

            except Exception as e:
                print(f"❌ {symbol_mexc} hatası: {e}")

        print(f"✅ {checked_count} coin kontrol edildi, {len(alert_list)} alert bulundu")

        # MA alert sorting & messaging
        alert_list.sort(key=lambda x: x[0], reverse=True)
        ma_condition_coins = [alert.split(' (')[0] for _, alert in alert_list]

        if check_ma_condition_changes(ma_condition_coins):
            if alert_list:
                msg = "🔺 MA(7)>MA(25) 1H:\n" + '\n'.join(alert for _, alert in alert_list)
                send_telegram_alert(msg)
                with open("alerts_log.csv", "a", encoding="utf-8") as f:
                    for _, alert in alert_list:
                        f.write(f"{pd.Timestamp.now(tz=TZ)}, {alert}\n")
            else:
                print("ℹ️ Hiçbir coin'de MA(7) > MA(25) koşulu sağlanmıyor")
        else:
            print("ℹ️ Alert listesi değişmedi, mesaj gönderilmedi")

        # --- EK KOŞUL MESAJI ---
        if rsi_macd_ema_alert_list:
            msg = "⚠️ RSI>70'den düşüp, MACD aşağı cross, EMA(9)<EMA(21) olanlar:\n" + '\n'.join(rsi_macd_ema_alert_list)
            send_telegram_alert(msg)
        else:
            print("Bu koşulları sağlayan coin yok.")

    except Exception as e:
        error_msg = f"Bot hatası: {e}"
        print(f"❌ {error_msg}")
        send_telegram_alert(error_msg)

# Flask ve scheduler kısımları da aynen duracak (eski botun)

app = Flask('')

@app.route('/')
def home():
    return "MEXC MA Alert Bot is running!"

@app.route('/test')
def manual_test():
    print("🧪 Manuel test başlatıldı")
    check_ma_signals_and_rsi_macd_ema()
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

    if scheduler and scheduler.running:
        try:
            scheduler.shutdown(wait=False)
        except:
            pass

    check_ma_signals_and_rsi_macd_ema()

    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(check_ma_signals_and_rsi_macd_ema, 'interval', minutes=2, max_instances=1)
    scheduler.start()
    print(f"✅ Bot başarıyla başlatıldı. Her 1 dakikada bir kontrol yapacak.")

    atexit.register(lambda: scheduler.shutdown() if scheduler and scheduler.running else None)

if __name__ == "__main__":
    try:
        Thread(target=run_web, daemon=True).start()
        start_bot()

        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        if scheduler and scheduler.running:
            scheduler.shutdown()
        print("Bot durduruldu.")
