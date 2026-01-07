import random
import time
import discord
from discord.ext import commands

class Clicker(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.cooldowns = {}  # user_id -> last trigger time

        self.triggers = {"click", "clicker", "click!"}

        self.dog_responses = [
            "🐶 *woof!*",
            "🐶 *bark bark!*",
            "🐶 tail wagging aggressively",
            "🐶 brings you a stick 🦴",
            "🐶 sits patiently waiting for pats"
        ]

        self.cat_responses = [
            "🐱 *meow*",
            "🐱 *mrrp*",
            "🐱 *purr*",
            "🐱 knocks something off the table",
            "🐱 stares at you ominously 👁️"
        ]

        self.reactions = ["🐾", "🐶", "🐱", "🦴", "🐟"]

        self.call_to_actions = [
            "Pat them back 👀",
            "Say `pspsps`",
            "Throw the stick!",
            "Give them a treat 🍖"
        ]

        self.cooldown_seconds = 5

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        content = message.content.lower()
        if not any(trigger in content for trigger in self.triggers):
            return

        # Cooldown check
        now = time.time()
        last = self.cooldowns.get(message.author.id, 0)
        if now - last < self.cooldown_seconds:
            return
        self.cooldowns[message.author.id] = now

        # Pick animal
        is_dog = random.random() < 0.5
        response = random.choice(self.dog_responses if is_dog else self.cat_responses)

        # Occasionally add engagement text
        if random.random() < 0.35:
            response += f"\n*{random.choice(self.call_to_actions)}*"

        # Reply instead of send (feels personal)
        await message.reply(response, mention_author=False)

        # Sometimes react too
        if random.random():
            try:
                await message.add_reaction(random.choice(self.reactions))
            except discord.HTTPException:
                pass

        await self.bot.process_commands(message)

async def setup(bot: commands.Bot):
    await bot.add_cog(Clicker(bot))
