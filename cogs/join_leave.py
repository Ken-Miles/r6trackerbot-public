from typing import List

import discord
from discord.ext import commands
from discord.utils import MISSING

from utils import (
    BotU,
    CogU,
    JOIN_LEAVE_WEBHOOK_URL as JOIN_LEAVE,
    URLButton,
    makeembed_bot,
)

class JoinLeaveCog(CogU):
    def __init__(self, bot: BotU):
        self.bot = bot

        # global JOIN_LEAVE
        # JOIN_LEAVE = discord.Webhook.from_url(JOIN_LEAVE, client=self.bot)

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        if not isinstance(JOIN_LEAVE, discord.Webhook):
            webhook = discord.Webhook.from_url(JOIN_LEAVE, client=self.bot)
        else:
            webhook = JOIN_LEAVE

        try:
            invites: List[discord.Invite] = await guild.invites()
        except discord.Forbidden:
            invites = []
        preferred_invite = None

        for invite in invites:
            if invite.max_age in [0, None] and invite.max_uses in [0, None] and not invite.temporary:
                preferred_invite = invite
                break
        
        bot_count = len([m for m in guild.members if m.bot])

        emb = makeembed_bot(
            title="Joined Guild",
            description=f"Joined `{guild.name}` (`{guild.id}`)\nOwner: {guild.owner.mention if guild.owner else '?'} (`{guild.owner_id}`)\nMembers: {guild.member_count}, Bots: {bot_count}",
            footer=f"Server count is now at {len(self.bot.guilds)}.",
            color=discord.Color.brand_green()
        )
        view = URLButton(buttontext="Invite", url=preferred_invite.url) if preferred_invite else MISSING
        await webhook.send(embed=emb, view=view)
    
    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild):
        if not isinstance(JOIN_LEAVE, discord.Webhook):
            webhook = discord.Webhook.from_url(JOIN_LEAVE, client=self.bot)
        else:
            webhook = JOIN_LEAVE

        # invites = await guild.invites()
        # preferred_invite = None

        # for invite in invites:
        #     if not invite.max_age and not invite.max_uses:
        #         preferred_invite = invite
        #         break
        emb = makeembed_bot(
            title="Left Guild",
            description=f"Left `{guild.name}` (`{guild.id}`)\nOwner: {guild.owner.mention if guild.owner else '?'} (`{guild.owner_id}`)\nMembers: {guild.member_count}",
            footer=f"Server count is now at {len(self.bot.guilds)}.",
            color=discord.Color.brand_red()
        )
        #view = URLButton(buttontext="Invite", url=preferred_invite.url) if preferred_invite else MISSING
        await webhook.send(embed=emb)

async def setup(bot: BotU):
    # cog = JoinLeaveCog(bot)
    # await bot.add_cog(cog)
    pass