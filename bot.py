from __future__ import annotations

import logging
import os
import sqlite3
from pathlib import Path

import discord
from aiohttp import web
from discord import app_commands
from discord.ext import commands

logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("inf_nickname_bot")

DATA_DIR = Path(os.getenv("DATA_DIR", "data"))
DATABASE_PATH = DATA_DIR / "settings.sqlite3"


def monospace_upper(text: str) -> str:
    """Return uppercase text with ASCII letters and digits in monospace Unicode."""
    formatted: list[str] = []
    for character in text.upper():
        if "A" <= character <= "Z":
            formatted.append(chr(0x1D670 + ord(character) - ord("A")))
        elif "0" <= character <= "9":
            formatted.append(chr(0x1D7F6 + ord(character) - ord("0")))
        else:
            formatted.append(character)
    return "".join(formatted)


def make_nickname(username: str) -> str:
    prefix = monospace_upper("INF ")
    name = monospace_upper(username.strip()) or monospace_upper("MEMBER")
    return (prefix + name)[:32]


class NicknameBot(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.members = True
        super().__init__(
            command_prefix=commands.when_mentioned,
            intents=intents,
        )
        self._web_runner: web.AppRunner | None = None

    async def setup_hook(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(DATABASE_PATH) as database:
            database.execute(
                """
                CREATE TABLE IF NOT EXISTS guild_settings (
                    guild_id INTEGER PRIMARY KEY,
                    enabled INTEGER NOT NULL DEFAULT 1
                )
                """
            )

        synced = await self.tree.sync()
        log.info("Synced %s application commands.", len(synced))
        await self._start_health_server()

    async def _start_health_server(self) -> None:
        application = web.Application()

        async def health(_: web.Request) -> web.Response:
            return web.json_response(
                {"status": "ok", "bot_ready": self.is_ready()}
            )

        application.router.add_get("/", health)
        application.router.add_get("/healthz", health)
        self._web_runner = web.AppRunner(application)
        await self._web_runner.setup()
        port = int(os.getenv("PORT", "8080"))
        site = web.TCPSite(self._web_runner, "0.0.0.0", port)
        await site.start()
        log.info("Health web service listening on port %s.", port)

    async def close(self) -> None:
        if self._web_runner is not None:
            await self._web_runner.cleanup()
            self._web_runner = None
        await super().close()

    def is_guild_enabled(self, guild_id: int) -> bool:
        with sqlite3.connect(DATABASE_PATH) as database:
            row = database.execute(
                "SELECT enabled FROM guild_settings WHERE guild_id = ?",
                (guild_id,),
            ).fetchone()
        return row is not None and bool(row[0])


bot = NicknameBot()


@bot.tree.command(
    name="setup",
    description="Enable automatic monospace nicknames for new members.",
)
@app_commands.guild_only()
@app_commands.default_permissions(manage_guild=True)
async def setup_nicknames(interaction: discord.Interaction) -> None:
    if interaction.guild is None:
        await interaction.response.send_message(
            "Run this command inside a server.",
            ephemeral=True,
        )
        return

    if not isinstance(interaction.user, discord.Member) or not (
        interaction.user.guild_permissions.manage_guild
    ):
        await interaction.response.send_message(
            "You need the Manage Server permission to run setup.",
            ephemeral=True,
        )
        return

    bot_member = interaction.guild.me
    if bot_member is None or not bot_member.guild_permissions.manage_nicknames:
        await interaction.response.send_message(
            "Give the bot the Manage Nicknames permission, then run /setup again.",
            ephemeral=True,
        )
        return

    with sqlite3.connect(DATABASE_PATH) as database:
        database.execute(
            """
            INSERT INTO guild_settings (guild_id, enabled)
            VALUES (?, 1)
            ON CONFLICT(guild_id) DO UPDATE SET enabled = 1
            """,
            (interaction.guild.id,),
        )

    await interaction.response.send_message(
        "Setup complete. New members will get an `INF NAME` monospace-style "
        "nickname when they join. Existing members are unchanged.",
        ephemeral=True,
    )


@bot.event
async def on_member_join(member: discord.Member) -> None:
    if not bot.is_guild_enabled(member.guild.id):
        return

    me = member.guild.me
    if me is None or not me.guild_permissions.manage_nicknames:
        log.error(
            "Cannot set nickname in guild %s: Manage Nicknames permission is missing.",
            member.guild.id,
        )
        return

    if me.top_role <= member.top_role:
        log.error(
            "Cannot set nickname for member %s in guild %s: bot role must be "
            "above the member's highest role.",
            member.id,
            member.guild.id,
        )
        return

    try:
        await member.edit(
            nick=make_nickname(member.name),
            reason="Automatic nickname configured with /setup",
        )
    except discord.Forbidden:
        log.exception(
            "Discord denied nickname update for member %s in guild %s.",
            member.id,
            member.guild.id,
        )
    except discord.HTTPException:
        log.exception(
            "Discord HTTP error while updating nickname for member %s in guild %s.",
            member.id,
            member.guild.id,
        )


def main() -> None:
    token = os.getenv("TOKEN")
    if not token:
        raise RuntimeError(
            "Missing TOKEN. Add your Discord bot token to the host's secret environment variables."
        )
    bot.run(token, log_handler=None)


if __name__ == "__main__":
    main()
