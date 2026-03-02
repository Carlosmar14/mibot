import os
import time
import threading
import json
import hashlib
from datetime import datetime
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
# BASE DE DATOS POR USUARIO (CHATS PERSONALES)
# ============================================
try:
    with open('database.json', 'r') as f:
        db = json.load(f)
except:
    db = {
        'usuarios': {},  # Información de usuarios
        'chats': {}      # CHATS PERSONALES: {user_id: [mensajes]}
    }

def guardar_db():
    with open('database.json', 'w') as f:
        json.dump(db, f)

# ============================================
# FUNCIONES PARA CHATS PERSONALES
# ============================================
def obtener_chat_usuario(user_id):
    """Obtiene el chat personal de un usuario"""
    if user_id not in db['chats']:
        db['chats'][user_id] = []
        guardar_db()
    return db['chats'][user_id]

def agregar_mensaje_chat(user_id, origen, nombre, texto):
    """Agrega un mensaje al chat personal del usuario"""
    if user_id not in db['chats']:
        db['chats'][user_id] = []
    
    mensaje = {
        'id': len(db['chats'][user_id]) + 1,
        'origen': origen,  # 'web', 'telegram', 'bot'
        'nombre': nombre,
        'texto': texto,
        'fecha': time.time()
    }
    
    db['chats'][user_id].append(mensaje)
    guardar_db()
    return mensaje

def obtener_mensajes_nuevos(user_id, ultimo_id_visto):
    """Obtiene solo los mensajes nuevos del chat personal"""
    chat = obtener_chat_usuario(user_id)
    return [m for m in chat if m['id'] > ultimo_id_visto]

def registrar_usuario(user_id, nombre, username=None):
    """Registra un usuario si no existe"""
    if user_id not in db['usuarios']:
        db['usuarios'][user_id] = {
            'user_id': user_id,
            'nombre': nombre,
            'username': username,
            'saldo': 0,
            'referido_por': None,
            'referidos': [],
            'historial': [],
            'fecha_registro': time.time()
        }
        db['chats'][user_id] = []  # Crear su chat personal
        guardar_db()
        return True
    return False

# ============================================
# RUTA PRINCIPAL (SOLO PARA ADMIN)
# ============================================
@app.route('/')
def home():
    total_mensajes = sum(len(chat) for chat in db['chats'].values())
    return f"""
    <html>
    <head>
        <title>Panel Admin - Chats Personales</title>
        <style>
            body {{ font-family: Arial; padding: 20px; background: #f5f5f5; }}
            .container {{ max-width: 1200px; margin: 0 auto; }}
            .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 10px; margin-bottom: 20px; }}
            .stats {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin-bottom: 20px; }}
            .card {{ background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
            table {{ width: 100%; background: white; border-radius: 10px; overflow: hidden; }}
            th {{ background: #667eea; color: white; padding: 10px; }}
            td {{ padding: 10px; border-bottom: 1px solid #ddd; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🤖 CHATS PERSONALES</h1>
                <p>Cada usuario tiene su propio chat privado</p>
            </div>
            
            <div class="stats">
                <div class="card">
                    <h3>Usuarios</h3>
                    <h2>{len(db['usuarios'])}</h2>
                </div>
                <div class="card">
                    <h3>Chats Activos</h3>
                    <h2>{len([c for c in db['chats'].values() if c])}</h2>
                </div>
                <div class="card">
                    <h3>Mensajes Totales</h3>
                    <h2>{total_mensajes}</h2>
                </div>
            </div>
            
            <h2>Usuarios Registrados</h2>
            <table>
                <tr>
                    <th>ID</th>
                    <th>Nombre</th>
                    <th>Username</th>
                    <th>Mensajes</th>
                    <th>Saldo</th>
                </tr>
                {''.join([f'''
                <tr>
                    <td>{uid[:8]}...</td>
                    <td>{u.get('nombre', '')}</td>
                    <td>@{u.get('username', '')}</td>
                    <td>{len(db['chats'].get(uid, []))}</td>
                    <td>${u.get('saldo', 0)}</td>
                </tr>
                ''' for uid, u in list(db['usuarios'].items())[:10]])}
            </table>
            
            <p style="margin-top: 20px;">
                <a href="/setup_webhook">Configurar Webhook</a>
            </p>
        </div>
    </body>
    </html>
    """

