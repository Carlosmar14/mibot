import os
import time
import json
import hashlib
import hmac
import threading
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
import telebot
import requests

# ============================================
# CONFIGURACIÓN INICIAL (CAMBIA ESTOS VALORES)
# ============================================
BOT_TOKEN = "8756602645:AAHZjNUJ1KKy-1L9i2CAJRMy-mIE5ambV_Q"  # ← OBLIGATORIO
BOT_USERNAME = "shopcmar_bot"  # ← OBLIGATORIO
WEB_URL = "carlosmar14.github.io/mibot/"  # ← TU WEB EN GITHUB

# Inicialización
app = Flask(__name__)
CORS(app, origins=["carlosmar14.github.io/mibot/", "http://localhost:3000"])  # ← AJUSTA
bot = telebot.TeleBot(BOT_TOKEN)

# ============================================
# BASE DE DATOS EN MEMORIA (tiempo real)
# ============================================
usuarios = {}        # user_id -> datos completos
mensajes = []        # historial global
chat_ids = {}        # user_id -> chat_id de Telegram
ultimo_id = 0        # contador de mensajes
usuarios_conectados = set()  # usuarios online ahora

# ============================================
# PÁGINA PRINCIPAL (MONITOREO)
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
            .card h3 {{ margin: 0 0 10px 0; color: #333; }}
            .number {{ font-size: 2.5em; font-weight: bold; color: #667eea; }}
            .online {{ display: inline-block; width: 10px; height: 10px; background: #4caf50; border-radius: 50%; margin-right: 5px; }}
            pre {{ background: #f0f0f0; padding: 10px; border-radius: 5px; overflow: auto; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🤖 Bot Sincronizado - Monitor en Tiempo Real</h1>
                <p>Bot: @{BOT_USERNAME} | Web: <a href="{WEB_URL}" style="color: white;">{WEB_URL}</a></p>
            </div>
            
            <div class="stats">
                <div class="card">
                    <h3>👥 Usuarios Registrados</h3>
                    <div class="number">{len(usuarios)}</div>
                    <p>Total de usuarios que han hecho login</p>
                </div>
                <div class="card">
                    <h3>🟢 Conectados Ahora</h3>
                    <div class="number">{len(usuarios_conectados)}</div>
                    <p>Usuarios activos en este momento</p>
                </div>
                <div class="card">
                    <h3>💬 Mensajes Totales</h3>
                    <div class="number">{len(mensajes)}</div>
                    <p>Mensajes sincronizados</p>
                </div>
            </div>
            
            <div class="card">
                <h3>📱 Usuarios Conectados</h3>
                <table style="width: 100%; border-collapse: collapse;">
                    <tr style="background: #f0f0f0;">
                        <th style="padding: 10px; text-align: left;">ID</th>
                        <th style="padding: 10px; text-align: left;">Nombre</th>
                        <th style="padding: 10px; text-align: left;">Username</th>
                        <th style="padding: 10px; text-align: left;">Última Conexión</th>
                        <th style="padding: 10px; text-align: left;">Estado</th>
                    </tr>
                    {''.join([f'''
                    <tr style="border-bottom: 1px solid #ddd;">
                        <td style="padding: 10px;">{uid}</td>
                        <td style="padding: 10px;">{u.get('first_name', '')} {u.get('last_name', '')}</td>
                        <td style="padding: 10px;">@{u.get('username', 'N/A')}</td>
                        <td style="padding: 10px;">{datetime.fromtimestamp(u.get('ultima', 0)).strftime('%H:%M:%S')}</td>
                        <td style="padding: 10px;"><span class="online"></span> Online</td>
                    </tr>
                    ''' for uid, u in usuarios.items() if uid in usuarios_conectados])}
                </table>
            </div>
            
            <div class="card" style="margin-top: 20px;">
                <h3>📝 Últimos Mensajes</h3>
                <div style="max-height: 300px; overflow: auto;">
                    {''.join([f'''
                    <div style="padding: 10px; border-bottom: 1px solid #eee;">
                        <strong>[{datetime.fromtimestamp(m['fecha']).strftime('%H:%M:%S')}]</strong>
                        <span style="color: {'#667eea' if m['origen']=='web' else '#4caf50' if m['origen']=='telegram' else '#ff9800'};">{m['origen'].upper()}</span>
                        <strong>{m.get('nombre', 'Usuario')}:</strong> {m['texto'][:50]}{'...' if len(m['texto'])>50 else ''}
                    </div>
                    ''' for m in mensajes[-20:][::-1]])}
                </div>
            </div>
            
            <div class="card" style="margin-top: 20px;">
                <h3>🔧 Endpoints API</h3>
                <pre>
POST /auth/telegram  - Login con Telegram (verificación real)
POST /api/enviar     - Enviar mensaje desde web
GET  /api/recibir/&lt;user_id&gt; - Recibir mensajes nuevos
GET  /api/usuarios   - Ver usuarios conectados
POST /webhook        - Webhook de Telegram (recibir mensajes)
GET  /setup_webhook  - Configurar webhook (ejecutar una vez)
                </pre>
            </div>
        </div>
    </body>
    </html>
    """

# ============================================
# FUNCIÓN DE VERIFICACIÓN DE TELEGRAM (SEGURIDAD)
# ============================================
def verificar_telegram_hash(data):
    """Verifica que los datos realmente vienen de Telegram"""
    if not data.get("hash"):
        print("❌ No hay hash en los datos")
        return False
    
    # Crear string de verificación
    check_list = []
    for key in sorted(data.keys()):
        if key != "hash":
            check_list.append(f"{key}={data[key]}")
    
    check_string = "\n".join(check_list)
    
    # Calcular hash esperado
    secret_key = hashlib.sha256(BOT_TOKEN.encode()).digest()
    calculated_hash = hmac.new(
        secret_key,
        check_string.encode(),
        hashlib.sha256
    ).hexdigest()
    
    es_valido = calculated_hash == data["hash"]
    if not es_valido:
        print(f"❌ Hash inválido: esperado={calculated_hash[:10]}..., recibido={data['hash'][:10]}...")
    
    return es_valido

# ============================================
# LOGIN REAL CON TELEGRAM
# ============================================
@app.route('/auth/telegram', methods=['POST', 'OPTIONS'])
def auth_telegram():
    """Endpoint de login - verifica y registra usuario"""
    if request.method == 'OPTIONS':
        return '', 200
    
    global ultimo_id
    
    try:
        data = request.json
        print(f"📥 Intento de login: ID={data.get('id')}, Nombre={data.get('first_name')}")
        
        # Verificar que los datos son de Telegram
        if not verificar_telegram_hash(data):
            return jsonify({"error": "Firma de seguridad inválida"}), 401
        
        user_id = str(data["id"])
        
        # Generar token de sesión único
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
            "auth_date": data.get("auth_date", ""),
            "session": session_token,
            "ultima": time.time(),
            "conectado": True
        }
        
        # Añadir a conectados
        usuarios_conectados.add(user_id)
        
        print(f"✅ LOGIN EXITOSO: {data.get('first_name')} (ID: {user_id})")
        
        # Mensaje de bienvenida en Telegram si tiene chat_id
        if user_id in chat_ids:
            try:
                bot.send_message(
                    chat_ids[user_id],
                    f"🔐 ¡Has iniciado sesión en la web!\n\nAhora web y Telegram están sincronizados.",
                    parse_mode="HTML"
                )
            except:
                pass
        
        return jsonify({
            "success": True,
            "user": usuarios[user_id],
            "session": session_token
        })
        
    except Exception as e:
        print(f"❌ Error en login: {e}")
        return jsonify({"error": str(e)}), 500

# ============================================
# WEBHOOK DE TELEGRAM (RECIBIR MENSAJES REALES)
# ============================================
@app.route('/webhook', methods=['POST'])
def telegram_webhook():
    """Recibe mensajes de Telegram en tiempo real"""
    try:
        update = telebot.types.Update.de_json(request.stream.read().decode("utf-8"))
        
        if update.message:
            # Procesar en segundo plano para no bloquear
            thread = threading.Thread(target=procesar_mensaje_telegram, args=(update.message,))
            thread.start()
        
        return "OK", 200
    except Exception as e:
        print(f"❌ Error en webhook: {e}")
        return "Error", 500

def procesar_mensaje_telegram(message):
    """Procesa cada mensaje de Telegram"""
    global ultimo_id
    
    try:
        user_id = str(message.from_user.id)
        texto = message.text or "📎 Mensaje sin texto"
        chat_id = message.chat.id
        nombre = message.from_user.first_name
        username = message.from_user.username
        
        print(f"📱 TELEGRAM [{nombre} @{username}]: {texto[:50]}...")
        
        # Guardar chat_id para poder responder después
        chat_ids[user_id] = chat_id
        
        # Si el usuario no está registrado, lo registramos automáticamente
        if user_id not in usuarios:
            usuarios[user_id] = {
                "id": user_id,
                "first_name": nombre,
                "last_name": message.from_user.last_name or "",
                "username": username or "",
                "photo_url": "",
                "session": None,
                "ultima": time.time()
            }
            print(f"📝 Usuario registrado automáticamente desde Telegram: {nombre}")
        
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
        
        # Generar respuesta según el comando
        respuesta = generar_respuesta_bot(texto, user_id, nombre)
        
        if respuesta:
            bot.send_message(chat_id, respuesta, parse_mode="HTML")
            
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

def generar_respuesta_bot(texto, user_id, nombre):
    """Genera respuestas automáticas según comandos"""
    texto_lower = texto.lower().strip()
    
    # Comprobar si el usuario está en la web
    en_web = "✅ Sí" if user_id in usuarios_conectados else "❌ No"
    
    if texto_lower == "/start":
        return (
            f"¡Hola {nombre}! 👋\n\n"
            f"🤖 **BOT SINCRONIZADO**\n\n"
            f"Este bot está conectado en tiempo real con la web.\n"
            f"Los mensajes que escribas aquí aparecerán en la web y viceversa.\n\n"
            f"🌐 Web: {WEB_URL}\n"
            f"📱 Estado: {en_web}\n\n"
            f"Usa /ayuda para ver todos los comandos."
        )
    
    elif texto_lower == "/ayuda":
        return (
            "📋 **COMANDOS DISPONIBLES**\n\n"
            "/start - Mensaje de bienvenida\n"
            "/ayuda - Ver esta ayuda\n"
            "/info - Información detallada\n"
            "/hora - Hora actual\n"
            "/perfil - Tu perfil de Telegram\n"
            "/web - Abrir la web sincronizada\n"
            "/estado - Estado de la sincronización"
        )
    
    elif texto_lower == "/info":
        return (
            "🤖 **INFORMACIÓN DEL BOT**\n\n"
            f"• **Usuario:** {nombre}\n"
            f"• **ID:** {user_id}\n"
            f"• **En web:** {en_web}\n"
            f"• **Usuarios totales:** {len(usuarios)}\n"
            f"• **Conectados ahora:** {len(usuarios_conectados)}\n"
            f"• **Mensajes totales:** {len(mensajes)}\n"
            f"• **Versión:** 2.0 REAL\n"
            f"• **Sincronización:** ✅ Tiempo real"
        )
    
    elif texto_lower == "/hora":
        ahora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        return f"📅 **{ahora}**"
    
    elif texto_lower == "/perfil":
        return (
            f"👤 **PERFIL DE TELEGRAM**\n\n"
            f"**ID:** {user_id}\n"
            f"**Nombre:** {nombre}\n"
            f"**Username:** @{message.from_user.username or 'No tiene'}\n"
            f"**En web:** {en_web}\n"
            f"**Última actividad:** {datetime.now().strftime('%H:%M:%S')}"
        )
    
    elif texto_lower == "/web":
        return f"🌐 **WEB SINCRONIZADA**\n\n{WEB_URL}\n\nAbre este enlace en tu navegador para chatear desde la web."
    
    elif texto_lower == "/estado":
        return (
            f"📊 **ESTADO DE SINCRONIZACIÓN**\n\n"
            f"• **Conexión web:** {en_web}\n"
            f"• **Mensajes pendientes:** 0\n"
            f"• **Latencia:** &lt;1s\n"
            f"• **Sincronización:** ✅ Activa\n\n"
            f"Todo funciona correctamente."
        )
    
    else:
        # Si no es comando, mostrar que se recibió
        return (
            f"✅ **Mensaje recibido**\n\n"
            f"_{texto}_\n\n"
            f"Este mensaje también aparecerá en la web si estás conectado.\n"
            f"Usa /ayuda para ver comandos."
        )

# ============================================
# API PARA LA WEB (ENVIAR MENSAJES)
# ============================================
@app.route('/api/enviar', methods=['POST', 'OPTIONS'])
def enviar_mensaje():
    """Recibe mensajes desde la web y los envía a Telegram"""
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
        
        # Actualizar última conexión
        if user_id in usuarios:
            usuarios[user_id]["ultima"] = time.time()
            usuarios_conectados.add(user_id)
        
        nombre = usuarios.get(user_id, {}).get("first_name", "Usuario")
        
        print(f"🌐 WEB [{nombre}]: {texto[:50]}...")
        
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
                chat_id = chat_ids[user_id]
                bot.send_message(
                    chat_id,
                    f"📱 **Mensaje desde la web:**\n\n{texto}",
                    parse_mode="HTML"
                )
            except Exception as e:
                print(f"❌ Error enviando a Telegram: {e}")
        
        return jsonify({"success": True, "id": ultimo_id})
        
    except Exception as e:
        print(f"❌ Error en /api/enviar: {e}")
        return jsonify({"error": str(e)}), 500

# ============================================
# API PARA LA WEB (RECIBIR MENSAJES)
# ============================================
@app.route('/api/recibir/<user_id>', methods=['GET', 'OPTIONS'])
def recibir_mensajes(user_id):
    """La web consulta mensajes nuevos"""
    if request.method == 'OPTIONS':
        return '', 200
    
    try:
        session = request.args.get("session")
        ultimo_id_recibido = int(request.args.get("ultimo_id", 0))
        
        # Verificar sesión
        if not verificar_sesion(user_id, session):
            return jsonify({"error": "Sesión inválida"}), 401
        
        # Actualizar último pulso
        if user_id in usuarios:
            usuarios[user_id]["ultima"] = time.time()
            usuarios_conectados.add(user_id)
        
        # Filtrar mensajes nuevos para este usuario
        mensajes_nuevos = [
            m for m in mensajes 
            if m["id"] > ultimo_id_recibido and (
                m["user_id"] == user_id or  # mensajes propios
                m["origen"] == "bot" or      # mensajes del bot
                (m["origen"] == "telegram" and m["user_id"] == user_id)  # sus propios mensajes de Telegram
            )
        ]
        
        # Obtener último ID global
        ultimo_id_global = max([m["id"] for m in mensajes]) if mensajes else 0
        
        return jsonify({
            "mensajes": mensajes_nuevos,
            "ultimo_id": ultimo_id_global,
            "timestamp": time.time(),
            "conectados": len(usuarios_conectados)
        })
        
    except Exception as e:
        print(f"❌ Error en /api/recibir: {e}")
        return jsonify({"error": str(e)}), 500

# ============================================
# API DE ESTADÍSTICAS
# ============================================
@app.route('/api/usuarios', methods=['GET'])
def ver_usuarios():
    """Devuelve estadísticas de usuarios"""
    return jsonify({
        "total": len(usuarios),
        "conectados_ahora": len(usuarios_conectados),
        "usuarios": [
            {
                "id": uid,
                "nombre": u.get("first_name"),
                "username": u.get("username"),
                "conectado": uid in usuarios_conectados,
                "ultima": u.get("ultima", 0)
            }
            for uid, u in usuarios.items()
        ]
    })

@app.route('/api/stats', methods=['GET'])
def stats():
    """Estadísticas rápidas"""
    return jsonify({
        "usuarios": len(usuarios),
        "conectados": len(usuarios_conectados),
        "mensajes": len(mensajes),
        "uptime": time.time()
    })

def verificar_sesion(user_id, session):
    """Verifica que la sesión es válida"""
    if not user_id or not session:
        return False
    user = usuarios.get(user_id)
    if not user:
        return False
    return user.get("session") == session

# ============================================
# LIMPIEZA DE USUARIOS INACTIVOS
# ============================================
def limpiar_inactivos():
    """Elimina usuarios que no han tenido actividad"""
    while True:
        time.sleep(60)  # cada minuto
        ahora = time.time()
        inactivos = []
        for user_id in usuarios_conectados:
            ultima = usuarios.get(user_id, {}).get("ultima", 0)
            if ahora - ultima > 120:  # 2 minutos sin actividad
                inactivos.append(user_id)
        
        for user_id in inactivos:
            usuarios_conectados.discard(user_id)
            print(f"👋 Usuario {user_id} desconectado por inactividad")

# Iniciar limpieza en segundo plano
threading.Thread(target=limpiar_inactivos, daemon=True).start()

# ============================================
# CONFIGURAR WEBHOOK (LLAMAR UNA VEZ)
# ============================================
@app.route('/setup_webhook')
def setup_webhook():
    """Configura el webhook para recibir mensajes de Telegram"""
    try:
        webhook_url = f"https://{request.host}/webhook"
        bot.remove_webhook()
        bot.set_webhook(url=webhook_url)
        return f"""
        <html>
        <body style="font-family: Arial; padding: 40px;">
            <h1 style="color: green;">✅ Webhook configurado</h1>
            <p>URL: {webhook_url}</p>
            <p>Tu bot ya puede recibir mensajes de Telegram.</p>
            <p><a href="/">Volver al monitor</a></p>
        </body>
        </html>
        """
    except Exception as e:
        return f"<h1 style='color: red;'>❌ Error: {e}</h1>"

# ============================================
# INICIAR SERVIDOR
# ============================================
if __name__ == "__main__":
    print("="*60)
    print("🤖 BOT SINCRONIZADO - MODO ESPEJO")
    print("="*60)
    print(f"Token: {BOT_TOKEN[:10]}...")
    print(f"Username: @{BOT_USERNAME}")
    print(f"Web: {WEB_URL}")
    print("="*60)
    print("📋 Endpoints disponibles:")
    print("  POST /auth/telegram  - Login real con Telegram")
    print("  POST /api/enviar     - Enviar mensaje desde web")
    print("  GET  /api/recibir/   - Recibir mensajes (polling)")
    print("  GET  /setup_webhook  - Configurar webhook (1 vez)")
    print("="*60)
    print("🚀 Servidor iniciado - Esperando conexiones...")
    print("="*60)
    
    app.run(host="0.0.0.0", port=5000, debug=True)