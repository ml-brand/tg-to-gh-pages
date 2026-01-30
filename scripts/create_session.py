#!/usr/bin/env python3
"""Create a Telethon StringSession for GitHub Actions.

Run locally:
  python scripts/create_session.py

It will ask for:
  - api_id / api_hash
  - phone number
  - login code (and 2FA password if enabled)

The result is a session string. Put it into GitHub Secrets as TG_SESSION.
"""

import asyncio
import os
from getpass import getpass

from telethon import TelegramClient
from telethon.sessions import StringSession


def _prompt(name: str, secret: bool = False) -> str:
    env = os.getenv(name)
    if env:
        return env
    if secret:
        return getpass(f"{name}: ")
    return input(f"{name}: ").strip()


async def main() -> None:
    api_id_raw = _prompt("TG_API_ID")
    api_hash = _prompt("TG_API_HASH", secret=True)

    try:
        api_id = int(api_id_raw)
    except Exception as e:
        raise SystemExit("TG_API_ID must be an integer") from e

    print("\nLogin to Telegram. Use a dedicated account if you prefer.")
    async with TelegramClient(StringSession(), api_id, api_hash) as client:
        await client.start()  # will prompt for phone/code/password in console
        session_str = client.session.save()
        print("\n=== COPY THIS SESSION STRING ===\n")
        print(session_str)
        print("\n=== END ===\n")
        print("Save it as GitHub Secret: TG_SESSION")


if __name__ == "__main__":
    asyncio.run(main())
