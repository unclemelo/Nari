import discord, random, asyncio
from discord.ext import commands
from discord import app_commands

class MiniGames(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.trivia_questions = [
            {"question": "What is the capital of France?", "answer": "paris"},
            {"question": "Who wrote '1984'?", "answer": "george orwell"},
            {"question": "What is the largest planet in our Solar System?", "answer": "jupiter"},
            {"question": "How many continents are there?", "answer": "7"},
            {"question": "What element does 'O' represent on the periodic table?", "answer": "oxygen"},
        ]

    # === /coinflip ===
    @app_commands.command(name="coinflip", description="Flip a coin — heads or tails!")
    async def coinflip(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        await asyncio.sleep(1)
        result = random.choice(["Heads", "Tails"])
        embed = discord.Embed(
            title="🪙 Coin Flip",
            description=f"The coin landed on **{result}!**",
            color=discord.Color.gold()
        )
        embed.set_footer(text="Better luck next time... or did you win?")
        await interaction.followup.send(embed=embed)

    # === /dice ===
    @app_commands.command(name="dice", description="Roll a dice — default 6 sides.")
    @app_commands.describe(sides="Number of sides for the dice (default is 6).")
    async def dice(self, interaction: discord.Interaction, sides: int = 6):
        if sides < 2:
            await interaction.response.send_message("⚠️ The dice needs at least 2 sides!", ephemeral=True)
            return
        roll = random.randint(1, sides)
        embed = discord.Embed(
            title="🎲 Dice Roll",
            description=f"You rolled a **{roll}** (1–{sides})!",
            color=discord.Color.random()
        )
        await interaction.response.send_message(embed=embed)

    # === /8ball ===
    @app_commands.command(name="8ball", description="Ask the magic 8-ball anything.")
    async def eightball(self, interaction: discord.Interaction, *, question: str):
        responses = [
            "Yes.", "No.", "Maybe.", "Definitely!", "Absolutely not.", "Ask again later.",
            "I'm not sure...", "Without a doubt.", "Don't count on it.", "It is certain."
        ]
        embed = discord.Embed(
            title="🎱 The Magic 8-Ball",
            description=f"**Question:** {question}\n**Answer:** {random.choice(responses)}",
            color=discord.Color.purple()
        )
        embed.set_footer(text="The 8-ball has spoken.")
        await interaction.response.send_message(embed=embed)

    # === /rps ===
    @app_commands.command(name="rps", description="Play Rock, Paper, Scissors against Nari!")
    @app_commands.describe(choice="Your choice: rock, paper, or scissors.")
    async def rps(self, interaction: discord.Interaction, choice: str):
        options = ["rock", "paper", "scissors"]
        choice = choice.lower()
        if choice not in options:
            await interaction.response.send_message("❌ Please choose rock, paper, or scissors.", ephemeral=True)
            return

        bot_choice = random.choice(options)
        result = None
        if choice == bot_choice:
            result = "It's a tie!"
        elif (choice == "rock" and bot_choice == "scissors") or \
             (choice == "paper" and bot_choice == "rock") or \
             (choice == "scissors" and bot_choice == "paper"):
            result = "You win! 🎉"
        else:
            result = "I win! 😎"

        embed = discord.Embed(
            title="✊ Rock Paper Scissors",
            description=f"You chose **{choice}**.\nI chose **{bot_choice}**.\n\n**{result}**",
            color=discord.Color.teal()
        )
        await interaction.response.send_message(embed=embed)

    # === /trivia ===
    @app_commands.command(name="trivia", description="Start a random trivia question!")
    async def trivia(self, interaction: discord.Interaction):
        question = random.choice(self.trivia_questions)
        embed = discord.Embed(
            title="🧠 Trivia Time!",
            description=f"**Question:** {question['question']}\n\nYou have 15 seconds to answer!",
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed)

        def check(msg: discord.Message):
            return msg.author == interaction.user and msg.channel == interaction.channel

        try:
            msg = await self.bot.wait_for("message", timeout=15.0, check=check)
        except asyncio.TimeoutError:
            await interaction.followup.send("⏰ Time's up! The correct answer was **{}**.".format(question["answer"].title()))
            return

        if msg.content.lower().strip() == question["answer"]:
            await interaction.followup.send(f"✅ Correct! Nice job, {interaction.user.mention}!")
        else:
            await interaction.followup.send(f"❌ Nope! The correct answer was **{question['answer'].title()}**.")

    # === /guessnumber ===
    @app_commands.command(name="guessnumber", description="Guess a number between 1 and 100.")
    async def guessnumber(self, interaction: discord.Interaction):
        number = random.randint(1, 100)
        embed = discord.Embed(
            title="🔢 Guess the Number",
            description="I'm thinking of a number between **1 and 100**.\nYou have 5 tries!",
            color=discord.Color.orange()
        )
        await interaction.response.send_message(embed=embed)

        def check(msg: discord.Message):
            return msg.author == interaction.user and msg.channel == interaction.channel and msg.content.isdigit()

        tries = 0
        while tries < 5:
            try:
                msg = await self.bot.wait_for("message", timeout=20.0, check=check)
            except asyncio.TimeoutError:
                await interaction.followup.send(f"⏰ You ran out of time! The number was **{number}**.")
                return

            guess = int(msg.content)
            tries += 1

            if guess == number:
                await interaction.followup.send(f"🎉 You got it in {tries} tries! The number was **{number}**!")
                return
            elif guess < number:
                await interaction.followup.send("🔺 Higher!")
            else:
                await interaction.followup.send("🔻 Lower!")

        await interaction.followup.send(f"😢 Out of tries! The number was **{number}**.")

async def setup(bot):
    await bot.add_cog(MiniGames(bot))
