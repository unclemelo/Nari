import discord
import json
import aiofiles
import os
import re
from discord.ext import commands, tasks
from datetime import datetime, timedelta, timezone

WARN_FILE = "data/warns.json"
LOG_FILE = "data/modlogs.json"


class Helpers(commands.Cog):
    """Handles background moderation helpers like auto-deleting old warns."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.warnings = self.load_json_sync(WARN_FILE)
        self.log_channels = self.load_json_sync(LOG_FILE)
        self.auto_warn_cleanup.start()

    # === JSON Handling ===

    def load_json_sync(self, path: str) -> dict:
        """Load a JSON file synchronously with safe defaults."""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as f:
                json.dump({}, f)
            return {}

        try:
            with open(path, "r", encoding="utf-8") as file:
                return json.load(file)
        except (json.JSONDecodeError, FileNotFoundError):
            return {}

    async def save_json(self, path: str, data: dict):
        """Save data to JSON asynchronously."""
        async with aiofiles.open(path, "w", encoding="utf-8") as f:
            await f.write(json.dumps(data, indent=4, ensure_ascii=False))

    # === Logging Helpers ===

    async def send_mod_log(self, guild: discord.Guild, embed: discord.Embed):
        """Send an embed to the guild’s mod log channel if configured."""
        channel_id = self.log_channels.get(str(guild.id))
        if not channel_id:
            return

        channel = guild.get_channel(channel_id)
        if channel and channel.permissions_for(guild.me).send_messages:
            await channel.send(embed=embed)

    # === Background Task ===

    @tasks.loop(hours=24)
    async def auto_warn_cleanup(self):
        """Runs every 24 hours to remove warnings older than 30 days."""
        print("[AutoWarnDel] Running daily cleanup task...")

        month_ago = datetime.now(timezone.utc) - timedelta(days=30)
        removed_count = 0

        for guild_id, members in list(self.warnings.items()):
            guild = self.bot.get_guild(int(guild_id))
            if not guild:
                continue

            for member_id, warns in list(members.items()):
                valid_warns = []

                for warn in warns:
                    try:
                        raw_time = warn["timestamp"].replace("Z", "+00:00")

                        # Fix non-padded months/days (e.g. 2024-1-9 → 2024-01-09)
                        if re.match(r"^\d{4}-\d{1,2}-\d{1,2}T", raw_time):
                            parts = raw_time.split("T")
                            date_parts = parts[0].split("-")
                            if len(date_parts) == 3:
                                year, month, day = date_parts
                                raw_time = f"{int(year):04d}-{int(month):02d}-{int(day):02d}T{parts[1]}"

                        warn_time = datetime.fromisoformat(raw_time)
                        if warn_time.tzinfo is None:
                            warn_time = warn_time.replace(tzinfo=timezone.utc)

                        if warn_time > month_ago:
                            valid_warns.append(warn)

                    except (KeyError, ValueError):
                        # If timestamp invalid or missing, keep it (safe fallback)
                        valid_warns.append(warn)

                if len(valid_warns) < len(warns):
                    diff = len(warns) - len(valid_warns)
                    removed_count += diff
                    self.warnings[guild_id][member_id] = valid_warns

                    member = guild.get_member(int(member_id))
                    if member:
                        embed = discord.Embed(
                            title="🗑️ Warning Auto-Deleted",
                            description=(
                                f"**User:** {member.mention} (`{member.id}`)\n"
                                f"**Reason:** Warning expired (30+ days old)\n"
                                f"**Removed:** `{diff}` warning(s)\n"
                                f"**Time:** <t:{int(discord.utils.utcnow().timestamp())}:F>"
                            ),
                            color=discord.Color.orange(),
                        )
                        embed.set_thumbnail(url=member.display_avatar.url)
                        await self.send_mod_log(guild, embed)

        if removed_count > 0:
            await self.save_json(WARN_FILE, self.warnings)
            print(f"[AutoWarnDel] Removed {removed_count} expired warnings.")
        else:
            print("[AutoWarnDel] No expired warnings found.")

    @auto_warn_cleanup.before_loop
    async def before_cleanup(self):
        """Wait until the bot is ready before starting the task."""
        await self.bot.wait_until_ready()

    def cog_unload(self):
        """Ensure background task stops when cog unloads."""
        self.auto_warn_cleanup.cancel()


async def setup(bot: commands.Bot):
    await bot.add_cog(Helpers(bot))
