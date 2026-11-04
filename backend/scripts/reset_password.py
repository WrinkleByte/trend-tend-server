# SPDX-FileCopyrightText: 2026 WrinkleByte LLC
# SPDX-License-Identifier: AGPL-3.0-only

"""Manually reset a user's password directly in the database.

For exactly the situation that motivated this: an admin locked out with no
SMTP configured yet (or anyone who'd rather not wait on email at all). Goes
through app.core.security.hash_password — the same Argon2 hasher
login()/register() use — so the result is a completely normal password,
not a special case; the user can change it again from the app afterward
like any other password.

Usage (from inside the backend container):
    python -m scripts.reset_password user@example.com
    python -m scripts.reset_password user@example.com --password 'new pw'
    python -m scripts.reset_password --list
"""

import argparse
import asyncio
import getpass
import sys

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import get_settings
from app.core.security import hash_password
from app.models.user import User


async def list_users() -> None:
    engine = create_async_engine(get_settings().database_url)
    async with async_sessionmaker(engine)() as session:
        result = await session.execute(select(User.email, User.display_name, User.is_instance_admin).order_by(User.created_at))
        rows = result.all()
    await engine.dispose()

    if not rows:
        print("No users exist yet.")
        return
    for email, display_name, is_admin in rows:
        marker = " (instance admin)" if is_admin else ""
        print(f"{email}  —  {display_name}{marker}")


async def reset_password(email: str, new_password: str) -> None:
    engine = create_async_engine(get_settings().database_url)
    session_factory = async_sessionmaker(engine)
    async with session_factory() as session:
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if user is None:
            print(f"No user found with email {email!r}.", file=sys.stderr)
            await engine.dispose()
            sys.exit(1)

        user.password_hash = hash_password(new_password)
        await session.commit()

    await engine.dispose()
    print(f"Password updated for {email}.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("email", nargs="?", help="Email of the account to reset")
    parser.add_argument("--password", help="New password (omit to be prompted, which avoids shell history)")
    parser.add_argument("--list", action="store_true", help="List existing users instead of resetting anything")
    args = parser.parse_args()

    if args.list:
        asyncio.run(list_users())
        return

    if not args.email:
        parser.error("email is required unless --list is given")

    new_password = args.password or getpass.getpass("New password: ")
    if len(new_password) < 8:
        parser.error("password must be at least 8 characters (same rule the app enforces)")

    asyncio.run(reset_password(args.email, new_password))


if __name__ == "__main__":
    main()
