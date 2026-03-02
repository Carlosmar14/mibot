import os
import time
import json
import hashlib
import hmac
import threading
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
import telebot

# ============================================
# CONFIGURACIÓN INICIAL
# ============================================
app = Flask(__name__)
CORS(app, origins=["https://carlosmar14.github.io", "http://localhost:3000"])

# ============================================
### ✅ DATOS CONFIGURADOS (YA ESTÁN TUS DATOS) ###
# ============================================
BOT_USERNAME = "shopcmar_bot"  # ← TU BOT
WEB_URL = "https://carlosmar14.github.io/mibot/"   # ← TU WEB
# ============================================

# Token desde variables de entorno (Render)
BOT_TOKEN = os.environ.get('TOKEN')
if not BOT_TOKEN:
    print("❌ ERROR: No hay token en variables de entorno")
    BOT_TOKEN = "8756602645:AAHZjNUJ1KKy-1L9i2CAJRMy-mIE5ambV_Q"  # ← TU TOKEN

bot = telebot.TeleBot(BOT_TOKEN)

# ============================================
# BASE DE DATOS EN MEMORIA
# ============================================
usuarios = {}              # user_id -> datos del usuario
mensajes = []              # historial de mensajes
chat_ids = {}              # user_id -> chat_id de Telegram
ultimo_id = 0              # contador de mensajes
usuarios_conectados = set()  # usuarios online ahora

# ============================================
### 🏠 RUTA PRINCIPAL (HOME) 🏠 ###
# ============================================
@app.route('/')
def home():
    return f"""
    <html>
    <head>
        <title>Bot Sincronizado - Monitor</title>
        <meta http-equiv="refresh" content="5">
        <style>
            body {{ font-family: 'Segoe UI', Arial; background: #f5f5f5; margin: 0; padding: 20px; }}
            .container {{ max-width: 1200px; margin: 0 auto; }}
            .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 15px; margin-bottom: 20px; }}
            .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-bottom: 20px; }}
            .card {{ background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
            .number {{ font-size: 2.5em; font-weight: bold; color: #667eea; }}
            .online {{ display: inline-block; width: 10px; height: 10px; background: #4caf50; border-radius: 50%; margin-right: 5px; }}
            .endpoints {{ background: #f0f0f0; padding: 15px; border-radius: 10px; margin-top: 20px; }}
            .endpoints a {{ color: #667eea; text-decoration: none; }}
            .endpoints a:hover {{ text-decoration: underline; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🤖 Bot Sincronizado - Monitor en Tiempo Real</h1>
                <p>Bot: @{BOT_USERNAME} | Web: <a href="{WEB_URL}" style="color: white;">{WEB_URL}</a></p>
                <p>Token: {BOT_TOKEN[:10]}... (configurado)</p>
            </div>
            
            <div class="stats">
                <div class="card">
                    <h3>👥 Usuarios Registrados</h3>
                    <div class="number">{len(usuarios)}</div>
                </div>
                <div class="card">
                    <h3>🟢 Conectados Ahora</h3>
                    <div class="number">{len(usuarios_conectados)}</div>
                </div>
                <div class="card">
                    <h3>💬 Mensajes Totales</h3>
                    <div class="number">{len(mensajes)}</div>
                </div>
            </div>
            
            <div class="card">
                <h3>📊 Últimos Mensajes</h3>
                <div style="max-height: 200px; overflow: auto;">
                    {''.join([f'<div style="padding: 5px; border-bottom: 1px solid #eee;"><strong>[{datetime.fromtimestamp(m["fecha"]).strftime("%H:%M:%S")}]</strong> {m["origen"].upper()}: {m["texto"][:50]}</div>' for m in mensajes[-10:]])}
                </div>
            </div>
            
            <div class="endpoints">
                <h3>🔧 Endpoints Disponibles:</h3>
                <ul>
                    <li><a href="/setup_webhook">/setup_webhook</a> - Configurar webhook (ejecutar una vez)</li>
                    <li><a href="/api/usuarios">/api/usuarios</a> - Ver usuarios conectados</li>
                    <li>/auth/telegram - Login (POST)</li>
                    <li>/api/enviar - Enviar mensaje (POST)</li>
                    <li>/api/recibir/&lt;user_id&gt; - Recibir mensajes (GET)</li>
                </ul>
            </div>
        </div>
    </body>
    </html>
    """

