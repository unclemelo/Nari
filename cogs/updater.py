import asyncio
import os
import sys
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import discord
from discord import app_commands
from discord.ext import commands

GITHUB_REPO = "https://github.com/unclemelo/Nari"
DEV_ROLE_ID = 1461982214215569482


@dataclass(slots=True)
class CommandResult:
    command: str
    returncode: int
    stdout: str
    stderr: str

    @property
    def output(self) -> str:
        return (self.stdout or self.stderr).strip() or "No output"

class Updater(commands.Cog):
    REPO_ROOT = Path(__file__).resolve().parents[1]

    def __init__(self, bot):
        self.bot = bot

    # -------------------------------------------------
    # Helper: Check for developer role
    # -------------------------------------------------
    async def _is_dev(self, interaction: discord.Interaction):
        if DEV_ROLE_ID == 0:
            return True
        roles = getattr(interaction.user, "roles", [])
        return any(role.id == DEV_ROLE_ID for role in roles)

    @staticmethod
    async def run_command(*command: str, cwd: Path | None = None) -> CommandResult:
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                cwd=str(cwd) if cwd else None,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()
        except FileNotFoundError as exc:
            return CommandResult(
                command=" ".join(command),
                returncode=127,
                stdout="",
                stderr=str(exc),
            )
        except Exception as exc:
            return CommandResult(
                command=" ".join(command),
                returncode=1,
                stdout="",
                stderr=str(exc),
            )

        return CommandResult(
            command=" ".join(command),
            returncode=cast(int, process.returncode),
            stdout=stdout.decode("utf-8", errors="replace"),
            stderr=stderr.decode("utf-8", errors="replace"),
        )

    def _dependency_command(self) -> tuple[str, ...] | None:
        pyproject = self.REPO_ROOT / "pyproject.toml"
        if pyproject.exists():
            return ("uv", "sync")
        return None

    async def update_code(self) -> tuple[CommandResult, CommandResult | None]:
        git_result = await self.run_command("git", "pull", cwd=self.REPO_ROOT)
        git_output = git_result.output.lower()

        should_sync_dependencies = (
            git_result.returncode == 0 and "already up to date" not in git_output
        )

        deps_result: CommandResult | None = None
        if should_sync_dependencies:
            command = self._dependency_command()
            if command is not None:
                deps_result = await self.run_command(*command, cwd=self.REPO_ROOT)

        return git_result, deps_result

    @staticmethod
    def restart_bot() -> None:
        os.execv(sys.executable, [sys.executable, *sys.argv])

    # -------------------------------------------------
    # Helper: Send error embed
    # -------------------------------------------------
    async def send_error_embed(self, interaction: discord.Interaction, error: Exception, command_name: str):
        """Sends an informative error message when a command fails."""
        tb = "".join(traceback.format_exception(type(error), error, error.__traceback__))
        embed = discord.Embed(
            title=f"⚠️ Error in `{command_name}`",
            description=f"An error occurred while running the `{command_name}` command.",
            color=discord.Color.red()
        )
        embed.add_field(name="Error Type", value=f"`{type(error).__name__}`", inline=True)
        embed.add_field(name="Error Message", value=f"```{str(error)[:500]}```", inline=False)
        embed.set_footer(text="Check console for traceback details.")
        await interaction.followup.send(embed=embed)
        print(f"[Updater Error] {command_name} failed:\n{tb}")

    # -------------------------------------------------
    # /update - main update + restart
    # -------------------------------------------------
    @app_commands.command(name="update", description="Pull updates from GitHub and restart the bot.")
    async def update_bot(self, interaction: discord.Interaction):
        if not await self._is_dev(interaction):
            return await interaction.response.send_message("You are not authorized to run this command.", ephemeral=True)

        await interaction.response.defer(thinking=True)
        try:
            git_result, deps_result = await self.update_code()
            output = git_result.output

            if git_result.returncode != 0:
                embed = discord.Embed(
                    title="⚠️ Update Failed",
                    description="`git pull` failed. Restart cancelled.",
                    color=discord.Color.red(),
                    timestamp=discord.utils.utcnow(),
                )
                embed.add_field(
                    name="Git Output",
                    value=f"```\n{output[:900]}\n```",
                    inline=False,
                )
                return await interaction.followup.send(embed=embed)

            if "already up to date" in output.lower():
                return await interaction.followup.send("✅ No updates available. The bot is already up to date.")

            if deps_result is not None and deps_result.returncode != 0:
                embed = discord.Embed(
                    title="⚠️ Dependency Sync Failed",
                    description="Code updated, but UV dependency sync failed. Restart cancelled.",
                    color=discord.Color.orange(),
                    timestamp=discord.utils.utcnow(),
                )
                embed.add_field(
                    name="UV Output",
                    value=f"```\n{deps_result.output[:900]}\n```",
                    inline=False,
                )
                return await interaction.followup.send(embed=embed)

            embed = discord.Embed(
                title="🔁 Bot Updated",
                description="Successfully pulled updates and synced dependencies with UV. Restarting...",
                color=discord.Color.green(),
                timestamp=discord.utils.utcnow(),
            )
            embed.add_field(name="GitHub Status", value=f"Updates applied successfully. [View on GitHub]({GITHUB_REPO})", inline=False)

            try:
                commits = await self.run_command(
                    "git",
                    "log",
                    "-5",
                    "--pretty=format:• %s (%an)",
                    cwd=self.REPO_ROOT,
                )
                commit_list = commits.output
                embed.add_field(name="Recent Commits", value=f"```\n{commit_list}\n```", inline=False)
            except Exception as e:
                embed.add_field(name="Recent Commits", value=f"Could not retrieve commit log.\nError: {e}", inline=False)

            if deps_result is not None:
                embed.add_field(
                    name="UV Sync",
                    value=f"`exit {deps_result.returncode}`",
                    inline=True,
                )
            await interaction.followup.send(embed=embed)

            self.restart_bot()

        except Exception as e:
            await self.send_error_embed(interaction, e, "update")

    # -------------------------------------------------
    # /update commits
    # -------------------------------------------------
    @app_commands.command(name="update_commits", description="View the most recent GitHub commits.")
    async def recent_commits(self, interaction: discord.Interaction):
        if not await self._is_dev(interaction):
            return await interaction.response.send_message("You are not authorized to run this command.", ephemeral=True)

        await interaction.response.defer()
        try:
            process = await self.run_command(
                "git",
                "log",
                "-5",
                "--pretty=format:• %s (%an)",
                cwd=self.REPO_ROOT,
            )
            commits = process.output or "No commits found."
            embed = discord.Embed(title="📝 Recent Commits", description=f"```\n{commits}\n```", color=discord.Color.blurple())
            await interaction.followup.send(embed=embed)
        except Exception as e:
            await self.send_error_embed(interaction, e, "update_commits")

    # -------------------------------------------------
    # /update test
    # -------------------------------------------------
    @app_commands.command(name="update_test", description="Simulate an update pull without restarting.")
    async def test_update(self, interaction: discord.Interaction):
        if not await self._is_dev(interaction):
            return await interaction.response.send_message("You are not authorized to run this command.", ephemeral=True)

        await interaction.response.defer()
        try:
            process = await self.run_command("git", "fetch", cwd=self.REPO_ROOT)
            ahead_check = await self.run_command("git", "status", "-uno", cwd=self.REPO_ROOT)
            embed = discord.Embed(title="🧪 Update Test", color=discord.Color.orange())
            embed.add_field(name="Git Fetch Output", value=f"```\n{process.output[:500]}\n```", inline=False)
            embed.add_field(name="Status", value=f"```\n{ahead_check.output[:500]}\n```", inline=False)
            await interaction.followup.send(embed=embed)
        except Exception as e:
            await self.send_error_embed(interaction, e, "update_test")

    # -------------------------------------------------
    # /update reload
    # -------------------------------------------------
    @app_commands.command(name="update_reload", description="Reload all cogs without a full restart.")
    async def reload_cogs(self, interaction: discord.Interaction):
        if not await self._is_dev(interaction):
            return await interaction.response.send_message("You are not authorized to run this command.", ephemeral=True)

        try:
            reloaded = []
            failed = []
            for ext in list(self.bot.extensions.keys()):
                try:
                    await self.bot.reload_extension(ext)
                    reloaded.append(ext)
                except Exception as e:
                    failed.append(f"{ext}: {e}")
                    print(f"Failed to reload {ext}: {e}")

            embed = discord.Embed(title="♻️ Reloaded Cogs", color=discord.Color.green())
            embed.add_field(name="Reloaded", value=f"```\n{chr(10).join(reloaded) or 'None'}\n```", inline=False)
            if failed:
                embed.add_field(name="Failed", value=f"```\n{chr(10).join(failed)[:1000]}\n```", inline=False)
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            await self.send_error_embed(interaction, e, "update_reload")

    # -------------------------------------------------
    # /update status
    # -------------------------------------------------
    @app_commands.command(name="update_status", description="Show current version, branch, and uptime.")
    async def update_status(self, interaction: discord.Interaction):
        try:
            branch_result = await self.run_command(
                "git", "rev-parse", "--abbrev-ref", "HEAD", cwd=self.REPO_ROOT
            )
            commit_result = await self.run_command(
                "git", "rev-parse", "--short", "HEAD", cwd=self.REPO_ROOT
            )
            branch = branch_result.output
            commit = commit_result.output

            embed = discord.Embed(title="📊 Bot Status", color=discord.Color.blue())
            embed.add_field(name="Branch", value=branch or "Unknown")
            embed.add_field(name="Commit", value=commit or "Unknown")
            embed.add_field(name="GitHub", value=f"[View Repository]({GITHUB_REPO})", inline=False)
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            await self.send_error_embed(interaction, e, "update_status")

    # -------------------------------------------------
    # /update info
    # -------------------------------------------------
    @app_commands.command(name="update_info", description="Display bot update info and recent activity.")
    async def update_info(self, interaction: discord.Interaction):
        try:
            process = await self.run_command(
                "git",
                "log",
                "-3",
                "--pretty=format:• %s (%an)",
                cwd=self.REPO_ROOT,
            )
            commit = await self.run_command("git", "rev-parse", "--short", "HEAD", cwd=self.REPO_ROOT)
            embed = discord.Embed(
                title="ℹ️ Bot Update Info",
                description="Quick summary of recent updates and version info.",
                color=discord.Color.purple()
            )
            embed.add_field(name="Current Commit", value=commit.output)
            embed.add_field(name="Recent Commits", value=f"```\n{process.output}\n```", inline=False)
            embed.add_field(name="GitHub Repo", value=f"[View Repository]({GITHUB_REPO})", inline=False)
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            await self.send_error_embed(interaction, e, "update_info")


async def setup(bot):
    await bot.add_cog(Updater(bot))
