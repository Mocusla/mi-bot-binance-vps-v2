#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
================================================================================
BOT DE TRADING PROTEGIDO - EDICIÓN VPS CON TOPE DE CAPITAL DIARIO MÁXIMO
================================================================================
Auditado y Corregido: Ajustes de Endpoints de Telegram, funciones de Balance
y control estricto de Drawdown integrados.
"""

import os            # REQUISITO DE SEGURIDAD: Recupera las variables cifradas del VPS
import sys           # Manejo de fallas críticas y salidas limpias de producción
import time          # Gestión de pausas para control de hilos y prevención de bans de IP
import datetime      # Control y aritmética de fechas/horas para reportes y reinicios
import requests      # Realización de peticiones HTTPS encriptadas hacia Telegram
import ccxt          # Conector unificado estándar para la API global de Binance Spot
import pandas as pd  # Estructuras de datos (DataFrames) para computación veloz en VPS
import pandas_ta as ta  # Biblioteca matemática para el cálculo exacto del RSI

# ==============================================================================
# 1. CARGA SEGURA DE CREDENCIALES (CORTAFUEGOS DEL VPS)
# ==============================================================================
API_KEY = os.getenv("BINANCE_TESTNET_API_KEY")
API_SECRET = os.getenv("BINANCE_TESTNET_SECRET_KEY") # Unificado para evitar errores de carga
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

if not API_KEY or not API_SECRET:
    print("❌ ERROR CRÍTICO DE SEGURIDAD: Las llaves API no están configuradas en el entorno del VPS.")
    sys.exit(1)

# ==============================================================================
# 2. CONFIGURACIÓN DE OPERACIONES Y GESTIÓN DE RIESGO DE CAPITAL
# ==============================================================================
PARES_BASE_DISEÑO = [
    "SOL/USDT", "BNB/USDT", "XRP/USDT", "ADA/USDT", "DOGE/USDT",
    "TRX/USDT", "LINK/USDT", "AVAX/USDT", "LTC/USDT", "ETC/USDT"
]

TF_COMPRA = "1h"   # Gráfico de 1 Hora para buscar giros estructurales estables
TF_VENTA = "15m"   # Gráfico de 15 minutos para ejecutar salidas rápidas
CANDLE_LIMIT = 100 # Historial de velas descargado para la precisión matemática del RSI

# PARAMETRIZACIÓN FINANCIERA (BASE $100 USDT CON TOPE MÁXIMO)
CAPITAL_MAXIMO_DIARIO = 100.0     # Techo máximo de dinero permitido para operar al iniciar un ciclo
capital_control_actual = 100.0    # Capital operativo del ciclo actual (se ajusta dinámicamente cada 24h)
MAX_PERDIDA_PCT = 5.0             # Drawdown Máximo (5%). Si el capital baja de $95 USDT, el bot se apaga.
ASSET_ALLOCATION_PCT = 0.15       # Asignamos el 15% por cada trade (~$15 USDT)

historial_operaciones = []  # Caché temporal para registrar las ejecuciones
bot_activo = True           # Mantiene el bucle infinito en ejecución permanente

# ANCLAS TEMPORALES DE SISTEMA
tiempo_arranque_sistema = datetime.datetime.now()
ultima_hora_reporte_8h = datetime.datetime.now()
ultimo_dia_reinicio_24h = datetime.date.today()

# ==============================================================================
# 3. CONEXIÓN RESTRINGIDA AL EXCHANGE Y CAPA SSL
# ==============================================================================
try:
    exchange = ccxt.binance({
        'apiKey': API_KEY,
        'secret': API_SECRET,
        'enableRateLimit': True,
        'options': {
            'defaultType': 'spot',
            'warnOnWithdrawal': True
        }
    })
    exchange.verify_certificates = True # Fuerza la validación estricta de certificados SSL en red
    exchange.set_sandbox_mode(True)     # Conexión directa a la Testnet (Dinero Ficticio)
    print("🔒 Conexión segura inicializada. Certificados SSL validados. Modo Sandbox Activo.")
except Exception as e:
    print(f"❌ Error al establecer la conexión segura con el API: {e}")
    sys.exit(1)

# ==============================================================================
# 4. CANAL DE COMUNICACIÓN ENCRIPTADO (HTTPS LOGGING A TELEGRAM - CORREGIDO)
# ==============================================================================
def enviar_log(mensaje):
    """ Escribe la actividad en la consola del VPS y la envía al Telegram del usuario """
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    mensaje_formateado = f"[{timestamp}] {mensaje}"
    print(mensaje_formateado)
    
    if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        try:
            # CORRECCIÓN DE SEGURIDAD: Se corrigió la URL oficial de la API de Telegram
            url = f"https://telegram.org{TELEGRAM_TOKEN}/sendMessage"
            payload = {"chat_id": TELEGRAM_CHAT_ID, "text": mensaje_formateado, "parse_mode": "Markdown"}
            requests.post(url, json=payload, timeout=4) 
        except Exception:
            pass # Falla silenciosa de red para no congelar el bucle del bot

# ==============================================================================
# 5. JERARQUIZACIÓN DE MERCADO POR VOLUMEN REAL EN 24 HORAS
# ==============================================================================
def obtener_pares_ordenados_por_volumen():
    """ Descarga estadísticas de Binance y ordena los 10 pares de mayor a menor volumen """
    try:
        tickers = exchange.fetch_tickers(PARES_BASE_DISEÑO)
        lista_volumen = []
        
        for par in PARES_BASE_DISEÑO:
            if par in tickers and tickers[par]['baseVolume'] is not None:
                volumen_token = float(tickers[par]['baseVolume'])
                precio_actual = float(tickers[par]['last'])
                volumen_usd = volumen_token * precio_actual 
                lista_volumen.append({'par': par, 'volumen_usd': volumen_usd})
            else:
                lista_volumen.append({'par': par, 'volumen_usd': 0.0})
                
        df_vol = pd.DataFrame(lista_volumen)
        df_vol = df_vol.sort_values(by='volumen_usd', ascending=False)
        return df_vol['par'].tolist()
    except Exception as e:
        enviar_log(f"⚠️ Inestabilidad de red en volumen: {e}. Usando lista base.")
        return PARES_BASE_DISEÑO

# ==============================================================================
# 6. MÓDULO MATEMÁTICO: PROCESADOR RSI ASIMÉTRICO
# ==============================================================================
def analizar_mercado_asimetrico(symbol, tipo_orden):
    """ Evalúa de forma cruzada: Compra en gráficos de 1H y Venta en gráficos de 15m """
    try:
        temporalidad_objetivo = TF_COMPRA if tipo_orden == "COMPRA" else TF_VENTA
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=temporalidad_objetivo, limit=CANDLE_LIMIT)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        
        if len(df) < 30:
            return False
        
        df['rsi'] = ta.rsi(df['close'], length=14)
        idx = -6 # Índice de análisis estructural dinámico
        
        if tipo_orden == "COMPRA":
            es_pivot_low = (df['rsi'].iloc[idx] < df['rsi'].iloc[idx-1]) and (df['rsi'].iloc[idx] < df['rsi'].iloc[idx+5])
            if es_pivot_low and (df['rsi'].iloc[idx] <= 30):
                return True
                
        elif tipo_orden == "VENTA":
            es_pivot_high = (df['rsi'].iloc[idx] > df['rsi'].iloc[idx-1]) and (df['rsi'].iloc[idx] > df['rsi'].iloc[idx+5])
            if es_pivot_high and (df['rsi'].iloc[idx] >= 70):
                return True
                
        return False
    except Exception as e:
        print(f"⚠️ Error analizando {symbol} en {temporalidad_objetivo}: {e}")
        return False

# ==============================================================================
# 7. FUNCIÓN COMPLETADA: OBTENCIÓN DE BALANCE REAL EN USDT
# ==============================================================================
def obtener_balance_total_usdt():
    """ Consulta de forma segura los fondos disponibles en USDT en la Testnet """
    try:
        balance = exchange.fetch_balance()
        return float(balance['total'].get('USDT', 0.0))
    except Exception as e:
        enviar_log(f"❌ Error al consultar balance: {e}")
        return 0.0

# ==============================================================================
# 8. BUCLE PRINCIPAL OPERATIVO (CIRCUIT BREAKER Y CONTROL 24H)
# ==============================================================================
enviar_log("🤖 Bot de Trading Protegido Inicializado con Éxito en el VPS.")

while bot_activo:
    try:
        ahora = datetime.datetime.now()
        
        # --- CONTROL DE RIESGO DE BALANCE (STOP-LOSS GLOBAL DE CUENTA) ---
        balance_actual = obtener_balance_total_usdt()
        drawdown_permitido = capital_control_actual * (1 - (MAX_PERDIDA_PCT / 100.0))
        
        if balance_actual <= drawdown_permitido:
            enviar_log(f"🚨 [CIRCUIT BREAKER] Apagando el bot. Balance actual ({balance_actual} USDT) inferior al límite permitido ({drawdown_permitido} USDT).")
            sys.exit(0)

        # --- GESTIÓN DE REINICIO DE CAPITAL CADA 24 HORAS ---
        if ahora.date() > ultimo_dia_reinicio_24h:
            if balance_actual > CAPITAL_MAXIMO_DIARIO:
                enviar_log(f"💰 [REINICIO 24H] Balance actual (${balance_actual:.2f}) supera los $100. Asegurando ganancias. Capital fijado en $100.00 USDT.")
                capital_control_actual = CAPITAL_MAXIMO_DIARIO
            else:
                enviar_log(f"📉 [REINICIO 24H] Balance actual (${balance_actual:.2f}) en pérdidas. Continuando con capital real restante.")
                capital_control_actual = balance_actual
            ultimo_dia_reinicio_24h = ahora.date()

        # --- REPORTE DE ESTADO PERIÓDICO CADA 8 HORAS ---
        if (ahora - ultima_hora_reporte_8h).total_seconds() >= 28800:
