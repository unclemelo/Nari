import discord, random, asyncio, json, os
from typing import Any, Optional
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

if not os.path.exists(CONFIG_FILE):
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(DEFAULT_CONFIG, f, indent=4)

with open(CONFIG_FILE, "r") as f:
    config = json.load(f)

# Cooldowns
cooldown_knockout = BoosterCooldownManager(rate=1, per=config.get("knockout_cooldown", 900), bucket_type="user")
cooldown_revive = BoosterCooldownManager(rate=1, per=config.get("revive_cooldown", 600), bucket_type="user")


class Knockout(commands.Cog):
    """This cog will be a reskined version of /knockout for Waifu Tactical Force."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.stats = self.load_stats()
        self.weapons = self.load_weapons()
        self.deathlog = self.load_deathlog()
        self.cleanup_task.start()
        self.debug = True

    async def debug_log(self, *msg):
        if self.debug:
            print("[Knockout DEBUG]:", *msg)

    async def _last_timeout_actor(self, guild: Optional[discord.Guild], member: discord.Member) -> Optional[discord.abc.User]:
        """Return the actor (User) who most recently changed the member's timeout via audit logs, or None.

        If `guild` is None (e.g., command invoked in DMs), return None immediately.
        """
        if guild is None:
            return None
        try:
            async for entry in guild.audit_logs(limit=20, action=discord.AuditLogAction.member_update):
                # The audit log member_update may include changes; find entries targeting this member
                if not entry.target or getattr(entry.target, "id", None) != member.id:
                    continue

                # entry.changes can be iterable in some discord.py versions, but may not be in others.
                changes: Any = entry.changes
                found = False

                # Prefer explicit sequence types to satisfy static checkers (AuditLogChanges may not be iterable)
                if isinstance(changes, (list, tuple)):
                    for change in changes:
                        attr = getattr(change, 'attribute', None) or getattr(change, 'key', None)
                        if attr == 'communication_disabled_until':
                            found = True
                            break

                # Fallback: inspect string representation for the attribute name
                if not found:
                    try:
                        if 'communication_disabled_until' in str(changes):
                            found = True
                    except Exception:
                        found = False

                if found:
                    return entry.user
            return None
        except Exception:
            return None

    async def _try_clear_timeout(self, member: discord.Member, reason: str = "Revived") -> bool:
        """Attempt to clear a member timeout safely, with retries for rate limits."""
        for attempt in range(3):
            try:
                # discord.Member.timeout accepts None to clear timeout
                await member.timeout(None, reason=reason)
                await asyncio.sleep(1.0)
                return True
            except discord.Forbidden:
                return False
            except discord.HTTPException as e:
                # handle rate limit and other HTTP issues
                try:
                    retry_after = float(e.response.headers.get("Retry-After", 1.0))
                    await asyncio.sleep(retry_after + 0.25)
                except Exception:
                    await asyncio.sleep(1.0)
            except Exception:
                await asyncio.sleep(0.25)
        return False

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
    def get_user(self, user_id):
        user_key = str(user_id)
        if user_key not in self.stats:
            self.stats[user_key] = {
                "kills": 0, "deaths": 0, "revives": 0, "failed_revives": 0,
                "xp": 0, "level": 1, "prestige": 0
            }
        return self.stats[user_key]

    def xp_needed(self, level: int):
        return 100 + (level * 25)

    def add_xp(self, user_id, amount: int):
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

    def add_kill(self, user_id):
        self.get_user(user_id)["kills"] += 1
        self.save_stats()

    def add_death(self, user_id):
        self.get_user(user_id)["deaths"] += 1
        self.save_stats()

    def add_revive(self, user_id, success: bool):
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
        except discord.Forbidden:
            return False, "forbidden"
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
        except Exception as e:
            return False, str(e)

    @cleanup_task.before_loop
    async def before_cleanup(self):
        await self.bot.wait_until_ready()

    @app_commands.command(name="knockout", description="Knock someone out with a random weapon!")
    @command_enabled()
    async def knockoutcmd(self, interaction: discord.Interaction, member: discord.Member):
        import random
        from datetime import timedelta

        await interaction.response.defer(thinking=True, ephemeral=False)

        # Cooldown
        remaining = await cooldown_knockout.get_remaining(interaction)
        if remaining > 0:
            return await interaction.followup.send(
                f"⏳ Slow down! Try again in **{round(remaining, 1)}s**.",
                ephemeral=True
            )
        await cooldown_knockout.trigger(interaction)

        # Auto-select a target if none given
        if member is None:
            candidates = [m for m in interaction.guild.members if not m.bot and m != interaction.user]
            if not candidates:
                return await interaction.followup.send("No valid targets found.", ephemeral=True)
            member = random.choice(candidates)

        # Self knockout check
        if member == interaction.user:
            embed = discord.Embed(
                title="Need Help?",
                description="It's okay to reach out — you matter ❤️\n`988` Suicide and Crisis Lifeline",
                color=discord.Color.red()
            ).set_footer(text="Available 24/7 — English & Spanish")
            return await interaction.followup.send(embed=embed, ephemeral=True)
        # ❌ Block knockout if target is in voice chat
        if member.voice and member.voice.channel:
            return await interaction.followup.send(
                f"🎧 You can't knock out {member.mention} while they're in a voice channel.",
                ephemeral=True
            )


        # ❗ FIXED BAD SYNTAX + TIMEOUT CHECK
        # Check if the user is ALREADY timed out
        if member.timed_out_until and member.timed_out_until > discord.utils.utcnow():
            return await interaction.followup.send(
                "⏳ That user is already knocked out!",
                ephemeral=True
            )

        # === Weapon Selection ===
        # Exclude dangerous/removed weapons like 'nuke' from runtime selection
        weapon_keys = [k for k in self.weapons.keys() if k != "nuke"]
        weights = []
        for key in weapon_keys:
            if key == "garande_hug":
                weights.append(50)
            else:
                weights.append(100)

        weapon_key = random.choices(weapon_keys, weights=weights, k=1)[0]
        weapon = self.weapons[weapon_key]

        # Timeout calculation
        raw_timeout = random.choice(weapon["timeout"]) if isinstance(weapon.get("timeout"), list) else weapon.get("timeout")
        timeout_value = int(raw_timeout) if str(raw_timeout).isdigit() else 30
        xp_multi = weapon.get("xp_multiplier", 1.0)
        outcome = random.choices(["hit", "miss", "crit"], weights=[0.7, 0.15, 0.15])[0]

        embed = discord.Embed(color=discord.Color.magenta(), title=weapon.get("title", "Knockout"))
        embed.set_image(url=weapon.get("gif", ""))

        # Miss outcome
        if outcome == "miss":
            embed.description = (
                f"😅 {interaction.user.mention} missed {member.mention}!\n"
                f"> {random.choice(weapon.get('miss_lines', ['They missed!']))}"
            )
            embed.set_footer(text=f"🕐 Cooldown: {config.get('knockout_cooldown', 1800)//60} min")
            return await interaction.followup.send(embed=embed)

        # Critical or normal hit
        crit = outcome == "crit"
        duration = timeout_value * (2 if crit else 1)
        now = discord.utils.utcnow()

        async def try_timeout(target: discord.Member, seconds: int, reason: str):
            for attempt in range(3):
                try:
                    await target.timeout(now + timedelta(seconds=seconds), reason=reason)
                    await asyncio.sleep(1.15)
                    return True
                except discord.Forbidden:
                    return False
                except discord.HTTPException as e:
                    if e.status == 429:
                        retry_after = float(e.response.headers.get("Retry-After", 1.3))
                        await asyncio.sleep(retry_after + 0.25)
                    else:
                        return False
                except Exception:
                    await asyncio.sleep(0.25)
            return False

        try:
            ok = await try_timeout(member, duration, "Knockout!")
            if not ok:
                embed.title = "🚫 Target Protected!"
                embed.description = f"{member.mention} resisted the attack!"
                self.add_kill(interaction.user.id)
                self.add_death(member.id)
                embed.set_image(url="https://media.discordapp.net/attachments/1308048258337345609/1435509129136439428/nope-anime.gif")
                embed.set_footer(text=f"🕐 Cooldown: {config.get('knockout_cooldown', 900)//60} min")
                return await interaction.followup.send(embed=embed)

            # XP and stats
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

            embed.description = (
                f"🔥 **CRITICAL HIT!** {interaction.user.mention} obliterated {member.mention} with **{weapon_key}!**\n"
                f"> {random.choice(weapon.get('crit_lines', ['Critical hit!']))}"
                if crit else
                f"{interaction.user.mention} hit {member.mention} with **{weapon_key}**!\n"
                f"> {random.choice(weapon.get('lines', ['Hit!']))}"
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
            except:
                pass

    @app_commands.command(name="revive", description="Attempt to revive (clear timeout) for a knocked-out user.")
    @command_enabled()
    async def revivecmd(self, interaction: discord.Interaction, member: discord.Member):
        await interaction.response.defer(thinking=True)

        # Cooldown
        remaining = await cooldown_revive.get_remaining(interaction)
        if remaining > 0:
            return await interaction.followup.send(f"⏳ Slow down! Try again in **{round(remaining,1)}s**.", ephemeral=True)
        await cooldown_revive.trigger(interaction)

        # Choose target if not provided: pick a random deathlog entry present in this guild
        if member is None:
            candidates = []
            for uid in list(self.deathlog.keys()):
                try:
                    m = interaction.guild.get_member(int(uid))
                    if m and m.timed_out_until and m.timed_out_until > discord.utils.utcnow():
                        candidates.append(m)
                except Exception:
                    continue
            if not candidates:
                return await interaction.followup.send("No valid knocked-out targets found in this server.", ephemeral=True)
            member = random.choice(candidates)

        # Verify target is knocked out via our deathlog
        entry = self.deathlog.get(str(member.id))
        if not entry:
            return await interaction.followup.send("❌ That user is not recorded as knocked out by the game. A moderator timeout cannot be bypassed.", ephemeral=True)

        # Verify member is actually timed out
        if not member.timed_out_until or member.timed_out_until <= discord.utils.utcnow():
            # cleanup stale entry
            self.deathlog.pop(str(member.id), None)
            self.save_deathlog()
            return await interaction.followup.send("That user is not currently timed out.", ephemeral=True)

        # Check audit log to see who applied the timeout
        actor = await self._last_timeout_actor(interaction.guild, member)
        blocked = False
        try:
            knocked_by = int(entry.get("by")) if entry.get("by") is not None else None
        except Exception:
            knocked_by = None

        # If a moderator (not our bot and not the original knocker) applied the timeout, do not allow revive
        bot_user = getattr(interaction.client, "user", None)
        if actor and bot_user and actor.id != bot_user.id and knocked_by is not None and actor.id != knocked_by:
            blocked = True

        if blocked:
            return await interaction.followup.send("🔒 A moderator applied or extended this timeout — you cannot revive them.", ephemeral=True)

        # Attempt to clear timeout
        ok = await self._try_clear_timeout(member, reason=f"Revived by {interaction.user}")
        if not ok:
            # log failure and mark revive as failed
            self.add_revive(interaction.user.id, success=False)
            return await interaction.followup.send("⚠️ Could not clear the timeout. The user may be protected or the bot lacks permissions.", ephemeral=True)

        # Success: remove from deathlog and award XP
        self.deathlog.pop(str(member.id), None)
        self.save_deathlog()
        xp_gain, leveled = self.add_revive(interaction.user.id, success=True)

        embed = discord.Embed(title="✨ Revived!", description=f"{interaction.user.mention} revived {member.mention}.", color=discord.Color.green())
        embed.add_field(name="🏅 XP Gained", value=f"+{xp_gain} XP", inline=False)
        if leveled:
            embed.add_field(name="🆙 Level Up!", value=f"{interaction.user.mention} reached Level {self.get_user(interaction.user.id)['level']}!", inline=False)
        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Knockout(bot))


