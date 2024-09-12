import discord
from discord.ext import commands

from cogs.models import CommandInvocation
from cogs.ranks import Platform
from cogs.ranksv2 import Platform as PlatformV2
from utils import BotU, CogU, ContextU, generate_transaction_id

class CmdLoggingCog(CogU):
    def __init__(self, bot: BotU):
        self.bot = bot

    @commands.Cog.listener()
    async def on_command(self, ctx: ContextU):
        args = []
        kwargs = {}
        transaction_id = generate_transaction_id()

        for arg in ctx.args:
            if isinstance(arg, (Platform, PlatformV2)):
                arg = arg.value
            if not isinstance(arg, (str, int, float, bool)):
                continue
            args.append(arg)
        
        for k, v in ctx.kwargs.items():
            if isinstance(v, (Platform, PlatformV2)):
                v = v.value
            if not isinstance(v, (str, int, float, bool)):
                continue
            kwargs[k] = v

        await CommandInvocation.create(
            transaction_id=transaction_id,
            command_id = ctx.interaction.id if ctx.interaction else ctx.message.id,
            prefix=ctx.clean_prefix if ctx.interaction is None else None,
            is_slash=ctx.interaction is not None,
            command=ctx.command.qualified_name,
            user_id=ctx.author.id,
            guild_id=ctx.guild.id if ctx.guild else None,
            channel_id=ctx.channel.id,
            args=args,
            kwargs=kwargs,
            timestamp=ctx.message.created_at,
        )
    
    @commands.Cog.listener()
    async def on_command_completion(self, ctx: ContextU):
        await CommandInvocation.filter(
            command_id = ctx.interaction.id if ctx.interaction else ctx.message.id
        ).update(
            completed=True,
            completion_timestamp=discord.utils.utcnow()
        )
    
    @commands.Cog.listener()
    async def on_command_error(self, ctx: ContextU, error: commands.CommandError):
        await CommandInvocation.filter(
            command_id = ctx.interaction.id if ctx.interaction else ctx.message.id
        ).update(
            completed=False,
            error=error.__class__.__name__,
            completion_timestamp=discord.utils.utcnow(),
        )

async def setup(bot: BotU):
    cog = CmdLoggingCog(bot)
    await bot.add_cog(cog)