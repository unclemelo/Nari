import discord
from discord import app_commands
from discord.ext import commands
from util.command_checks import command_enabled

class HelpCommand(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def build_embed(self, category: str) -> discord.Embed:
        embed = discord.Embed(
            title="📖 • Nari's Commands & Features",
            color=discord.Color.magenta()
        )

        if category in ("all", "moderation"):
            embed.add_field(
                name="📌 Moderation Tools",
                value=(
                    "• `/mute <user> <duration> [reason]` — Temporarily mute a user.\n"
                    "• `/unmute <user>` — Remove a timeout from a user.\n"
                    "• `/clear <amount>` — Delete messages in bulk.\n"
                    "• `/warn <user> <reason>` — Warn a member.\n"
                    "• `/warnings <user>` — Show warnings for a user.\n"
                    "• `/delwarn <warning_id>` — Delete a specific warning.\n"
                    "• `/clearwarns <user>` — Clear all warnings for a user.\n"
                    "• `/kick <user> [reason]` — Kick a member.\n"
                    "• `/ban <user> [reason]` — Ban a member.\n"
                    "• `/unban <user>` — Unban a previously banned user.\n"
                    "• `/setlogs <channel_id>` — Set Nari’s moderation logs channel."
                ),
                inline=False
            )

        if category in ("all", "automod"):
            embed.add_field(
                name="🛡️ AutoMod Commands",
                value=(
                    "• `/setup` — Interactive AutoMod setup wizard.\n"
                    "• `/forceupdate` — Refresh AutoMod rules immediately.\n"
                    "• `/show_config` — View your AutoMod settings in an embed.\n"
                    "• `/clear_config` — Wipe AutoMod settings for the guild.\n"
                    "• `/set_log_channel` — Set the AutoMod log channel."
                ),
                inline=False
            )

        if category in ("all", "vc"):
            embed.add_field(
                name="🔊 VC Tools",
                value=(
                    "• `/move <user> <target_vc>` — Move a user to another voice channel.\n"
                    "• `/vc_mute <user>` — Server mute a user in VC.\n"
                    "• `/vc_unmute <user>` — Unmute a user in VC.\n"
                    "• `/deafen <user>` — Server deafen a user.\n"
                    "• `/undeafen <user>` — Undeafen a user.\n"
                    "• `/kickvc <user>` — Disconnect a user from voice chat."
                ),
                inline=False
            )

        if category in ("all", "utility"):
            embed.add_field(
                name="💡 Utility Commands",
                value=(
                    "• `/whois <user>` — View detailed info about a member.\n"
                    "• `/serverinfo` — Show info about the current server.\n"
                    "• `/userinfo <user>` — Display account details.\n"
                    "• `/avatar <user>` — View a user’s avatar or banner.\n"
                    "• `/ping` — Check bot latency.\n"
                    "• `/uptime` — Show how long Nari’s been online.\n"
                    "• `/botinfo` — Display system stats and command info."
                ),
                inline=False
            )

        if category in ("all", "fun", "minigames"):
            embed.add_field(
                name="🎮 Mini-Games & Fun",
                value=(
                    "• `/coinflip` — Flip a coin.\n"
                    "• `/dice [sides]` — Roll a dice (default 6 sides).\n"
                    "• `/8ball <question>` — Ask the magic 8-ball.\n"
                    "• `/rps <choice>` — Play Rock, Paper, Scissors.\n"
                    "• `/trivia` — Answer a random trivia question.\n"
                    "• `/guessnumber` — Guess a number between 1–100."
                ),
                inline=False
            )

        if category in ("all", "social"):
            embed.add_field(
                name="💞 Social & Interactions",
                value=(
                    "• `/hug <user>` — Hug someone warmly.\n"
                    "• `/kiss <user>` — Kiss someone affectionately.\n"
                    "• `/pat <user>` — Pat someone gently.\n"
                    "• `/snuggle <user>` — Cuddle with someone.\n"
                    "• `/poke <user>` — Poke another user playfully.\n"
                    "• `/blush` — Show embarrassment.\n"
                    "• `/highfive <user>` — High-five a friend.\n"
                    "• `/bonk <user>` — Bonk someone being silly.\n"
                    "• `/slap <user>` — Slap someone playfully.\n"
                    "• `/interactlist` — Show all social commands."
                ),
                inline=False
            )

        embed.set_footer(text="Need more help? Join the support server or ping a mod!")
        return embed

    @app_commands.command(name="help", description="Get a list of Nari's available commands")
    @app_commands.describe(category="Pick a category to view its commands")
    @app_commands.choices(category=[
        app_commands.Choice(name="All", value="all"),
        app_commands.Choice(name="Moderation", value="moderation"),
        app_commands.Choice(name="AutoMod", value="automod"),
        app_commands.Choice(name="VC Tools", value="vc"),
        app_commands.Choice(name="Utility", value="utility"),
        app_commands.Choice(name="Mini-Games", value="minigames"),
        app_commands.Choice(name="Social", value="social"),
        app_commands.Choice(name="Fun", value="fun"),
    ])
    @command_enabled()
    async def help(self, interaction: discord.Interaction, category: app_commands.Choice[str] = None):
        selected_category = category.value if category else "all"
        embed = self.build_embed(selected_category)
        view = HelpView(self)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=False)


class HelpView(discord.ui.View):
    def __init__(self, cog: HelpCommand):
        super().__init__(timeout=120)
        self.cog = cog

    @discord.ui.select(
        placeholder="Select a command category...",
        min_values=1,
        max_values=1,
        options=[
            discord.SelectOption(label="All", value="all", emoji="📖"),
            discord.SelectOption(label="Moderation", value="moderation", emoji="📌"),
            discord.SelectOption(label="AutoMod", value="automod", emoji="🛡️"),
            discord.SelectOption(label="VC Tools", value="vc", emoji="🔊"),
            discord.SelectOption(label="Utility", value="utility", emoji="💡"),
            discord.SelectOption(label="Mini-Games", value="minigames", emoji="🎮"),
            discord.SelectOption(label="Social", value="social", emoji="💞"),
        ]
    )
    async def select_callback(self, interaction: discord.Interaction, select: discord.ui.Select):
        value = select.values[0]
        embed = self.cog.build_embed(value)
        await interaction.response.edit_message(embed=embed, view=self)

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        try:
            await self.message.edit(view=self)
        except Exception:
            pass


async def setup(bot: commands.Bot):
    await bot.add_cog(HelpCommand(bot))
