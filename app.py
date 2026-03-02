import os
import time
import threading
import json
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
# BASE DE DATOS (usuarios.json)
# ============================================
try:
    with open('usuarios.json', 'r') as f:
        usuarios = json.load(f)
except:
    usuarios = {}  # user_id -> {nombre, saldo, referido_por, referidos[], historial[]}

try:
    with open('mensajes.json', 'r') as f:
        mensajes = json.load(f)
except:
    mensajes = []  # historial de mensajes

ultimo_id = len(mensajes)
usuarios_conectados = set()

def guardar_datos():
    with open('usuarios.json', 'w') as f:
        json.dump(usuarios, f)
    with open('mensajes.json', 'w') as f:
        json.dump(mensajes, f)

# ============================================
# RUTA PRINCIPAL
# ============================================
@app.route('/')
def home():
    return f"""
    <html>
    <head>
        <title>Bot de Referidos</title>
        <style>
            body {{ font-family: Arial; padding: 40px; background: #f5f5f5; }}
            .container {{ max-width: 1000px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; }}
            h1 {{ color: #333; }}
            .stats {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin: 20px 0; }}
            .card {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 10px; }}
            table {{ width: 100%; border-collapse: collapse; }}
            th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🤖 Bot de Referidos</h1>
            <div class="stats">
                <div class="card">
                    <h3>Usuarios</h3>
                    <h2>{len(usuarios)}</h2>
                </div>
                <div class="card">
                    <h3>Conectados</h3>
                    <h2>{len(usuarios_conectados)}</h2>
                </div>
                <div class="card">
                    <h3>Mensajes</h3>
                    <h2>{len(mensajes)}</h2>
                </div>
            </div>
            
            <h2>Usuarios y Saldos</h2>
            <table>
                <tr>
                    <th>ID</th>
                    <th>Nombre</th>
                    <th>Saldo</th>
                    <th>Referidos</th>
                    <th>Referido por</th>
                </tr>
                {''.join([f'''
                <tr>
                    <td>{uid}</td>
                    <td>{u.get('nombre', '')}</td>
                    <td>${u.get('saldo', 0)}</td>
                    <td>{len(u.get('referidos', []))}</td>
                    <td>{u.get('referido_por', 'Ninguno')}</td>
                </tr>
                ''' for uid, u in usuarios.items()])}
            </table>
            
            <p><a href="/setup_webhook">Configurar Webhook</a></p>
        </div>
    </body>
    </html>
    """

