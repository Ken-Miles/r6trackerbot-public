from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from main import PROD
from utils import BotU, CogU, ContextU, Cooldown, makeembed_bot

BOT_ID = 1082452014157545502
VOTING_SITES = {
    'top.gg': f"https://top.gg/bot/{BOT_ID}",
    'discordbotlist.com': "https://discordbotlist.com/bots/rainbow-six-stats",
    'discord.bots.gg': f"https://discord.bots.gg/bots/{BOT_ID}",
    'discordlist.gg': f"https://discordlist.gg/bot/{BOT_ID}",
    'botlist.me': f"https://discordlist.gg/bot/{BOT_ID}",
}

class MultiURLButton(discord.ui.View):
    def __init__(self, buttons: dict[str, str]):
        super().__init__()
        for label, url in buttons.items():
            self.add_item(discord.ui.Button(label=label, url=url, style=discord.ButtonStyle.url))
    
class VotingCog(CogU, name='Voting'):
    """Commands for voting for the bot on various websites."""
    bot: BotU

    def __init__(self, bot: BotU):
        self.bot = bot
    
    @commands.hybrid_command(name='vote', description="Vote for the bot on websites like top.gg.")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @Cooldown(1, 15, commands.BucketType.user)
    async def vote(self, ctx: ContextU):
        await ctx.defer()

        emb = makeembed_bot(
            title="Vote for the bot!",
            description="Vote for the bot on the following websites to support the bot and get some cool perks (coming soon)!\nThis bot will be free to use forever, but voting helps me out a lot!",
            color=discord.Color.brand_green()
        )

        # for site, url in VOTING_SITES.items():
        #     site = f""
        view = MultiURLButton(VOTING_SITES)
        
        await ctx.reply(embed=emb, view=view)

async def setup(bot: BotU):
    if PROD:    
        cog = VotingCog(bot)
        await bot.add_cog(cog)
    else:
        pass