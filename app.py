import os
import time
import threading
import json
from datetime import datetime
from flask import Flask, request, jsonify, session
from flask_cors import CORS
import telebot
import hashlib
import hmac

# ============================================
# CONFIGURACIÓN
# ============================================
app = Flask(__name__)
app.secret_key = os.urandom(24)
CORS(app, origins=["https://carlosmar14.github.io"])

# Token desde variables de entorno
BOT_TOKEN = os.environ.get('TOKEN')
if not BOT_TOKEN:
    BOT_TOKEN = "8756602645:AAHZjNUJ1KKy-1L9i2CAJRMy-mIE5ambV_Q"

BOT_USERNAME = "shopcmar_bot"
WEB_URL = "https://carlosmar14.github.io/mibot/"

bot = telebot.TeleBot(BOT_TOKEN)

# ============================================
# BASE DE DATOS (usuarios.json)
# ============================================
try:
    with open('usuarios.json', 'r') as f:
        usuarios = json.load(f)
except:
    usuarios = {}  # user_id -> {nombre, saldo, referido_por, referidos[], historial[], mensajes[]}

try:
    with open('mensajes.json', 'r') as f:
        mensajes_globales = json.load(f)
except:
    mensajes_globales = []  # historial global

ultimo_id = len(mensajes_globales)
usuarios_conectados = set()

def guardar_datos():
    with open('usuarios.json', 'w') as f:
        json.dump(usuarios, f)
    with open('mensajes.json', 'w') as f:
        json.dump(mensajes_globales, f)

# ============================================
# RUTA PRINCIPAL (MONITOR GLOBAL - SOLO PARA TI)
# ============================================
@app.route('/')
def home():
    return f"""
    <html>
    <head>
        <title>Bot de Referidos - Admin</title>
        <style>
            body {{ font-family: Arial; padding: 40px; background: #f5f5f5; }}
            .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; }}
            h1 {{ color: #333; }}
            .stats {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin: 20px 0; }}
            .card {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 10px; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
            th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }}
            th {{ background: #667eea; color: white; }}
            tr:hover {{ background: #f5f5f5; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🤖 Panel de Administración</h1>
            <div class="stats">
                <div class="card">
                    <h3>Usuarios Totales</h3>
                    <h2>{len(usuarios)}</h2>
                </div>
                <div class="card">
                    <h3>Conectados Ahora</h3>
                    <h2>{len(usuarios_conectados)}</h2>
                </div>
                <div class="card">
                    <h3>Mensajes Totales</h3>
                    <h2>{len(mensajes_globales)}</h2>
                </div>
            </div>
            
            <h2>📊 Usuarios Registrados</h2>
            <table>
                <tr>
                    <th>ID</th>
                    <th>Nombre</th>
                    <th>Username</th>
                    <th>Saldo</th>
                    <th>Referidos</th>
                    <th>Referido por</th>
                    <th>Acciones</th>
                </tr>
                {''.join([f'''
                <tr>
                    <td>{uid[:8]}...</td>
                    <td>{u.get('nombre', '')}</td>
                    <td>@{u.get('username', '')}</td>
                    <td>${u.get('saldo', 0)}</td>
                    <td>{len(u.get('referidos', []))}</td>
                    <td>{u.get('referido_por', 'Ninguno')[:8] if u.get('referido_por') else 'Ninguno'}</td>
                    <td>
                        <a href="/admin/usuario/{uid}" style="color: #667eea;">Ver detalles</a>
                    </td>
                </tr>
                ''' for uid, u in list(usuarios.items())[:20]])}
            </table>
            
            <p><a href="/setup_webhook">Configurar Webhook</a></p>
        </div>
    </body>
    </html>
    """