# ============================================
### 🔐 RUTA DE LOGIN 🔐 ###
# ============================================
@app.route('/auth/telegram', methods=['POST', 'OPTIONS'])
def auth_telegram():
    if request.method == 'OPTIONS':
        return '', 200
    
    try:
        data = request.json
        print(f"📥 Login intent: ID={data.get('id')}, Nombre={data.get('first_name')}")
        
        user_id = str(data["id"])
        
        # Generar token de sesión
        session_token = hashlib.sha256(
            f"{user_id}{time.time()}{os.urandom(16)}".encode()
        ).hexdigest()[:20]
        
        # Guardar usuario
        usuarios[user_id] = {
            "id": user_id,
            "first_name": data.get("first_name", ""),
            "last_name": data.get("last_name", ""),
            "username": data.get("username", ""),
            "photo_url": data.get("photo_url", ""),
            "session": session_token,
            "ultima": time.time()
        }
        
        usuarios_conectados.add(user_id)
        
        print(f"✅ Login exitoso: {data.get('first_name')}")
        
        return jsonify({
            "success": True,
            "user": usuarios[user_id],
            "session": session_token
        })
        
    except Exception as e:
        print(f"❌ Error en login: {e}")
        return jsonify({"error": str(e)}), 500

# ============================================
### 📱 RUTA DEL WEBHOOK (RECIBIR MENSAJES DE TELEGRAM) 📱 ###
# ============================================
@app.route('/webhook', methods=['POST'])
def telegram_webhook():
    try:
        update = telebot.types.Update.de_json(request.stream.read().decode("utf-8"))
        
        if update.message:
            thread = threading.Thread(target=procesar_mensaje_telegram, args=(update.message,))
            thread.start()
        
        return "OK", 200
    except Exception as e:
        print(f"❌ Error en webhook: {e}")
        return "Error", 500

def procesar_mensaje_telegram(message):
    global ultimo_id
    
    try:
        user_id = str(message.from_user.id)
        texto = message.text or "📎 Mensaje sin texto"
        chat_id = message.chat.id
        nombre = message.from_user.first_name
        
        print(f"📱 Telegram [{nombre}]: {texto[:50]}")
        
        # Guardar chat_id
        chat_ids[user_id] = chat_id
        
        # Registrar usuario si no existe
        if user_id not in usuarios:
            usuarios[user_id] = {
                "id": user_id,
                "first_name": nombre,
                "last_name": message.from_user.last_name or "",
                "username": message.from_user.username or "",
                "photo_url": "",
                "ultima": time.time()
            }
        
        # Guardar mensaje
        ultimo_id += 1
        mensajes.append({
            "id": ultimo_id,
            "origen": "telegram",
            "user_id": user_id,
            "nombre": nombre,
            "texto": texto,
            "fecha": time.time()
        })
        
        # Generar respuesta
        texto_lower = texto.lower().strip()
        
        if texto_lower == "/start":
            respuesta = f"¡Hola {nombre}! 👋\n\nBot sincronizado con la web. Usa /ayuda para comandos."
        elif texto_lower == "/ayuda":
            respuesta = "📋 Comandos: /start, /ayuda, /info, /hora, /perfil, /web"
        elif texto_lower == "/info":
            respuesta = f"🤖 Bot sincronizado\nUsuarios: {len(usuarios)}\nConectados: {len(usuarios_conectados)}"
        elif texto_lower == "/hora":
            respuesta = f"📅 {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
        elif texto_lower == "/perfil":
            respuesta = f"👤 Nombre: {nombre}\nID: {user_id}"
        elif texto_lower == "/web":
            respuesta = f"🌐 Web: {WEB_URL}"
        else:
            respuesta = f"✅ Recibido: {texto}"
        
        bot.send_message(chat_id, respuesta)
        
        # Guardar respuesta del bot
        ultimo_id += 1
        mensajes.append({
            "id": ultimo_id,
            "origen": "bot",
            "user_id": user_id,
            "nombre": "Bot",
            "texto": respuesta,
            "fecha": time.time()
        })
        
    except Exception as e:
        print(f"❌ Error procesando mensaje: {e}")

# ============================================
### 🌐 RUTA PARA ENVIAR MENSAJES DESDE LA WEB 🌐 ###
# ============================================
@app.route('/api/enviar', methods=['POST', 'OPTIONS'])
def enviar_mensaje():
    if request.method == 'OPTIONS':
        return '', 200
    
    global ultimo_id
    
    try:
        data = request.json
        user_id = data.get("user_id")
        texto = data.get("texto")
        session = data.get("session")
        
        # Verificar sesión
        if not verificar_sesion(user_id, session):
            return jsonify({"error": "Sesión inválida"}), 401
        
        usuarios_conectados.add(user_id)
        
        if user_id in usuarios:
            usuarios[user_id]["ultima"] = time.time()
        
        nombre = usuarios.get(user_id, {}).get("first_name", "Usuario")
        
        print(f"🌐 Web [{nombre}]: {texto[:50]}")
        
        # Guardar mensaje
        ultimo_id += 1
        mensajes.append({
            "id": ultimo_id,
            "origen": "web",
            "user_id": user_id,
            "nombre": nombre,
            "texto": texto,
            "fecha": time.time()
        })
        
        # Enviar a Telegram si está conectado
        if user_id in chat_ids:
            try:
                bot.send_message(chat_ids[user_id], f"📱 Web: {texto}")
            except:
                pass
        
        return jsonify({"success": True, "id": ultimo_id})
        
    except Exception as e:
        print(f"❌ Error en /api/enviar: {e}")
        return jsonify({"error": str(e)}), 500

