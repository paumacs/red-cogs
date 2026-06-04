import asyncio
import logging
import time
from typing import Optional

import discord
from redbot.core import Config, commands
from redbot.core.bot import Red
from redbot.core.utils import chat_formatting as cf

log = logging.getLogger(__name__)


class JungleShotcaller(commands.Cog):
    """Send Jungle shotcall notifications at regular intervals."""

    __author__ = ["Cheodl"]
    __version__ = "1.0.0"

    SPAWN_OFFSETS = [0, 5, 10, 15, 20, 25]
    DEFAULT_BUFFER_SECONDS = 30

    def __init__(self, bot: Red):
        self.bot = bot
        self.active_shotcall: Optional[asyncio.Task] = None
        self.config = Config.get_conf(self, 2074396482, force_registration=True)
        self.config.register_guild(buffer_seconds=self.DEFAULT_BUFFER_SECONDS)

    async def red_delete_data_for_user(self, *, requester, user_id: int):
        if self.active_shotcall and not self.active_shotcall.done():
            self.active_shotcall.cancel()
            self.active_shotcall = None

    def format_help_for_context(self, ctx: commands.Context) -> str:
        pre_processed = super().format_help_for_context(ctx) or ""
        n = "\n" if "\n\n" not in pre_processed else ""
        text = [
            f"{pre_processed}{n}",
            f"Cog Version: **{self.__version__}**",
            f"Author: {cf.humanize_list(self.__author__)}",
        ]
        return "\n".join(text)

    @commands.guild_only()
    @commands.bot_has_permissions(send_messages=True)
    @commands.command(name="shotcall")
    async def shotcall(self, ctx: commands.Context, delay: int, role: discord.Role):
        """
        Start a jungle shotcall that notifies a role ahead of each jungle spawn.

        The jungle spawns at 0m, 5m, 10m, 15m, 20m, and 25m in the 30-minute window.
        `delay`: Seconds to wait before the shotcalling schedule begins.
        `role`: The role to notify for each shotcall message.
        """
        if delay < 0:
            await ctx.send("Delay must be zero or a positive number of seconds.")
            return

        if self.active_shotcall and not self.active_shotcall.done():
            await ctx.send("A jungle shotcall is already running.")
            return

        self.active_shotcall = self.bot.loop.create_task(
            self._run_shotcall(ctx.channel, role, delay)
        )
        await ctx.send(f"Jungle shotcall will start in {delay} seconds for {role.mention}.")

    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    @commands.command(name="shotcallbuffer")
    async def shotcallbuffer(self, ctx: commands.Context, seconds: Optional[int] = None):
        """View or set the buffer time for jungle spawn notifications."""
        if seconds is None:
            current = await self.config.guild(ctx.guild).buffer_seconds()
            await ctx.send(f"Current jungle buffer is {current} seconds.")
            return

        if seconds < 0:
            await ctx.send("Buffer time must be zero or a positive number of seconds.")
            return

        await self.config.guild(ctx.guild).buffer_seconds.set(seconds)
        await ctx.send(f"Jungle buffer updated to {seconds} seconds.")

    @commands.guild_only()
    @commands.bot_has_permissions(send_messages=True)
    @commands.command(name="stopshotcall")
    async def stop_shotcall(self, ctx: commands.Context):
        """Stop the currently running jungle shotcall immediately."""
        if self.active_shotcall and not self.active_shotcall.done():
            self.active_shotcall.cancel()
            await ctx.send("Jungle shotcall canceled.")
            return

        self.active_shotcall = None
        await ctx.send("There is no active jungle shotcall to stop.")

    async def _run_shotcall(
        self, channel: discord.abc.Messageable, role: discord.Role, delay: int
    ):
        try:
            if delay > 0:
                await asyncio.sleep(delay)

            buffer_seconds = await self.config.guild(role.guild).buffer_seconds()
            start_time = time.monotonic()
            for index, offset in enumerate(self.SPAWN_OFFSETS):
                spawn_seconds = offset * 60
                notification_seconds = max(0, spawn_seconds - buffer_seconds)
                sleep_seconds = notification_seconds - (time.monotonic() - start_time)
                if sleep_seconds > 0:
                    await asyncio.sleep(sleep_seconds)

                if index == 0:
                    await channel.send(f"{role.mention} Jungle shotcall started!")
                else:
                    await channel.send(
                        f"{role.mention} Jungle spawn in {buffer_seconds} seconds (spawn at {offset}m)."
                    )

            await channel.send("Shotcalling ended.")
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.error("Error while running jungle shotcall", exc_info=exc)
        finally:
            self.active_shotcall = None