# ============================================
# RUTA PARA VER DETALLE DE USUARIO (SOLO ADMIN)
# ============================================
@app.route('/admin/usuario/<user_id>')
def admin_usuario(user_id):
    user = usuarios.get(user_id, {})
    if not user:
        return "Usuario no encontrado"
    
    return f"""
    <html>
    <head>
        <title>Detalle de Usuario</title>
        <style>
            body {{ font-family: Arial; padding: 40px; background: #f5f5f5; }}
            .container {{ max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; }}
            h1 {{ color: #333; }}
            .info {{ background: #f8f9fa; padding: 20px; border-radius: 10px; margin: 20px 0; }}
            table {{ width: 100%; border-collapse: collapse; }}
            th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>👤 Detalle de Usuario</h1>
            <div class="info">
                <p><strong>ID:</strong> {user_id}</p>
                <p><strong>Nombre:</strong> {user.get('nombre', '')}</p>
                <p><strong>Username:</strong> @{user.get('username', '')}</p>
                <p><strong>Saldo:</strong> ${user.get('saldo', 0)}</p>
                <p><strong>Referidos:</strong> {len(user.get('referidos', []))}</p>
                <p><strong>Referido por:</strong> {user.get('referido_por', 'Ninguno')}</p>
                <p><strong>Fecha registro:</strong> {datetime.fromtimestamp(user.get('fecha_registro', 0)).strftime('%d/%m/%Y %H:%M')}</p>
            </div>
            
            <h2>📋 Historial de Transacciones</h2>
            <table>
                <tr>
                    <th>Fecha</th>
                    <th>Tipo</th>
                    <th>Monto</th>
                </tr>
                {''.join([f'''
                <tr>
                    <td>{datetime.fromtimestamp(h['fecha']).strftime('%d/%m/%Y %H:%M')}</td>
                    <td>{h['tipo']}</td>
                    <td>${h['monto']}</td>
                </tr>
                ''' for h in user.get('historial', [])[-10:]])}
            </table>
            
            <p><a href="/">← Volver al panel</a></p>
        </div>
    </body>
    </html>
    """

