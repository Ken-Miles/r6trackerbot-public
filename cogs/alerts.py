import discord
from discord.ext import commands
from discord import app_commands

from cogs.models import Alerts
from utils import BotU, CogU, ContextU, Cooldown, makeembed_bot
from utils.cogs.error_handler import makeembed_successfulaction
from utils.constants import GUILDS

class AlertCog(CogU, name='Alerts'):
    """Commands for viewing alerts from the bot."""
    bot: BotU

    def __init__(self, bot: BotU):
        self.bot = bot

    @commands.Cog.listener()
    async def on_command_completion(self, ctx: ContextU):
        if ctx.author.bot:
            return
        
        alerts = await Alerts.unviewed_alerts(ctx.author.id)

        if not alerts:
            return
        
        alert_cmd = await self.bot.get_command_mention("alerts")

        emb = makeembed_bot(
            title="Alerts",
            description=f"You have {len(alerts)} new alerts! Check them out with {alert_cmd}.",
            color=discord.Color.brand_green()
        )

        await ctx.reply(embed=emb)

    @commands.hybrid_command(name='alerts', description="View your alerts.")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @Cooldown(1, 15, commands.BucketType.user)
    async def alerts(self, ctx: ContextU):
        await ctx.defer()

        alerts = await Alerts.unviewed_alerts(ctx.author.id)

        embs = []
        if not alerts:
            embs.append(makeembed_bot(
                title="Alerts",
                description="You have no alerts.",
                color=discord.Color.brand_red()
            ))
        else:
            for alert in alerts:
                await alert.viewed_alert(ctx.author.id)
                embs.append(makeembed_bot(
                    title=alert.alert_title,
                    description=alert.alert_message,
                    color=discord.Color.brand_green(),
                    timestamp=alert.created_at,
                ))
                if len(embs) > 9:
                    break

        return await ctx.reply(embeds=embs, ephemeral=True)

    @commands.group(name='alert',description="Owner only commands relating to alerts.", hidden=True)
    @commands.is_owner()
    @app_commands.guilds(*GUILDS)
    async def alert_config(self, ctx: ContextU):
        pass
    
    @alert_config.command(name='create',description="Create an alert.")
    async def alert_create(self, ctx: ContextU, title: str, *, descripton: str):
        await ctx.defer(ephemeral=True)

        a = await Alerts.create(
            alert_title=title,
            alert_description=descripton,
            is_active=True,
        )

        return await ctx.reply(makeembed_successfulaction(description=f'Sucessfully created alert (ID `{a.id}).'))

async def setup(bot: BotU):
    cog = AlertCog(bot)
    await bot.add_cog(cog)
