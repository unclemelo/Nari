# bot.py — Nari v2.0 (Terminal Edition)
# ──────────────────────────────────────────────
# Terminal-only version styled like Watch_Dogs 2

import discord
import os
import asyncio
from discord.ext import commands, tasks
from dotenv import load_dotenv
from colorama import Fore, Style, init
from datetime import datetime

init(autoreset=True)

# ──────────────────────────────────────────────
# Load environment
load_dotenv()
TOKEN = os.getenv("TOKEN")

# ──────────────────────────────────────────────
# Bot setup
intents = discord.Intents.all()
intents.members = True
client = commands.AutoShardedBot(command_prefix="n!", shard_count=1, intents=intents)
client.remove_command("help")

# ──────────────────────────────────────────────
# Terminal Style Helpers
def terminal_banner():
    print(f"""{Fore.MAGENTA}{Style.BRIGHT}
╔════════════════════════════════════════════════╗
║               NARI SYSTEM v0.7                 ║
╚════════════════════════════════════════════════╝
    """)

def log(msg: str, level: str = "info"):
    time = datetime.now().strftime("%H:%M:%S")
    levels = {
        "info": Fore.CYAN + "[INFO]",
        "success": Fore.GREEN + "[SUCCESS]",
        "warn": Fore.YELLOW + "[WARN]",
        "error": Fore.RED + "[ERROR]",
        "critical": Fore.MAGENTA + "[CRITICAL]",
    }
    tag = levels.get(level, Fore.WHITE + "[LOG]")
    print(f"{Fore.BLACK}[{time}]{Style.RESET_ALL} {tag} {Fore.WHITE}{msg}{Style.RESET_ALL}")

# ──────────────────────────────────────────────
# Status messages
status_messages = [
    "🍋 | I'm a goofer. :3",
    "⚙️ | Type /help for commands!"
]
status_index = 0

@tasks.loop(seconds=10)
async def update_status_loop():
    global status_index

    try:
        guild_count = len(client.guilds)
        latency = round(client.latency * 1000)
        latency_message = "📡 | Ping: 999+ms" if latency > 999 else f"📡 | Ping: {latency}ms"
        all_statuses = status_messages + [latency_message]
        current = all_statuses[status_index % len(all_statuses)].format(guild_count=guild_count)
        status_index += 1
        await client.change_presence(
            status=discord.Status.dnd,
            activity=discord.Activity(type=discord.ActivityType.watching, name=current)
        )
    except Exception as e:
        log(f"Status update failed: {e}", "error")

# ──────────────────────────────────────────────
# Events
@client.event
async def on_ready():
    terminal_banner()
    if client.user:
        log(f"System online as {client.user} ({client.user.id})", "success")
    log(f"Connected to {len(client.guilds)} guilds.", "info")

    try:
        synced = await client.tree.sync()
        log(f"Slash commands synced: {len(synced)}", "success")
    except Exception as e:
        log(f"Command sync failed: {e}", "error")

    if not update_status_loop.is_running():
        update_status_loop.start()

# ──────────────────────────────────────────────
# Cog loader
async def load_cogs():
    loaded = []
    failed = []

    for filename in os.listdir("cogs"):
        if filename.endswith(".py"):
            name = filename[:-3]
            try:
                await client.load_extension(f"cogs.{name}")
                loaded.append(filename)
            except Exception as e:
                failed.append((filename, str(e)))

    if loaded:
        log("Loaded cogs:", "success")
        for file in loaded:
            print(Fore.GREEN + f"   → {file}")
    if failed:
        log("Failed to load cogs:", "error")
        for file, error in failed:
            print(Fore.RED + f"   → {file}: {error}")

# ──────────────────────────────────────────────
# Main entry
async def main():
    try:
        await load_cogs()
    except Exception as e:
        log(f"Critical error loading cogs: {e}", "critical")

    try:
        log("Starting Nari client...", "info")
        if not TOKEN:
            raise RuntimeError("TOKEN is not set in environment variables")
        await client.start(TOKEN)
    except KeyboardInterrupt:
        log("Manual shutdown requested (Ctrl+C)", "warn")
        await client.close()
    except Exception as e:
        log(f"Failed to start bot: {e}", "critical")

if __name__ == "__main__":
    asyncio.run(main())
