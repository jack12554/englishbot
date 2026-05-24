import os
import json
import logging
import random
import httpx
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ["BOT_TOKEN"]
GROQ_API_KEY = os.environ["GROQ_API_KEY"]

USERS_FILE = "users.json"

def load_users():
    try:
        with open(USERS_FILE, 'r') as f:
            return json.load(f)
    except:
        return []

def save_user(chat_id):
    users = load_users()
    if chat_id not in users:
        users.append(chat_id)
        with open(USERS_FILE, 'w') as f:
            json.dump(users, f)

CATEGORIES = [
    "Daily Use Sentences", "Attitude Lines", "Question Sentences",
    "Emotional Lines", "Funny Lines", "Conversation Starters",
    "Student Life", "Office / Work", "Shopping", "Food & Restaurant",
    "Travel", "Friendship", "Breakup / Sad Lines", "Motivational Lines",
    "Time & Routine", "Social Media Lines", "Smart / Advanced English",
    "Common Mistakes", "Synonyms / Alternatives", "Word Meanings",
]

CATEGORY_EMOJIS = {
    "Daily Use Sentences": "🗣️", "Attitude Lines": "😎",
    "Question Sentences": "❓", "Emotional Lines": "💙",
    "Funny Lines": "😂", "Conversation Starters": "💬",
    "Student Life": "📚", "Office / Work": "💼",
    "Shopping": "🛍️", "Food & Restaurant": "🍽️",
    "Travel": "✈️", "Friendship": "🤝",
    "Breakup / Sad Lines": "💔", "Motivational Lines": "🔥",
    "Time & Routine": "⏰", "Social Media Lines": "📱",
    "Smart / Advanced English": "🧠", "Common Mistakes": "✅",
    "Synonyms / Alternatives": "📖", "Word Meanings": "💡",
}

POST_TYPES = ["sentences", "quiz", "poll", "tip", "sentences"]
post_type_index = 0


async def groq_call(prompt: str) -> str:
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.8,
        "max_tokens": 1500
    }
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()


async def generate_sentences(category: str) -> str:
    emoji = CATEGORY_EMOJIS.get(category, "📝")
    prompt = f"""Generate exactly 5 Hindi to English sentence pairs for category: "{category}"

Format EXACTLY like this:
1. हिंदी वाक्य → English sentence
2. हिंदी वाक्य → English sentence
3. हिंदी वाक्य → English sentence
4. हिंदी वाक्य → English sentence
5. हिंदी वाक्य → English sentence

Rules:
- Natural commonly used sentences
- Category specific only
- No extra text, just 5 pairs"""

    content = await groq_call(prompt)
    lines = [l.strip() for l in content.strip().split('\n') if l.strip() and '→' in l][:5]

    post = f"{emoji} *{category}*\n"
    post += "━━━━━━━━━━━━━━━━━━━━\n\n"
    for line in lines:
        parts = line.split('→')
        if len(parts) == 2:
            hindi = parts[0].strip().lstrip('0123456789. ')
            english = parts[1].strip()
            post += f"🇮🇳 _{hindi}_\n"
            post += f"🇬🇧 *{english}*\n\n"
    post += "━━━━━━━━━━━━━━━━━━━━\n"
    post += "💫 *Rozana seekho, rozana badho!*"
    return post


async def generate_quiz(category: str) -> tuple:
    emoji = CATEGORY_EMOJIS.get(category, "📝")
    prompt = f"""Create a Hindi to English quiz for category: "{category}"

Return EXACTLY:
HINDI: [hindi sentence]
CORRECT: [correct translation]
WRONG1: [wrong option]
WRONG2: [wrong option]
WRONG3: [wrong option]"""

    content = await groq_call(prompt)
    lines = {l.split(':')[0].strip(): ':'.join(l.split(':')[1:]).strip()
             for l in content.strip().split('\n') if ':' in l}

    hindi = lines.get('HINDI', '')
    correct = lines.get('CORRECT', '')
    wrong1 = lines.get('WRONG1', '')
    wrong2 = lines.get('WRONG2', '')
    wrong3 = lines.get('WRONG3', '')

    options = [correct, wrong1, wrong2, wrong3]
    random.shuffle(options)
    correct_index = options.index(correct)

    question = f"🧠 *Quiz Time!* {emoji}\n"
    question += "━━━━━━━━━━━━━━━━━━━━\n\n"
    question += f"🇮🇳 *Sahi English translation kya hai?*\n\n"
    question += f"_{hindi}_\n\n"
    question += "━━━━━━━━━━━━━━━━━━━━\n"
    question += "👇 *Option chuno:*"

    return question, options, correct_index, correct