# ============================================
# COMANDOS PERSONALIZADOS DEL BOT
# ============================================
@bot.message_handler(commands=['start', 'ayuda', 'balance', 'misreferidos', 'depositar', 'retirar', 'perfil', 'web', 'historial'])
def handle_commands(message):
    user_id = str(message.from_user.id)
    chat_id = message.chat.id
    texto = message.text.split()
    comando = texto[0].lower()
    nombre = message.from_user.first_name
    username = message.from_user.username
    
    print(f"📱 Comando: {comando} de {nombre} (ID: {user_id})")
    
    # ========================================
    # REGISTRAR USUARIO SI NO EXISTE
    # ========================================
    if user_id not in usuarios:
        usuarios[user_id] = {
            'user_id': user_id,
            'nombre': nombre,
            'username': username,
            'saldo': 0,
            'referido_por': None,
            'referidos': [],
            'historial': [],
            'mensajes': [],
            'fecha_registro': time.time(),
            'ultima_conexion': time.time()
        }
        guardar_datos()
        
        # Mensaje de bienvenida personalizado
        bot.reply_to(message, f"👋 ¡Bienvenido {nombre}! Has sido registrado en el sistema.")
    
    # Actualizar última conexión
    usuarios[user_id]['ultima_conexion'] = time.time()
    usuarios[user_id]['nombre'] = nombre
    usuarios[user_id]['username'] = username
    usuarios_conectados.add(user_id)
    
    # ========================================
    # COMANDO /START - PERSONALIZADO
    # ========================================
    if comando == '/start':
        # Verificar si tiene referido
        if len(texto) > 1 and 'ref_' in texto[1]:
            ref_id = texto[1].replace('ref_', '')
            if ref_id != user_id and ref_id in usuarios and not usuarios[user_id]['referido_por']:
                usuarios[user_id]['referido_por'] = ref_id
                usuarios[ref_id]['referidos'].append(user_id)
                guardar_datos()
                
                # Mensaje personalizado para el nuevo usuario
                bot.reply_to(message, f"✅ ¡Bienvenido {nombre}! Has sido registrado como referido.")
                
                # Notificar al referidor
                try:
                    bot.send_message(
                        ref_id,
                        f"🎉 ¡{nombre} se ha unido con tu link de referido!\n"
                        f"💰 Ganarás 10% de sus depósitos."
                    )
                except:
                    pass
        
        # Mensaje de bienvenida personalizado con su información
        saldo = usuarios[user_id]['saldo']
        referidos = len(usuarios[user_id]['referidos'])
        
        respuesta = (
            f"👋 **¡Hola {nombre}!**\n\n"
            f"**💰 Tu saldo actual:** ${saldo}\n"
            f"**👥 Tus referidos:** {referidos}\n\n"
            f"📋 **Comandos disponibles:**\n"
            f"/balance - Ver tu saldo\n"
            f"/misreferidos - Ver tus referidos\n"
            f"/depositar [monto] - Registrar depósito\n"
            f"/retirar [monto] - Solicitar retiro\n"
            f"/perfil - Ver tu perfil\n"
            f"/historial - Ver tus movimientos\n"
            f"/ayuda - Ayuda general\n\n"
            f"**🔗 Tu link de referido:**\n"
            f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}\n\n"
            f"_Ganas 10% de cada depósito de tus referidos_"
        )
        bot.reply_to(message, respuesta, parse_mode='Markdown')
    
    # ========================================
    # COMANDO /AYUDA - PERSONALIZADO
    # ========================================
    elif comando == '/ayuda':
        respuesta = (
            f"📋 **AYUDA PERSONALIZADA**\n\n"
            f"**Tus datos:**\n"
            f"• Saldo: ${usuarios[user_id]['saldo']}\n"
            f"• Referidos: {len(usuarios[user_id]['referidos'])}\n\n"
            f"**Comandos:**\n"
            f"/balance - Ver saldo\n"
            f"/misreferidos - Ver tus referidos\n"
            f"/depositar [monto] - Depositar\n"
            f"/retirar [monto] - Retirar\n"
            f"/perfil - Ver perfil\n"
            f"/historial - Ver movimientos\n"
            f"/web - Abrir web\n\n"
            f"**Sistema de referidos:**\n"
            f"• Ganas 10% de los depósitos de tus referidos\n"
            f"• Tu link: https://t.me/{BOT_USERNAME}?start=ref_{user_id}"
        )
        bot.reply_to(message, respuesta, parse_mode='Markdown')
    
    # ========================================
    # COMANDO /BALANCE - PERSONALIZADO
    # ========================================
    elif comando == '/balance':
        saldo = usuarios[user_id]['saldo']
        respuesta = (
            f"💰 **TU SALDO PERSONAL**\n\n"
            f"**Usuario:** {nombre}\n"
            f"**Saldo disponible:** ${saldo}\n"
            f"**Referidos activos:** {len(usuarios[user_id]['referidos'])}\n\n"
            f"Para depositar usa: /depositar [monto]"
        )
        bot.reply_to(message, respuesta, parse_mode='Markdown')
    
    # ========================================
    # COMANDO /MISREFERIDOS - PERSONALIZADO
    # ========================================
    elif comando == '/misreferidos':
        referidos = usuarios[user_id].get('referidos', [])
        
        if not referidos:
            respuesta = (
                f"📭 **No tienes referidos aún**\n\n"
                f"Comparte tu link personal:\n"
                f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}\n\n"
                f"Ganarás 10% de cada depósito que hagan."
            )
        else:
            texto_ref = ""
            ganancias_totales = 0
            
            for ref_id in referidos:
                ref = usuarios.get(ref_id, {})
                nombre_ref = ref.get('nombre', 'Desconocido')
                saldo_ref = ref.get('saldo', 0)
                ganancias = saldo_ref * 0.1
                ganancias_totales += ganancias
                texto_ref += f"• {nombre_ref} - Depósitos: ${saldo_ref} - Tus ganancias: ${ganancias:.2f}\n"
            
            respuesta = (
                f"👥 **TUS REFERIDOS ({len(referidos)})**\n\n"
                f"{texto_ref}\n"
                f"💰 **Total ganado por referidos:** ${ganancias_totales:.2f}\n\n"
                f"**Tu link personal:**\n"
                f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}"
            )
        
        bot.reply_to(message, respuesta, parse_mode='Markdown')
    
    # ========================================
    # COMANDO /PERFIL - PERSONALIZADO
    # ========================================
    elif comando == '/perfil':
        user = usuarios[user_id]
        fecha_reg = datetime.fromtimestamp(user.get('fecha_registro', 0)).strftime('%d/%m/%Y')
        
        respuesta = (
            f"👤 **PERFIL PERSONAL**\n\n"
            f"**ID:** {user_id}\n"
            f"**Nombre:** {user.get('nombre')}\n"
            f"**Username:** @{user.get('username', 'No tiene')}\n"
            f"**Saldo:** ${user.get('saldo', 0)}\n"
            f"**Referidos:** {len(user.get('referidos', []))}\n"
            f"**Referido por:** {user.get('referido_por', 'Ninguno')}\n"
            f"**Registro:** {fecha_reg}\n\n"
            f"**🔗 Link personal:**\n"
            f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}"
        )
        bot.reply_to(message, respuesta, parse_mode='Markdown')
    
    # ========================================
    # COMANDO /HISTORIAL - PERSONALIZADO
    # ========================================
    elif comando == '/historial':
        historial = usuarios[user_id].get('historial', [])
        
        if not historial:
            respuesta = "📭 No tienes movimientos registrados."
        else:
            texto_hist = ""
            for h in historial[-10:]:  # últimos 10 movimientos
                fecha = datetime.fromtimestamp(h['fecha']).strftime('%d/%m/%Y %H:%M')
                texto_hist += f"• {fecha} - {h['tipo']}: ${h['monto']}\n"
            
            respuesta = (
                f"📋 **TUS ÚLTIMOS MOVIMIENTOS**\n\n"
                f"{texto_hist}\n"
                f"**Saldo actual:** ${usuarios[user_id]['saldo']}"
            )
        
        bot.reply_to(message, respuesta, parse_mode='Markdown')
    
    # ========================================
    # COMANDO /DEPOSITAR - PERSONALIZADO
    # ========================================
    elif comando == '/depositar':
        if len(texto) < 2:
            bot.reply_to(message, "❌ Usa: /depositar [monto]")
            return
        
        try:
            monto = float(texto[1])
            if monto <= 0:
                bot.reply_to(message, "❌ El monto debe ser positivo")
                return
            
            # Actualizar saldo del usuario
            usuarios[user_id]['saldo'] += monto
            
            # Guardar en historial
            usuarios[user_id]['historial'].append({
                'tipo': 'deposito',
                'monto': monto,
                'fecha': time.time()
            })
            
            # Pagar comisión al referidor (10%)
            referido_por = usuarios[user_id].get('referido_por')
            if referido_por and referido_por in usuarios:
                comision = monto * 0.1
                usuarios[referido_por]['saldo'] += comision
                
                # Guardar en historial del referidor
                usuarios[referido_por]['historial'].append({
                    'tipo': 'comision',
                    'monto': comision,
                    'fecha': time.time(),
                    'de': user_id
                })
                
                # Notificar al referidor
                try:
                    bot.send_message(
                        referido_por,
                        f"🎉 **¡Nueva comisión!**\n\n"
                        f"Tu referido {nombre} depositó ${monto}\n"
                        f"💰 Has ganado ${comision:.2f} (10%)\n"
                        f"**Tu nuevo saldo:** ${usuarios[referido_por]['saldo']}"
                    )
                except:
                    pass
                
                respuesta = (
                    f"✅ **Depósito exitoso**\n\n"
                    f"**Monto:** ${monto}\n"
                    f"**Tu nuevo saldo:** ${usuarios[user_id]['saldo']}\n"
                    f"💰 **Comisión pagada a tu referidor:** ${comision:.2f}"
                )
            else:
                respuesta = (
                    f"✅ **Depósito exitoso**\n\n"
                    f"**Monto:** ${monto}\n"
                    f"**Tu nuevo saldo:** ${usuarios[user_id]['saldo']}"
                )
            
            guardar_datos()
            bot.reply_to(message, respuesta, parse_mode='Markdown')
            
        except ValueError:
            bot.reply_to(message, "❌ Monto inválido. Usa: /depositar [monto]")
    
    # ========================================
    # COMANDO /RETIRAR - PERSONALIZADO
    # ========================================
    elif comando == '/retirar':
        if len(texto) < 2:
            bot.reply_to(message, "❌ Usa: /retirar [monto]")
            return
        
        try:
            monto = float(texto[1])
            saldo_actual = usuarios[user_id]['saldo']
            
            if monto <= 0:
                bot.reply_to(message, "❌ El monto debe ser positivo")
                return
            
            if monto > saldo_actual:
                bot.reply_to(message, f"❌ Saldo insuficiente. Tu saldo es ${saldo_actual}")
                return
            
            usuarios[user_id]['saldo'] -= monto
            usuarios[user_id]['historial'].append({
                'tipo': 'retiro',
                'monto': monto,
                'fecha': time.time()
            })
            
            guardar_datos()
            
            # Notificar al admin (tú)
            admin_id = "TU_ID_DE_TELEGRAM"  # ← Pon tu ID de Telegram
            try:
                bot.send_message(
                    admin_id,
                    f"💰 **SOLICITUD DE RETIRO**\n\n"
                    f"**Usuario:** {nombre}\n"
                    f"**ID:** {user_id}\n"
                    f"**Monto:** ${monto}\n"
                    f"**Saldo restante:** ${usuarios[user_id]['saldo']}"
                )
            except:
                pass
            
            bot.reply_to(
                message, 
                f"✅ **Solicitud de retiro registrada**\n\n"
                f"**Monto solicitado:** ${monto}\n"
                f"**Tu nuevo saldo:** ${usuarios[user_id]['saldo']}\n\n"
                f"Te contactaremos pronto para procesar el retiro.",
                parse_mode='Markdown'
            )
            
        except ValueError:
            bot.reply_to(message, "❌ Monto inválido. Usa: /retirar [monto]")
    
    # ========================================
    # COMANDO /WEB
    # ========================================
    elif comando == '/web':
        bot.reply_to(message, f"🌐 **WEB SINCRONIZADA**\n\n{WEB_URL}\n\nInicia sesión con Telegram para ver tus datos.")

