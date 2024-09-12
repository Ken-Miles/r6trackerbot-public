from typing import Literal, Optional, Union

import discord
from discord import app_commands
from discord.ext import commands
from discord.ext.commands import BucketType

from cogs.models import Blacklist
from utils import (
    BotU,
    CogU,
    ContextU,
    Cooldown,
    FiveButtonPaginator,
    GUILDS,
    create_paginator,
    generate_pages,
    makeembed_failedaction,
    makeembed_successfulaction,
)

class BlacklistCog(CogU, name='Blacklist',hidden=True):
    """Commands for viewing, adding and removing user's access from the bot."""
    bot: BotU

    def __init__(self, bot: BotU):
        self.bot = bot

    @commands.hybrid_group(name='blacklist',description='View the Blacklist.',hidden=True)
    @commands.is_owner()
    @app_commands.guilds(*GUILDS)
    @Cooldown(1, 5, BucketType.user)
    async def blacklist(self, ctx: ContextU):
        pass

    @blacklist.command(name='add',description="Add a user or guild to the blacklist.")
    async def blacklist_add(self, ctx: ContextU, object1: Optional[discord.User]=None, *, reason: Optional[str]=None):
        """Add a user to the blacklist."""
        await ctx.defer(ephemeral=True)

        #object = object1 or object2

        if not object:
            emb = makeembed_failedaction(description="Could not find object.")
            return await ctx.reply(embed=emb)

        if await Blacklist.add(object, reason):
            emb = makeembed_successfulaction(description="Added user to blacklist.")
            await ctx.reply(embed=emb)
        else:
            emb = makeembed_failedaction(description="Could not add user to blacklist.")
        await ctx.reply(embed=emb)

    @blacklist.command(name='remove',description="Remove a user to the blacklist.")
    async def blacklist_remove(self, ctx: ContextU, object1: Optional[discord.User]=None):
        """Remove a user from the blacklist."""
        await ctx.defer(ephemeral=True)

        #object = object1 or object2

        if not object:
            emb = makeembed_failedaction(description="Could not find object.")
            return await ctx.reply(embed=emb)

        if await Blacklist.remove(object.id):
            emb = makeembed_successfulaction(description="Removed object from blacklist.")
            await ctx.reply(embed=emb)
        else:
            emb = makeembed_failedaction(description="Could not remove object from blacklist.")
        await ctx.reply(embed=emb)

    @blacklist.command(name='list',description="List all users on the blacklist.")
    async def blacklist_list(self, ctx: ContextU, type: Optional[Literal['user','guild','all']]='user'):
        """List all users or guilds on the blacklist. Defaults to users."""

        await ctx.defer(ephemeral=True)

        if type == 'all':
            blacklist = await Blacklist.all()
        else:
            blacklist = await Blacklist.filter(type=type)
        
        lines = []
        for blacklist_item in blacklist:
            lines.append(f"`{blacklist_item.offender_name}` (`{blacklist_item.offender_id}`)")
        
        if lines:
            pages = generate_pages(lines, title="Blacklisted Objects", color=discord.Colour.dark_gray())
            return await create_paginator(ctx, pages, paginator=FiveButtonPaginator, author_id=ctx.author.id, go_to_button=True, delete_message_after=True)
        else:
            return await ctx.reply(embed=makeembed_failedaction(description="No blacklisted objects found."))

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        blacklist = await Blacklist.filter(offender_id=guild.id, type='guild')
        if blacklist:
            return await guild.leave()
    
    # @commands.Cog.listener()
    # async def on_member_join(self, member: discord.Member):
    #     if await self.bot.is_owner(member.guild.owner): # type: ignore
    #         blacklist = await Blacklist.filter(offender_id=member.id, type='user')
    #         if blacklist:
    #             return await member.kick(reason="User is blacklisted.")

async def setup(bot: BotU):
    cog = BlacklistCog(bot)
    await bot.add_cog(cog)
