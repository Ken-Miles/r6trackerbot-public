from __future__ import annotations

from typing import Dict, List, Optional, Union

import discord
from discord.ext import commands, tasks

from main import PROD
import yaml
import dateparser
from utils import BotU, CogU, ContextU
import traceback

class MultiURLButton(discord.ui.View):
    def __init__(self, buttons: dict[str, str]):
        super().__init__()
        for label, url in buttons.items():
            self.add_item(discord.ui.Button(label=label, url=url, style=discord.ButtonStyle.url))

TOPGG_API = "https://top.gg/api"
DISCORDBOTLIST_API = "https://discordbotlist.com/api/v1"
DISCORDBOTSGG_API = "https://discord.bots.gg/api/v1"
DISCORDLISTGG_API = "https://api.discordlist.gg/v0"
BOTLIST_ME_API = "https://api.botlist.me/api/v1"

with open('apikeys.yml','r') as f:
    apikeys = dict(yaml.safe_load(f))
    TOPGG_TOKEN = apikeys.get('topgg')
    DISCORDBOTLIST_TOKEN = apikeys.get('discordbotlist')
    DISCORDBOTSGG_TOKEN = apikeys.get('discordbotsgg')
    DISCORDLISTGG_TOKEN = apikeys.get('discordlistgg')
    BOTLIST_ME_TOKEN = apikeys.get('botlistme')
    assert TOPGG_TOKEN is not None and DISCORDBOTLIST_TOKEN is not None and DISCORDBOTSGG_TOKEN is not None and DISCORDLISTGG_TOKEN is not None and BOTLIST_ME_TOKEN is not None

