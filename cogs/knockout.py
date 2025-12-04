# royale.py
import discord, random, asyncio, json, os
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timedelta
from util.command_checks import command_enabled
from util.booster_cooldown import BoosterCooldownManager

# === Configuration ===
CONFIG_FILE = "data/royale_config.json"
STATS_FILE = "data/royal_stats.json"
WEAPON_FILE = "data/weapons.json"
DEATHLOG_FILE = "data/deathlog.json"

# === Default Config Template ===
DEFAULT_CONFIG = {
    "knockout_cooldown": 1800,
    "revive_cooldown": 600
}

# Load or create config
if not os.path.exists(CONFIG_FILE):
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(DEFAULT_CONFIG, f, indent=4)

with open(CONFIG_FILE, "r") as f:
    config = json.load(f)

# Cooldowns
cooldown_knockout = BoosterCooldownManager(rate=1, per=config.get("knockout_cooldown", 900), bucket_type="user")
cooldown_revive = BoosterCooldownManager(rate=1, per=config.get("revive_cooldown", 600), bucket_type="user")


class Royale(commands.Cog):
    """⚔️ Knockout Royale — weaponized chaos & resurrection"""
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.stats = self.load_stats()
        self.weapons = self.load_weapons()
        self.deathlog = self.load_deathlog()
        self.cleanup_task.start()

    # === File Handling ===
    def load_stats(self):
        os.makedirs(os.path.dirname(STATS_FILE), exist_ok=True)
        if not os.path.exists(STATS_FILE):
            with open(STATS_FILE, "w") as f: json.dump({}, f)
        with open(STATS_FILE, "r") as f:
            return json.load(f)

    def save_stats(self):
        with open(STATS_FILE, "w") as f:
            json.dump(self.stats, f, indent=4)

    def load_weapons(self):
        if not os.path.exists(WEAPON_FILE):
            raise FileNotFoundError(f"Weapon file missing: {WEAPON_FILE}")
        with open(WEAPON_FILE, "r") as f:
            return json.load(f)

    def load_deathlog(self):
        os.makedirs(os.path.dirname(DEATHLOG_FILE), exist_ok=True)
        if not os.path.exists(DEATHLOG_FILE):
            with open(DEATHLOG_FILE, "w") as f: json.dump({}, f)
        with open(DEATHLOG_FILE, "r") as f:
            return json.load(f)

    def save_deathlog(self):
        with open(DEATHLOG_FILE, "w") as f:
            json.dump(self.deathlog, f, indent=4)

    # === Stats Management ===
    def get_user(self, user_id: str):
        if str(user_id) not in self.stats:
            self.stats[str(user_id)] = {
                "kills": 0, "deaths": 0, "revives": 0, "failed_revives": 0,
                "xp": 0, "level": 1, "prestige": 0
            }
        return self.stats[str(user_id)]

    def xp_needed(self, level: int):
        return 100 + (level * 25)

    def add_xp(self, user_id: str, amount: int):
        user = self.get_user(user_id)
        user["xp"] += amount
        leveled_up = False
        while user["xp"] >= self.xp_needed(user["level"]):
            user["xp"] -= self.xp_needed(user["level"])
            user["level"] += 1
            if user["level"] > 15:
                user["level"] = 15
            leveled_up = True
        self.save_stats()
        return leveled_up

    def add_kill(self, user_id: str):
        self.get_user(user_id)["kills"] += 1
        self.save_stats()

    def add_death(self, user_id: str):
        self.get_user(user_id)["deaths"] += 1
        self.save_stats()

    def add_revive(self, user_id: str, success: bool):
        user = self.get_user(user_id)
        if success:
            user["revives"] += 1
            xp_gain = random.randint(15, 30)
            leveled_up = self.add_xp(user_id, xp_gain)
            return xp_gain, leveled_up
        else:
            user["failed_revives"] += 1
            self.save_stats()
            return 0, False

    # === Background Cleanup ===
    @tasks.loop(minutes=5)
    async def cleanup_task(self):
        removed = []
        for guild in self.bot.guilds:
            for user_id in list(self.deathlog.keys()):
                try:
                    member = guild.get_member(int(user_id))
                    if not member:
                        continue
                    timeout_end = datetime.fromisoformat(self.deathlog[user_id]["timeout_end"])
                    if member.timed_out_until is None or member.timed_out_until < discord.utils.utcnow() or timeout_end < discord.utils.utcnow():
                        self.deathlog.pop(user_id, None)
                        removed.append(user_id)
                except Exception as e:
                    print(f"[Royale] Cleanup error for {user_id}: {e}")
        if removed:
            self.save_deathlog()
            print(f"[Royale] Cleaned {len(removed)} entries from deathlog.")

    # --- Safe Timeout Helper ---
    async def safe_timeout(self, member: discord.Member, until, reason, delay=1.15):
        try:
            await member.timeout(until, reason=reason)
            await asyncio.sleep(delay)
            return True, None
        except discord.HTTPException as e:
            if e.status == 429:
                try:
                    retry_after = e.response.headers.get("Retry-After")
                    if retry_after:
                        await asyncio.sleep(float(retry_after))
                except Exception:
                    await asyncio.sleep(1)
                return False, "rate_limited"
            return False, str(e)
        except discord.Forbidden:
            return False, "forbidden"
        except Exception as e:
            return False, str(e)

    @cleanup_task.before_loop
    async def before_cleanup(self):
        await self.bot.wait_until_ready()

    @app_commands.command(name="knockout", description="Knock someone out with a random weapon!")
    @command_enabled()
    async def knockoutcmd(self, interaction: discord.Interaction, member: discord.Member = None):
        # Defer immediately to avoid interaction timeout (prevents 404)
        await interaction.response.defer(thinking=True, ephemeral=False)

        remaining = await cooldown_knockout.get_remaining(interaction)
        if remaining > 0:
            return await interaction.followup.send(
                f"⏳ Slow down! Try again in **{round(remaining, 1)}s**.",
                ephemeral=True
            )
        await cooldown_knockout.trigger(interaction)

        # Pick a random target if none provided
        if member is None:
            candidates = [m for m in interaction.guild.members if not m.bot and m != interaction.user]
            if not candidates:
                return await interaction.followup.send("No valid targets found.", ephemeral=True)
            member = random.choice(candidates)

        # Prevent self or bot targeting
        if member == interaction.user:
            embed = discord.Embed(
                title="Need Help?",
                description="It's okay to reach out — you matter ❤️\n`988` Suicide and Crisis Lifeline",
                color=discord.Color.red()
            ).set_footer(text="Available 24/7 — English & Spanish")
            return await interaction.followup.send(embed=embed, ephemeral=True)

        if member.user.name == "pitr1010":
            return await interaction.followup.send("❌ I'm not going down that easily!", ephemeral=True)

        if member == interaction.guild.me:
            return await interaction.followup.send("❌ I'm not going down that easily!", ephemeral=True)
        
        if member.timeout > 1800:
            return await interaction.response.send_message(
                "⏳ That user is alredy knocked out!", ephemeral=True
            )
        
        # === Weapon Selection ===
        weapon_keys = list(self.weapons.keys())
        weights = []
        for key in weapon_keys:
            if key == "nuke":
                weights.append(0.1)   # rare
            elif key == "garande_hug":
                weights.append(50)    # uncommon
            else:
                weights.append(100)     # normal

        weapon_key = random.choices(weapon_keys, weights=weights, k=1)[0]
        weapon = self.weapons[weapon_key]

        # Timeout duration normalization
        raw_timeout = random.choice(weapon["timeout"]) if isinstance(weapon.get("timeout"), list) else weapon.get("timeout")
        timeout_value = int(raw_timeout) if str(raw_timeout).isdigit() else 30
        xp_multi = weapon.get("xp_multiplier", 1.0)
        outcome = random.choices(["hit", "miss", "crit"], weights=[0.7, 0.15, 0.15])[0]

        embed = discord.Embed(color=discord.Color.magenta(), title=weapon.get("title", "Knockout"))
        embed.set_image(url=weapon.get("gif", ""))

        # --- Miss outcome ---
        if outcome == "miss":
            embed.description = f"😅 {interaction.user.mention} missed {member.mention}!\n> {random.choice(weapon.get('miss_lines', ['They missed!']))}"
            embed.set_footer(text=f"🕐 Cooldown: {config.get('knockout_cooldown', 1800)//60} min")
            return await interaction.followup.send(embed=embed)

        crit = (outcome == "crit")
        base_duration = timeout_value
        duration = base_duration * (2 if crit else 1)
        now = discord.utils.utcnow()

        async def try_timeout(target: discord.Member, seconds: int, reason: str):
            for attempt in range(3):
                try:
                    await target.timeout(now + timedelta(seconds=seconds), reason=reason)
                    await asyncio.sleep(1.15)
                    return True
                except discord.HTTPException as e:
                    if e.status == 429:
                        retry_after = float(e.response.headers.get("Retry-After", 1.3))
                        await asyncio.sleep(retry_after + 0.25)
                    else:
                        return False
                except discord.Forbidden:
                    return False
                except Exception:
                    await asyncio.sleep(0.25)
            return False

        try:
            # Normal single target
            ok = await try_timeout(member, duration, "Knockout!")
            if not ok:
                embed.title = "🚫 Target Protected!"
                embed.description = f"{member.mention} resisted the attack!"
                self.add_kill(interaction.user.id)
                self.add_death(member.id)
                embed.set_image(url="https://media.discordapp.net/attachments/1308048258337345609/1435509129136439428/nope-anime.gif")
                embed.set_footer(text=f"🕐 Cooldown: {config.get('knockout_cooldown', 900)//60} min")
                return await interaction.followup.send(embed=embed)

            # record stats
            xp_gain = int(random.randint(20 if crit else 10, 35 if crit else 25) * xp_multi)
            leveled = self.add_xp(interaction.user.id, xp_gain)
            self.add_kill(interaction.user.id)
            self.add_death(member.id)
            self.deathlog[str(member.id)] = {
                "by": interaction.user.id,
                "weapon": weapon_key,
                "timeout_end": (now + timedelta(seconds=duration)).isoformat(),
                "crit": crit
            }
            self.save_deathlog()

            # embed
            embed.description = (
                f"🔥 **CRITICAL HIT!** {interaction.user.mention} obliterated {member.mention} with **{weapon_key}!**\n> {random.choice(weapon.get('crit_lines', ['Critical hit!']))}"
                if crit
                else f"{interaction.user.mention} hit {member.mention} with **{weapon_key}**!\n> {random.choice(weapon.get('lines', ['Hit!']))}"
            )
            embed.add_field(name="🏅 XP Gained", value=f"**+{xp_gain} XP**", inline=False)
            if leveled:
                embed.add_field(name="🆙 Level Up!", value=f"{interaction.user.mention} reached **Level {self.get_user(interaction.user.id)['level']}!**", inline=False)

            embed.set_footer(text=f"🕐 Cooldown: {config.get('knockout_cooldown', 900)//60} min")
            await interaction.followup.send(embed=embed)

        except Exception as e:
            print(f"[Royale] knockout error: {e}")
            try:
                await interaction.followup.send("⚠️ Something went wrong while performing the knockout.", ephemeral=True)
            except Exception:
                pass





    # === Revive Command ===
    @app_commands.command(name="revive", description="Attempt to bring a timed-out user back to life!")
    @command_enabled()
    async def revivecmd(self, interaction: discord.Interaction, member: discord.Member):
        remaining = await cooldown_revive.get_remaining(interaction)
        if remaining > 0:
            return await interaction.response.send_message(
                f"⏳ Your healing hands need to rest! Try again in **{round(remaining,1)}s**.",
                ephemeral=True
            )
        await cooldown_revive.trigger(interaction)

        if member == interaction.user:
            return await interaction.response.send_message("🪞 You can't revive yourself!", ephemeral=True)

        # Ensure deathlog is current
        await self.cleanup_task()

        entry = self.deathlog.get(str(member.id))
        if not entry:
            return await interaction.response.send_message(
                "⚖️ Only those knocked out by the bot can be revived!", ephemeral=True
            )
        
        if member.timeout > 1800:
            return await interaction.response.send_message(
                "⏳ That user isn't ready to be revived yet!", ephemeral=True
            )
        
        outcome = random.choices(["fail","success","miracle"], weights=[0.3,0.6,0.1])[0]
        embed = discord.Embed(color=discord.Color.blurple())
        embed.set_footer(text=f"🕐 Cooldown: {config.get('revive_cooldown',600)//60} min")

        if outcome=="fail":
            embed.title = "💀 Revival Failed!"
            embed.description = f"{interaction.user.mention} tried to revive {member.mention}, but the light flickered out."
            embed.set_image(url="https://cdn.discordapp.com/attachments/1183985896039661658/1326217477395953726/revive-fail.gif")
            self.add_revive(interaction.user.id, success=False)
        else:
            embed.title = "✨ Resurrection Complete!" if outcome=="success" else "🌈 Miracle Revival!"
            embed.description = f"{interaction.user.mention} revived {member.mention}!" if outcome=="success" else f"✨ Miracle revival! {member.mention} rises!"
            embed.set_image(url="https://cdn.discordapp.com/attachments/1183985896039661658/1308808048030126162/love-live-static.gif")
            try:
                await member.edit(timed_out_until=None)
                xp_gain, leveled = self.add_revive(interaction.user.id, success=True)
                self.deathlog.pop(str(member.id), None)
                self.save_deathlog()
                if xp_gain>0:
                    embed.add_field(name="🏅 XP Gained", value=f"**+{xp_gain} XP**", inline=False)
                if leveled:
                    embed.add_field(name="🆙 Level Up!", value="📈 You leveled up!", inline=False)
            except discord.Forbidden:
                embed.description += "\n⚠️ Missing permission."
                self.add_revive(interaction.user.id, success=False)
            except discord.HTTPException:
                embed.description += "\n👻 Something went wrong."
                self.add_revive(interaction.user.id, success=False)

        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Royale(bot))
