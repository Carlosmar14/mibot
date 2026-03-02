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
# TUS DATOS (YA CONFIGURADOS)
# ============================================
BOT_USERNAME = "shopcmar_bot"
WEB_URL = "https://carlosmar14.github.io/mibot/"
BOT_TOKEN = "8756602645:AAHZjNUJ1KKy-1L9i2CAJRMy-mIE5ambV_Q"

bot = telebot.TeleBot(BOT_TOKEN)

# ============================================
# BASE DE DATOS EN MEMORIA
# ============================================
usuarios = {}
mensajes = []
chat_ids = {}
ultimo_id = 0
usuarios_conectados = set()

# ============================================
### 🏠 RUTA PRINCIPAL - ¡LA QUE FALTABA! 🏠 ###
# ============================================
@app.route('/')
def home():
    return f"""
    <html>
    <head>
        <title>Bot Sincronizado - Monitor</title>
        <style>
            body {{ font-family: Arial; background: #f5f5f5; padding: 40px; }}
            .container {{ max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; }}
            h1 {{ color: #333; }}
            .status {{ color: green; font-weight: bold; }}
            .info {{ background: #e3f2fd; padding: 15px; border-radius: 5px; margin: 20px 0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🤖 BOT SINCRONIZADO</h1>
            <p>Estado: <span class="status">✅ FUNCIONANDO</span></p>
            
            <div class="info">
                <p><strong>Bot:</strong> @{BOT_USERNAME}</p>
                <p><strong>Web:</strong> <a href="{WEB_URL}" target="_blank">{WEB_URL}</a></p>
                <p><strong>Usuarios conectados:</strong> {len(usuarios_conectados)}</p>
                <p><strong>Mensajes totales:</strong> {len(mensajes)}</p>
            </div>
            
            <h3>🔧 Endpoints:</h3>
            <ul>
                <li><a href="/setup_webhook">/setup_webhook</a> - Configurar webhook</li>
                <li><a href="/api/usuarios">/api/usuarios</a> - Ver usuarios</li>
                <li>/auth/telegram - Login (POST)</li>
                <li>/api/enviar - Enviar mensaje (POST)</li>
                <li>/api/recibir/&lt;id&gt; - Recibir mensajes (GET)</li>
            </ul>
        </div>
    </body>
    </html>
    """

# ============================================
### 🔐 RUTA DE LOGIN ###
# ============================================
@app.route('/auth/telegram', methods=['POST', 'OPTIONS'])
def auth_telegram():
    if request.method == 'OPTIONS':
        return '', 200
    
    try:
        data = request.json
        user_id = str(data["id"])
        
        session_token = hashlib.sha256(f"{user_id}{time.time()}".encode()).hexdigest()[:20]
        
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
        
        return jsonify({
            "success": True,
            "user": usuarios[user_id],
            "session": session_token
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ============================================
### 📱 WEBHOOK DE TELEGRAM ###
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
        return "Error", 500

def procesar_mensaje_telegram(message):
    global ultimo_id
    user_id = str(message.from_user.id)
    texto = message.text or "📎 Mensaje sin texto"
    chat_id = message.chat.id
    nombre = message.from_user.first_name
    
    chat_ids[user_id] = chat_id
    
    ultimo_id += 1
    mensajes.append({
        "id": ultimo_id,
        "origen": "telegram",
        "user_id": user_id,
        "nombre": nombre,
        "texto": texto,
        "fecha": time.time()
    })
    
    # Respuesta automática
    texto_lower = texto.lower().strip()
    if texto_lower == "/start":
        respuesta = f"¡Hola {nombre}! 👋 Bot sincronizado con la web."
    elif texto_lower == "/ayuda":
        respuesta = "Comandos: /start, /ayuda, /info, /hora, /perfil"
    elif texto_lower == "/hora":
        respuesta = f"📅 {datetime.now().strftime('%H:%M:%S')}"
    else:
        respuesta = f"✅ Recibido: {texto}"
    
    bot.send_message(chat_id, respuesta)
    
    ultimo_id += 1
    mensajes.append({
        "id": ultimo_id,
        "origen": "bot",
        "user_id": user_id,
        "nombre": "Bot",
        "texto": respuesta,
        "fecha": time.time()
    })

# ============================================
### 🌐 API PARA LA WEB ###
# ============================================
@app.route('/api/enviar', methods=['POST', 'OPTIONS'])
def enviar_mensaje():
    if request.method == 'OPTIONS':
        return '', 200
    
    global ultimo_id
    data = request.json
    user_id = data.get("user_id")
    texto = data.get("texto")
    session = data.get("session")
    
    if not verificar_sesion(user_id, session):
        return jsonify({"error": "Sesión inválida"}), 401
    
    usuarios_conectados.add(user_id)
    
    ultimo_id += 1
    mensajes.append({
        "id": ultimo_id,
        "origen": "web",
        "user_id": user_id,
        "nombre": usuarios.get(user_id, {}).get("first_name", "Usuario"),
        "texto": texto,
        "fecha": time.time()
    })
    
    if user_id in chat_ids:
        try:
            bot.send_message(chat_ids[user_id], f"📱 Web: {texto}")
        except:
            pass
    
    return jsonify({"success": True})

@app.route('/api/recibir/<user_id>', methods=['GET', 'OPTIONS'])
def recibir_mensajes(user_id):
    if request.method == 'OPTIONS':
        return '', 200
    
    session = request.args.get("session")
    ultimo_id_recibido = int(request.args.get("ultimo_id", 0))
    
    if not verificar_sesion(user_id, session):
        return jsonify({"error": "Sesión inválida"}), 401
    
    usuarios_conectados.add(user_id)
    
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

@app.route('/api/usuarios', methods=['GET'])
def ver_usuarios():
    return jsonify({
        "total": len(usuarios),
        "conectados": len(usuarios_conectados)
    })

def verificar_sesion(user_id, session):
    user = usuarios.get(user_id)
    if not user:
        return False
    return user.get("session") == session

# ============================================
### 🔧 CONFIGURAR WEBHOOK ###
# ============================================
@app.route('/setup_webhook')
def setup_webhook():
    try:
        webhook_url = f"https://{request.host}/webhook"
        bot.remove_webhook()
        bot.set_webhook(url=webhook_url)
        return f"✅ Webhook configurado en: {webhook_url}"
    except Exception as e:
        return f"❌ Error: {e}"

# ============================================
### 🚀 INICIAR ###
# ============================================
if __name__ == "__main__":
    print("="*50)
    print("🤖 BOT INICIADO")
    print("="*50)
    print(f"Bot: @{BOT_USERNAME}")
    print(f"Monitor: https://mibot-yuz8.onrender.com/")
    print("="*50)
    app.run(host="0.0.0.0", port=5000)
