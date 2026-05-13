import os
import requests
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes, CallbackQueryHandler
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# =============================================
# SOZLAMALAR — faqat shu yerni o'zgartiring
# =============================================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")           # Render da kiritasiz
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "") # aistudio.google.com dan bepul
OWNER_ID = int(os.environ.get("OWNER_ID", "7299954359"))  # Sizning ID
OWNER_NAME = os.environ.get("OWNER_NAME", "Xo'jayin")
WEATHER_API_KEY = os.environ.get("WEATHER_API_KEY", "")  # openweathermap.org (bepul)
# =============================================

# Har bir foydalanuvchi uchun suhbat tarixi
chat_histories = {}

def is_owner(user_id: int) -> bool:
    """Faqat egasi ishlatishi mumkin"""
    return user_id == OWNER_ID

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("Kechirasiz, men faqat o'z egamga xizmat qilaman.")
        return

    keyboard = [
        [
            InlineKeyboardButton("🤖 AI savol", callback_data="ai"),
            InlineKeyboardButton("🎵 YouTube", callback_data="youtube"),
        ],
        [
            InlineKeyboardButton("🌤 Ob-havo", callback_data="weather"),
            InlineKeyboardButton("🌐 Tarjimon", callback_data="translate"),
        ],
        [
            InlineKeyboardButton("❓ Yordam", callback_data="help"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"Salom, {OWNER_NAME}! Men Hoshmjon — sizning shaxsiy yordamchingizman 🤖\n\n"
        "Nima qilishimni xohlaysiz?",
        reply_markup=reply_markup
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "ai":
        await query.message.reply_text("Savolingizni yozing — javob beraman 🤖")
        context.user_data["mode"] = "ai"
    elif query.data == "youtube":
        await query.message.reply_text("Qaysi qo'shiq yoki video qidiray? 🎵")
        context.user_data["mode"] = "youtube"
    elif query.data == "weather":
        await query.message.reply_text("Qaysi shahar ob-havosini bilmoqchisiz? 🌤")
        context.user_data["mode"] = "weather"
    elif query.data == "translate":
        await query.message.reply_text(
            "Tarjima qilmoqchi bo'lgan matnni yozing.\n"
            "Format: `en: Hello` yoki shunchaki matn yozing 🌐"
        )
        context.user_data["mode"] = "translate"
    elif query.data == "help":
        await query.message.reply_text(
            "📖 *Hoshmjon buyruqlari:*\n\n"
            "/start — Bosh menyu\n"
            "/ai [savol] — AI ga savol\n"
            "/yt [qo'shiq] — YouTube qidirish\n"
            "/ob [shahar] — Ob-havo\n"
            "/tarjima [matn] — Tarjima qilish\n"
            "/tozala — Suhbat tarixini tozalash\n\n"
            "Yoki shunchaki xabar yozing — avtomatik javob beraman!",
            parse_mode="Markdown"
        )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        return

    text = update.message.text
    mode = context.user_data.get("mode", "ai")

    # Rejimga qarab yo'naltirish
    if mode == "youtube":
        await youtube_search(update, text)
        context.user_data["mode"] = "ai"
    elif mode == "weather":
        await get_weather(update, text)
        context.user_data["mode"] = "ai"
    elif mode == "translate":
        await translate_text(update, context, text)
        context.user_data["mode"] = "ai"
    else:
        await ai_reply(update, context, text)

# ─────────────────────────────────────────
# AI JAVOB (Gemini API — bepul)
# ─────────────────────────────────────────
async def ai_reply(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    user_id = update.effective_user.id

    # Tarix
    if user_id not in chat_histories:
        chat_histories[user_id] = []

    chat_histories[user_id].append({
        "role": "user",
        "parts": [{"text": text}]
    })

    # Tarixni 20 ta bilan cheklash
    if len(chat_histories[user_id]) > 20:
        chat_histories[user_id] = chat_histories[user_id][-20:]

    await update.message.reply_text("⏳ Fikrlamoqda...")

    try:
        system_prompt = (
            f"Sen Hoshmjon — {OWNER_NAME}ning o'zbek tilidagi shaxsiy AI yordamchisisisan. "
            "Qisqa, aniq va do'stona javob ber. O'zbek tilida gapir. "
            "Agar savol texnik bo'lsa — bosqichma-bosqich tushuntir."
        )

        response = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}",
            headers={"Content-Type": "application/json"},
            json={
                "system_instruction": {
                    "parts": [{"text": system_prompt}]
                },
                "contents": chat_histories[user_id]
            },
            timeout=30
        )
        data = response.json()
        reply = data["candidates"][0]["content"]["parts"][0]["text"]

        chat_histories[user_id].append({
            "role": "model",
            "parts": [{"text": reply}]
        })

        await update.message.reply_text(f"🤖 {reply}")

    except Exception as e:
        logger.error(f"AI xato: {e}")
        await update.message.reply_text("Kechirasiz, hozir javob berolmayapman. Keyinroq urinib ko'ring.")

# ─────────────────────────────────────────
# YOUTUBE QIDIRISH
# ─────────────────────────────────────────
async def youtube_search(update: Update, query: str):
    await update.message.reply_text(f"🔍 '{query}' qidirilmoqda...")

    try:
        # YouTube qidiruv havolasi
        search_query = query.replace(" ", "+")
        url = f"https://www.youtube.com/results?search_query={search_query}"

        # Birinchi natija uchun havola
        watch_url = f"https://www.youtube.com/results?search_query={search_query}"

        await update.message.reply_text(
            f"🎵 *{query}* uchun YouTube natijalar:\n\n"
            f"🔗 [YouTube da ko'rish]({watch_url})\n\n"
            f"💡 Yoqtirgan videoni bosing va tinglang!",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"YouTube xato: {e}")
        await update.message.reply_text("YouTube qidirishda xato bo'ldi.")

# ─────────────────────────────────────────
# OB-HAVO
# ─────────────────────────────────────────
async def get_weather(update: Update, city: str):
    await update.message.reply_text(f"🌤 {city} ob-havosi tekshirilmoqda...")

    try:
        if not WEATHER_API_KEY:
            # API yo'q bo'lsa Claude orqali javob
            await update.message.reply_text(
                f"🌤 *{city}* ob-havosi uchun:\n\n"
                f"🔗 [weather.com da ko'rish](https://weather.com/weather/today/l/{city})\n"
                f"🔗 [yandex.uz ob-havo](https://yandex.uz/pogoda/{city})\n\n"
                "Weather API kaliti qo'shilsa aniq ma'lumot beraman!",
                parse_mode="Markdown"
            )
            return

        resp = requests.get(
            "https://api.openweathermap.org/data/2.5/weather",
            params={
                "q": city,
                "appid": WEATHER_API_KEY,
                "units": "metric",
                "lang": "uz"
            },
            timeout=10
        )
        data = resp.json()

        if data.get("cod") != 200:
            await update.message.reply_text(f"'{city}' shahri topilmadi. To'g'ri yozing.")
            return

        temp = data["main"]["temp"]
        feels = data["main"]["feels_like"]
        desc = data["weather"][0]["description"]
        humidity = data["main"]["humidity"]
        wind = data["wind"]["speed"]

        # Haroratga qarab emoji
        if temp > 30:
            emoji = "🔥"
        elif temp > 20:
            emoji = "☀️"
        elif temp > 10:
            emoji = "🌤"
        elif temp > 0:
            emoji = "🌧"
        else:
            emoji = "❄️"

        await update.message.reply_text(
            f"{emoji} *{city.title()} ob-havosi*\n\n"
            f"🌡 Harorat: *{temp:.0f}°C* (his etiladi: {feels:.0f}°C)\n"
            f"☁️ Holat: {desc}\n"
            f"💧 Namlik: {humidity}%\n"
            f"💨 Shamol: {wind} m/s",
            parse_mode="Markdown"
        )

    except Exception as e:
        logger.error(f"Ob-havo xato: {e}")
        await update.message.reply_text("Ob-havo ma'lumotini ololmadim.")

# ─────────────────────────────────────────
# TARJIMON
# ─────────────────────────────────────────
async def translate_text(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    await update.message.reply_text("🌐 Tarjima qilinmoqda...")

    try:
        response = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}",
            headers={"Content-Type": "application/json"},
            json={
                "contents": [{
                    "role": "user",
                    "parts": [{"text": (
                        f"Quyidagi matnni tarjima qil. "
                        f"Agar o'zbek tilida bo'lsa — inglizchaga, "
                        f"inglizcha bo'lsa — o'zbekchaga tarjima qil. "
                        f"Faqat tarjimani yoz, boshqa hech narsa yozma:\n\n{text}"
                    )}]
                }]
            },
            timeout=30
        )
        data = response.json()
        translation = data["candidates"][0]["content"]["parts"][0]["text"]
        await update.message.reply_text(
            f"🌐 *Tarjima:*\n\n"
            f"📝 Asl: {text}\n"
            f"✅ Tarjima: {translation}",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Tarjima xato: {e}")
        await update.message.reply_text("Tarjimada xato bo'ldi.")

# ─────────────────────────────────────────
# BUYRUQLAR
# ─────────────────────────────────────────
async def cmd_ai(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):
        return
    text = " ".join(context.args)
    if not text:
        await update.message.reply_text("Savol yozing: /ai [savol]")
        return
    await ai_reply(update, context, text)

async def cmd_youtube(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):
        return
    query = " ".join(context.args)
    if not query:
        await update.message.reply_text("Qo'shiq yozing: /yt [qo'shiq nomi]")
        return
    await youtube_search(update, query)

async def cmd_weather(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):
        return
    city = " ".join(context.args) or "Toshkent"
    await get_weather(update, city)

async def cmd_translate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):
        return
    text = " ".join(context.args)
    if not text:
        await update.message.reply_text("Matn yozing: /tarjima [matn]")
        return
    await translate_text(update, context, text)

async def cmd_clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):
        return
    user_id = update.effective_user.id
    chat_histories[user_id] = []
    await update.message.reply_text("✅ Suhbat tarixi tozalandi!")

# ─────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────
def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN yo'q!")
        return

    app = Application.builder().token(BOT_TOKEN).build()

    # Buyruqlar
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ai", cmd_ai))
    app.add_handler(CommandHandler("yt", cmd_youtube))
    app.add_handler(CommandHandler("ob", cmd_weather))
    app.add_handler(CommandHandler("tarjima", cmd_translate))
    app.add_handler(CommandHandler("tozala", cmd_clear))

    # Tugmalar
    app.add_handler(CallbackQueryHandler(button_handler))

    # Oddiy xabarlar
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Hoshmjon bot ishga tushdi!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
