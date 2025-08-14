import asyncio
from telethon import TelegramClient, events
from telethon.errors import AuthKeyUnregisteredError

# ====== YOUR SETTINGS ======
API_ID = "21303916"  # Replace with your API ID
API_HASH = "a95f38df3dc1f71b6497798a40b993ab"  # Replace with your API Hash
SESSION_PATH = "/data/data/com.termux/files/home/Save-Restricted-Bot/sessions/+916006440903"
# ============================

async def main():
    try:
        print("🔄 Connecting to Telegram...")
        client = TelegramClient(SESSION_PATH, API_ID, API_HASH)
        await client.connect()

        if not await client.is_user_authorized():
            print("❌ Session not authorized. Please log in again.")
            return

        me = await client.get_me()
        print(f"✅ Logged in as {me.first_name} ({me.id})")

        @client.on(events.NewMessage(incoming=True))
        async def handler(event):
            sender = await event.get_sender()
            name = sender.first_name if sender else "Unknown"
            print(f"\n📩 New message from {name}: {event.raw_text}")

        print("📡 Listening for messages... Press CTRL+C to stop.")
        await client.run_until_disconnected()

    except AuthKeyUnregisteredError:
        print("❌ Session file is invalid or expired. Please create a new one.")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
