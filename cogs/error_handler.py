import discord
import traceback
import logging
import sys
import os
import asyncio
import aiohttp
from discord import app_commands, Interaction
from discord.ext import commands
from colorama import Fore, Style, init
from dotenv import load_dotenv
from typing import Type

load_dotenv()
WEBHOOK_URL = os.getenv("WEBHOOK")

init(autoreset=True)

# ----------------------------
# Logging (configured once)
# ----------------------------
logger = logging.getLogger("discord_bot")
logger.setLevel(logging.INFO)

if not logger.handlers:
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        "%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.FileHandler("bot_errors.log", encoding="utf-8")
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler(sys.__stdout__)
    stream_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)


class ErrorHandler(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.bot.tree.on_error = self.on_app_command_error

        sys.excepthook = self.handle_uncaught_exception
        self._last_webhook_send = 0.0  # rate limit webhook spam

    # ----------------------------
    # Slash command error handler
    # ----------------------------
    async def on_app_command_error(self, interaction: Interaction, error: Exception):
        # Unwrap invoke errors
        if isinstance(error, app_commands.CommandInvokeError):
            error = error.original

        error_type = type(error).__name__
        trace = "".join(traceback.format_exception(type(error), error, error.__traceback__))

        user_message = self.get_user_message(error)

        # Respond safely
        await self.safe_respond(interaction, user_message)

        # Context info
        user = interaction.user
        command = interaction.command.name if interaction.command else "Unknown"
        guild = interaction.guild.name if interaction.guild else "DMs"

        # Console output
        print(
            f"\n{Fore.RED}{Style.BRIGHT}[SLASH ERROR] {Fore.YELLOW}{error_type}\n"
            f"{Fore.CYAN}Command: {Fore.WHITE}/{command}\n"
            f"{Fore.CYAN}User: {Fore.WHITE}{user} ({user.id})\n"
            f"{Fore.CYAN}Guild: {Fore.WHITE}{guild}\n"
            f"{Fore.MAGENTA}Traceback:\n{Fore.WHITE}{trace}"
        )

        logger.error(f"[SLASH ERROR] {error_type} in /{command}\n{trace}")

        # Only webhook unexpected errors
        if not self.is_expected_error(error):
            await self.send_to_webhook(
                f"**[SLASH ERROR]** `{error_type}` in `/{command}`\n```py\n{trace[:1900]}\n```"
            )

    # ----------------------------
    # Error classification
    # ----------------------------
    def get_user_message(self, error: Exception) -> str:
        error_map: dict[Type[Exception], str] = {
            app_commands.CommandOnCooldown:
                "⌛ This command is on cooldown. Try again later.",
            app_commands.MissingPermissions:
                "🚫 You do not have permission to use this command.",
            app_commands.BotMissingPermissions:
                "⚠️ I’m missing required permissions.",
            app_commands.NoPrivateMessage:
                "📵 This command can’t be used in DMs.",
            app_commands.CheckFailure:
                "❌ You don’t meet the requirements for this command.",
        }

        if isinstance(error, app_commands.MissingRole):
            return f"🔐 You must have the `{error.missing_role}` role."

        if isinstance(error, app_commands.MissingAnyRole):
            roles = ", ".join(f"`{r}`" for r in error.missing_roles)
            return f"🔐 You need one of these roles: {roles}"

        for exc, message in error_map.items():
            if isinstance(error, exc):
                return message

        return "❌ An unexpected error occurred. The developers have been notified.\nIf you wanna give us more details feel free to join our support server\nhttps://discord.gg/Jd5kSsvb56"

    def is_expected_error(self, error: Exception) -> bool:
        return isinstance(
            error,
            (
                app_commands.CommandOnCooldown,
                app_commands.MissingPermissions,
                app_commands.BotMissingPermissions,
                app_commands.CheckFailure,
                app_commands.NoPrivateMessage,
                app_commands.MissingRole,
                app_commands.MissingAnyRole,
            ),
        )

    # ----------------------------
    # Safe interaction responses
    # ----------------------------
    async def safe_respond(self, interaction: Interaction, message: str):
        try:
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)
        except discord.HTTPException:
            pass

    # ----------------------------
    # Uncaught exceptions
    # ----------------------------
    def handle_uncaught_exception(self, exctype, value, tb):
        if exctype is KeyboardInterrupt:
            print(f"{Fore.YELLOW}[!] KeyboardInterrupt — shutting down cleanly.")
            return

        trace = "".join(traceback.format_exception(exctype, value, tb))

        print(
            f"\n{Fore.RED}{Style.BRIGHT}[CRITICAL ERROR] {Fore.YELLOW}{exctype.__name__}\n"
            f"{Fore.MAGENTA}Traceback:\n{Fore.WHITE}{trace}"
        )

        logger.critical(f"Uncaught exception:\n{trace}")

        asyncio.create_task(
            self.send_to_webhook(
                f"**[CRITICAL ERROR]** `{exctype.__name__}`\n```py\n{trace[:1900]}\n```"
            )
        )

    # ----------------------------
    # Async webhook sender
    # ----------------------------
    async def send_to_webhook(self, content: str):
        if not WEBHOOK_URL:
            return

        # simple rate limit (1 message / 5s)
        now = asyncio.get_event_loop().time()
        if now - self._last_webhook_send < 5:
            return
        self._last_webhook_send = now

        payload = {
            "content": content,
            "username": "Nari Console",
            "avatar_url": "https://www.setra.com/hubfs/Sajni/crc_error.jpg",
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(WEBHOOK_URL, json=payload) as resp:
                    if resp.status >= 400:
                        logger.error(f"Webhook failed with status {resp.status}")
        except Exception as e:
            logger.error(f"Failed to send webhook: {e}")


async def setup(bot: commands.Bot):
    await bot.add_cog(ErrorHandler(bot))
