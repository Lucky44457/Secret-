import os
import time
import json
import asyncio
import threading

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import UserAlreadyParticipant, InviteHashExpired, UsernameNotOccupied

with open('config.json', 'r') as f:
    DATA = json.load(f)

def getenv(var): return os.environ.get(var) or DATA.get(var, None)

API_ID = int(getenv("ID"))
API_HASH = getenv("HASH")
BOT_TOKEN = getenv("TOKEN")
STRING = getenv("STRING")

bot = Client("mybot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
acc = Client("myacc", api_id=API_ID, api_hash=API_HASH, session_string=STRING) if STRING else None

REPLACE_WORDS = {}

@bot.on_message(filters.command("replace"))
async def set_replace(client, message):
    try:
        parts = message.text.split(" ", 1)[1]
        old, new = map(str.strip, parts.split("|"))
        REPLACE_WORDS[message.from_user.id] = (old, new)
        await message.reply_text(f"✅ Will replace `{old}` with `{new}` in captions.")
    except:
        await message.reply_text("❌ Format wrong. Use:\n`/replace oldword | newword`", parse_mode="markdown")

@bot.on_message(filters.command("stopreplace"))
async def stop_replace(client, message):
    user_id = message.from_user.id
    if user_id in REPLACE_WORDS:
        REPLACE_WORDS.pop(user_id, None)
        await message.reply("🛑 Replace words cleared.")
    else:
        await message.reply("ℹ️ No replace settings were active.")

@bot.on_message(filters.text)
async def save_handler(client, message):
    print(message.text)

    if "https://t.me/+" in message.text or "https://t.me/joinchat/" in message.text:
        if acc is None:
            await message.reply("**String Session not set!**")
            return
        try:
            await acc.join_chat(message.text)
            await message.reply("✅ Joined chat.")
        except UserAlreadyParticipant:
            await message.reply("✅ Already joined.")
        except InviteHashExpired:
            await message.reply("❌ Invalid invite link.")
        except Exception as e:
            await message.reply(f"❌ Error: {e}")
        return

    elif "https://t.me/" in message.text:
        datas = message.text.split("/")
        temp = datas[-1].replace("?single", "").split("-")
        fromID = int(temp[0].strip())
        try:
            toID = int(temp[1].strip())
        except:
            toID = fromID

        rep = REPLACE_WORDS.get(message.from_user.id)

        for msgid in range(fromID, toID + 1):
            if "https://t.me/c/" in message.text:
                chatid = int("-100" + datas[4])
                if acc is None:
                    await message.reply("**String Session not set!**")
                    return
                await handle_private(message, chatid, msgid)
            elif "https://t.me/b/" in message.text:
                username = datas[4]
                if acc is None:
                    await message.reply("**String Session not set!**")
                    return
                try:
                    await handle_private(message, username, msgid)
                except Exception as e:
                    await message.reply(f"❌ Error: {e}")
            else:
                username = datas[3]
                try:
                    msg = await bot.get_messages(username, msgid)
                    replace_caption = msg.caption

                    if rep and replace_caption:
                        replace_caption = replace_caption.replace(rep[0], rep[1])

                    await bot.copy_message(
                        message.chat.id, msg.chat.id, msg.id,
                        caption=replace_caption if replace_caption else None,
                        reply_to_message_id=message.id
                    )
                except UsernameNotOccupied:
                    await message.reply("❌ Username not found.")
                except Exception as e:
                    if acc is None:
                        await message.reply("**String Session not set!**")
                        return
                    await handle_private(message, username, msgid)
            await asyncio.sleep(2)

async def handle_private(message, chatid, msgid):
    msg = await acc.get_messages(chatid, msgid)
    msg_type = get_message_type(msg)

    replace_pair = REPLACE_WORDS.get(message.from_user.id)
    caption = msg.caption
    caption_entities = msg.caption_entities

    if replace_pair and caption:
        caption = caption.replace(replace_pair[0], replace_pair[1])
        caption_entities = None

    smsg = await bot.send_message(message.chat.id, "__Downloading__", reply_to_message_id=message.id)

    threading.Thread(target=downstatus, args=(f"{message.id}downstatus.txt", smsg), daemon=True).start()
    file = await acc.download_media(msg, progress=progress, progress_args=[message, "down"])
    os.remove(f"{message.id}downstatus.txt")

    threading.Thread(target=upstatus, args=(f"{message.id}upstatus.txt", smsg), daemon=True).start()

    kwargs = {
        "caption": caption,
        "caption_entities": caption_entities,
        "reply_to_message_id": message.id,
        "progress": progress,
        "progress_args": [message, "up"]
    }

    if msg_type == "Document":
        thumb = await try_thumb(msg.document)
        await bot.send_document(message.chat.id, file, thumb=thumb, **kwargs)
        if thumb: os.remove(thumb)
    elif msg_type == "Video":
        thumb = await try_thumb(msg.video)
        await bot.send_video(message.chat.id, file, duration=msg.video.duration,
                             width=msg.video.width, height=msg.video.height,
                             thumb=thumb, **kwargs)
        if thumb: os.remove(thumb)
    elif msg_type == "Photo":
        await bot.send_photo(message.chat.id, file, **kwargs)
    elif msg_type == "Audio":
        thumb = await try_thumb(msg.audio)
        await bot.send_audio(message.chat.id, file, thumb=thumb, **kwargs)
        if thumb: os.remove(thumb)
    elif msg_type == "Voice":
        await bot.send_voice(message.chat.id, file, **kwargs)
    elif msg_type == "Animation":
        await bot.send_animation(message.chat.id, file, reply_to_message_id=message.id)
    elif msg_type == "Sticker":
        await bot.send_sticker(message.chat.id, file, reply_to_message_id=message.id)

    os.remove(file)
    if os.path.exists(f"{message.id}upstatus.txt"): os.remove(f"{message.id}upstatus.txt")
    await bot.delete_messages(message.chat.id, smsg.id)

async def try_thumb(media):
    try: return await acc.download_media(media.thumbs[0].file_id)
    except: return None

def downstatus(statusfile, message):
    while not os.path.exists(statusfile): time.sleep(3)
    while os.path.exists(statusfile):
        with open(statusfile, "r") as f:
            txt = f.read()
        try:
            asyncio.run_coroutine_threadsafe(
                bot.edit_message_text(message.chat.id, message.id, f"__Downloaded__: **{txt}**"),
                bot.loop
            )
            time.sleep(10)
        except: time.sleep(5)

def upstatus(statusfile, message):
    while not os.path.exists(statusfile): time.sleep(3)
    while os.path.exists(statusfile):
        with open(statusfile, "r") as f:
            txt = f.read()
        try:
            asyncio.run_coroutine_threadsafe(
                bot.edit_message_text(message.chat.id, message.id, f"__Uploaded__: **{txt}**"),
                bot.loop
            )
            time.sleep(10)
        except: time.sleep(5)

def progress(current, total, message, type):
    with open(f"{message.id}{type}status.txt", "w") as f:
        f.write(f"{current * 100 / total:.1f}%")

def get_message_type(msg):
    if msg.document: return "Document"
    if msg.video: return "Video"
    if msg.photo: return "Photo"
    if msg.audio: return "Audio"
    if msg.voice: return "Voice"
    if msg.animation: return "Animation"
    if msg.sticker: return "Sticker"
    if msg.text: return "Text"

USAGE = """
**FOR PUBLIC CHATS**
Just send post link.

**FOR PRIVATE CHATS**
Send chat invite link, then post link.

**FOR BOT CHATS**
Use format:
`https://t.me/b/botusername/4321`

**MULTIPLE MESSAGES**
Use format like:
`https://t.me/channel/1001-1005`
"""

if acc: acc.start()
bot.run()
