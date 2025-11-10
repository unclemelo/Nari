import discord
import json
import aiofiles
import os
from discord import app_commands
from discord.ext import commands
from datetime import timedelta
from util.command_checks import command_enabled
import asyncio

WARN_FILE = 'data/warns.json'
LOG_FILE = 'data/modlogs.json'


class Moderation(commands.Cog):
    """🛠️ Nari's Moderation Tools"""
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.warnings = self.load_json_sync(WARN_FILE)
        self.log_channels = self.load_json_sync(LOG_FILE)

    # ───────────────────────────────────────────────
    # Utility methods
    # ───────────────────────────────────────────────
    def load_json_sync(self, path: str):
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as file:
                try:
                    return json.load(file)
                except json.JSONDecodeError:
                    return {}
        return {}

    async def save_json(self, path: str, data: dict):
        async with aiofiles.open(path, 'w', encoding='utf-8') as file:
            await file.write(json.dumps(data, indent=4))

    def ensure_guild_user(self, guild_id: str, user_id: str):
        self.warnings.setdefault(guild_id, {}).setdefault(user_id, [])

    def build_embed(self, title: str, description: str = None, color: discord.Color = discord.Color.blurple()):
        embed = discord.Embed(title=title, description=description, color=color)
        embed.set_footer(text="Nari Moderation System")
        return embed

    async def send_mod_log(self, guild: discord.Guild, embed: discord.Embed):
        guild_id = str(guild.id)
        if guild_id not in self.log_channels:
            return
        channel_id = self.log_channels[guild_id]
        channel = guild.get_channel(channel_id)
        if channel:
            await channel.send(embed=embed)

    async def dm_user(self, member: discord.Member, embed: discord.Embed):
        try:
            await member.send(embed=embed)
        except discord.Forbidden:
            pass

    async def respond_and_delete(
        self,
        interaction: discord.Interaction,
        content=None,
        embed: discord.Embed = None,
        ephemeral=True,
        delay=5
    ):
        """
        Respond immediately to an interaction, then auto-delete after a delay.
        Supports text or embed.
        """
        try:
            await interaction.response.send_message(content=content, embed=embed, ephemeral=ephemeral)
        except discord.errors.InteractionResponded:
            # fallback if already responded
            await interaction.followup.send(content=content, embed=embed, ephemeral=ephemeral)

        # Delete after delay
        try:
            msg = await interaction.original_response()
            await msg.delete(delay=delay)
        except Exception:
            pass

    # ───────────────────────────────────────────────
    # Configuration command
    # ───────────────────────────────────────────────
    @app_commands.command(name="setlogs", description="Set the channel for moderation logs.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setlogs_cmd(self, interaction: discord.Interaction, channel: discord.TextChannel):
        guild_id = str(interaction.guild.id)
        self.log_channels[guild_id] = channel.id
        await self.save_json(LOG_FILE, self.log_channels)

        embed = self.build_embed(
            "📝 Mod-Log Channel Set",
            f"Logs will now be sent to {channel.mention}.",
            discord.Color.green()
        )
        await self.respond_and_delete(interaction, embed=embed)

    # ───────────────────────────────────────────────
    # Moderation Commands
    # ───────────────────────────────────────────────
    @app_commands.command(name="warnings", description="Check all warnings for a user.")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def warnings_cmd(self, interaction: discord.Interaction, member: discord.Member):
        guild_id, user_id = str(interaction.guild.id), str(member.id)
        self.ensure_guild_user(guild_id, user_id)

        warns = self.warnings[guild_id][user_id]
        if not warns:
            return await self.respond_and_delete(
                interaction,
                embed=self.build_embed("✅ No Warnings", f"{member.mention} has no warnings.")
            )

        description = "\n\n".join(
            [f"**#{i+1}** — **Reason:** {w['reason']}\n**Moderator:** {w['moderator']}\n**Date:** <t:{int(discord.utils.parse_time(w['timestamp']).timestamp())}:F>"
             for i, w in enumerate(warns)]
        )

        embed = self.build_embed(f"⚠️ Warnings for {member.display_name}", description, discord.Color.yellow())
        await self.respond_and_delete(interaction, embed=embed)

    @app_commands.command(name="delwarn", description="Delete a specific warning from a user.")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def delwarn_cmd(self, interaction: discord.Interaction, member: discord.Member, index: int):
        guild_id, user_id = str(interaction.guild.id), str(member.id)
        self.ensure_guild_user(guild_id, user_id)

        warns = self.warnings[guild_id][user_id]
        if not warns:
            return await self.respond_and_delete(interaction, content=f"{member.mention} has no warnings.")

        if index < 1 or index > len(warns):
            return await self.respond_and_delete(interaction, content=f"Invalid warning number. They have {len(warns)} warnings.")

        removed = warns.pop(index - 1)
        await self.save_json(WARN_FILE, self.warnings)

        log_embed = self.build_embed(
            "🗑️ Warning Deleted",
            f"**User:** {member.mention} (`{member.id}`)\n"
            f"**Moderator:** {interaction.user.mention} (`{interaction.user.id}`)\n"
            f"**Removed Reason:** {removed['reason']}\n"
            f"**Timestamp:** <t:{int(discord.utils.utcnow().timestamp())}:F>",
            discord.Color.orange()
        )
        log_embed.set_thumbnail(url=member.display_avatar.url)
        await self.send_mod_log(interaction.guild, log_embed)

        await self.respond_and_delete(interaction, embed=self.build_embed(f"🗑️ Removed warning #{index} from {member.display_name}.", color=discord.Color.orange()))

    @app_commands.command(name="clearwarns", description="Clear all warnings from a user.")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def clearwarns_cmd(self, interaction: discord.Interaction, member: discord.Member):
        guild_id, user_id = str(interaction.guild.id), str(member.id)
        self.ensure_guild_user(guild_id, user_id)

        if not self.warnings[guild_id][user_id]:
            return await self.respond_and_delete(interaction, content=f"{member.mention} has no warnings.")

        count = len(self.warnings[guild_id][user_id])
        self.warnings[guild_id][user_id] = []
        await self.save_json(WARN_FILE, self.warnings)

        log_embed = self.build_embed(
            "🧹 Warnings Cleared",
            f"**User:** {member.mention} (`{member.id}`)\n"
            f"**Moderator:** {interaction.user.mention} (`{interaction.user.id}`)\n"
            f"**Cleared:** {count} warnings\n"
            f"**Timestamp:** <t:{int(discord.utils.utcnow().timestamp())}:F>",
            discord.Color.green()
        )
        log_embed.set_thumbnail(url=member.display_avatar.url)
        await self.send_mod_log(interaction.guild, log_embed)

        await self.respond_and_delete(interaction, embed=self.build_embed(f"🧹 Cleared {count} warnings from {member.display_name}.", color=discord.Color.green()))

    @app_commands.command(name="mute", description="Temporarily mute a user using Discord's timeout system.")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def mute_cmd(self, interaction: discord.Interaction, member: discord.Member, minutes: int, reason: str = "No reason provided"):
        if member.top_role >= interaction.user.top_role:
            return await self.respond_and_delete(interaction, content="You can't mute someone with an equal or higher role.")

        try:
            await member.timeout(discord.utils.utcnow() + timedelta(minutes=minutes), reason=reason)

            dm_embed = self.build_embed("🔇 You’ve been muted!", f"Server: **{interaction.guild.name}**\nReason: {reason}\nDuration: {minutes} minutes.")
            await self.dm_user(member, dm_embed)

            log_embed = self.build_embed(
                "🤐 Member Muted",
                f"**User:** {member.mention} (`{member.id}`)\n"
                f"**Moderator:** {interaction.user.mention} (`{interaction.user.id}`)\n"
                f"**Reason:** {reason}\n"
                f"**Duration:** {minutes} minutes\n"
                f"**Timestamp:** <t:{int(discord.utils.utcnow().timestamp())}:F>",
                discord.Color.blue()
            )
            log_embed.set_thumbnail(url=member.display_avatar.url)
            await self.send_mod_log(interaction.guild, log_embed)

            await self.respond_and_delete(interaction, embed=self.build_embed(f"🤐 {member.display_name} muted!", f"Duration: {minutes} minutes", discord.Color.blue()))
        except Exception as e:
            await self.respond_and_delete(interaction, content=f"❌ Failed to mute {member.mention}.\n`{e}`")

    @app_commands.command(name="warn", description="Warn a user and log it.")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def warn_cmd(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
        if member.bot:
            return await self.respond_and_delete(interaction, content="You cannot warn a bot.")

        guild_id, user_id = str(interaction.guild.id), str(member.id)
        self.ensure_guild_user(guild_id, user_id)
        self.warnings[guild_id][user_id].append({
            "reason": reason,
            "moderator": str(interaction.user),
            "timestamp": discord.utils.utcnow().isoformat()
        })
        await self.save_json(WARN_FILE, self.warnings)

        await self.respond_and_delete(interaction, embed=self.build_embed(f"⚠️ Warned {member.display_name}", f"Reason: {reason}", discord.Color.yellow()))

        dm_embed = self.build_embed("⚠️ You’ve received a warning!", f"Server: **{interaction.guild.name}**\nReason: {reason}")
        await self.dm_user(member, dm_embed)

        log_embed = self.build_embed(
            "⚠️ User Warned",
            f"**User:** {member.mention} (`{member.id}`)\n"
            f"**Moderator:** {interaction.user.mention} (`{interaction.user.id}`)\n"
            f"**Reason:** {reason}\n"
            f"**Timestamp:** <t:{int(discord.utils.utcnow().timestamp())}:F>",
            discord.Color.yellow()
        )
        log_embed.set_thumbnail(url=member.display_avatar.url)
        await self.send_mod_log(interaction.guild, log_embed)

    @app_commands.command(name="kick", description="Kick a user from the server.")
    @app_commands.checks.has_permissions(kick_members=True)
    async def kick_cmd(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
        if member.top_role >= interaction.user.top_role:
            return await self.respond_and_delete(interaction, content="You can't kick someone with an equal or higher role.")

        try:
            dm_embed = self.build_embed("🥾 You’ve been kicked!", f"Server: **{interaction.guild.name}**\nReason: {reason}")
            await self.dm_user(member, dm_embed)
            await member.kick(reason=reason)

            log_embed = self.build_embed(
                "🥾 Member Kicked",
                f"**User:** {member.mention} (`{member.id}`)\n"
                f"**Moderator:** {interaction.user.mention} (`{interaction.user.id}`)\n"
                f"**Reason:** {reason}\n"
                f"**Timestamp:** <t:{int(discord.utils.utcnow().timestamp())}:F>",
                discord.Color.orange()
            )
            log_embed.set_thumbnail(url=member.display_avatar.url)
            await self.send_mod_log(interaction.guild, log_embed)

            await self.respond_and_delete(interaction, embed=self.build_embed(f"🥾 {member.display_name} kicked!", f"Reason: {reason}", discord.Color.orange()))
        except Exception as e:
            await self.respond_and_delete(interaction, content=f"❌ Failed to kick {member.mention}.\n`{e}`")

    @app_commands.command(name="ban", description="Ban a user from the server.")
    @app_commands.checks.has_permissions(ban_members=True)
    async def ban_cmd(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
        if member.top_role >= interaction.user.top_role:
            return await self.respond_and_delete(interaction, content="You can't ban someone with an equal or higher role.")

        try:
            dm_embed = self.build_embed("🔨 You’ve been banned!", f"Server: **{interaction.guild.name}**\nReason: {reason}")
            await self.dm_user(member, dm_embed)
            await member.ban(reason=reason)

            log_embed = self.build_embed(
                "🔨 Member Banned",
                f"**User:** {member.mention} (`{member.id}`)\n"
                f"**Moderator:** {interaction.user.mention} (`{interaction.user.id}`)\n"
                f"**Reason:** {reason}\n"
                f"**Timestamp:** <t:{int(discord.utils.utcnow().timestamp())}:F>",
                discord.Color.red
            )
            log_embed.set_thumbnail(url=member.display_avatar.url)
            await self.send_mod_log(interaction.guild, log_embed)

            await self.respond_and_delete(interaction, embed=self.build_embed(f"🔨 {member.display_name} banned!", f"Reason: {reason}", discord.Color.red()))
        except Exception as e:
            await self.respond_and_delete(interaction, content=f"❌ Failed to ban {member.mention}.\n`{e}`")

    @app_commands.command(name="unban", description="Unban a user by their ID.")
    @app_commands.checks.has_permissions(ban_members=True)
    async def unban_cmd(self, interaction: discord.Interaction, user_id: int):
        try:
            user = await self.bot.fetch_user(user_id)
            await interaction.guild.unban(user)

            log_embed = self.build_embed(
                "✨ User Unbanned",
                f"**User:** {user} (`{user.id}`)\n"
                f"**Moderator:** {interaction.user.mention} (`{interaction.user.id}`)\n"
                f"**Timestamp:** <t:{int(discord.utils.utcnow().timestamp())}:F>",
                discord.Color.green()
            )
            await self.send_mod_log(interaction.guild, log_embed)

            await self.respond_and_delete(interaction, embed=self.build_embed(f"✨ {user.name} unbanned!", "Let's hope they behave this time.", discord.Color.green()))
        except Exception as e:
            await self.respond_and_delete(interaction, content=f"❌ Couldn't unban that user.\n`{e}`")


async def setup(bot: commands.Bot):
    await bot.add_cog(Moderation(bot))
