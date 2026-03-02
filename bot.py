import telebot
import time

# PON AQUÍ TU TOKEN (el que te dio @BotFather)
TOKEN = '8756602645:AAHZjNUJ1KKy-1L9i2CAJRMy-mIE5ambV_Q'  # ¡CAMBIA ESTO POR TU TOKEN REAL!

# Crear el bot
bot = telebot.TeleBot(TOKEN)

# Comando /start
@bot.message_handler(commands=['start'])
def send_welcome(message):
    nombre = message.from_user.first_name
    bot.reply_to(message, f"¡Hola {nombre}! Bienvenido a mi bot. Usa /ayuda para ver los comandos disponibles.")

# Comando /ayuda
@bot.message_handler(commands=['ayuda', 'help'])
def send_help(message):
    ayuda_texto = """
    🤖 **COMANDOS DISPONIBLES:**
    /start - Iniciar el bot
    /ayuda - Ver esta ayuda
    /info - Información del bot
    /hora - Ver la hora actual
    """
    bot.reply_to(message, ayuda_texto)

# Comando /info
@bot.message_handler(commands=['info'])
def send_info(message):
    info_texto = """
    📌 **INFORMACIÓN DEL BOT**
    • Nombre: Mi Bot Asistente
    • Versión: 1.0
    • Creado por: [Tu nombre]
    • Lenguaje: Python
    """
    bot.reply_to(message, info_texto)

# Comando /hora
@bot.message_handler(commands=['hora'])
def send_time(message):
    hora_actual = time.strftime("%H:%M:%S")
    fecha_actual = time.strftime("%d/%m/%Y")
    bot.reply_to(message, f"📅 Fecha: {fecha_actual}\n⏰ Hora: {hora_actual}")

# Responder a cualquier mensaje
@bot.message_handler(func=lambda message: True)
def echo_all(message):
    respuestas = [
        "¡Interesante! Cuéntame más.",
        "No entiendo eso, usa /ayuda para ver comandos.",
        "¿Podrías repetirlo?",
        "Soy un bot, solo entiendo comandos específicos."
    ]
    import random
    bot.reply_to(message, random.choice(respuestas))

# Iniciar el bot
print("🤖 Bot iniciado...")
print("Presiona Ctrl+C para detener el bot")
bot.infinity_polling()