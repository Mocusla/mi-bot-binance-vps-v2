# -*- coding: utf-8 -*-

import os
import sys
import time
import datetime
import threading
import telebot
import ccxt
import pandas as pd
import pandas_ta as ta
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("BINANCE_TESTNET_API_KEY")
API_SECRET = os.getenv("BINANCE_TESTNET_API_SECRET")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

if not API_KEY or not API_SECRET or not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
    print("❌ ERROR DE CONFIGURACIÓN: Faltan llaves en el archivo .env local.")
    sys.exit(1)

bot_trading_encendido = False  
par_actual = "SOL/USDT"        
CANDLE_LIMIT = 100
TF_COMPRA = "1h"
TF_VENTA = "15m"

total_operaciones = 0          
operaciones_ganadas = 0        
operaciones_perdidas = 0       
posicion_abierta = False       
orden_compra_info = {}         
ASSET_ALLOCATION_PCT = 0.15    

ultima_hora_reporte_8h = datetime.datetime.now()
bot_telegram = telebot.TeleBot(TELEGRAM_TOKEN)

try:
    exchange = ccxt.binance({
        'apiKey': API_KEY,
        'secret': API_SECRET,
        'enableRateLimit': True,
        'options': {
            'defaultType': 'spot',
            'adjustForTimeDifference': True   
        }
    })
    exchange.set_sandbox_mode(True)     
    exchange.verify_certificates = True  
    print("🔒 Conexión segura completada. Conectado a Binance Testnet (Dinero Ficticio).")
except Exception as e:
    print(f"❌ Error crítico de enlace con Binance Testnet: {e}")
    sys.exit(1)

def enviar_alerta(mensaje):
    try:
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        bot_telegram.send_message(TELEGRAM_CHAT_ID, f"[{timestamp}] {mensaje}", parse_mode="Markdown")
    except Exception as e:
        print(f"Error de red en Telegram: {e}")

def obtener_balance_real_testnet():
    try:
        balance = exchange.fetch_balance()
        return float(balance['total'].get('USDT', 0.0))
    except Exception as e:
        print(f"Error de lectura de balance: {e}")
        return 0.0

def analizar_estrategia(symbol, tipo_orden):
    try:
        tf = TF_COMPRA if tipo_orden == "COMPRA" else TF_VENTA
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=tf, limit=CANDLE_LIMIT)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])

        if len(df) < 30: return False
        df['rsi'] = ta.rsi(df['close'], length=14)
        idx = -6 

        if tipo_orden == "COMPRA":
            es_pivot_low = (df['rsi'].iloc[idx] < df['rsi'].iloc[idx-1]) and (df['rsi'].iloc[idx] < df['rsi'].iloc[idx+5])
            if es_pivot_low and (df['rsi'].iloc[idx] <= 30): return True
        elif tipo_orden == "VENTA":
            es_pivot_high = (df['rsi'].iloc[idx] > df['rsi'].iloc[idx-1]) and (df['rsi'].iloc[idx] > df['rsi'].iloc[idx+5])
            if es_pivot_high and (df['rsi'].iloc[idx] >= 70): return True
        return False
    except Exception as e:
        print(f"Aviso técnico en indicadores: {e}")
        return False

