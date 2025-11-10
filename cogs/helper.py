import discord
import json
import aiofiles
import os
from discord import app_commands
from discord.ext import commands
from datetime import timedelta
import asyncio

WARN_FILE = 'data/warns.json'

class Autodel_warns(commands.Cog):
    """On interaction check and delete warns over a month old"""
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.warnings = self.load_json_sync(WARN_FILE)

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

async def setup(bot: commands.Bot):
    await bot.add_cog(Autodel_warns(bot))