# ============================================
# MENSAJES NORMALES (RESPUESTA PERSONALIZADA)
# ============================================
@bot.message_handler(func=lambda m: True)
def handle_messages(message):
    user_id = str(message.from_user.id)
    texto = message.text
    
    # Registrar usuario si no existe
    if user_id not in usuarios:
        usuarios[user_id] = {
            'user_id': user_id,
            'nombre': message.from_user.first_name,
            'username': message.from_user.username,
            'saldo': 0,
            'referido_por': None,
            'referidos': [],
            'historial': [],
            'mensajes': [],
            'fecha_registro': time.time()
        }
        guardar_datos()
    
    # Guardar mensaje
    usuarios[user_id]['mensajes'].append({
        'texto': texto,
        'fecha': time.time()
    })
    
    # Respuesta personalizada según el usuario
    saldo = usuarios[user_id]['saldo']
    
    if 'hola' in texto.lower():
        respuesta = f"¡Hola {message.from_user.first_name}! 👋\n\nTu saldo actual es ${saldo}\nUsa /ayuda para ver comandos."
    elif 'saldo' in texto.lower():
        respuesta = f"💰 Tu saldo actual es: ${saldo}"
    elif 'gracias' in texto.lower():
        respuesta = f"¡De nada {message.from_user.first_name}! 😊"
    else:
        respuesta = f"Hola {message.from_user.first_name}, no entendí tu mensaje.\nUsa /ayuda para ver los comandos disponibles."
    
    bot.reply_to(message, respuesta)