def bucle_trading_algoritmico():
    global bot_trading_encendido, par_actual, posicion_abierta
    global total_operaciones, operaciones_ganadas, operaciones_perdidas, orden_compra_info, ultima_hora_reporte_8h

    while True:
        try:
            ahora = datetime.datetime.now()

            if (ahora - ultima_hora_reporte_8h).total_seconds() >= 28800:
                balance_ficticio = obtener_balance_real_testnet()
                pnl_global = balance_ficticio - 1000.0 
                reporte = (
                    f"📊 *REPORTE FINANCIERO AUTOMÁTICO (8 HORAS)*\n\n"
                    f"💱 *Par Activo:* `{par_actual}`\n"
                    f"💼 *Balance de Pruebas:* `${balance_ficticio:.2f} USDT`\n"
                    f"🔹 *Trades Finalizados:* {total_operaciones}\n"
                    f"🟩 *Operaciones Ganadas:* {operaciones_ganadas}\n"
                    f"🟥 *Operaciones Perdidas:* {operaciones_perdidas}\n"
                    f"💰 *PNL Acumulado:* `${pnl_global:.2f} USDT`"
                )
                enviar_alerta(reporte)
                ultima_hora_reporte_8h = ahora

            if not bot_trading_encendido:
                time.sleep(10)
                continue

            if not posicion_abierta:
                if analizar_estrategia(par_actual, "COMPRA"):
                    balance_actual = obtener_balance_real_testnet()
                    if balance_actual <= 10.0:
                        time.sleep(60)
                        continue
                    monto_usdt_invertir = balance_actual * ASSET_ALLOCATION_PCT
                    print(f"[EJECUCIÓN] Comprando {par_actual} en Testnet...")
                    orden_compra_info = exchange.create_market_buy_order(par_actual, monto_usdt_invertir)
                    posicion_abierta = True
                    enviar_alerta(f"🟢 *COMPRA EJECUTADA EN BINANCE TESTNET*\n🛒 Par: `{par_actual}`\n💵 Costo: `${float(orden_compra_info['cost']):.4f} USDT`")

            else:
                if analizar_estrategia(par_actual, "VENTA"):
                    cantidad_a_vender = float(orden_compra_info['filled'])
                    print(f"[EJECUCIÓN] Vendiendo {par_actual} en Testnet...")
                    orden_venta_info = exchange.create_market_sell_order(par_actual, cantidad_a_vender)

                    precio_compra = float(orden_compra_info['average'] or orden_compra_info['price'])
                    precio_venta = float(orden_venta_info['average'] or orden_venta_info['price'])
                    pnl_trade = (precio_venta - precio_compra) * cantidad_a_vender
                    total_operaciones += 1

                    emoji_res = "🟩 GANANCIA NETA" if pnl_trade > 0 else "🟥 PÉRDIDA NETA"
                    if pnl_trade > 0: operaciones_ganadas += 1
                    else: operaciones_perdidas += 1

                    enviar_alerta(f"🔴 *VENTA EJECUTADA EN BINANCE TESTNET*\n📈 Par: `{par_actual}`\n💰 Rendimiento: `${pnl_trade:.4f} USDT`\n📊 Balance: *{emoji_res}*")
                    posicion_abierta = False

            time.sleep(30)
        except Exception as e:
            print(f"Aviso en bucle de trading: {e}")
            time.sleep(30)

@bot_telegram.message_handler(commands=['start'])
def comando_start(message):
    global bot_trading_encendido
    if str(message.chat.id) != TELEGRAM_CHAT_ID: return
    bot_trading_encendido = True
    enviar_alerta(f"🚀 *MOTORES ALGORÍTMICOS ENCENDIDOS.* Monitoreando el par `{par_actual}`.")

@bot_telegram.message_handler(commands=['stop'])
def comando_stop(message):
    global bot_trading_encendido
    if str(message.chat.id) != TELEGRAM_CHAT_ID: return
    bot_trading_encendido = False
    enviar_alerta("🛑 *MANDOS EN PAUSA.* Operaciones detenidas temporalmente.")

@bot_telegram.message_handler(commands=['status'])
def comando_status(message):
    if str(message.chat.id) != TELEGRAM_CHAT_ID: return
    estado = "🟢 Operando activamente" if bot_trading_encendido else "🛑 Apagado en pausa"
    pos = "Sí" if posicion_abierta else "No"
    balance = obtener_balance_real_testnet()
    bot_telegram.send_message(
        TELEGRAM_CHAT_ID,
        f"ℹ️ *ESTADO DEL SISTEMA EN TIEMPO REAL*\n\n🤖 *Estatus:* {estado}\n💱 *Par:* `{par_actual}`\n💰 *Balance:* `${balance:.2f} USDT`\n💼 *Invertido:* {pos}\n📊 *Trades:* {total_operaciones} (🟩 {operaciones_ganadas} | 🟥 {operaciones_perdidas})",
        parse_mode="Markdown"
    )

@bot_telegram.message_handler(commands=['setpair'])
def comando_setpair(message):
    global par_actual, posicion_abierta
    if str(message.chat.id) != TELEGRAM_CHAT_ID: return
    if posicion_abierta:
        enviar_alerta("⚠️ *Bloqueado:* Tienes una posición abierta en la Testnet. Espera la venta.")
        return
    try:
        nuevo_par = message.text.split()[1].upper()
        if "/" not in nuevo_par: raise Exception
        par_actual = nuevo_par
        enviar_alerta(f"💱 *CAMBIO DE MONEDA:* Operando el par `{par_actual}`.")
    except Exception:
        enviar_alerta("❌ *Error:* Usa el formato correcto. Ejemplo: `/setpair ETH/USDT`")

if __name__ == "__main__":
    hilo_trading = threading.Thread(target=bucle_trading_algoritmico)
    hilo_trading.daemon = True
    hilo_trading.start()
    print("[HILO A] Escáner algorítmico de Binance encendido.")
    print("[HILO B] Receptor de comandos de Telegram encendido. Escuchando...")
    enviar_alerta("🔌 *Conexión Establecida.* Bot listo. Envía `/status` para iniciar.")
    bot_telegram.infinity_polling()
