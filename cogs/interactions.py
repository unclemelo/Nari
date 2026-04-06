import discord
import aiohttp
from discord.ext import commands
from discord import app_commands

ANIME_API = "https://nekos.best/api/v2"

class ReplyButton(discord.ui.View):
    def __init__(self, bot, action_name, endpoint, author, target):
        super().__init__(timeout=300)  # 5 minutes
        self.bot = bot
        self.action_name = action_name
        self.endpoint = endpoint
        self.author = author
        self.target = target

    @discord.ui.button(label="Reply back 💞", style=discord.ButtonStyle.blurple)
    async def reply_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Only target can reply
        if interaction.user.id != self.target.id:
            return await interaction.response.send_message(
                "❌ Only the mentioned user can reply back!",
                ephemeral=True
            )

        gif = await self.fetch_gif(self.endpoint)
        if not gif:
            return await interaction.response.send_message(
                "⚠️ Couldn't fetch a GIF right now.",
                ephemeral=True
            )

        embed = discord.Embed(
            description=f"💫 {interaction.user.mention} {self.action_name}s {self.author.mention} back!",
            color=discord.Color.pink()
        )
        embed.set_image(url=gif)
        embed.set_footer(
            text=f"Requested by {interaction.user}",
            icon_url=interaction.user.display_avatar.url
        )

        # 🔒 Disable the button
        button.disabled = True
        if interaction.message:
            await interaction.message.edit(view=self)

        await interaction.response.send_message(embed=embed)

        self.stop()


    async def fetch_gif(self, endpoint):
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{ANIME_API}/{endpoint}") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data["results"][0]["url"]
                return None


class Social(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def fetch_gif(self, endpoint):
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{ANIME_API}/{endpoint}") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data["results"][0]["url"]
                return None

    async def send_interaction(self, interaction, target, action, endpoint, description):
        await interaction.response.defer()
        # Detect self-target
        if target == interaction.user:
            # Fetch gif normally
            gif = await self.fetch_gif(endpoint)
            if not gif:
                return await interaction.response.send_message("⚠️ Couldn't fetch a GIF right now.", ephemeral=True)

            # Custom cute message for self-hug/pat/etc.
            self_messages = {
                "hug": "🫂 Sometimes we all need a hug... even from ourselves.",
                "pat": "🤗 It's okay to give yourself some encouragement.",
                "snuggle": "🫶 Cozying up with yourself counts too!",
                "poke": "👉 You poked yourself... why tho?",
                "highfive": "✋ High-fiving yourself? Ambitious!",
                "slap": "👋 ...why did you slap yourself?",
            }

            embed = discord.Embed(
                description=f"{interaction.user.mention} {action}s themselves!\n\n{self_messages.get(action, '')}",
                color=discord.Color.pink()
            )
            embed.set_image(url=gif)
            embed.set_footer(text=f"Requested by {interaction.user}", icon_url=interaction.user.display_avatar.url)

            # No reply button for self-actions
            return await interaction.followup.send(embed=embed)

        # ————— Normal interaction for two users ————— #
        gif = await self.fetch_gif(endpoint)
        if not gif:
            return await interaction.followup.send("⚠️ Couldn't fetch a GIF right now.", ephemeral=True)

        embed = discord.Embed(description=description, color=discord.Color.pink())
        embed.set_image(url=gif)
        embed.set_footer(text=f"Requested by {interaction.user}", icon_url=interaction.user.display_avatar.url)

        view = ReplyButton(self.bot, action, endpoint, interaction.user, target)
        await interaction.followup.send(embed=embed, view=view)


    # ——— Interaction Commands ——— #

    @app_commands.command(name="hug", description="Hug someone warmly.")
    @app_commands.describe(user="The user you want to hug")
    @app_commands.checks.cooldown(1, 300, key=lambda i: i.user.id)
    async def hug(self, interaction: discord.Interaction, user: discord.User):
        await self.send_interaction(interaction, user, "hug", "hug",
            f"🫂 {interaction.user.mention} hugs {user.mention} tightly!")

    @app_commands.command(name="pat", description="Pat someone on the head.")
    @app_commands.describe(user="The user you want to pat")
    @app_commands.checks.cooldown(1, 300, key=lambda i: i.user.id)
    async def pat(self, interaction: discord.Interaction, user: discord.User):
        await self.send_interaction(interaction, user, "pat", "pat",
            f"🤗 {interaction.user.mention} pats {user.mention} gently!")

    @app_commands.command(name="snuggle", description="Cuddle someone warmly.")
    @app_commands.describe(user="The user you want to snuggle")
    @app_commands.checks.cooldown(1, 300, key=lambda i: i.user.id)
    async def snuggle(self, interaction: discord.Interaction, user: discord.User):
        await self.send_interaction(interaction, user, "snuggle", "cuddle",
            f"🫶 {interaction.user.mention} snuggles {user.mention} warmly!")

    @app_commands.command(name="poke", description="Playfully poke another user.")
    @app_commands.describe(user="The user you want to poke")
    @app_commands.checks.cooldown(1, 300, key=lambda i: i.user.id)
    async def poke(self, interaction: discord.Interaction, user: discord.User):
        await self.send_interaction(interaction, user, "poke", "poke",
            f"👉 {interaction.user.mention} pokes {user.mention} playfully!")

    @app_commands.command(name="blush", description="React with embarrassment or shyness.")
    @app_commands.checks.cooldown(1, 300, key=lambda i: i.user.id)
    async def blush(self, interaction: discord.Interaction):
        gif = await self.fetch_gif("blush")
        if not gif:
            return await interaction.response.send_message("⚠️ Couldn't fetch a GIF right now.", ephemeral=True)
        embed = discord.Embed(description=f"😳 {interaction.user.mention} is blushing!", color=discord.Color.pink())
        embed.set_image(url=gif)
        embed.set_footer(text=f"Requested by {interaction.user}", icon_url=interaction.user.display_avatar.url)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="highfive", description="High-five a friend.")
    @app_commands.describe(user="The user you want to high-five")
    @app_commands.checks.cooldown(1, 300, key=lambda i: i.user.id)
    async def highfive(self, interaction: discord.Interaction, user: discord.User):
        await self.send_interaction(interaction, user, "highfive", "highfive",
            f"✋ {interaction.user.mention} high-fives {user.mention}!")

    @app_commands.command(name="slap", description="Slap someone (playfully or dramatically).")
    @app_commands.describe(user="The user you want to slap")
    @app_commands.checks.cooldown(1, 300, key=lambda i: i.user.id)
    async def slap(self, interaction: discord.Interaction, user: discord.User):
        await self.send_interaction(interaction, user, "slap", "slap",
            f"👋 {interaction.user.mention} slaps {user.mention}!")


async def setup(bot):
    await bot.add_cog(Social(bot))
