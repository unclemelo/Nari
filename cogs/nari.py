import discord
from discord.ext import commands, tasks
import psutil
import platform
import time

CHANNEL_ID = 1461990186245296329
MESSAGE_ID = 1461994336718950410


class Nari(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.start_time = time.time()
        self.update_stats.start()

    async def cog_unload(self):
        self.update_stats.cancel()

    def format_uptime(self):
        seconds = int(time.time() - self.start_time)
        mins, sec = divmod(seconds, 60)
        hrs, mins = divmod(mins, 60)
        days, hrs = divmod(hrs, 24)
        return f"{days}d {hrs}h {mins}m {sec}s"

    def build_embed(self):
        process = psutil.Process()
        mem = process.memory_info().rss / 1024 / 1024

        embed = discord.Embed(
            title="🤖 Nari — Bot Stats",
            color=discord.Color.purple()
        )

        embed.add_field(name="Servers", value=str(len(self.bot.guilds)))
        embed.add_field(name="Users", value=str(len(self.bot.users)))
        embed.add_field(name="Latency", value=f"{round(self.bot.latency * 1000)}ms")

        embed.add_field(name="Uptime", value=self.format_uptime(), inline=False)
        embed.add_field(name="Memory Usage", value=f"{mem:.2f} MB")
        embed.add_field(name="Python", value=platform.python_version())
        embed.add_field(name="discord.py", value=discord.__version__)

        embed.set_footer(text="Updates every 60 seconds")

        return embed

    @tasks.loop(minutes=1)
    async def update_stats(self):
        await self.bot.wait_until_ready()
        channel = self.bot.get_channel(CHANNEL_ID)

        if not isinstance(channel, discord.TextChannel):
            return

        embed = self.build_embed()

        global MESSAGE_ID

        try:
            if MESSAGE_ID:
                message = await channel.fetch_message(MESSAGE_ID)
                await message.edit(embed=embed)
            else:
                message = await channel.send(embed=embed)
                MESSAGE_ID = message.id
                print(f"[Nari] Stats message created: {MESSAGE_ID}")

        except discord.NotFound:
            message = await channel.send(embed=embed)
            MESSAGE_ID = message.id

    @update_stats.before_loop
    async def before_update(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(Nari(bot))