async def generate_tip(category: str) -> str:
    emoji = CATEGORY_EMOJIS.get(category, "📝")
    prompt = f"""English learning tip for Hindi speakers about "{category}"

Return EXACTLY:
TIP: [tip in Hinglish]
EXAMPLE_WRONG: [wrong example]
EXAMPLE_RIGHT: [correct example]
EXPLANATION: [short Hindi explanation]"""

    content = await groq_call(prompt)
    lines = {l.split(':')[0].strip(): ':'.join(l.split(':')[1:]).strip()
             for l in content.strip().split('\n') if ':' in l}

    post = f"💡 *Pro Tip!* {emoji}\n"
    post += "━━━━━━━━━━━━━━━━━━━━\n\n"
    post += f"📌 *{lines.get('TIP', '')}*\n\n"
    if lines.get('EXAMPLE_WRONG'):
        post += f"❌ *Galat:* `{lines.get('EXAMPLE_WRONG', '')}`\n"
        post += f"✅ *Sahi:* `{lines.get('EXAMPLE_RIGHT', '')}`\n\n"
    if lines.get('EXPLANATION'):
        post += f"📖 _{lines.get('EXPLANATION', '')}_\n\n"
    post += "━━━━━━━━━━━━━━━━━━━━\n"
    post += "🔥 *Yeh trick yaad rakhna!*"
    return post


async def send_scheduled_post(app):
    global post_type_index
    users = load_users()
    if not users:
        logger.info("Koi user nahi hai abhi")
        return

    category = random.choice(CATEGORIES)
    post_type = POST_TYPES[post_type_index % len(POST_TYPES)]
    post_type_index += 1

    for chat_id in users:
        try:
            if post_type == "sentences":
                text = await generate_sentences(category)
                await app.bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")

            elif post_type == "quiz":
                question, options, correct_index, correct_answer = await generate_quiz(category)
                keyboard = [[InlineKeyboardButton(
                    f"{'ABCD'[i]}. {opt}",
                    callback_data=f"quiz_{i}_{correct_index}_{opt[:20]}"
                )] for i, opt in enumerate(options)]
                await app.bot.send_message(
                    chat_id=chat_id, text=question,
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )

            elif post_type == "poll":
                prompt = f"""Poll question for English learners about "{category}"
Return EXACTLY:
QUESTION: [question in Hinglish, max 50 chars]
OPT1: [option, max 80 chars]
OPT2: [option, max 80 chars]
OPT3: [option, max 80 chars]
OPT4: [option, max 80 chars]"""
                content = await groq_call(prompt)
                lines = {l.split(':')[0].strip(): ':'.join(l.split(':')[1:]).strip()
                         for l in content.strip().split('\n') if ':' in l}
                question = lines.get('QUESTION', f'{category} ke baare mein?')[:255]
                poll_options = [
                    lines.get('OPT1', 'Bahut achha! 🔥')[:100],
                    lines.get('OPT2', 'Achha hai 👍')[:100],
                    lines.get('OPT3', 'Thoda aur chahiye 📚')[:100],
                    lines.get('OPT4', 'Mushkil laga 😅')[:100],
                ]
                await app.bot.send_poll(
                    chat_id=chat_id,
                    question=f"🗳️ {question}",
                    options=poll_options,
                    is_anonymous=True
                )

            elif post_type == "tip":
                text = await generate_tip(category)
                await app.bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")

            logger.info(f"Sent to {chat_id}: {post_type} | {category}")

        except Exception as e:
            logger.error(f"Error sending to {chat_id}: {e}")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    save_user(chat_id)

    text = """🎓 *English Seekho Bot*
━━━━━━━━━━━━━━━━━━━━

*Namaste!* 🙏 Main tumhara personal English teacher hoon!

*Rozana 5 posts milenge:*
🗣️ *8:00 AM* — Hindi→English Sentences
🧠 *11:00 AM* — Quiz
🗳️ *2:00 PM* — Poll
💡 *5:30 PM* — Pro Tip
😎 *8:00 PM* — More Sentences

*20 Categories:*
Daily Use • Attitude • Funny • Travel
Student Life • Office • Motivational aur bahut kuch!

*Commands:*
/test — Abhi ek post dekho
/categories — Saari categories

✅ *Tumhara subscription shuru ho gaya!*
━━━━━━━━━━━━━━━━━━━━"""
    await update.message.reply_text(text, parse_mode="Markdown")