# ============================================
# LOGIN CON TELEGRAM
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
        
        # Registrar usuario (crea su chat personal automáticamente)
        registrar_usuario(user_id, nombre, username)
        
        # Crear sesión
        session_token = hashlib.sha256(f"{user_id}{time.time()}".encode()).hexdigest()[:20]
        
        # Mensaje de bienvenida en su chat personal
        agregar_mensaje_chat(user_id, 'bot', 'Sistema', f"🎉 ¡Bienvenido {nombre}! Has iniciado sesión.")
        
        return jsonify({
            'success': True,
            'user': db['usuarios'][user_id],
            'session': session_token
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============================================
# API PARA LA WEB (CHAT PERSONAL)
# ============================================
@app.route('/api/chat/<user_id>', methods=['GET'])
def obtener_chat(user_id):
    """Cada usuario obtiene SOLO su chat personal"""
    session = request.args.get('session')
    ultimo_id = int(request.args.get('ultimo_id', 0))
    
    # Verificar que el usuario solo ve su propio chat
    if user_id != request.args.get('user_id'):
        return jsonify({'error': 'No autorizado'}), 403
    
    # Obtener solo sus mensajes nuevos
    chat = obtener_chat_usuario(user_id)
    mensajes_nuevos = [m for m in chat if m['id'] > ultimo_id]
    
    return jsonify({
        'mensajes': mensajes_nuevos,
        'ultimo_id': max([m['id'] for m in chat]) if chat else 0
    })

@app.route('/api/enviar', methods=['POST'])
def enviar_mensaje():
    """Envía un mensaje al chat personal del usuario"""
    data = request.json
    user_id = data.get('user_id')
    texto = data.get('texto')
    
    # Verificar que el usuario solo envía a su propio chat
    if user_id != data.get('user_id'):
        return jsonify({'error': 'No autorizado'}), 403
    
    user = db['usuarios'].get(user_id, {})
    nombre = user.get('nombre', 'Usuario')
    
    # Guardar en su chat personal
    mensaje = agregar_mensaje_chat(user_id, 'web', nombre, texto)
    
    # Si está conectado a Telegram, enviarle una copia
    if user_id in chat_ids_telegram:
        try:
            bot.send_message(
                chat_ids_telegram[user_id],
                f"📱 **Tú (Web):** {texto}",
                parse_mode='Markdown'
            )
        except:
            pass
    
    return jsonify({'success': True, 'id': mensaje['id']})

# ============================================
# WEBHOOK DE TELEGRAM (CHAT PERSONAL)
# ============================================
chat_ids_telegram = {}  # user_id -> chat_id

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        update = telebot.types.Update.de_json(request.stream.read().decode('utf-8'))
        
        if update.message:
            thread = threading.Thread(target=procesar_mensaje_telegram, args=(update.message,))
            thread.start()
        
        return 'OK', 200
    except Exception as e:
        print(f"Error: {e}")
        return 'Error', 500

def procesar_mensaje_telegram(message):
    user_id = str(message.from_user.id)
    chat_id = message.chat.id
    texto = message.text
    nombre = message.from_user.first_name
    username = message.from_user.username
    
    # Guardar chat_id para responder
    chat_ids_telegram[user_id] = chat_id
    
    # Registrar usuario (crea su chat personal)
    registrar_usuario(user_id, nombre, username)
    
    print(f"📱 Telegram [{nombre}]: {texto}")
    
    # Guardar mensaje en SU chat personal
    agregar_mensaje_chat(user_id, 'telegram', nombre, texto)
    
    # Procesar comandos
    if texto.startswith('/'):
        procesar_comando(user_id, chat_id, texto, nombre)
    else:
        # Respuesta automática
        respuesta = f"✅ Mensaje recibido en tu chat personal"
        bot.send_message(chat_id, respuesta)
        agregar_mensaje_chat(user_id, 'bot', 'Bot', respuesta)

def procesar_comando(user_id, chat_id, texto, nombre):
    """Procesa comandos - cada usuario ve SOLO sus datos"""
    partes = texto.split()
    comando = partes[0].lower()
    
    user = db['usuarios'][user_id]
    saldo = user['saldo']
    referidos = len(user['referidos'])
    
    if comando == '/start':
        if len(partes) > 1 and 'ref_' in partes[1]:
            ref_id = partes[1].replace('ref_', '')
            if ref_id != user_id and ref_id in db['usuarios'] and not user['referido_por']:
                user['referido_por'] = ref_id
                db['usuarios'][ref_id]['referidos'].append(user_id)
                guardar_db()
                
                # Notificar al referidor en SU chat personal
                if ref_id in chat_ids_telegram:
                    try:
                        bot.send_message(
                            chat_ids_telegram[ref_id],
                            f"🎉 ¡{nombre} se unió con tu link de referido!"
                        )
                    except:
                        pass
        
        respuesta = (
            f"👋 **¡Bienvenido a tu chat personal!**\n\n"
            f"**Tus datos:**\n"
            f"💰 Saldo: ${saldo}\n"
            f"👥 Referidos: {referidos}\n\n"
            f"**Comandos:**\n"
            f"/balance - Ver saldo\n"
            f"/referidos - Ver tus referidos\n"
            f"/perfil - Tu perfil\n"
            f"/ayuda - Ayuda\n\n"
            f"**Link de referido:**\n"
            f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}"
        )
    
    elif comando == '/balance':
        respuesta = f"💰 **Tu saldo:** ${saldo}"
    
    elif comando == '/referidos':
        if not user['referidos']:
            respuesta = f"📭 No tienes referidos. Comparte tu link:\nhttps://t.me/{BOT_USERNAME}?start=ref_{user_id}"
        else:
            texto_ref = ""
            for ref_id in user['referidos']:
                ref = db['usuarios'].get(ref_id, {})
                texto_ref += f"• {ref.get('nombre', 'Desconocido')}\n"
            respuesta = f"👥 **Tus referidos ({len(user['referidos'])}):**\n\n{texto_ref}"
    
    elif comando == '/perfil':
        respuesta = (
            f"👤 **Tu perfil**\n\n"
            f"**Nombre:** {nombre}\n"
            f"**ID:** {user_id}\n"
            f"**Saldo:** ${saldo}\n"
            f"**Referidos:** {referidos}\n"
            f"**Link:** https://t.me/{BOT_USERNAME}?start=ref_{user_id}"
        )
    
    elif comando == '/ayuda':
        respuesta = (
            "📋 **Comandos disponibles:**\n\n"
            "/start - Inicio\n"
            "/balance - Ver saldo\n"
            "/referidos - Ver referidos\n"
            "/perfil - Ver perfil\n"
            "/ayuda - Esta ayuda\n\n"
            "**Web sincronizada:**\n"
            f"{WEB_URL}"
        )
    
    else:
        respuesta = "Comando no reconocido. Usa /ayuda"
    
    bot.send_message(chat_id, respuesta, parse_mode='Markdown')
    agregar_mensaje_chat(user_id, 'bot', 'Bot', respuesta)

# ============================================
# CONFIGURAR WEBHOOK
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
    print("🤖 CHATS PERSONALES - CADA USUARIO SU CHAT")
    print("="*60)
    print(f"Bot: @{BOT_USERNAME}")
    print(f"Usuarios: {len(db['usuarios'])}")
    print(f"Chats activos: {len([c for c in db['chats'].values() if c])}")
    print("="*60)
    app.run(host="0.0.0.0", port=5000)
