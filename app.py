import os
import time
import threading
import json
import hashlib
import random
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from flask_cors import CORS
import telebot

# ============================================
# CONFIGURACIÓN
# ============================================
app = Flask(__name__)
CORS(app, origins=["https://carlosmar14.github.io"])

# Token desde variables de entorno
BOT_TOKEN = os.environ.get('TOKEN')
if not BOT_TOKEN:
    BOT_TOKEN = "8756602645:AAHZjNUJ1KKy-1L9i2CAJRMy-mIE5ambV_Q"

BOT_USERNAME = "shopcmar_bot"
WEB_URL = "https://carlosmar14.github.io/mibot/"

bot = telebot.TeleBot(BOT_TOKEN)

# ============================================
# BASE DE DATOS
# ============================================
try:
    with open('database.json', 'r') as f:
        db = json.load(f)
except:
    db = {
        'usuarios': {},      # Datos de usuarios
        'chats': {},         # Chats personales
        'inversiones': {},   # Inversiones activas
        'historial': {},     # Historial de transacciones
        'planes': {          # Planes de inversión
            'basico': {'nombre': 'Básico', 'min': 10, 'max': 100, 'ganancia': 5, 'diario': True},
            'avanzado': {'nombre': 'Avanzado', 'min': 101, 'max': 500, 'ganancia': 10, 'diario': True},
            'premium': {'nombre': 'Premium', 'min': 501, 'max': 2000, 'ganancia': 15, 'diario': True},
            'vip': {'nombre': 'VIP', 'min': 2001, 'max': 10000, 'ganancia': 20, 'diario': True}
        }
    }

def guardar_db():
    with open('database.json', 'w') as f:
        json.dump(db, f)

# ============================================
# FUNCIONES PRINCIPALES
# ============================================
def obtener_chat(user_id):
    if user_id not in db['chats']:
        db['chats'][user_id] = []
    return db['chats'][user_id]

def agregar_mensaje(user_id, origen, nombre, texto):
    if user_id not in db['chats']:
        db['chats'][user_id] = []
    
    mensaje = {
        'id': len(db['chats'][user_id]) + 1,
        'origen': origen,
        'nombre': nombre,
        'texto': texto,
        'fecha': time.time()
    }
    db['chats'][user_id].append(mensaje)
    guardar_db()
    return mensaje

def registrar_usuario(user_id, nombre, username=None):
    if user_id not in db['usuarios']:
        db['usuarios'][user_id] = {
            'user_id': user_id,
            'nombre': nombre,
            'username': username,
            'saldo': 0,
            'saldo_invertido': 0,
            'ganancias_totales': 0,
            'referido_por': None,
            'referidos': [],
            'nivel': 'principiante',
            'puntos': 0,
            'fecha_registro': time.time(),
            'ultima_actividad': time.time()
        }
        db['chats'][user_id] = []
        db['inversiones'][user_id] = []
        db['historial'][user_id] = []
        guardar_db()
        return True
    return False

# ============================================
# RUTA PRINCIPAL
# ============================================
@app.route('/')
def home():
    return f"""
    <html>
    <head>
        <title>Bot de Inversión - Panel</title>
        <style>
            body {{ font-family: Arial; padding: 20px; background: #f5f5f5; }}
            .container {{ max-width: 1200px; margin: 0 auto; }}
            .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 10px; margin-bottom: 20px; }}
            .stats {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; margin-bottom: 20px; }}
            .card {{ background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
            table {{ width: 100%; background: white; border-radius: 10px; overflow: hidden; }}
            th {{ background: #667eea; color: white; padding: 10px; }}
            td {{ padding: 10px; border-bottom: 1px solid #ddd; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>💰 BOT DE INVERSIÓN</h1>
                <p>@shopcmar_bot | {WEB_URL}</p>
            </div>
            
            <div class="stats">
                <div class="card">
                    <h3>Usuarios</h3>
                    <h2>{len(db['usuarios'])}</h2>
                </div>
                <div class="card">
                    <h3>Inversiones</h3>
                    <h2>{sum(len(i) for i in db['inversiones'].values())}</h2>
                </div>
                <div class="card">
                    <h3>Capital Total</h3>
                    <h2>${sum(u['saldo'] for u in db['usuarios'].values()):.2f}</h2>
                </div>
                <div class="card">
                    <h3>Ganancias</h3>
                    <h2>${sum(u['ganancias_totales'] for u in db['usuarios'].values()):.2f}</h2>
                </div>
            </div>
            
            <p><a href="/setup_webhook">Configurar Webhook</a></p>
        </div>
    </body>
    </html>
    """

