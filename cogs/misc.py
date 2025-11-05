import discord
import asyncio
import random
import json
import os
from discord.ext import commands, tasks
from discord import app_commands
from typing import List
from discord.ext.commands import cooldown, BucketType
from datetime import timedelta
from util.command_checks import command_enabled
from util.booster_cooldown import BoosterCooldownManager

cooldown_manager_user = BoosterCooldownManager(rate=1, per=600, bucket_type="user")
cooldown_manager_guild = BoosterCooldownManager(rate=1, per=600, bucket_type="guild")


class MISC(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    ## Removed /prank & /chaos ##


async def setup(bot: commands.Bot):
    await bot.add_cog(MISC(bot))