import discord
from discord.ext import commands
from discord import app_commands
import json, os, random, aiofiles

DATA_FILE = "data/interactions.json"

def ensure_data_file():
    """Ensure the JSON data file exists with default content."""
    if not os.path.exists(DATA_FILE):
        os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
        default = {
            "hug": ["https://media.tenor.com/hug1.gif", "https://media.tenor.com/hug2.gif"],
            "kiss": ["https://media.tenor.com/kiss1.gif", "https://media.tenor.com/kiss2.gif"],
            "pat": ["https://media.tenor.com/pat1.gif", "https://media.tenor.com/pat2.gif"],
            "snuggle": ["https://media.tenor.com/snuggle1.gif", "https://media.tenor.com/snuggle2.gif"]
        }
        with open(DATA_FILE, "w") as f:
            json.dump(default, f, indent=4)

def load_interactions():
    """Load the latest version of interaction data."""
    ensure_data_file()
    with open(DATA_FILE, "r") as f:
        return json.load(f)

class Interactions(commands.Cog):
    """🤗 Fun interaction commands like hugs, pats, and more!"""

    def __init__(self, bot):
        self.bot = bot

    async def send_interaction(self, interaction: discord.Interaction, action: str, target: discord.Member):
        data = load_interactions()
        gifs = data.get(action, [])
        gif = random.choice(gifs) if gifs else None

        # Self targeting responses
        if target.id == interaction.user.id:
            desc = f"**{interaction.user.display_name}** tried to {action} themselves... cute! 💕"
        else:
            desc = f"**{interaction.user.display_name}** gives **{target.display_name}** a {action}! 💞"

        embed = discord.Embed(
            title=f"{action.capitalize()}!",
            description=desc,
            color=discord.Color.random()
        )
        if gif:
            embed.set_image(url=gif)

        await interaction.response.send_message(embed=embed)

    # === Slash Commands ===
    @app_commands.command(name="hug", description="Give someone a warm hug!")
    async def hug(self, interaction: discord.Interaction, user: discord.Member):
        await self.send_interaction(interaction, "hug", user)

    """@app_commands.command(name="kiss", description="Give someone a sweet kiss!")
    async def kiss(self, interaction: discord.Interaction, user: discord.Member):
        await self.send_interaction(interaction, "kiss", user)

    @app_commands.command(name="pat", description="Pat someone gently on the head!")
    async def pat(self, interaction: discord.Interaction, user: discord.Member):
        await self.send_interaction(interaction, "pat", user)

    @app_commands.command(name="snuggle", description="Snuggle up with someone cozy!")
    async def snuggle(self, interaction: discord.Interaction, user: discord.Member):
        await self.send_interaction(interaction, "snuggle", user)"""


async def setup(bot):
    ensure_data_file()
    await bot.add_cog(Interactions(bot))