# ============================================
# COMANDOS DEL BOT
# ============================================
@bot.message_handler(commands=['start', 'ayuda', 'balance', 'referidos', 'depositar', 'retirar', 'perfil', 'web'])
def handle_commands(message):
    user_id = str(message.from_user.id)
    chat_id = message.chat.id
    texto = message.text.split()
    comando = texto[0].lower()
    nombre = message.from_user.first_name
    
    print(f"📱 Comando: {comando} de {nombre}")
    
    # Registrar usuario si no existe
    if user_id not in usuarios:
        usuarios[user_id] = {
            'nombre': nombre,
            'username': message.from_user.username,
            'saldo': 0,
            'referido_por': None,
            'referidos': [],
            'historial': [],
            'fecha_registro': time.time()
        }
        guardar_datos()
    
    # ========================================
    # COMANDO /START
    # ========================================
    if comando == '/start':
        # Verificar si tiene referido
        if len(texto) > 1 and 'ref_' in texto[1]:
            ref_id = texto[1].replace('ref_', '')
            if ref_id != user_id and ref_id in usuarios and not usuarios[user_id]['referido_por']:
                usuarios[user_id]['referido_por'] = ref_id
                usuarios[ref_id]['referidos'].append(user_id)
                guardar_datos()
                bot.reply_to(message, f"✅ ¡Bienvenido {nombre}! Has sido registrado como referido.")
                # Notificar al referidor
                try:
                    bot.send_message(ref_id, f"🎉 ¡{nombre} se ha unido con tu link de referido!")
                except:
                    pass
        
        respuesta = (
            f"👋 ¡Hola {nombre}!\n\n"
            f"💰 **Sistema de Referidos 10%**\n\n"
            f"Comandos disponibles:\n"
            f"/balance - Ver tu saldo\n"
            f"/referidos - Ver tus referidos\n"
            f"/depositar - Registrar un depósito\n"
            f"/retirar - Solicitar retiro\n"
            f"/perfil - Tu perfil\n"
            f"/ayuda - Ver ayuda\n\n"
            f"**Tu link de referido:**\n"
            f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}"
        )
        bot.reply_to(message, respuesta, parse_mode='Markdown')
    
    # ========================================
    # COMANDO /AYUDA
    # ========================================
    elif comando == '/ayuda':
        respuesta = (
            "📋 **COMANDOS DISPONIBLES**\n\n"
            "/start - Iniciar y ver link de referido\n"
            "/balance - Ver tu saldo actual\n"
            "/referidos - Ver lista de tus referidos\n"
            "/depositar [monto] - Registrar un depósito\n"
            "/retirar [monto] - Solicitar retiro\n"
            "/perfil - Ver tu perfil completo\n"
            "/web - Abrir la web\n\n"
            "**Sistema de referidos:**\n"
            "• Ganas 10% de cada depósito de tus referidos\n"
            "• Los referidos se registran con tu link\n"
            "• Sin límite de referidos"
        )
        bot.reply_to(message, respuesta, parse_mode='Markdown')
    
    # ========================================
    # COMANDO /BALANCE
    # ========================================
    elif comando == '/balance':
        saldo = usuarios[user_id].get('saldo', 0)
        respuesta = f"💰 **Tu saldo actual:** ${saldo}"
        bot.reply_to(message, respuesta, parse_mode='Markdown')
    
    # ========================================
    # COMANDO /REFERIDOS
    # ========================================
    elif comando == '/referidos':
        referidos = usuarios[user_id].get('referidos', [])
        if not referidos:
            respuesta = "📭 No tienes referidos aún.\n\nComparte tu link:\n" + \
                       f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}"
        else:
            texto_ref = ""
            for ref_id in referidos:
                ref = usuarios.get(ref_id, {})
                nombre_ref = ref.get('nombre', 'Desconocido')
                saldo_ref = ref.get('saldo', 0)
                texto_ref += f"• {nombre_ref} - Saldo: ${saldo_ref}\n"
            
            ganancias = sum(usuarios.get(r, {}).get('saldo', 0) * 0.1 for r in referidos)
            respuesta = (
                f"👥 **Tus Referidos ({len(referidos)}):**\n\n"
                f"{texto_ref}\n"
                f"💰 **Ganancias por referidos:** ${ganancias:.2f}\n\n"
                f"**Tu link:**\n"
                f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}"
            )
        bot.reply_to(message, respuesta, parse_mode='Markdown')
    
    # ========================================
    # COMANDO /PERFIL
    # ========================================
    elif comando == '/perfil':
        user = usuarios[user_id]
        respuesta = (
            f"👤 **PERFIL**\n\n"
            f"**Nombre:** {user.get('nombre')}\n"
            f"**ID:** {user_id}\n"
            f"**Saldo:** ${user.get('saldo', 0)}\n"
            f"**Referidos:** {len(user.get('referidos', []))}\n"
            f"**Referido por:** {user.get('referido_por', 'Ninguno')}\n"
            f"**Link:** https://t.me/{BOT_USERNAME}?start=ref_{user_id}"
        )
        bot.reply_to(message, respuesta, parse_mode='Markdown')
    
    # ========================================
    # COMANDO /DEPOSITAR
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
            
            # Actualizar saldo
            usuarios[user_id]['saldo'] = usuarios[user_id].get('saldo', 0) + monto
            
            # Pagar comisión al referidor (10%)
            referido_por = usuarios[user_id].get('referido_por')
            if referido_por and referido_por in usuarios:
                comision = monto * 0.1
                usuarios[referido_por]['saldo'] = usuarios[referido_por].get('saldo', 0) + comision
                
                # Notificar al referidor
                try:
                    bot.send_message(
                        referido_por,
                        f"🎉 ¡Tu referido {usuarios[user_id]['nombre']} depositó ${monto}!\n"
                        f"💰 Has ganado ${comision:.2f} (10%)"
                    )
                except:
                    pass
                
                respuesta = f"✅ Depósito de ${monto} registrado.\n💰 Se pagó ${comision:.2f} a tu referidor."
            else:
                respuesta = f"✅ Depósito de ${monto} registrado."
            
            # Guardar historial
            usuarios[user_id]['historial'].append({
                'tipo': 'deposito',
                'monto': monto,
                'fecha': time.time()
            })
            
            guardar_datos()
            bot.reply_to(message, respuesta)
            
        except ValueError:
            bot.reply_to(message, "❌ Monto inválido. Usa: /depositar [monto]")
    
    # ========================================
    # COMANDO /RETIRAR
    # ========================================
    elif comando == '/retirar':
        if len(texto) < 2:
            bot.reply_to(message, "❌ Usa: /retirar [monto]")
            return
        
        try:
            monto = float(texto[1])
            saldo_actual = usuarios[user_id].get('saldo', 0)
            
            if monto <= 0:
                bot.reply_to(message, "❌ El monto debe ser positivo")
                return
            
            if monto > saldo_actual:
                bot.reply_to(message, f"❌ Saldo insuficiente. Tu saldo es ${saldo_actual}")
                return
            
            usuarios[user_id]['saldo'] = saldo_actual - monto
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
                    f"💰 Solicitud de retiro:\n"
                    f"Usuario: {usuarios[user_id]['nombre']}\n"
                    f"Monto: ${monto}\n"
                    f"ID: {user_id}"
                )
            except:
                pass
            
            bot.reply_to(
                message, 
                f"✅ Solicitud de retiro por ${monto} registrada.\n"
                f"Tu nuevo saldo es ${usuarios[user_id]['saldo']}\n"
                f"Te contactaremos pronto."
            )
            
        except ValueError:
            bot.reply_to(message, "❌ Monto inválido. Usa: /retirar [monto]")
    
    # ========================================
    # COMANDO /WEB
    # ========================================
    elif comando == '/web':
        bot.reply_to(message, f"🌐 Abre la web:\n{WEB_URL}")

