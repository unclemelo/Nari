import discord
import random
import json
import time
import asyncio
import os
from discord.ext import commands, tasks

PET_CHANNEL_ID = 1467659443683725436
TOP_CARETAKER_ROLE_ID = None
STATE_FILE = "data/server_pet.json"

class PetView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    async def interact(self, interaction: discord.Interaction, amount: int):
        if not interaction.channel or interaction.channel.id != PET_CHANNEL_ID:
            return await interaction.response.send_message(
                "❌ The server pet lives in its own channel!",
                ephemeral=True
            )

        success, msg = await self.cog.apply_interaction(
            interaction.user.display_name,
            amount
        )

        await interaction.response.send_message(msg, ephemeral=True)

    @discord.ui.button(label="Pat 🐾", style=discord.ButtonStyle.primary)
    async def pat(self, interaction: discord.Interaction, _):
        await self.interact(interaction, 2)

    @discord.ui.button(label="Treat 🍖", style=discord.ButtonStyle.success)
    async def treat(self, interaction: discord.Interaction, _):
        await self.interact(interaction, 3)

    @discord.ui.button(label="Play 🎾", style=discord.ButtonStyle.secondary)
    async def play(self, interaction: discord.Interaction, _):
        await self.interact(interaction, 3)


class ServerPet(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.lock = asyncio.Lock()

        self.state = {
            "active": False,
            "is_dog": True,
            "mood": 0,
            "max_mood": 15,
            "contributors": {},
            "last_action": 0,
            "status_message_id": None
        }

        self.load_state()
        self.daily_reset.start()

    # ---------------- STATE ----------------

    def load_state(self):
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        if not os.path.exists(STATE_FILE):
            with open(STATE_FILE, "w") as f:
                json.dump({}, f)
        try:
            with open(STATE_FILE, "r") as f:
                self.state.update(json.load(f))
        except FileNotFoundError:
            pass

    def save_state(self):
        with open(STATE_FILE, "w") as f:
            json.dump(self.state, f, indent=4)

    # ---------------- EMBED ----------------

    def build_status_embed(self):
        mood = self.state["mood"]
        max_mood = self.state["max_mood"]
        is_dog = self.state["is_dog"]

        bar = "🟩" * mood + "⬛" * (max_mood - mood)

        return discord.Embed(
            title="🐾 Server Pet",
            description=(
                f"{'🐶 Dog' if is_dog else '🐱 Cat'}\n\n"
                f"💖 Mood: `{mood}/{max_mood}`\n"
                f"{bar}\n\n"
                "Interact using the buttons below!"
            ),
            color=discord.Color.green()
        )

    async def update_status_message(self):
        channel = self.bot.get_channel(PET_CHANNEL_ID)
        if not isinstance(channel, discord.TextChannel):
            return

        try:
            msg = await channel.fetch_message(self.state["status_message_id"])
            await msg.edit(embed=self.build_status_embed(), view=PetView(self))
        except Exception:
            msg = await channel.send(
                embed=self.build_status_embed(),
                view=PetView(self)
            )
            await msg.pin()
            self.state["status_message_id"] = msg.id

        self.save_state()

    # ---------------- INTERACTION LOGIC ----------------

    async def apply_interaction(self, name: str, amount: int):
        async with self.lock:
            now = time.time()
            if now - self.state["last_action"] < 2:
                return False, "⏳ The pet needs a second!"

            self.state["active"] = True
            self.state["mood"] = min(
                self.state["mood"] + amount,
                self.state["max_mood"]
            )
            self.state["contributors"][name] = (
                self.state["contributors"].get(name, 0) + amount
            )
            self.state["last_action"] = now

            await self.update_status_message()

            if self.state["mood"] >= self.state["max_mood"]:
                await self.finish_cycle()
                return True, "✨ The pet is completely happy!"

            responses = [
                "🥰 The pet looks happier!",
                "🐾 Tail wag intensifies!",
                "💖 Happy noises!"
            ]

            return True, random.choice(responses)

    async def finish_cycle(self):
        channel = self.bot.get_channel(PET_CHANNEL_ID)
        if not isinstance(channel, discord.TextChannel):
            return

        leaderboard = sorted(
            self.state["contributors"].items(),
            key=lambda x: x[1],
            reverse=True
        )

        text = "\n".join(
            f"**{i+1}. {name}** — {score}"
            for i, (name, score) in enumerate(leaderboard[:5])
        )

        await channel.send(
            "✨ **The server pet curls up happily!**\n\n"
            f"🏆 **Top Caretakers:**\n{text}"
        )

        if TOP_CARETAKER_ROLE_ID and leaderboard:
            guild = channel.guild
            role = guild.get_role(TOP_CARETAKER_ROLE_ID)
            if role:
                for member in role.members:
                    await member.remove_roles(role)

                top_member = discord.utils.get(
                    guild.members,
                    display_name=leaderboard[0][0]
                )
                if top_member:
                    await top_member.add_roles(role)

        self.state.update({
            "active": False,
            "mood": 0,
            "contributors": {}
        })

        self.save_state()
        await self.update_status_message()

    # ---------------- TASKS ----------------

    @tasks.loop(hours=24)
    async def daily_reset(self):
        self.state.update({
            "active": False,
            "mood": 0,
            "contributors": {}
        })
        self.save_state()
        await self.update_status_message()

    @daily_reset.before_loop
    async def before_reset(self):
        await self.bot.wait_until_ready()

    # ---------------- MOD COMMAND ----------------

    @commands.command(name="petreset")
    @commands.has_permissions(manage_guild=True)
    async def pet_reset(self, ctx):
        if ctx.channel.id != PET_CHANNEL_ID:
            return

        self.state.update({
            "active": False,
            "mood": 0,
            "contributors": {}
        })
        self.save_state()
        await self.update_status_message()
        await ctx.send("♻️ Server pet has been reset.")

async def setup(bot: commands.Bot):
    await bot.add_cog(ServerPet(bot))
