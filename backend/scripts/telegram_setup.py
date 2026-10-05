"""Telegram setup helper (Phase 5). Never prints the bot token.

  uv run python scripts/telegram_setup.py discover   # find your chat id (after you /start the bot)
  uv run python scripts/telegram_setup.py test       # send a test message to TELEGRAM_CHAT_ID
  uv run python scripts/telegram_setup.py sample     # send one sample alert (real alert format)

Steps: 1) create a bot with @BotFather and put the token in .env as TELEGRAM_BOT_TOKEN,
2) open a chat with your bot and send /start, 3) run `discover`, 4) put the printed chat id in
.env as TELEGRAM_CHAT_ID, 5) run `test`, then restart the worker (docker compose up -d worker).
"""

from __future__ import annotations

import asyncio
import sys
from datetime import UTC, datetime

from tss.clients.telegram import TelegramClient, TelegramError
from tss.core.settings import Settings
from tss.domain.notifier import connectivity_message, format_event_message


async def discover(client: TelegramClient) -> int:
    me = await client.get_me()
    print(f"Token accepted: bot @{me.get('username', '?')} ({me.get('first_name', '')})")
    updates = await client.get_updates()
    chats: dict[int, str] = {}
    for update in updates:
        message = update.get("message") or update.get("channel_post") or {}
        chat = message.get("chat") or {}
        if "id" in chat:
            name = chat.get("title") or chat.get("first_name") or chat.get("username") or ""
            chats[int(chat["id"])] = f"{chat.get('type', '?')} {name}".strip()
    if not chats:
        print("No messages found. Open your bot in Telegram, send /start, then run this again.")
        return 1
    print("Chats that messaged the bot (use the id of YOUR chat):")
    for chat_id, label in chats.items():
        print(f"  TELEGRAM_CHAT_ID={chat_id}    # {label}")
    return 0


async def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    settings = Settings()
    token = settings.telegram_bot_token
    if mode not in ("discover", "test", "sample"):
        print(__doc__)
        return 2
    if token is None or not token.get_secret_value().strip():
        print("TELEGRAM_BOT_TOKEN is empty in .env: create a bot with @BotFather first.")
        return 2
    chat_id = (settings.telegram_chat_id or "").strip()
    if mode in ("test", "sample") and not chat_id:
        print("TELEGRAM_CHAT_ID is empty in .env: run `discover` first.")
        return 2
    client = TelegramClient(token, chat_id)
    try:
        if mode == "discover":
            return await discover(client)
        if mode == "sample":
            sample = format_event_message(
                symbol="UMA_USDT",
                timeframe="5m",
                event="BUY",
                against_htf=False,
                bar_close_time=datetime.now(UTC),
            )
            await client.send_message(sample, html=True)
            print("Sample alert sent (format only, not a real signal).")
            return 0
        await client.send_message(connectivity_message())
        print("Test message sent. Check your Telegram chat.")
        return 0
    except TelegramError as exc:
        print(f"Telegram error: {exc.message}")
        return 1
    finally:
        await client.aclose()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