class VoteBackend(CogU, name='Voting Backend', hidden=True):
    bot: BotU

    def __init__(self, bot: BotU):
        self.bot = bot
    
    async def topgg_get_votes(self) -> List[Dict[str, Union[str, int]]]:
        """
        Gets the last 1000 voters for your bot.

        If your bot receives more than 1000 votes monthly you cannot use this endpoints and must use webhooks and implement your own caching instead.

        This endpoint only returns unique votes, it does not include double votes (weekend votes).

        Returns:
            List[Dict[str, Union[str, int]]]: A list of dictionaries containing the voter's ID and username/avatar.
        """        
        url = f"{TOPGG_API}/bots/{self.bot.user.id}/votes"

        r = await self._get_json_or_empty(url)

        return r

    async def topgg_get_num_votes(self) -> int:
        """Get the number of votes for your bot.
        Calls the `topgg_get_votes` method and returns the length of the list.

        Returns:
            int: The number of votes for your bot.
        """        
        return len(await self.topgg_get_votes())
    
    async def topgg_get_bot_stats(self):
        """Get the bot's stats on top.gg.

        Specific stats about a bot.

        Returns:
            dict: A dictionary containing the bot's stats.
        """        
        url = f"{TOPGG_API}/bots/{self.bot.user.id}/stats"

        headers = {
            'Authorization': TOPGG_TOKEN,
        }

        return await self._get_json_or_empty(url, headers=headers)

    async def topgg_get_user_voted(self, user: discord.abc.User) -> bool:
        """Check if a user has voted for your bot.

        Args:
            user (discord.abc.User): The user to check.

        Returns:
            bool: Whether the user has voted for your bot.
        """        
        url = f"{TOPGG_API}/bots/{self.bot.user.id}/check"

        r = await self._get_json_or_empty(url, params={"userId": user.id})

        voted = dict(r).get("voted", False)

        if voted == 1: voted = True
        elif voted == 0: voted = False
        else: raise ValueError(f"Unexpected value for voted: {voted}")

        return voted

    async def dcbotlist_get_votes(self) -> List[Dict[str, Union[str, int]]]:
        """Get the last 500 voters for your bot.

        If your bot receives more than 500 votes monthly you cannot use this endpoints and must use webhooks and implement your own caching instead.

        This endpoint only returns unique votes, it does not include double votes (weekend votes).

        Returns:
            List[Dict[str, Union[str, int]]]: A list of dictionaries containing the voter's ID and username/avatar.
        """        
        url = f"{DISCORDBOTLIST_API}/bots/{self.bot.user.id}/upvotes"

        headers = {
            "Authorization": DISCORDBOTLIST_TOKEN,
            'Content-Type': 'application/json',
        }

        r = await self._get_json_or_empty(url, headers=headers)
        upvotes = []
        for upvote in r.get('upvotes', []):
            if upvote.get('timestamp',None):
                upvote['timestamp'] = dateparser.parse(upvote['timestamp'])
            upvotes.append(upvote)
        
        return upvotes

    async def dcbotlist_get_num_votes(self) -> int:
        """Get the number of votes for your bot.

        Returns:
            int: The number of votes for your bot.
        """        
        url = f"{DISCORDBOTLIST_API}/bots/{self.bot.user.id}/upvotes"

        headers = {
            "Authorization": DISCORDBOTLIST_TOKEN,
            'Content-Type': 'application/json',
        }

        r = await self._get_json_or_empty(url, headers=headers)

        return len(r.get('total', -1))
    
    async def dcbotlist_post_command_data(self):
        """Post command data to discordbotlist.com.

        Args:
            data (dict): The command data to post.

        Returns:
            dict: A dictionary containing the response.
        """        
        url = f"{DISCORDBOTLIST_API}/bots/{self.bot.user.id}/commands"

        headers = {
            "Authorization": DISCORDBOTLIST_TOKEN,
            'Content-Type': 'application/json',
        }

        guild = None

        commands = self.bot.tree._get_all_commands(guild=guild)
        data = [command.to_dict(self.bot.tree) for command in commands]

        #json.dumps(data)

        return await self._post(url, json=data, headers=headers)

    async def topgg_post_stats(self):
        """Post the bot's stats to top.gg.

        This endpoint is used to update the bot's stats on top.gg.

        Returns:
            dict: A dictionary containing the bot's stats.
        """

        data = {}

        headers = {
            'Authorization': TOPGG_TOKEN,
            'Content-Type': 'application/json',
        }

        data["shard_id"] = self.bot.shard_id or 0
        data["shard_count"] = self.bot.shard_count or 1
        data["server_count"] = len(self.bot.guilds)
        
        url = f"{TOPGG_API}/bots/{self.bot.user.id}/stats"

        return await self._post(url, json=data, headers=headers)

    async def dcbotlist_post_stats(self):
        """Post the bot's stats to discordbotlist.com.

        This endpoint is used to update the bot's stats on discordbotlist.com.

        Returns:
            dict: A dictionary containing the bot's stats.
        """

        data = {
            'voice_connections': len(self.bot.voice_clients),
            'users': len(self.bot.users),
            'guilds': len(self.bot.guilds),
        }

        headers = {
            "Authorization": DISCORDBOTLIST_TOKEN,
            #'Content-Type': 'application/json',
        }

        url = f"{DISCORDBOTLIST_API}/bots/{self.bot.user.id}/stats"

        # if isinstance(self.bot, commands.AutoShardedBot):
        #     data["shard_id"] = self.bot.shard_id # type: ignore
            #data["shard_count"] = self.bot.shard_count
        
        return await self._post(url, json=data, headers=headers)

    async def dcbotsgg_post_stats(self):
        """Post the bot's stats to discord.bots.gg.

        This endpoint is used to update the bot's stats on discord.bots.gg.

        Returns:
            dict: A dictionary containing the bot's stats.

        """

        if isinstance(self.bot, commands.AutoShardedBot):
            # assert self.bot.shard_id is not None
            # shard = self.bot.get_shard(self.bot.shard_id)
            guild_count = len(self.bot.guilds)
            shard_count = self.bot.shard_count
            shard_id = self.bot.shard_id
        else:
            guild_count = len(self.bot.guilds)
            shard_count = 1
            shard_id = 0

        data = {
            "guildCount": guild_count,
            "shardCount": shard_count,
            "shardId": shard_id,
        }

        headers = {
            "Authorization": DISCORDBOTSGG_TOKEN,
            'Content-Type': 'application/json',
        }

        url = f"{DISCORDBOTSGG_API}/bots/{self.bot.user.id}/stats"

        return await self._post(url, json=data, headers=headers)
    
    async def dclistgg_post_stats(self):
        """Post the bot's stats to discordlist.gg.

        This endpoint is used to update the bot's stats on discordlist.gg.

        Returns:
            dict: A dictionary containing the bot's stats.
        """
        url = f"{DISCORDLISTGG_API}/bots/{self.bot.user.id}/guilds?count={len(self.bot.guilds)}"

        headers = {
            "Authorization": DISCORDLISTGG_TOKEN,
            'Content-Type': 'application/json',
        }

        return await self._put(url, headers=headers)
    
    async def botlistme_post_stats(self):
        """Post the bot's stats to botlist.me.

        This endpoint is used to update the bot's stats on botlist.me.

        Returns:
            dict: A dictionary containing the bot's stats.
        """
        data = {
            "server_count": len(self.bot.guilds),
            "shard_id": self.bot.shard_count or 1,
        }

        headers = {
            "Authorization": BOTLIST_ME_TOKEN,
            #'Content-Type': 'application/json',
        }

        url = f"{BOTLIST_ME_API}/bots/{self.bot.user.id}/stats"

        return await self._post(url, data=data, headers=headers)
    
    stats_funcs = [
        topgg_post_stats,
        dcbotlist_post_stats,
        #dcbotsgg_post_stats, # wont work
        #dclistgg_post_stats, # docs dont load
        botlistme_post_stats,
    ]

    @tasks.loop(minutes=1)
    async def post_stats(self):
        try:
            if not hasattr(self.bot.user, 'id'): return
            for func in self.stats_funcs:
                try:
                    await func(self)
                except Exception as e:
                    continue
        except Exception as e:
            traceback.print_exc()
            raise e
    # @tasks.loop(hours=1)
    # async def post_command_data(self):
    #     await self.dcbotlist_post_command_data()

    @commands.command(name='synccommands', hidden=True)
    @commands.is_owner()
    async def synccommands(self, ctx: ContextU):
        await self.dcbotlist_post_command_data()
        await ctx.reply("done")
    
    @commands.command(name='poststats', hidden=True)
    @commands.is_owner()
    async def poststats(self, ctx: ContextU):
        try:
            if not hasattr(self.bot.user, 'id'): return
            for func in self.stats_funcs:
                try:
                    await func(self)
                except Exception as e:
                    continue
        except Exception as e:
            traceback.print_exc()
            raise e
        await ctx.reply("done")

    async def _get_json(self, url: str, *args, **kwargs) -> Optional[dict]:
        r = await self._get(url, *args, **kwargs)
        return await r.json()

    async def _get_json_or_empty(self, url: str, *args, **kwargs) -> Union[dict, list]:
        try:
            return await self._get_json(url, *args, **kwargs) # type: ignore
        except: return {}

async def setup(bot: BotU):
    if PROD:    
        cog = VoteBackend(bot)
        cog.post_stats.start()
        #cog.post_command_data.start()
        await bot.add_cog(cog)
    else:
        pass