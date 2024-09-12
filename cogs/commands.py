from __future__ import annotations
from typing import Literal, Optional

import discord
from discord.ext import commands

from utils import BotU, CogU, ContextU, emojidict

class CommandsCog(CogU, name='Commands', hidden=True):
    bot: BotU

    def __init__(self, bot: BotU):
        self.bot = bot
    
    @commands.command(name='sync', description="Syncs the command tree to the current guild or a list of guilds.", hidden=True)
    @commands.guild_only()
    @commands.is_owner()
    async def sync(self, ctx: ContextU, guilds: commands.Greedy[discord.Object], spec: Optional[Literal["~", "*", "^"]] = None):
        await ctx.defer()
        
        assert ctx.guild is not None

        if not guilds:
            if spec == "~":
                synced = await self.bot.tree.sync(guild=ctx.guild)
            elif spec == "*":
                self.bot.tree.copy_global_to(guild=ctx.guild)
                synced = await self.bot.tree.sync(guild=ctx.guild)
            elif spec == "^":
                self.bot.tree.clear_commands(guild=ctx.guild)
                await self.bot.tree.sync(guild=ctx.guild)
                synced = []
            else:
                synced = await self.bot.tree.sync()

            return await ctx.reply(
                f"{emojidict.get('satellite')} Synced {len(synced)} {'global' if spec is None else 'guild'} commands."
            )
        else:
            ret = 0
            for guild in guilds:
                try:
                    await self.bot.tree.sync(guild=guild)
                except discord.HTTPException:
                    pass
                else:
                    ret += 1

            return await ctx.reply(f"Synced the tree to {ret}/{len(guilds)}.")

    @commands.command(name='error',description="Raises an error for testing purposes.", hidden=True)
    @commands.is_owner()
    async def error(self, ctx: ContextU, *, message: str = "This is a test error."):
        #raise RuntimeError("This is a test error.")
        #raise commands.Command(RuntimeError(message))
        print('e')
        assert False, message

    # @app_commands.command(name='help', description="Help Command.", hidden=True)
    # async def help(self, interaction: discord.Interaction, command_or_group: Optional[str] = None):
    #     ctx = await ContextU.from_interaction(interaction)
    #     await ctx.defer()

    #     await ctx.send_help(command_or_group)

async def setup(bot: BotU):
    cog = CommandsCog(bot)
    await bot.add_cog(cog)