# ============================================
# LOGIN
# ============================================
@app.route('/auth/telegram', methods=['POST', 'OPTIONS'])
def auth_telegram():
    if request.method == 'OPTIONS':
        return '', 200
    
    try:
        data = request.json
        user_id = str(data['id'])
        nombre = data.get('first_name', '')
        username = data.get('username', '')
        
        registrar_usuario(user_id, nombre, username)
        
        session_token = hashlib.sha256(f"{user_id}{time.time()}".encode()).hexdigest()[:20]
        
        agregar_mensaje(user_id, 'bot', 'Sistema', f"🎉 ¡Bienvenido {nombre} al Bot de Inversión!")
        
        return jsonify({
            'success': True,
            'user': db['usuarios'][user_id],
            'session': session_token
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============================================
# API WEB
# ============================================
@app.route('/api/chat/<user_id>', methods=['GET'])
def obtener_chat_api(user_id):
    ultimo_id = int(request.args.get('ultimo_id', 0))
    chat = obtener_chat(user_id)
    mensajes_nuevos = [m for m in chat if m['id'] > ultimo_id]
    return jsonify({
        'mensajes': mensajes_nuevos,
        'ultimo_id': max([m['id'] for m in chat]) if chat else 0
    })

@app.route('/api/enviar', methods=['POST'])
def enviar_mensaje_api():
    data = request.json
    user_id = data.get('user_id')
    texto = data.get('texto')
    
    user = db['usuarios'].get(user_id, {})
    nombre = user.get('nombre', 'Usuario')
    
    agregar_mensaje(user_id, 'web', nombre, texto)
    
    # Procesar comandos desde la web
    if texto.startswith('/'):
        procesar_comando_web(user_id, texto, nombre)
    
    return jsonify({'success': True})

@app.route('/api/usuario/<user_id>', methods=['GET'])
def api_usuario(user_id):
    user = db['usuarios'].get(user_id, {})
    inversiones = db['inversiones'].get(user_id, [])
    historial = db['historial'].get(user_id, [])[-10:]
    
    return jsonify({
        'user': user,
        'inversiones': inversiones,
        'historial': historial
    })

# ============================================
# WEBHOOK TELEGRAM
# ============================================
chat_ids_telegram = {}

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        update = telebot.types.Update.de_json(request.stream.read().decode('utf-8'))
        if update.message:
            thread = threading.Thread(target=procesar_mensaje_telegram, args=(update.message,))
            thread.start()
        return 'OK', 200
    except Exception as e:
        return 'Error', 500

def procesar_mensaje_telegram(message):
    user_id = str(message.from_user.id)
    chat_id = message.chat.id
    texto = message.text
    nombre = message.from_user.first_name
    
    chat_ids_telegram[user_id] = chat_id
    registrar_usuario(user_id, nombre, message.from_user.username)
    
    agregar_mensaje(user_id, 'telegram', nombre, texto)
    
    if texto.startswith('/'):
        procesar_comando_telegram(user_id, chat_id, texto, nombre)
    else:
        respuesta = f"❓ Usa /ayuda para ver los comandos disponibles"
        bot.send_message(chat_id, respuesta)
        agregar_mensaje(user_id, 'bot', 'Bot', respuesta)

# ============================================
# PROCESAR COMANDOS
# ============================================
def procesar_comando_telegram(user_id, chat_id, texto, nombre):
    partes = texto.split()
    comando = partes[0].lower()
    
    user = db['usuarios'][user_id]
    
    if comando == '/start':
        respuesta = (
            f"💰 **BOT DE INVERSIÓN**\n\n"
            f"¡Bienvenido {nombre}!\n\n"
            f"**Tus datos:**\n"
            f"• Saldo disponible: ${user['saldo']:.2f}\n"
            f"• Invertido: ${user['saldo_invertido']:.2f}\n"
            f"• Ganancias: ${user['ganancias_totales']:.2f}\n\n"
            f"**Comandos principales:**\n"
            f"/invertir [monto] - Hacer una inversión\n"
            f"/planes - Ver planes disponibles\n"
            f"/misinversiones - Ver tus inversiones\n"
            f"/balance - Ver tu saldo\n"
            f"/retirar [monto] - Retirar fondos\n"
            f"/referidos - Sistema de referidos\n"
            f"/ayuda - Todos los comandos\n\n"
            f"**Link de referido:**\n"
            f"https://t.me/{BOT_USERNAME}?start={user_id}"
        )
        
    elif comando == '/ayuda':
        respuesta = (
            "📋 **COMANDOS COMPLETOS**\n\n"
            "**💰 Inversiones:**\n"
            "/invertir [monto] - Invertir dinero\n"
            "/planes - Ver planes de inversión\n"
            "/misinversiones - Ver inversiones activas\n"
            "/ganancias - Ver ganancias generadas\n\n"
            "**💳 Billetera:**\n"
            "/balance - Ver saldo disponible\n"
            "/depositar [monto] - Registrar depósito\n"
            "/retirar [monto] - Solicitar retiro\n"
            "/historial - Ver movimientos\n\n"
            "**👥 Referidos:**\n"
            "/referidos - Ver tus referidos\n"
            "/gananciasref - Ganancias por referidos\n"
            "/link - Tu link de referido\n\n"
            "**📊 Estadísticas:**\n"
            "/perfil - Ver perfil completo\n"
            "/estadisticas - Estadísticas globales"
        )
    
    elif comando == '/balance':
        respuesta = (
            f"💰 **TU BALANCE**\n\n"
            f"• Saldo disponible: ${user['saldo']:.2f}\n"
            f"• Saldo invertido: ${user['saldo_invertido']:.2f}\n"
            f"• Capital total: ${user['saldo'] + user['saldo_invertido']:.2f}\n"
            f"• Ganancias totales: ${user['ganancias_totales']:.2f}"
        )
    
    elif comando == '/planes':
        respuesta = "📊 **PLANES DE INVERSIÓN**\n\n"
        for p, datos in db['planes'].items():
            respuesta += (
                f"**{datos['nombre']}**\n"
                f"• Monto: ${datos['min']} - ${datos['max']}\n"
                f"• Ganancia: {datos['ganancia']}% diario\n"
                f"• Duración: Ilimitada\n\n"
            )
        respuesta += "Usa /invertir [monto] para comenzar"
    
    elif comando == '/invertir':
        if len(partes) < 2:
            respuesta = "❌ Usa: /invertir [monto]"
        else:
            try:
                monto = float(partes[1])
                if monto < 10:
                    respuesta = "❌ Monto mínimo: $10"
                elif monto > user['saldo']:
                    respuesta = f"❌ Saldo insuficiente. Tienes ${user['saldo']:.2f}"
                else:
                    # Determinar plan
                    plan = None
                    for p, datos in db['planes'].items():
                        if datos['min'] <= monto <= datos['max']:
                            plan = p
                            break
                    if not plan:
                        plan = 'vip'
                    
                    # Crear inversión
                    inversion = {
                        'id': len(db['inversiones'].get(user_id, [])) + 1,
                        'monto': monto,
                        'plan': plan,
                        'ganancia_diaria': monto * (db['planes'][plan]['ganancia'] / 100),
                        'fecha_inicio': time.time(),
                        'ultimo_pago': time.time(),
                        'activa': True,
                        'total_generado': 0
                    }
                    
                    if user_id not in db['inversiones']:
                        db['inversiones'][user_id] = []
                    
                    db['inversiones'][user_id].append(inversion)
                    user['saldo'] -= monto
                    user['saldo_invertido'] += monto
                    
                    # Registrar en historial
                    if user_id not in db['historial']:
                        db['historial'][user_id] = []
                    
                    db['historial'][user_id].append({
                        'tipo': 'inversion',
                        'monto': monto,
                        'plan': plan,
                        'fecha': time.time()
                    })
                    
                    guardar_db()
                    
                    respuesta = (
                        f"✅ **INVERSIÓN REALIZADA**\n\n"
                        f"• Monto: ${monto:.2f}\n"
                        f"• Plan: {db['planes'][plan]['nombre']}\n"
                        f"• Ganancia diaria: ${inversion['ganancia_diaria']:.2f}\n"
                        f"• Saldo restante: ${user['saldo']:.2f}\n\n"
                        f"Usa /misinversiones para ver detalles"
                    )
            except ValueError:
                respuesta = "❌ Monto inválido"
    
    elif comando == '/misinversiones':
        inversiones = db['inversiones'].get(user_id, [])
        if not inversiones:
            respuesta = "📭 No tienes inversiones activas"
        else:
            respuesta = "📊 **TUS INVERSIONES**\n\n"
            total_ganado = 0
            for i, inv in enumerate(inversiones, 1):
                if inv['activa']:
                    horas = (time.time() - inv['fecha_inicio']) / 3600
                    ganado = inv['ganancia_diaria'] * (horas / 24)
                    total_ganado += ganado
                    respuesta += (
                        f"**Inversión #{i}**\n"
                        f"• Monto: ${inv['monto']:.2f}\n"
                        f"• Plan: {db['planes'][inv['plan']]['nombre']}\n"
                        f"• Ganado: ${ganado:.2f}\n"
                        f"• Diario: ${inv['ganancia_diaria']:.2f}\n\n"
                    )
            respuesta += f"💰 **Total ganado:** ${total_ganado:.2f}"
    
    elif comando == '/ganancias':
        inversiones = db['inversiones'].get(user_id, [])
        total_ganado = 0
        for inv in inversiones:
            if inv['activa']:
                horas = (time.time() - inv['fecha_inicio']) / 3600
                ganado = inv['ganancia_diaria'] * (horas / 24)
                total_ganado += ganado
        respuesta = f"💰 **Ganancias generadas:** ${total_ganado:.2f}"
    
    elif comando == '/depositar':
        if len(partes) < 2:
            respuesta = "❌ Usa: /depositar [monto]"
        else:
            try:
                monto = float(partes[1])
                if monto <= 0:
                    respuesta = "❌ Monto inválido"
                else:
                    user['saldo'] += monto
                    
                    # Registrar historial
                    if user_id not in db['historial']:
                        db['historial'][user_id] = []
                    db['historial'][user_id].append({
                        'tipo': 'deposito',
                        'monto': monto,
                        'fecha': time.time()
                    })
                    
                    guardar_db()
                    
                    # Comisión para referidor
                    if user['referido_por'] and user['referido_por'] in db['usuarios']:
                        comision = monto * 0.1
                        db['usuarios'][user['referido_por']]['saldo'] += comision
                        db['usuarios'][user['referido_por']]['ganancias_totales'] += comision
                        
                        # Notificar al referidor
                        if user['referido_por'] in chat_ids_telegram:
                            try:
                                bot.send_message(
                                    chat_ids_telegram[user['referido_por']],
                                    f"🎉 ¡Comisión de referido!\n\n{nombre} depositó ${monto}\n💰 Has ganado ${comision:.2f}"
                                )
                            except:
                                pass
                    
                    respuesta = f"✅ Depósito de ${monto:.2f} realizado. Nuevo saldo: ${user['saldo']:.2f}"
            except ValueError:
                respuesta = "❌ Monto inválido"
    
    elif comando == '/retirar':
        if len(partes) < 2:
            respuesta = "❌ Usa: /retirar [monto]"
        else:
            try:
                monto = float(partes[1])
                if monto <= 0:
                    respuesta = "❌ Monto inválido"
                elif monto > user['saldo']:
                    respuesta = f"❌ Saldo insuficiente. Tienes ${user['saldo']:.2f}"
                else:
                    user['saldo'] -= monto
                    
                    db['historial'][user_id].append({
                        'tipo': 'retiro',
                        'monto': monto,
                        'fecha': time.time()
                    })
                    
                    guardar_db()
                    
                    respuesta = (
                        f"✅ **SOLICITUD DE RETIRO**\n\n"
                        f"• Monto: ${monto:.2f}\n"
                        f"• Nuevo saldo: ${user['saldo']:.2f}\n"
                        f"• Estado: En proceso\n\n"
                        f"Te contactaremos pronto."
                    )
            except ValueError:
                respuesta = "❌ Monto inválido"
    
    elif comando == '/perfil':
        respuesta = (
            f"👤 **PERFIL COMPLETO**\n\n"
            f"**Usuario:** {nombre}\n"
            f"**Nivel:** {user['nivel']}\n"
            f"**Puntos:** {user['puntos']}\n\n"
            f"**💰 Finanzas:**\n"
            f"• Saldo: ${user['saldo']:.2f}\n"
            f"• Invertido: ${user['saldo_invertido']:.2f}\n"
            f"• Ganancias: ${user['ganancias_totales']:.2f}\n\n"
            f"**👥 Referidos:**\n"
            f"• Tus referidos: {len(user['referidos'])}\n"
            f"• Referido por: {user['referido_por'] or 'Ninguno'}\n\n"
            f"**🔗 Tu link:**\n"
            f"https://t.me/{BOT_USERNAME}?start={user_id}"
        )
    
    elif comando == '/historial':
        historial = db['historial'].get(user_id, [])[-20:]
        if not historial:
            respuesta = "📭 No hay movimientos"
        else:
            respuesta = "📋 **ÚLTIMOS MOVIMIENTOS**\n\n"
            for h in reversed(historial):
                fecha = datetime.fromtimestamp(h['fecha']).strftime('%d/%m %H:%M')
                respuesta += f"• {fecha} - {h['tipo']}: ${h['monto']:.2f}\n"
    
    elif comando == '/referidos':
        referidos = user['referidos']
        if not referidos:
            respuesta = (
                f"📭 **No tienes referidos**\n\n"
                f"Comparte tu link y gana 10% de sus depósitos:\n"
                f"https://t.me/{BOT_USERNAME}?start={user_id}"
            )
        else:
            respuesta = f"👥 **TUS REFERIDOS ({len(referidos)})**\n\n"
            for ref_id in referidos[:10]:
                ref = db['usuarios'].get(ref_id, {})
                respuesta += f"• {ref.get('nombre', 'Desconocido')}\n"
    
    elif comando == '/gananciasref':
        ganancias = 0
        for ref_id in user['referidos']:
            ref = db['usuarios'].get(ref_id, {})
            ganancias += ref.get('ganancias_totales', 0) * 0.1
        respuesta = f"💰 **Ganancias por referidos:** ${ganancias:.2f}"
    
    elif comando == '/link':
        respuesta = f"🔗 **TU LINK DE REFERIDO:**\nhttps://t.me/{BOT_USERNAME}?start={user_id}"
    
    elif comando == '/estadisticas':
        total_usuarios = len(db['usuarios'])
        total_invertido = sum(u['saldo_invertido'] for u in db['usuarios'].values())
        total_ganancias = sum(u['ganancias_totales'] for u in db['usuarios'].values())
        respuesta = (
            f"📊 **ESTADÍSTICAS GLOBALES**\n\n"
            f"• Usuarios totales: {total_usuarios}\n"
            f"• Capital invertido: ${total_invertido:.2f}\n"
            f"• Ganancias pagadas: ${total_ganancias:.2f}\n"
            f"• Usuarios online: {len(chat_ids_telegram)}"
        )
    
    else:
        respuesta = "❓ Comando no reconocido. Usa /ayuda"
    
    bot.send_message(chat_id, respuesta, parse_mode='Markdown')
    agregar_mensaje(user_id, 'bot', 'Bot', respuesta)

def procesar_comando_web(user_id, texto, nombre):
    """Procesa comandos desde la web"""
    partes = texto.split()
    comando = partes[0].lower()
    
    # Los comandos web también se procesan igual
    # La respuesta se enviará por polling
    
# ============================================
# SISTEMA DE GANANCIAS AUTOMÁTICAS
# ============================================
def calcular_ganancias():
    """Calcula ganancias cada hora"""
    while True:
        time.sleep(3600)  # Cada hora
        ahora = time.time()
        
        for user_id, inversiones in db['inversiones'].items():
            for inv in inversiones:
                if inv['activa']:
                    # Calcular ganancia desde último pago
                    horas = (ahora - inv['ultimo_pago']) / 3600
                    if horas >= 24:  # Pago diario
                        ganancia = inv['ganancia_diaria'] * (horas / 24)
                        inv['total_generado'] += ganancia
                        inv['ultimo_pago'] = ahora
                        
                        # Acreditar al usuario
                        db['usuarios'][user_id]['saldo'] += ganancia
                        db['usuarios'][user_id]['ganancias_totales'] += ganancia
                        
                        # Notificar
                        if user_id in chat_ids_telegram:
                            try:
                                bot.send_message(
                                    chat_ids_telegram[user_id],
                                    f"💰 **GANANCIA DIARIA**\n\n"
                                    f"Has recibido ${ganancia:.2f} de tu inversión"
                                )
                            except:
                                pass
        
        guardar_db()

# Iniciar hilo de ganancias
threading.Thread(target=calcular_ganancias, daemon=True).start()

# ============================================
# WEBHOOK SETUP
# ============================================
@app.route('/setup_webhook')
def setup_webhook():
    try:
        webhook_url = f"https://{request.host}/webhook"
        bot.remove_webhook()
        bot.set_webhook(url=webhook_url)
        return f"✅ Webhook configurado: {webhook_url}"
    except Exception as e:
        return f"❌ Error: {e}"

# ============================================
# INICIAR
# ============================================
if __name__ == "__main__":
    print("="*60)
    print("💰 BOT DE INVERSIÓN COMPLETO")
    print("="*60)
    print(f"Bot: @{BOT_USERNAME}")
    print(f"Usuarios: {len(db['usuarios'])}")
    print(f"Inversiones: {sum(len(i) for i in db['inversiones'].values())}")
    print("="*60)
    app.run(host="0.0.0.0", port=5000)