# ============================================
### 🔄 RUTA PARA RECIBIR MENSAJES (POLLING) 🔄 ###
# ============================================
@app.route('/api/recibir/<user_id>', methods=['GET', 'OPTIONS'])
def recibir_mensajes(user_id):
    if request.method == 'OPTIONS':
        return '', 200
    
    try:
        session = request.args.get("session")
        ultimo_id_recibido = int(request.args.get("ultimo_id", 0))
        
        # Verificar sesión
        if not verificar_sesion(user_id, session):
            return jsonify({"error": "Sesión inválida"}), 401
        
        usuarios_conectados.add(user_id)
        
        if user_id in usuarios:
            usuarios[user_id]["ultima"] = time.time()
        
        # Filtrar mensajes nuevos
        mensajes_nuevos = [
            m for m in mensajes 
            if m["id"] > ultimo_id_recibido and (
                m["user_id"] == user_id or m["origen"] == "bot"
            )
        ]
        
        ultimo_id_global = max([m["id"] for m in mensajes]) if mensajes else 0
        
        return jsonify({
            "mensajes": mensajes_nuevos,
            "ultimo_id": ultimo_id_global,
            "conectados": len(usuarios_conectados)
        })
        
    except Exception as e:
        print(f"❌ Error en /api/recibir: {e}")
        return jsonify({"error": str(e)}), 500

# ============================================
### 📊 RUTA PARA VER USUARIOS 📊 ###
# ============================================
@app.route('/api/usuarios', methods=['GET'])
def ver_usuarios():
    return jsonify({
        "total": len(usuarios),
        "conectados": len(usuarios_conectados),
        "usuarios": [
            {
                "id": uid,
                "nombre": u.get("first_name"),
                "username": u.get("username")
            }
            for uid, u in usuarios.items()
        ]
    })

def verificar_sesion(user_id, session):
    if not user_id or not session:
        return False
    user = usuarios.get(user_id)
    if not user:
        return False
    return user.get("session") == session

# ============================================
### 🔧 RUTA PARA CONFIGURAR WEBHOOK 🔧 ###
# ============================================
@app.route('/setup_webhook')
def setup_webhook():
    try:
        webhook_url = f"https://{request.host}/webhook"
        bot.remove_webhook()
        bot.set_webhook(url=webhook_url)
        return f"""
        <html>
        <body style="font-family: Arial; padding: 40px;">
            <h1 style="color: green;">✅ Webhook configurado</h1>
            <p>URL: {webhook_url}</p>
            <p><a href="/">Volver al monitor</a></p>
        </body>
        </html>
        """
    except Exception as e:
        return f"<h1 style='color: red;'>❌ Error: {e}</h1>"

# ============================================
### 🧹 LIMPIEZA DE USUARIOS INACTIVOS 🧹 ###
# ============================================
def limpiar_inactivos():
    while True:
        time.sleep(60)
        ahora = time.time()
        inactivos = []
        for user_id in usuarios_conectados:
            if user_id in usuarios and ahora - usuarios[user_id].get("ultima", 0) > 120:
                inactivos.append(user_id)
        for user_id in inactivos:
            usuarios_conectados.discard(user_id)
            print(f"👋 Usuario {user_id} desconectado por inactividad")

threading.Thread(target=limpiar_inactivos, daemon=True).start()

# ============================================
### 🚀 INICIAR SERVIDOR 🚀 ###
# ============================================
if __name__ == "__main__":
    print("="*50)
    print("🤖 BOT SINCRONIZADO INICIADO")
    print("="*50)
    print(f"Username: @{BOT_USERNAME}")
    print(f"Web: {WEB_URL}")
    print(f"Token: {BOT_TOKEN[:10]}...")
    print("="*50)
    print("📍 RUTAS DISPONIBLES:")
    print("  / - Monitor principal")
    print("  /auth/telegram - Login")
    print("  /webhook - Webhook de Telegram")
    print("  /api/enviar - Enviar mensaje")
    print("  /api/recibir/<id> - Recibir mensajes")
    print("  /api/usuarios - Ver usuarios")
    print("  /setup_webhook - Configurar webhook")
    print("="*50)
    
    app.run(host="0.0.0.0", port=5000)