# ============================================
# WEBHOOK
# ============================================
@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        update = telebot.types.Update.de_json(request.stream.read().decode('utf-8'))
        bot.process_new_updates([update])
        return 'OK', 200
    except Exception as e:
        print(f"Error: {e}")
        return 'Error', 500

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
# API PARA LA WEB (DATOS PERSONALIZADOS)
# ============================================
@app.route('/api/usuario/<user_id>', methods=['GET'])
def api_usuario(user_id):
    """Devuelve datos PERSONALIZADOS del usuario"""
    session = request.args.get('session')
    
    # Aquí deberías verificar la sesión
    
    user = usuarios.get(user_id, {})
    if not user:
        return jsonify({'error': 'Usuario no encontrado'}), 404
    
    # Calcular ganancias por referidos
    ganancias = 0
    for ref_id in user.get('referidos', []):
        ref = usuarios.get(ref_id, {})
        ganancias += ref.get('saldo', 0) * 0.1
    
    return jsonify({
        'user_id': user_id,
        'nombre': user.get('nombre'),
        'username': user.get('username'),
        'saldo': user.get('saldo', 0),
        'referidos': len(user.get('referidos', [])),
        'ganancias_referidos': ganancias,
        'historial': user.get('historial', [])[-10:],  # últimos 10
        'fecha_registro': user.get('fecha_registro', 0),
        'link_referido': f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}"
    })

@app.route('/api/usuarios', methods=['GET'])
def api_usuarios():
    """Solo para admin - datos globales"""
    return jsonify({
        'total': len(usuarios),
        'conectados': len(usuarios_conectados),
        'usuarios': [
            {
                'id': uid,
                'nombre': u.get('nombre'),
                'saldo': u.get('saldo', 0),
                'referidos': len(u.get('referidos', []))
            }
            for uid, u in usuarios.items()
        ]
    })

# ============================================
# INICIAR
# ============================================
if __name__ == "__main__":
    print("="*60)
    print("🤖 BOT DE REFERIDOS - CHAT PERSONALIZADO")
    print("="*60)
    print(f"Bot: @{BOT_USERNAME}")
    print(f"Usuarios registrados: {len(usuarios)}")
    print(f"Webhook: https://mibot-espejo.onrender.com/setup_webhook")
    print(f"Panel admin: https://mibot-espejo.onrender.com/")
    print("="*60)
    app.run(host="0.0.0.0", port=5000)