# ============================================
# MENSAJES NORMALES (SIN DUPLICAR)
# ============================================
@bot.message_handler(func=lambda m: True)
def handle_messages(message):
    user_id = str(message.from_user.id)
    chat_id = message.chat.id
    texto = message.text
    
    print(f"💬 Mensaje de {message.from_user.first_name}: {texto}")
    
    # Solo responder si NO es un comando (ya lo manejamos arriba)
    if not texto.startswith('/'):
        bot.reply_to(message, f"Usa /ayuda para ver los comandos disponibles")

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
# API PARA LA WEB
# ============================================
@app.route('/api/balance/<user_id>', methods=['GET'])
def api_balance(user_id):
    user = usuarios.get(user_id, {})
    return jsonify({
        'saldo': user.get('saldo', 0),
        'referidos': len(user.get('referidos', [])),
        'ganancias': sum(usuarios.get(r, {}).get('saldo', 0) * 0.1 for r in user.get('referidos', []))
    })

@app.route('/api/usuarios', methods=['GET'])
def api_usuarios():
    return jsonify({
        'total': len(usuarios),
        'conectados': len(usuarios_conectados),
        'usuarios': usuarios
    })

# ============================================
# INICIAR
# ============================================
if __name__ == "__main__":
    print("="*50)
    print("🤖 BOT DE REFERIDOS INICIADO")
    print("="*50)
    print(f"Bot: @{BOT_USERNAME}")
    print(f"Webhook: https://mibot-espejo.onrender.com/setup_webhook")
    print(f"Usuarios cargados: {len(usuarios)}")
    print("="*50)
    app.run(host="0.0.0.0", port=5000)
