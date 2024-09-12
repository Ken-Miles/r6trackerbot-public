import asyncio
import datetime
import time

import aiohttp
import discord
from discord.ext import commands
import discord.utils
import sentry_sdk
from sentry_sdk.integrations.asyncio import AsyncioIntegration
import yaml

from cogs import EXTENSIONS
from cogs.help_cmd import Help
from cogs.models import Blacklist
from utils import BotU, MentionableTree, SENTRY_URL, bot_logger, handler

import environ

from utils.cogs.error_handler import makeembed_failedaction

env = environ.Env(
    PROD=(bool, False)
)

PROD = env("PROD")

if PROD:
    with open("client.yml", "r") as f:
        token = dict(yaml.safe_load(f)).get("token")
    prefixes = ["r6!", "r6! "]
else:
    with open("client_beta.yml", "r") as f:
        token = dict(yaml.safe_load(f)).get("token")
    prefixes = ["r6dev!", "r6beta!", "r6!dev ", "r6!beta "]
    
currentdate_epoch = int(time.time())
currentdate = datetime.datetime.fromtimestamp(currentdate_epoch)

if __name__ == "__main__":
    print(
    f"""Started running:
PROD: {PROD}
{currentdate}
{currentdate_epoch}"""
)

intents = discord.Intents.default()
#intents.message_content = True
#intents.members = True

bot = BotU(
    command_prefix=commands.when_mentioned_or(*prefixes),
    intents=intents,
    activity=discord.Activity(type=discord.ActivityType.watching, name="the Rainbow Six Siege Pro League"),
    status=discord.Status.dnd,
    help_command=Help(),
    tree_cls=MentionableTree,
)
tree = bot.tree

@bot.event
async def on_ready():
    date = datetime.datetime.fromtimestamp(int(time.time()))
    print(f"{date}: Ready!")

@bot.check
async def ensure_not_on_blacklist(ctx):
    if blacklist := (await Blacklist.blacklisted(ctx.author.id)):
        desc = "You are currently blacklisted from using the bot. Please reach out to the bot developer on the support server for more information."
        if blacklist.reason:
            desc += f"\nReason: `{blacklist.reason}`"
        emb = makeembed_failedaction(description=desc)
        await ctx.reply(embed=emb, ephemeral=True, delete_after=10 if not ctx.interaction else None)
        return False
    return True

def before_send(event, hint):
    if 'exc_info' in hint:
        exc_type, exc_value, tb = hint['exc_info']
        if isinstance(exc_value, aiohttp.ClientError):
            return None
        
        if 'client_exceptions' in event.get('exception',{}).get('values', [{}])[0].get('type'):
            return None
    return event

async def main():
    #if PROD:
    sentry_sdk.init(
        dsn=SENTRY_URL,
        # Set traces_sample_rate to 1.0 to capture 100%
        # of transactions for performance monitoring.
        traces_sample_rate=.5,
        # Set profiles_sample_rate to 1.0 to profile 100%
        # of sampled transactions.
        # We recommend adjusting this value in production.
        profiles_sample_rate=.5,

        environment="production" if PROD else "development",

        integrations=[
            AsyncioIntegration(),
        ],

        _experiments={
            "profiles_sample_rate": .5, #type: ignore
        },

        before_send=before_send
    )

    async with aiohttp.ClientSession() as session:
        async with aiohttp.ClientSession() as session2:
            async with aiohttp.ClientSession() as session3:
                bot.session = session
                bot.session2 = session2
                bot.session3 = session3
                discord.utils.setup_logging(handler=handler)
                for file in EXTENSIONS:
                    await bot.load_extension(file)
                    bot_logger.debug(f"Loaded extension {file}")
                await bot.load_extension("jishaku")
                bot_logger.debug("Loaded extension jishaku")
                # await bot.load_extension("utils.cogs.error_handler")
                # bot_logger.debug("Loaded extension utils.cogs.error_handler")
                await bot.start(token)


if __name__ == "__main__":
    asyncio.run(main())
