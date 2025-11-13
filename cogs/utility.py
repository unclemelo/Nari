import discord, platform, psutil, datetime, time
from discord.ext import commands
from discord import app_commands

class Utility(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.start_time = time.time()

    # === Helper: format uptime nicely ===
    def format_uptime(self):
        delta = time.time() - self.start_time
        days, remainder = divmod(int(delta), 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{days}d {hours}h {minutes}m {seconds}s"

    # === /ping ===
    @app_commands.command(name="ping", description="Check the bot's latency.")
    async def ping(self, interaction: discord.Interaction):
        latency = round(self.bot.latency * 1000)
        await interaction.response.send_message(
            embed=discord.Embed(
                title="🏓 Pong!",
                description=f"Latency: `{latency}ms`",
                color=discord.Color.blurple()
            )
        )

    # === /uptime ===
    @app_commands.command(name="uptime", description="See how long Nari has been online.")
    async def uptime(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🕒 Bot Uptime",
            description=f"Nari has been running for **{self.format_uptime()}**.",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)

    # === /botinfo ===
    @app_commands.command(name="botinfo", description="Show info about Nari and system stats.")
    async def botinfo(self, interaction: discord.Interaction):
        mem = psutil.virtual_memory()
        cpu = psutil.cpu_percent()
        uptime = self.format_uptime()

        embed = discord.Embed(
            title="🤖 Nari Bot Info",
            color=discord.Color.magenta()
        )
        embed.add_field(name="Developer", value="**Melo & Kiwi**", inline=True)
        embed.add_field(name="Library", value=f"discord.py `{discord.__version__}`", inline=True)
        embed.add_field(name="Python", value=f"`{platform.python_version()}`", inline=True)
        embed.add_field(name="CPU Usage", value=f"`{cpu}%`", inline=True)
        embed.add_field(name="RAM Usage", value=f"`{mem.percent}%`", inline=True)
        embed.add_field(name="Uptime", value=f"`{uptime}`", inline=False)
        embed.add_field(name="Servers", value=f"`{len(self.bot.guilds)}`", inline=True)
        embed.add_field(name="Users", value=f"`{len(self.bot.users)}`", inline=True)
        embed.add_field(name="Commands", value=f"`{len(self.bot.tree.get_commands())}`", inline=True)

        embed.set_footer(text="Nari — Keeping your community comfy 💜")
        await interaction.response.send_message(embed=embed)

    # === /whois ===
    @app_commands.command(name="whois", description="View detailed info about a member.")
    async def whois(self, interaction: discord.Interaction, user: discord.User):
        member = interaction.guild.get_member(user.id)
        embed = discord.Embed(
            title=f"🔍 Who is {user.name}?",
            color=discord.Color.magenta(),
            timestamp=datetime.datetime.utcnow()
        )

        embed.set_thumbnail(url=user.avatar.url if user.avatar else user.default_avatar.url)
        embed.add_field(name="Username", value=f"{user}", inline=True)
        embed.add_field(name="ID", value=f"`{user.id}`", inline=True)
        embed.add_field(name="Created", value=discord.utils.format_dt(user.created_at, style='R'), inline=True)

        if member:
            embed.add_field(name="Joined Server", value=discord.utils.format_dt(member.joined_at, style='R'), inline=True)
            embed.add_field(name="Roles", value=", ".join([r.mention for r in member.roles[1:]]) or "None", inline=False)
        else:
            embed.add_field(name="Member Status", value="Not in this server", inline=False)

        await interaction.response.send_message(embed=embed)

    # === /userinfo ===
    @app_commands.command(name="userinfo", description="Display user stats, mutual servers, etc.")
    async def userinfo(self, interaction: discord.Interaction, user: discord.User):
        mutual_guilds = len([g for g in self.bot.guilds if g.get_member(user.id)])
        embed = discord.Embed(
            title=f"🧾 User Info — {user.name}",
            color=discord.Color.blurple()
        )
        embed.set_thumbnail(url=user.avatar.url if user.avatar else user.default_avatar.url)
        embed.add_field(name="Username", value=f"{user}", inline=True)
        embed.add_field(name="ID", value=f"`{user.id}`", inline=True)
        embed.add_field(name="Account Created", value=discord.utils.format_dt(user.created_at, style='F'), inline=False)
        embed.add_field(name="Mutual Servers", value=f"`{mutual_guilds}`", inline=True)
        embed.set_footer(text="Requested by " + interaction.user.name)
        await interaction.response.send_message(embed=embed)

    # === /avatar ===
    @app_commands.command(name="avatar", description="Get a user's avatar or banner.")
    async def avatar(self, interaction: discord.Interaction, user: discord.User = None):
        user = user or interaction.user
        embed = discord.Embed(
            title=f"🖼️ Avatar — {user.name}",
            color=discord.Color.random()
        )
        embed.set_image(url=user.avatar.url if user.avatar else user.default_avatar.url)
        await interaction.response.send_message(embed=embed)

    # === /serverinfo ===
    @app_commands.command(name="serverinfo", description="Show info about the current server.")
    async def serverinfo(self, interaction: discord.Interaction):
        guild = interaction.guild
        embed = discord.Embed(
            title=f"🏰 Server Info — {guild.name}",
            color=discord.Color.gold()
        )
        embed.set_thumbnail(url=guild.icon.url if guild.icon else discord.Embed.Empty)
        embed.add_field(name="Server ID", value=f"`{guild.id}`", inline=True)
        embed.add_field(name="Owner", value=f"{guild.owner.mention}", inline=True)
        embed.add_field(name="Members", value=f"`{guild.member_count}`", inline=True)
        embed.add_field(name="Channels", value=f"`{len(guild.channels)}`", inline=True)
        embed.add_field(name="Roles", value=f"`{len(guild.roles)}`", inline=True)
        embed.add_field(name="Created", value=discord.utils.format_dt(guild.created_at, style='F'), inline=False)
        embed.set_footer(text=f"Requested by {interaction.user}")
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(Utility(bot))
