import os
import time
import threading
import json
import hashlib
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
import telebot

app = Flask(__name__)
CORS(app, origins=["https://carlosmar14.github.io"])

BOT_TOKEN = "8756602645:AAHZjNUJ1KKy-1L9i2CAJRMy-mIE5ambV_Q"
BOT_USERNAME = "shopcmar_bot"
WEB_URL = "https://carlosmar14.github.io/mibot/"

bot = telebot.TeleBot(BOT_TOKEN)

# Base de datos simple
try:
    with open('database.json', 'r') as f:
        db = json.load(f)
except:
    db = {
        'usuarios': {},
        'chats': {},
        'inversiones': {},
        'historial': {}
    }

def guardar_db():
    with open('database.json', 'w') as f:
        json.dump(db, f)

# ============================================
# RUTA PRINCIPAL
# ============================================
@app.route('/')
def home():
    return "✅ BOT FUNCIONANDO CORRECTAMENTE"

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
# LOGIN
# ============================================
@app.route('/auth/telegram', methods=['POST'])
def auth_telegram():
    try:
        data = request.json
        user_id = str(data['id'])
        nombre = data.get('first_name', '')
        
        if user_id not in db['usuarios']:
            db['usuarios'][user_id] = {
                'nombre': nombre,
                'saldo': 0,
                'invertido': 0,
                'ganancias': 0,
                'referidos': []
            }
            db['chats'][user_id] = []
            db['inversiones'][user_id] = []
            db['historial'][user_id] = []
            guardar_db()
        
        return jsonify({'success': True, 'user': db['usuarios'][user_id]})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============================================
# API CHAT
# ============================================
@app.route('/api/chat/<user_id>', methods=['GET'])
def obtener_chat(user_id):
    ultimo_id = int(request.args.get('ultimo_id', 0))
    chat = db['chats'].get(user_id, [])
    nuevos = [m for m in chat if m['id'] > ultimo_id]
    return jsonify({
        'mensajes': nuevos,
        'ultimo_id': max([m['id'] for m in chat]) if chat else 0
    })

@app.route('/api/enviar', methods=['POST'])
def enviar_mensaje():
    data = request.json
    user_id = data.get('user_id')
    texto = data.get('texto')
    
    if user_id not in db['chats']:
        db['chats'][user_id] = []
    
    mensaje = {
        'id': len(db['chats'][user_id]) + 1,
        'origen': 'web',
        'texto': texto,
        'fecha': time.time()
    }
    db['chats'][user_id].append(mensaje)
    guardar_db()
    
    return jsonify({'success': True})

@app.route('/api/usuario/<user_id>', methods=['GET'])
def api_usuario(user_id):
    return jsonify({
        'user': db['usuarios'].get(user_id, {}),
        'inversiones': db['inversiones'].get(user_id, [])
    })

# ============================================
# WEBHOOK TELEGRAM
# ============================================
@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        update = telebot.types.Update.de_json(request.stream.read().decode('utf-8'))
        if update.message:
            thread = threading.Thread(target=procesar_mensaje, args=(update.message,))
            thread.start()
        return 'OK', 200
    except Exception as e:
        return 'Error', 500

def procesar_mensaje(message):
    user_id = str(message.from_user.id)
    chat_id = message.chat.id
    texto = message.text
    nombre = message.from_user.first_name
    
    # Registrar usuario
    if user_id not in db['usuarios']:
        db['usuarios'][user_id] = {
            'nombre': nombre,
            'saldo': 0,
            'invertido': 0,
            'ganancias': 0,
            'referidos': []
        }
        db['chats'][user_id] = []
        db['inversiones'][user_id] = []
        db['historial'][user_id] = []
    
    # Guardar mensaje
    if user_id not in db['chats']:
        db['chats'][user_id] = []
    
    db['chats'][user_id].append({
        'id': len(db['chats'][user_id]) + 1,
        'origen': 'telegram',
        'texto': texto,
        'fecha': time.time()
    })
    guardar_db()
    
    # Responder
    if texto == '/start':
        respuesta = f"👋 ¡Hola {nombre}! Bienvenido al Bot de Inversiones."
    elif texto == '/balance':
        saldo = db['usuarios'][user_id]['saldo']
        respuesta = f"💰 Tu saldo es: ${saldo}"
    elif texto.startswith('/depositar'):
        try:
            monto = float(texto.split()[1])
            db['usuarios'][user_id]['saldo'] += monto
            guardar_db()
            respuesta = f"✅ Depósito de ${monto} realizado. Nuevo saldo: ${db['usuarios'][user_id]['saldo']}"
        except:
            respuesta = "❌ Usa: /depositar [monto]"
    else:
        respuesta = "❓ Usa /start para comenzar"
    
    bot.send_message(chat_id, respuesta)
    
    # Guardar respuesta
    db['chats'][user_id].append({
        'id': len(db['chats'][user_id]) + 1,
        'origen': 'bot',
        'texto': respuesta,
        'fecha': time.time()
    })
    guardar_db()

if __name__ == "__main__":
    print("="*50)
    print("🤖 BOT INICIADO")
    print("="*50)
    app.run(host="0.0.0.0", port=5000)