async def test_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    save_user(chat_id)
    msg = await update.message.reply_text("⏳ Post generate ho rahi hai...")

    category = random.choice(CATEGORIES)
    post_types = ["sentences", "quiz", "tip"]
    post_type = random.choice(post_types)

    try:
        if post_type == "sentences":
            text = await generate_sentences(category)
            await update.message.reply_text(text, parse_mode="Markdown")
        elif post_type == "quiz":
            question, options, correct_index, correct_answer = await generate_quiz(category)
            keyboard = [[InlineKeyboardButton(
                f"{'ABCD'[i]}. {opt}",
                callback_data=f"quiz_{i}_{correct_index}_{opt[:20]}"
            )] for i, opt in enumerate(options)]
            await update.message.reply_text(
                question, parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        elif post_type == "tip":
            text = await generate_tip(category)
            await update.message.reply_text(text, parse_mode="Markdown")

        await msg.delete()
    except Exception as e:
        await msg.edit_text(f"❌ Error: {str(e)}")


async def show_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "📚 *Supported Categories:*\n━━━━━━━━━━━━━━━━━━━━\n\n"
    for i, cat in enumerate(CATEGORIES, 1):
        emoji = CATEGORY_EMOJIS.get(cat, "📝")
        text += f"{emoji} {i}\\. {cat}\n"
    text += "\n━━━━━━━━━━━━━━━━━━━━\n🔥 *Rozana nayi category se seekho!*"
    await update.message.reply_text(text, parse_mode="MarkdownV2")


async def handle_quiz_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data.split('_')
    if len(data) < 4:
        return
    chosen = int(data[1])
    correct = int(data[2])
    correct_text = '_'.join(data[3:])
    if chosen == correct:
        await query.answer("✅ Sahi jawab! Bahut badhiya! 🎉", show_alert=True)
    else:
        await query.answer(f"❌ Galat! Sahi tha: {correct_text}", show_alert=True)


def main():
    # job_queue(None) — Python 3.13 compatibility fix
    app = ApplicationBuilder().token(BOT_TOKEN).job_queue(None).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("test", test_post))
    app.add_handler(CommandHandler("categories", show_categories))
    app.add_handler(CallbackQueryHandler(handle_quiz_answer, pattern="^quiz_"))

    scheduler = AsyncIOScheduler(timezone="Asia/Kolkata")
    scheduler.add_job(send_scheduled_post, 'cron', hour=8,  minute=0,  args=[app])
    scheduler.add_job(send_scheduled_post, 'cron', hour=11, minute=0,  args=[app])
    scheduler.add_job(send_scheduled_post, 'cron', hour=14, minute=0,  args=[app])
    scheduler.add_job(send_scheduled_post, 'cron', hour=17, minute=30, args=[app])
    scheduler.add_job(send_scheduled_post, 'cron', hour=20, minute=0,  args=[app])
    scheduler.start()

    logger.info("Bot chal raha hai! Posts: 8AM 11AM 2PM 5:30PM 8PM IST")
    app.run_polling()


if __name__ == "__main__":
    main()
