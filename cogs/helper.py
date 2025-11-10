import discord
import json
import aiofiles
import os
from discord import app_commands
from discord.ext import commands, tasks
from datetime import datetime, timedelta
import asyncio

WARN_FILE = 'data/warns.json'
LOG_FILE = 'data/modlogs.json'

class helpers(commands.Cog):
    """On interaction check and delete warns over a month old"""
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.warnings = self.load_json_sync(WARN_FILE)
        self.log_channels = self.load_json_sync(LOG_FILE)
        self.auto_warn_cleanup.start()

    def load_json_sync(self, path: str):
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as file:
                try:
                    return json.load(file)
                except json.JSONDecodeError:
                    return {}
        return {}
    
    async def save_json(self, path: str, data: dict):
        async with aiofiles.open(path, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(data, indent=4, ensure_ascii=False))
    
    async def send_mod_log(self, guild: discord.Guild, embed: discord.Embed):
        guild_id = str(guild.id)
        if guild_id not in self.log_channels:
            return
        channel_id = self.log_channels[guild_id]
        channel = guild.get_channel(channel_id)
        if channel:
            await channel.send(embed=embed)

    @tasks.loop(hours=24)
    async def auto_warn_cleanup(self):
        """Runs automatically every 24 hours to remove old warnings."""
        print("[AutoWarnDel] Running daily cleanup task...")
        month_ago = datetime.now() - timedelta(days=30)
        removed_count = 0
        for guild_id, members in list(self.warnings.items()):
            guild = self.bot.get_guild(int(guild_id))
            if not guild:
                continue

            for member_id, warns in list(members.items()):
                updated_warns = []
                for warn in warns:
                    try:
                        warn_time = datetime.fromisoformat(warn["timestamp"].replace("Z", "+00:00"))
                        if warn_time > month_ago:
                            updated_warns.append(warn)
                    except Exception:
                        updated_warns.append(warn)

                if len(updated_warns) < len(warns):
                    removed_count += len(warns) - len(updated_warns)
                    self.warnings[guild_id][member_id] = updated_warns

                    member = guild.get_member(int(member_id))
                    if member:
                        embed = discord.Embed(
                            title="🗑️ Warning Auto-Deleted",
                            description=(
                                f"**User:** {member.mention} (`{member.id}`)\n"
                                f"**Reason:** Warning expired (30+ days old)\n"
                                f"**Timestamp:** <t:{int(discord.utils.utcnow().timestamp())}:F>"
                            ),
                            color=discord.Color.orange()
                        )
                        embed.set_thumbnail(url=member.display_avatar.url)
                        await self.send_mod_log(guild, embed)

        if removed_count > 0:
            await self.save_json(WARN_FILE, self.warnings)

async def setup(bot: commands.Bot):
    await bot.add_cog(helpers(bot))