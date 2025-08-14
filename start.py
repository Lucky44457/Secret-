from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram import Client, filters
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, AuthKeyUnregisteredError
import os
import json
import signal
import subprocess
import asyncio

CONFIG_PATH = "config.json"
if not os.path.exists(CONFIG_PATH):
    print("❌ config.json not found!")
    exit()

with open(CONFIG_PATH, "r") as f:
    config = json.load(f)

API_ID = config.get("ID")
API_HASH = config.get("HASH")
BOT_TOKEN = config.get("TOKEN")

if not API_ID or not API_HASH or not BOT_TOKEN:
    print("❌ Missing ID, HASH, or TOKEN in config.json")
    exit()

if not os.path.exists("sessions"):
    os.makedirs("sessions")

bot = Client("my_bot", bot_token=BOT_TOKEN, api_id=API_ID, api_hash=API_HASH)

login_states = {}
running_processes = {}
watch_tasks = {}

async def watch_session(user_id, phone):
    session_path = os.path.join("sessions", phone + ".session")
    client = TelegramClient(session_path, API_ID, API_HASH)
    await client.connect()

    while True:
        await asyncio.sleep(5)
        try:
            await client.get_me()
        except AuthKeyUnregisteredError:
            print(f"⚠️ Session removed for {phone}, stopping bot...")
            if user_id in running_processes:
                os.kill(running_processes[user_id].pid, signal.SIGTERM)
                del running_processes[user_id]
            if os.path.exists(session_path):
                os.remove(session_path)
            await bot.send_message(user_id, "🚪 You have been logged out from Telegram. Bot stopped.")
            break
        except Exception as e:
            print(f"Error checking session: {e}")
            break

    await client.disconnect()


# ✅ /start command
@bot.on_message(filters.command("start") & filters.private)
async def send_start(client, message):
    buttons = [
        [InlineKeyboardButton("❣️ Developer", url="https://t.me/kingvj01")],
        [
            InlineKeyboardButton('🔍 sᴜᴘᴘᴏʀᴛ ɢʀᴏᴜᴘ', url='https://t.me/vj_bot_disscussion'),
            InlineKeyboardButton('🤖 ᴜᴘᴅᴀᴛᴇ ᴄʜᴀɴɴᴇʟ', url='https://t.me/vj_botz')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(buttons)

    await client.send_message(
        chat_id=message.chat.id,
        text=(
            f"<b>👋 Hi {message.from_user.mention}, I am Save Restricted Content Bot.\n"
            f"I can send you restricted content by its post link.\n\n"
            f"For downloading restricted content use /login first.\n\n"
            f"Know how to use the bot by - /help</b>"
        ),
        reply_markup=reply_markup,
        reply_to_message_id=message.id
    )


# ✅ /help command
@bot.on_message(filters.command("help") & filters.private)
async def send_help(_, message):
    help_text = (
        "<b>🌟 Help Menu</b>\n\n"
        "<b>FOR PRIVATE CHATS</b>\n"
        "First send invite link of the chat (unnecessary if the account of string session is already a member of the chat),\n"
        "then send post/s link.\n\n"
        "<b>FOR BOT CHATS</b>\n"
        "Send link with '/b/', bot's username and message ID. You might need an unofficial client to get the ID, like below:\n"
        "https://t.me/b/botusername/4321\n\n"
        "<b>MULTI POSTS</b>\n"
        "Send public/private post links as explained above with format 'from - to' to send multiple messages, like below:\n"
        "https://t.me/xxxx/1001-1101\n"
        "https://t.me/c/xxxx/101-200"
    )
    await message.reply(help_text)


# ✅ /login command
@bot.on_message(filters.command("login") & filters.private)
async def start_login(_, message):
    await message.reply("📱 Send your Telegram phone number (e.g. +911234567890):")
    login_states[message.from_user.id] = {"step": "phone"}


# ✅ /logout command
@bot.on_message(filters.command("logout") & filters.private)
async def logout_user(_, message):
    user_id = message.from_user.id
    if user_id in running_processes:
        os.kill(running_processes[user_id].pid, signal.SIGTERM)
        del running_processes[user_id]
    if user_id in watch_tasks:
        watch_tasks[user_id].cancel()
        del watch_tasks[user_id]
    for file in os.listdir("sessions"):
        if file.startswith("+") or file.endswith(".session"):
            os.remove(os.path.join("sessions", file))
    await message.reply("✅ Logout successful! Bot function stopped.")


# ✅ Handle login steps
@bot.on_message(filters.private)
async def handle_login_steps(_, message):
    user_id = message.from_user.id
    if user_id not in login_states:
        return

    state = login_states[user_id]

    if state["step"] == "phone":
        phone = message.text.strip()
        state["phone"] = phone
        state["client"] = TelegramClient(os.path.join("sessions", phone), API_ID, API_HASH)
        await state["client"].connect()
        try:
            await state["client"].send_code_request(phone)
            await message.reply(
                "📱 Please check your official Telegram account for the OTP.\n\n"
                "✏️ Once received, send the OTP here in the following format:\n"
                "If OTP is `12345`, type it as: 1️⃣ 2️⃣ 3️⃣ 4️⃣ 5️⃣\n\n"
                "⚠️ Make sure to add spaces between the digits.\n"
                "✅ Example: 1 2 3 4 5"
            )
            state["step"] = "code"
        except Exception as e:
            await message.reply(f"❌ Error sending code: {e}")
            await state["client"].disconnect()
            del login_states[user_id]

    elif state["step"] == "code":
        code = message.text.strip()
        try:
            await state["client"].sign_in(state["phone"], code)
            await message.reply("✅ Login successful! Starting bot function...")
            proc = subprocess.Popen(["python", "main.py"])
            running_processes[user_id] = proc
            watch_tasks[user_id] = asyncio.create_task(watch_session(user_id, state["phone"]))
            await state["client"].disconnect()
            del login_states[user_id]
        except SessionPasswordNeededError:
            await message.reply("🔑 Two-step verification is enabled. Send your password:")
            state["step"] = "password"
        except Exception as e:
            await message.reply(f"❌ Login failed: {e}")
            await state["client"].disconnect()
            del login_states[user_id]

    elif state["step"] == "password":
        password = message.text.strip()
        try:
            await state["client"].sign_in(password=password)
            await message.reply("✅ Login successful with 2FA! Starting bot function...")
            proc = subprocess.Popen(["python", "main.py"])
            running_processes[user_id] = proc
            watch_tasks[user_id] = asyncio.create_task(watch_session(user_id, state["phone"]))
        except Exception as e:
            await message.reply(f"❌ Login failed: {e}")
        await state["client"].disconnect()
        del login_states[user_id]


if __name__ == "__main__":
    bot.run()
