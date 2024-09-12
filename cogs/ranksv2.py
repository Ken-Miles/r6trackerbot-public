from __future__ import annotations
import asyncio
import datetime
from enum import Enum
import json
import logging
import random
import re
from typing import Dict, List, Literal, Optional, Tuple, Union
from urllib import parse

import aiohttp
import async_lru
from curl_cffi.requests import AsyncSession
import discord
from discord import app_commands
from discord.ext import commands, tasks
from discord.ext.commands import BucketType
import environ
import humanize
from siegeapi import Auth
from tortoise import Tortoise
from typing_extensions import Self
import yaml

from cogs.models import (
    NameChanges,
    PlayerEncounters,
    R6User,
    R6UserConnections,
    RankedStatsSeasonal,
    RankedStatsV2,
    Settings,
)
from utils import (
    BotU,
    CURRENT_SEASON_NUM,
    CogU,
    ContextU,
    Cooldown,
    FiveButtonPaginator,
    HTTPCode,
    PROXY_URL,
    RATELIMIT_WEBHOOK_URL,
    TOURNEY_SERVER,
    URLButton,
    USERNAME_CHANNEL,
    create_paginator,
    dchyperlink,
    dctimestamp,
    emojidict,
    generate_pages,
    handler,
    makeembed,
    makeembed_bot,
    requests_logger,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(handler)

R6_GAME_APPIDS = [
    "4008612d-3baf-49e4-957a-33066726a7bc", # xbox one
    "76f580d5-7f50-47cc-bbc1-152d000bfe59", # xbox series x
    "6e3c99c9-6c3f-43f4-b4f6-f1a3143f2764", # ps5
    "fb4cc4c9-2063-461d-a1e8-84a7d36525fc", # ps4
    "e3d5ea9e-50bd-43b7-88bf-39794f4e3d40", # pc
]

SUPPORT_SERVER = "https://discord.gg/SfJMwjPATV"

_STARTUP = datetime.datetime.now()
EMAIL = None
PASSWORD = None
XBOX_API_KEY = None
PSN_API_KEY = None
UPLAY_API_KEY = None
STEAM_API_KEY = None

#API_BASE = 'http://localhost:4000'
#API_BASE = 'https://public-ubiservices.ubi.com/v3'
API_BASEV1 =  "https://api.tracker.gg/api/v1/r6siege"
API_BASEV2 = "https://api.tracker.gg/api/v2/r6siege"

VALID_ROUTES = [
    '/status',
    
    '/{platform}/id/{username}',
    
    '/{platform}/level/id/{id}',
    '/{platform}/rank/username/{username}',

    '/{platform}/playtime/id/{id}',
    '/{platform}/playtime/username/{username}',

    '/{platform}/stats/id/{id}',
    '/{platform}/stats/username/{username}',

    '/{platform}/username/{id}',
]

SAMPLE_IDS = [
    '4cd63ce4-be57-4908-9431-02a8632624ac', # me
    '2c39b972-5b97-406f-8625-997f0d1ff930', # junko
    '5ea729f7-076a-46d4-809d-86607363effa', # caseoh
    'c0eebe30-107f-4b70-b826-e5d6c5dc2e0c', # brendan
]

XBOX_LIVE_RE = re.compile(r'(?!.*\s{2})(?P<username>[a-zA-Z][a-zA-Z0-9 ]{0,12})')

PSN_RE = re.compile(r'^(?=.*[a-zA-Z])[a-zA-Z][a-zA-Z0-9_-]{2,15}$')

UPLAY_RE = re.compile(r'(?!.*\b(?:ubi|ubi$))(?!^\d)[a-zA-Z][a-zA-Z0-9_.-]{2,14}')

ID_RE = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}')

URL_RE = re.compile(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*(),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+')

COMPLETE_RANK_ICON_DICT = {
    'unranked': "https://trackercdn.com/cdn/r6.tracker.network/ranks/s28/small/unranked.png",

    'copper': "https://trackercdn.com/cdn/r6.tracker.network/ranks/s28/small/copper-1.png",
    'copper_5': "https://trackercdn.com/cdn/r6.tracker.network/ranks/s28/small/copper-5.png",
    'copper_4': "https://trackercdn.com/cdn/r6.tracker.network/ranks/s28/small/copper-4.png",
    'copper_3': "https://trackercdn.com/cdn/r6.tracker.network/ranks/s28/small/copper-3.png",
    'copper_2': "https://trackercdn.com/cdn/r6.tracker.network/ranks/s28/small/copper-2.png",
    'copper_1': "https://trackercdn.com/cdn/r6.tracker.network/ranks/s28/small/copper-1.png",

    'bronze': "https://trackercdn.com/cdn/r6.tracker.network/ranks/s28/small/bronze-1.png",
    'bronze_5': "https://trackercdn.com/cdn/r6.tracker.network/ranks/s28/small/bronze-5.png",
    'bronze_4': "https://trackercdn.com/cdn/r6.tracker.network/ranks/s28/small/bronze-4.png",
    'bronze_3': "https://trackercdn.com/cdn/r6.tracker.network/ranks/s28/small/bronze-3.png",
    'bronze_2': "https://trackercdn.com/cdn/r6.tracker.network/ranks/s28/small/bronze-2.png",
    'bronze_1': "https://trackercdn.com/cdn/r6.tracker.network/ranks/s28/small/bronze-1.png",

    'silver': "https://trackercdn.com/cdn/r6.tracker.network/ranks/s28/small/silver-1.png",
    'silver_5': "https://trackercdn.com/cdn/r6.tracker.network/ranks/s28/small/silver-5.png",
    'silver_4': "https://trackercdn.com/cdn/r6.tracker.network/ranks/s28/small/silver-4.png",
    'silver_3': "https://trackercdn.com/cdn/r6.tracker.network/ranks/s28/small/silver-3.png",
    'silver_2': "https://trackercdn.com/cdn/r6.tracker.network/ranks/s28/small/silver-2.png",
    'silver_1': "https://trackercdn.com/cdn/r6.tracker.network/ranks/s28/small/silver-1.png",
    
    'gold': "https://trackercdn.com/cdn/r6.tracker.network/ranks/s28/small/gold-1.png",
    'gold_5': "https://trackercdn.com/cdn/r6.tracker.network/ranks/s28/small/gold-5.png",
    'gold_4': "https://trackercdn.com/cdn/r6.tracker.network/ranks/s28/small/gold-4.png",
    'gold_3': "https://trackercdn.com/cdn/r6.tracker.network/ranks/s28/small/gold-3.png",
    'gold_2': "https://trackercdn.com/cdn/r6.tracker.network/ranks/s28/small/gold-2.png",
    'gold_1': "https://trackercdn.com/cdn/r6.tracker.network/ranks/s28/small/gold-1.png",

    'platinum': "https://trackercdn.com/cdn/r6.tracker.network/ranks/s28/small/platinum-1.png",
    'platinum_5': "https://trackercdn.com/cdn/r6.tracker.network/ranks/s28/small/platinum-5.png",
    'platinum_4': "https://trackercdn.com/cdn/r6.tracker.network/ranks/s28/small/platinum-4.png",
    'platinum_3': "https://trackercdn.com/cdn/r6.tracker.network/ranks/s28/small/platinum-3.png",
    'platinum_2': "https://trackercdn.com/cdn/r6.tracker.network/ranks/s28/small/platinum-2.png",
    'platinum_1': "https://trackercdn.com/cdn/r6.tracker.network/ranks/s28/small/platinum-1.png",

    'emerald': "https://trackercdn.com/cdn/r6.tracker.network/ranks/s28/small/emerald-1.png",
    'emerald_5': "https://trackercdn.com/cdn/r6.tracker.network/ranks/s28/small/emerald-5.png",
    'emerald_4': "https://trackercdn.com/cdn/r6.tracker.network/ranks/s28/small/emerald-4.png",
    'emerald_3': "https://trackercdn.com/cdn/r6.tracker.network/ranks/s28/small/emerald-3.png",
    'emerald_2': "https://trackercdn.com/cdn/r6.tracker.network/ranks/s28/small/emerald-2.png",
    'emerald_1': "https://trackercdn.com/cdn/r6.tracker.network/ranks/s28/small/emerald-1.png",
    
    'diamond': "https://trackercdn.com/cdn/r6.tracker.network/ranks/s28/small/diamond-1.png",
    'diamond_5': "https://trackercdn.com/cdn/r6.tracker.network/ranks/s28/small/diamond-5.png",
    'diamond_4': "https://trackercdn.com/cdn/r6.tracker.network/ranks/s28/small/diamond-4.png",
    'diamond_3': "https://trackercdn.com/cdn/r6.tracker.network/ranks/s28/small/diamond-3.png",
    'diamond_2': "https://trackercdn.com/cdn/r6.tracker.network/ranks/s28/small/diamond-2.png",
    'diamond_1': "https://trackercdn.com/cdn/r6.tracker.network/ranks/s28/small/diamond-1.png",

    'champion': "https://trackercdn.com/cdn/r6.tracker.network/ranks/s28/small/champions.png",
}

def dict_to_list(d: dict) -> Union[list, dict]:
    for tr, kv in enumerate(d.items()):
        k, v = kv[0], kv[1]
        if str(k).isnumeric():
            if k != str(tr):
                return d
        else: return d
    return list(d.values())

class Platform(Enum):
    XBOX = ('xbl', 'Xbox', XBOX_LIVE_RE, discord.Color.dark_green(), 2)
    PSN = ('psn', 'PlayStation', PSN_RE, discord.Color.blue(), 1)
    UBI = ('ubi', 'UPlay', UPLAY_RE, discord.Color.light_gray(), 4)
    UPLAY = ('uplay', 'UPlay', UPLAY_RE, discord.Color.light_gray(), 4)
    PC = UBI
    ALL = ('id', 'All Platforms', None, discord.Color.blurple(), 3)

    @classmethod
    def all_platforms(cls):
        return [cls.XBOX, cls.PSN, cls.UBI, cls.ALL]

    def to_choice(self) -> app_commands.Choice:
        return app_commands.Choice(name=self.proper_name, value=self.route)

    @property
    def proper_name(self):
        return self.value[1]
    
    @property
    def route(self):
        if self.is_pc:
            return Platform.UBI.value[0]
        return self.value[0]

    @property
    def username_re(self):
        return self.value[2]
    
    @property
    def emoji(self) -> str:
        return emojidict.get(self.route) # type: ignore
    
    @property
    def color(self) -> discord.Colour:
        return self.value[3]

    @property
    def id_re(self):
        return ID_RE

    @property
    def is_console(self):
        return self is Platform.XBOX or self is Platform.PSN
    
    @property
    def is_pc(self):
        return self in [Platform.UBI, Platform.UPLAY, Platform.PC]

    @classmethod
    def from_route(cls, route: str) -> Self:
        route = route.lstrip('/').lower().strip()
        for platform in cls:
            if platform.route.lower().strip() == route:
                return platform
        raise ValueError("give me a valid route fucker")

    @classmethod
    def from_str(cls, s: str) -> Self:
        if isinstance(s, cls): 
            return s

        s = str(s).strip().lower()
        for platform in cls:
            if platform.route.lower().strip() == s \
            or platform.proper_name.lower().strip() == s:
                return platform
        raise ValueError("give me a valid platform fucker")
    
    @classmethod
    def from_num(cls, n: int) -> Self:
        for platform in cls:
            if platform.num == n:
                return platform
        raise ValueError(f"invalid platform number: {n}")
        
    @property
    def num(self) -> int:
        return self.value[4]
    
    def __int__(self) -> int:
        return self.num

    def __str__(self) -> str:
        return self.route
    
    def __eq__(self, other) -> bool:
        return self.num == other.num
    
    def __hash__(self):
        return super().__hash__()


class Gamemode(Enum):
    RANKED = (1, "ranked", "Ranked", 'pvp_ranked')
    STANDARD = (2, 'standard', 'Standard', 'pvp_standard')
    CASUAL = (3, "casual", "Casual", 'pvp_casual')

    ARCADE = (4, "arcade", "Arcade", 'pvp_warmup')
    WARMUP = (4, "warmup", "Warmup", 'pvp_warmup')

    EVENT = (5, "event", "Event", 'pvp_event')
    NEWCOMER = (6, 'newcomer', "Newcomer", 'pvp_newcomer')
    QUICKPLAY = (7, 'quickplay','Quick Play','pvp_quickplay') # casual + standard?

    @classmethod
    def all_with_leaderboard(cls):
        return [cls.RANKED, cls.STANDARD, cls.CASUAL, cls.WARMUP]

    def to_choice(self) -> app_commands.Choice:
        return app_commands.Choice(name=self.proper_name, value=self.proper_name)

    @property
    def num(self) -> int:
        return self.value[0]

    @property
    def name(self) -> str:
        return self.value[1]

    @property
    def proper_name(self) -> str:
        return self.value[2]

    @property
    def route(self) -> str:
        return self.value[3]

    @classmethod
    def from_str(cls, s: Union[str, int]) -> Self:
        if not isinstance(s, cls):
            if isinstance(s, int) or s.isnumeric():
                s = int(s)
                for item in cls:
                    if item.value[0] == s:
                        return item
            else:
                for item in cls:
                    if item.value[1] == s or item.value[2] == s:
                        return item
            raise ValueError(f"Gamemode with string/num {s} doesn't exist.")
        return s

class GamemodeConverter(commands.Converter, app_commands.Transformer):
    @property
    def choices(self):
        _choices = []
        for platform in Gamemode:
            _choices.append(platform.to_choice())
            #_choices.append(platform.to_choice())
        return _choices
    
    async def convert(self, ctx, argument):
        try:
            return Gamemode.from_str(argument)
        except ValueError:
            raise commands.BadArgument(f"Invalid gamemode: {argument}")
    
    async def transform(self, interaction, value):
        return await self.convert(await ContextU.from_interaction(interaction), value)

class LeaderboardGamemodeConverter(commands.Converter, app_commands.Transformer):
    @property
    def choices(self):
        _choices = []
        for platform in Gamemode.all_with_leaderboard():
            _choices.append(platform.to_choice())
            #_choices.append(platform.to_choice())
        return _choices
    
    async def convert(self, ctx, argument):
        try:
            return Gamemode.from_str(argument)
        except ValueError:
            raise commands.BadArgument(f"Invalid gamemode: {argument}")
    
    async def transform(self, interaction, value):
        return await self.convert(await ContextU.from_interaction(interaction), value)


class OriginalLeaderboardFilter(Enum):
    ranked_kills = (1, 'RankedKills', 'Ranked Kills')
    ranked_wins = (2, 'RankedWins', 'Ranked Wins')
    ranked_losses = (3, 'RankedLosses', 'Ranked Losses')
    ranked_kd = (4, 'RankedKd', 'Ranked K/D')
    ranked_kpg = (5, 'RankedKpg', 'Ranked KPG')

    wins = (6, 'Wins', 'Wins')
    losses = (7, 'Losses', 'Losses')
    abandons = (8, 'Abandons', 'Abandons')
    matches = (9, 'Matches', 'Matches')
    wl_ratio = (10, 'WLRatio', 'Win/Loss Ratio')
    rankpoints = (11, 'rankpoints', 'Rank Points')
    maxrankpoints = (12, 'maxrankpoints', 'Max Rank Points')

    @classmethod
    def ranked_filters(cls):
        return [cls.ranked_kills, cls.ranked_wins, cls.ranked_losses, cls.ranked_kd, cls.ranked_kpg]
    
    @classmethod
    def nonranked_filters(cls):
        return [cls.wins, cls.losses, cls.abandons, cls.matches, cls.wl_ratio]

    def to_choice(self) -> app_commands.Choice:
        return app_commands.Choice(name=self.proper_name, value=self.proper_name)

    def to_non_ranked_option(self):
        """Converts a ranked option into a non ranked option.
        eg: ranked_wins -> wins
        Returns itself if there is no non-ranked equivelant or if it is already non-ranked."""

        if self is self.__class__.ranked_wins:
            return self.__class__.wins
        elif self is self.__class__.ranked_losses:
            return self.__class__.losses
        elif self is self.__class__.ranked_kd \
        or self is self.__class__.ranked_kpg \
        or self is self.__class__.ranked_kills:
            return None
        return self
    
    def to_ranked_option(self):
        """Converts a non-ranked option into a ranked option.
        eg: wins -> ranked_wins
        Returns itself if there is no ranked equivelant or if it is already ranked."""
        if self is self.__class__.wins:
            return self.__class__.ranked_wins
        elif self is self.__class__.losses:
            return self.__class__.ranked_losses
        elif self in [self.__class__.abandons, self.__class__.matches, self.__class__.wl_ratio]:
            return None
        return self

    @property
    def num(self) -> int:
        return self.value[0]

    @property
    def name(self) -> str:
        return self.value[1]
    
    @property
    def proper_name(self) -> str:
        return self.value[2]
    
    @classmethod
    def from_str(cls, s: str) -> Self:
        if not isinstance(s, cls):
            if isinstance(s, int) or s.isnumeric():
                return cls.from_num(int(s))
            else:
                for item in cls:
                    if item.value[1] == s or item.value[2] == s:
                        return item
            raise ValueError(f"LeaderboardFilter with string/num {s} doesn't exist.")
        return s
    
    @classmethod
    def from_num(cls, n: int) -> Self:
        for item in cls:
            if item.value[0] == n:
                return item
        raise ValueError(f"LeaderboardFilter with num {n} doesn't exist.")

    @property
    def route(self) -> str:
        return self.value[1]

#         #filter_by: Literal['Current MMR', 'Current Rank Points','Current Rank', 'Peak MMR', 'Peak Rank Points', 'Peak Rank', 'Wins', 'Losses', 'Kills', 'Deaths', 'Abandons']='Current MMR',

class LeaderboardFilter(Enum):
    current_mmr = (1, 'Current MMR', 'Current MMR', 'rankpoints')
    current_rank = (1, 'Current Rank', 'Current Rank', 'rankpoints')

    peak_mmr = (2, 'Peak MMR', 'Peak MMR', 'maxrankpoints')
    peak_rank = (2, 'Peak Rank', 'Peak Rank', 'maxrankpoints')

    wins = (3, 'Wins', 'Wins', 'matcheswon')
    losses = (4, 'Losses', 'Losses', 'matcheslost')
    kills = (5, 'Kills', 'Kills')
    deaths = (6, 'Deaths', 'Deaths', 'deaths')
    abandons = (7, 'Abandons', 'Abandons', 'abandons')

    @classmethod
    def all_filters(cls):
        return [cls.current_mmr, cls.current_rank, cls.peak_mmr, cls.peak_rank, cls.wins, cls.losses, cls.kills, cls.deaths, cls.abandons]
    
    @classmethod
    def ranked_filters(cls):
        return [cls.current_mmr, cls.current_rank, cls.peak_mmr, cls.peak_rank]
    
    @classmethod
    def nonranked_filters(cls):
        return [cls.wins, cls.losses, cls.kills, cls.deaths, cls.abandons]
    
    def to_choice(self) -> app_commands.Choice:
        return app_commands.Choice(name=self.proper_name, value=self.proper_name)
    
    

    @property
    def num(self) -> int:
        return self.value[0]
    
    @property
    def name(self) -> str:
        return self.value[1]
    
    @property
    def proper_name(self) -> str:
        return self.value[2]
    
    @property
    def route(self) -> str:
        return self.value[3]

    @classmethod
    def from_str(cls, s: str) -> Self:
        if not isinstance(s, cls):
            if isinstance(s, int) or s.isnumeric():
                return cls.from_num(int(s))
            else:
                for item in cls:
                    if item.value[1] == s or item.value[2] == s:
                        return item
            raise ValueError(f"LeaderboardFilter with string/num {s} doesn't exist.")
        return s
    
    @classmethod
    def from_num(cls, n: int) -> Self:
        for item in cls:
            if item.value[0] == n:
                return item
        raise ValueError(f"LeaderboardFilter with num {n} doesn't exist.")
    
    # @property
    # def route(self) -> str:
    #     return self.value[1]
    
    def __str__(self) -> str:
        return self.route
    
    def __int__(self) -> int:
        return self.num
    
    def __eq__(self, other) -> bool:
        return self.num == other.num
    
    def __hash__(self):
        return super().__hash__()

    

class LeaderboardFilterConverter(commands.Converter, app_commands.Transformer):
    @property
    def choices(self):
        _choices = []
        for platform in LeaderboardFilter.all_filters():
            _choices.append(platform.to_choice())
            #_choices.append(platform.to_choice())
        return _choices

    async def convert(self, ctx, argument):
        try:
            return Platform.from_str(argument)
        except ValueError:
            raise commands.BadArgument(f"Invalid platform: {argument}")

    async def transform(self, interaction, value):
        return await self.convert(await ContextU.from_interaction(interaction), value)

# class LeaderboardFilterGeneralConverter(commands.Converter, app_commands.Transformer):
#     @property
#     def choices(self):
#         _choices = []
#         for f in  LeaderboardFilter.all_filters():
#             if (choice := f.to_non_ranked_option()):
#                 _choices.append(choice.to_choice())
#             #_choices.append(platform.to_choice())
#         return _choices

#     async def convert(self, ctx, argument):
#         try:
#             return Platform.from_str(argument)
#         except ValueError:
#             raise commands.BadArgument(f"Invalid platform: {argument}")

#     async def transform(self, interaction, value):
#         return await self.convert(await ContextU.from_interaction(interaction), value)


class R6GeneralRank(Enum):
    UNRANKED = {"name": "Unranked", "min_mmr": 0, "max_mmr": 0, 'color': discord.Colour.from_str('#281c24')}
    COPPER = {"name": "Copper", "min_mmr": 1000, "max_mmr": 1499, 'color': discord.Colour.from_str('#900201')}
    BRONZE = {"name": "Bronze",  "min_mmr": 1500, "max_mmr": 1999, 'color': discord.Colour.from_str('#b3732a')}
    SILVER = {"name": "Silver", "min_mmr": 2000, "max_mmr": 2499, 'color': discord.Colour.from_str('#a4a4a4')}
    GOLD = {"name": "Gold", "min_mmr": 2500, "max_mmr": 2999, 'color': discord.Colour.from_str('#e5c613')}
    PLATINUM = {"name": "Platinum", "min_mmr": 3000, "max_mmr": 3499, 'color': discord.Colour.from_str('#44ccc2')}
    EMERALD = {"name": "Emerald", "min_mmr": 3500, "max_mmr": 3999, 'color': discord.Colour.from_str('#05cc77')}
    DIAMOND = {"name": "Diamond", "min_mmr": 4000, "max_mmr": 4499, 'color': discord.Colour.from_str('#b093ff')}
    CHAMPION = {"name": "Champion", "min_mmr": 4500, "max_mmr": 999999, 'color': discord.Colour.from_str('#d0073c')}
    CHAMPIONS = CHAMPION

    @classmethod
    def from_mmr(cls, mmr: int) -> "R6GeneralRank":
        """Get a rank enum object from a given MMR integer.

        Args:
            mmr (int): The MMR number.

        Raises:
            ValueError: If the MMR value is not in the range of a rank.

        Returns:
            R6GeneralRank: The enum object.
        """        
        for rank in cls:
            if mmr in range(int(rank.value.get('min_mmr',0))-1, int(rank.value.get('max_mmr',0))):
                return rank
        raise ValueError("No rank matched the given MMR.")

    @staticmethod
    def from_str(s: str) -> "R6GeneralRank":
        """Get a rank enum object from a given string.

        Args:
            s (str): The string to match.

        Raises:
            ValueError: If the string does not match any ranks.

        Returns:
            R6GeneralRank: The enum object.
        """
        # remove a space and a number at the end of the string if present
        # ex: "Copper 5" -> "Copper"
        s = re.sub(r'\d+$', '', s.strip().lower()).rstrip('s')

        for rank in __class__:
            if str(rank.value.get('name')).lower().strip()== s:
                return rank
        raise ValueError("No rank matched the given string.")

    @property
    def name(self) -> str:
        return self.value.get('name','')
    
    @property
    def min_mmr(self) -> int:
        return self.value.get('min_mmr',0)
    
    @property
    def max_mmr(self) -> int:
        return self.value.get('max_mmr',0)

    @property
    def image_url(self) -> str:
        return COMPLETE_RANK_ICON_DICT.get(self.name.lower().replace(' ','_'), '')
    
    @property
    def color(self) -> discord.Colour:
        return self.value.get('color', discord.Colour.default())

    @property
    def is_copper(self):
        return self is R6GeneralRank.COPPER
    
    @property
    def is_bronze(self):
        return self is R6GeneralRank.BRONZE
    
    @property
    def is_silver(self):
        return self is R6GeneralRank.SILVER
    
    @property
    def is_gold(self):
        return self is R6GeneralRank.GOLD
    
    @property
    def is_platinum(self):
        return self is R6GeneralRank.PLATINUM
    
    @property
    def is_emerald(self):
        return self is R6GeneralRank.EMERALD
    
    @property
    def is_diamond(self):
        return self is R6GeneralRank.DIAMOND
    
    @property
    def is_champion(self):
        return self is R6GeneralRank.CHAMPION
    
    @property
    def is_unranked(self):
        return self is R6GeneralRank.UNRANKED
    
    @property
    def is_ranked(self):
        return not self.is_unranked
    
    def __lt__(self, other: "R6GeneralRank"):
        return self.min_mmr < other.min_mmr
    
    def __le__(self, other: "R6GeneralRank"):
        return self.min_mmr <= other.min_mmr
    
    def __gt__(self, other: "R6GeneralRank"):
        return self.min_mmr > other.min_mmr
    
    def __ge__(self, other: "R6GeneralRank"):
        return self.min_mmr >= other.min_mmr
    
    def __str__(self):
        return self.name

class R6Rank(Enum):
    UNRANKED = {"min_mmr": 0, "max_mmr": 0,"name": "Unranked", "rank": R6GeneralRank.UNRANKED}
    COPPER_5 = {"min_mmr": 1000, "max_mmr": 1099, "name": "Copper 5", "rank": R6GeneralRank.COPPER}
    COPPER_4 = {"min_mmr": 1100, "max_mmr": 1199, "name": "Copper 4", "rank": R6GeneralRank.COPPER}
    COPPER_3 = {"min_mmr": 1200, "max_mmr": 1299, "name": "Copper 3", "rank": R6GeneralRank.COPPER}
    COPPER_2 = {"min_mmr": 1300, "max_mmr": 1399, "name": "Copper 2", "rank": R6GeneralRank.COPPER}
    COPPER_1 = {"min_mmr": 1400, "max_mmr": 1499, "name": "Copper 1", "rank": R6GeneralRank.COPPER}

    BRONZE_5 = {"min_mmr": 1500, "max_mmr": 1599, "name": "Bronze 5", "rank": R6GeneralRank.BRONZE}
    BRONZE_4 = {"min_mmr": 1600, "max_mmr": 1699, "name": "Bronze 4", "rank": R6GeneralRank.BRONZE}
    BRONZE_3 = {"min_mmr": 1700, "max_mmr": 1799, "name": "Bronze 3", "rank": R6GeneralRank.BRONZE}
    BRONZE_2 = {"min_mmr": 1800, "max_mmr": 1899, "name": "Bronze 2", "rank": R6GeneralRank.BRONZE}
    BRONZE_1 = {"min_mmr": 1900, "max_mmr": 1999, "name": "Bronze 1", "rank": R6GeneralRank.BRONZE}

    SILVER_5 = {"min_mmr": 2000, "max_mmr": 2099, "name": "Silver 5", "rank": R6GeneralRank.SILVER}
    SILVER_4 = {"min_mmr": 2100, "max_mmr": 2199, "name": "Silver 4", "rank": R6GeneralRank.SILVER} 
    SILVER_3 = {"min_mmr": 2200, "max_mmr": 2299, "name": "Silver 3", "rank": R6GeneralRank.SILVER} 
    SILVER_2 = {"min_mmr": 2300, "max_mmr": 2399, "name": "Silver 2", "rank": R6GeneralRank.SILVER} 
    SILVER_1 = {"min_mmr": 2400, "max_mmr": 2499, "name": "Silver 1", "rank": R6GeneralRank.SILVER} 

    GOLD_5 = {"min_mmr": 2500, "max_mmr": 2599, "name": "Gold 5", "rank": R6GeneralRank.GOLD}
    GOLD_4 = {"min_mmr": 2600, "max_mmr": 2699, "name": "Gold 4", "rank": R6GeneralRank.GOLD}
    GOLD_3 = {"min_mmr": 2700, "max_mmr": 2799, "name": "Gold 3", "rank": R6GeneralRank.GOLD}
    GOLD_2 = {"min_mmr": 2800, "max_mmr": 2899, "name": "Gold 2", "rank": R6GeneralRank.GOLD}
    GOLD_1 = {"min_mmr": 2900, "max_mmr": 2999, "name": "Gold 1", "rank": R6GeneralRank.GOLD}

    PLATINUM_5 = {"min_mmr": 3000, "max_mmr": 3099, "name": "Platinum 5", "rank": R6GeneralRank.PLATINUM}
    PLATINUM_4 = {"min_mmr": 3100, "max_mmr": 3199, "name": "Platinum 4", "rank": R6GeneralRank.PLATINUM}
    PLATINUM_3 = {"min_mmr": 3200, "max_mmr": 3299, "name": "Platinum 3", "rank": R6GeneralRank.PLATINUM}
    PLATINUM_2 = {"min_mmr": 3300, "max_mmr": 3399, "name": "Platinum 2", "rank": R6GeneralRank.PLATINUM}
    PLATINUM_1 = {"min_mmr": 3400, "max_mmr": 3499, "name": "Platinum 1", "rank": R6GeneralRank.PLATINUM}

    EMERALD_5 = {"min_mmr": 3500, "max_mmr": 3599, "name": "Emerald 5", "rank": R6GeneralRank.EMERALD}
    EMERALD_4 = {"min_mmr": 3600, "max_mmr": 3699, "name": "Emerald 4", "rank": R6GeneralRank.EMERALD}
    EMERALD_3 = {"min_mmr": 3700, "max_mmr": 3799, "name": "Emerald 3", "rank": R6GeneralRank.EMERALD}
    EMERALD_2 = {"min_mmr": 3800, "max_mmr": 3899, "name": "Emerald 2", "rank": R6GeneralRank.EMERALD}
    EMERALD_1 = {"min_mmr": 3900, "max_mmr": 3999, "name": "Emerald 1", "rank": R6GeneralRank.EMERALD}

    DIAMOND_5 = {"min_mmr": 4000, "max_mmr": 4099, "name": "Diamond 5", "rank": R6GeneralRank.DIAMOND}
    DIAMOND_4 = {"min_mmr": 4100, "max_mmr": 4199, "name": "Diamond 4", "rank": R6GeneralRank.DIAMOND}
    DIAMOND_3 = {"min_mmr": 4200, "max_mmr": 4299, "name": "Diamond 3", "rank": R6GeneralRank.DIAMOND}
    DIAMOND_2 = {"min_mmr": 4300, "max_mmr": 4399, "name": "Diamond 2", "rank": R6GeneralRank.DIAMOND}
    DIAMOND_1 = {"min_mmr": 4400, "max_mmr": 4499, "name": "Diamond 1", "rank": R6GeneralRank.DIAMOND}

    CHAMPIONS = {"min_mmr": 4500, "max_mmr": 999999, "name": "Champion", "rank": R6GeneralRank.CHAMPION}
    CHAMPION = CHAMPIONS

    @property
    def name(self) -> str:
        return self.value.get('name','')

    @property
    def min_mmr(self) -> int:
        return self.value.get('min_mmr',0)
    
    @property
    def max_mmr(self) -> int:
        return self.value.get('max_mmr',0)
    
    @property
    def rank(self) -> R6GeneralRank:
        """Get the generic rank of the R6Rank (eg, Copper from Copper 5)"""        
        return self.value.get('rank', R6GeneralRank.UNRANKED)

    @property
    def color(self) -> discord.Colour:
        return self.rank.color

    @classmethod
    def from_mmr(cls, mmr: int) -> "R6Rank":
        """Get a rank enum object from a given MMR integer.

        Args:
            mmr (int): The MMR number.

        Raises:
            ValueError: If the MMR value is not in the range of a rank.

        Returns:
            R6Rank: The enum object.
        """
        for rank in cls:
            if mmr in range(rank.min_mmr, rank.max_mmr+1):
                return rank
        raise ValueError("No rank matched the given MMR.")

    @classmethod
    def from_str(cls, s: str) -> "R6Rank":
        """Get a rank enum object from a given string.

        Args:
            s (str): The string to match.

        Raises:
            ValueError: If the string does not match any ranks.

        Returns:
            R6Rank: The enum object.
        """
        # remove a space and a number at the end of the string if present
        # ex: "Copper 5" -> "Copper"
        s = s.strip().lower().rstrip('s')

        for rank in cls:
            if rank.name.strip().lower().rstrip('s')== s:
                return rank
        raise ValueError("No rank matched the given string.")

    @property
    def route(self) -> str:
        return f"{self.rank.name.lower().replace(' ','_')}"

    @property
    def emoji(self) -> str:
        return emojidict.get(str(self.route)) # type: ignore

    @property
    def image_url(self) -> str:
        return COMPLETE_RANK_ICON_DICT.get(self.name.lower().replace(' ','_'), '')

    @property
    def is_copper(self):
        return self.rank is R6GeneralRank.COPPER
    
    @property
    def is_bronze(self):
        return self.rank is R6GeneralRank.BRONZE
    
    @property
    def is_silver(self):
        return self.rank is R6GeneralRank.SILVER
    
    @property
    def is_gold(self):
        return self.rank is R6GeneralRank.GOLD
    
    @property
    def is_platinum(self):
        return self.rank is R6GeneralRank.PLATINUM
    
    @property
    def is_emerald(self):
        return self.rank is R6GeneralRank.EMERALD
    
    @property
    def is_diamond(self):
        return self.rank is R6GeneralRank.DIAMOND
    
    @property
    def is_champion(self):
        return self.rank is R6GeneralRank.CHAMPION
    
    @property
    def is_unranked(self):
        return self.rank is R6GeneralRank.UNRANKED
    
    @property
    def is_ranked(self):
        return not self.is_unranked

    def __eq__(self, other):
        if hasattr(other, 'min_mmr'):
            return self.min_mmr == other.min_mmr
        return self == other

    def __lt__(self, other: "R6Rank"):
        return self.min_mmr < other.min_mmr
    
    def __le__(self, other: "R6Rank"):
        return self.min_mmr <= other.min_mmr
    
    def __gt__(self, other: "R6Rank"):
        return self.min_mmr > other.min_mmr
    
    def __ge__(self, other: "R6Rank"):
        return self.min_mmr >= other.min_mmr

def is_username(s: str):
    s = s.strip()
    return XBOX_LIVE_RE.match(s) \
        or PSN_RE.match(s) \
        or UPLAY_RE.match(s)

def is_valid_id(s: str): 
    s = s.strip().lower()
    return ID_RE.match(s)

def is_valid_username(username: str, platform: Platform):
    if platform is Platform.PC:
        r = UPLAY_RE
    elif platform is Platform.PSN:
        r = PSN_RE
    elif platform is Platform.XBOX:
        r = XBOX_LIVE_RE
    else: raise ValueError("Invalid Platform")

    if r.match(username):
        return username.strip()
    return False

def clean_username(username: str) -> str:
    """Cleans a username string by removing whitespace from the beginning and end of the string, removing newlines, and stripping the string.
    In addition, it should also remove any quotes or other special characters that may be present in the username.
    """
    return username.replace('\n','').replace('"','').replace("'",'').strip()

def plural(n: int, plural_name: str='s') -> str:
    """Returns 's' if the number is not 1, otherwise returns ''.

    Args:
        n (int): Number of items.
        plural_name (str): What to reutrn if n != 1. Defaults to 's'.

    Returns:
        str: plural_name if n != 1, otherwise ''.
    """
    return plural_name if n != 1 else ''

def get_perma_r6_tracker_url(id: str, plat: Platform) -> str:
    """Get the permalink for the R6 Tracker page for a given user ID and platform.

    Args:
        id (str): The user's ID on the platform.
        platform (Platform): The platform of the user.

    Returns:
        str: The URL for the R6 Tracker page.
    """
    #return f"https://tracker.gg/r6siege/profile/{plat.route}/{id}"
    if plat is Platform.ALL or not plat:
        return f"https://r6.tracker.network/profile/id/{id}"
    else:
        return f"https://r6.tracker.network/r6siege/profile/{plat.route}/{id}/overview"

def get_r6_tracker_url(username: str, platform: Optional[Union[Platform, int]]=3) -> str:
    """Get the URL for the R6 Tracker page for a given username and platform.

    Args:
        username (str): The user's username on the platform.
        platform (Platform): The platform of the user.
        permalink (bool, optional): Whether to return the URL as a permalink. Defaults to True.

    Returns:
        str: The URL for the R6 Tracker page.
    """    
    username = parse.quote(username)
    # if isinstance(platform, int):
    #     platform = Platform.from_num(platform)
    
    assert platform is not None

    if isinstance(platform, int):
        plat = platform
    else:
        plat = platform.route.lower()

    #return f"https://tracker.gg/r6siege/profile/{plat}/{username}"
    return f"https://r6.tracker.network/r6siege/profile/{plat}/{username}/overview"

def get_r6_leaderboard_url(platform: Optional[Platform], season: int=CURRENT_SEASON_NUM, gamemode: Union[Gamemode, str, int]=Gamemode.RANKED) -> Optional[str]:
    """Get the URL for the R6 leaderboard for a given platform, season, and gamemode.

    Args:
        platform (Platform): Platform to get the leaderboard for. Pass None to get all platforms.
        gamemode (Literal[1, 2, 3, 4]): Integer cooresponding to the game mode. Ranked=1, Casual=2, Arcade=3, Event=4. Defaults to 1.
        season (int, optional): Season number. Defaults to 33.

    Returns:
        str: The URL for the leaderboard.
    """
    if platform:
        if not platform.is_pc:
            plat = platform.name.lower()
        else:
            plat = 'pc'
    else:
        plat = 'all'
    try:
        gamemode = Gamemode.from_str(gamemode) # type: ignore
        return f"https://r6.tracker.network/leaderboards/pvp-season/{plat}/rankpoints?page=1&platformFamily={plat}&season={season}&gamemode={gamemode.route}"
    except Exception as e:
        return None

def clean_str(s: str) -> str:
    """Removes excess whitespace from a string, including at the beginning and end of newlines.

    Args:
        s (str): The string to clean.

    Returns:
        str: The cleaned string.
    """
    s = re.sub(r'\n\s+', '\n', s.strip()).sub(r'\s+', ' ', s)
    return s

class PlatformConverter(commands.Converter, app_commands.Transformer):
    @property
    def choices(self):
        _choices = []
        for platform in Platform.all_platforms():
            if platform is not Platform.ALL:
                _choices.append(platform.to_choice())
            #_choices.append(platform.to_choice())
        return _choices

    async def convert(self, ctx, argument):
        try:
            return Platform.from_str(argument)
        except ValueError:
            raise commands.BadArgument(f"Invalid platform: {argument}")

    async def transform(self, interaction, value):
        return await self.convert(await ContextU.from_interaction(interaction), value)

class ApiCogV2(CogU, name='R6 Commands'):
    """All Rainbow Six Siege related commands."""
    bot: BotU
    session: AsyncSession
    #auth: Auth
    auths: List[Auth]

    current_auth_index: int = 0
    """The current index of the auth object in the auths list to use for requests."""

    def __init__(self, bot: BotU, auths: List[Auth]):
        self.bot = bot
        self.default_headers = {
            "mode": "cors",
            "credentials": "include",
            "accept": "application/json, text/plain, */*",
            "accept-language": "en-GB,en;q=0.9",
            "cache-control": "no-cache",
            "pragma": "no-cache",
            "priority": "u=1, i"
        }

        #self.reauth_session.start()

        self.bot.tree.add_command(app_commands.ContextMenu(
            name='Get Ranked Stats (Xbox)',
            callback=self.r6_ranked_context_menu_xbox,
        ))

        self.bot.tree.add_command(app_commands.ContextMenu(
            name='Get Ranked Stats (PSN)',
            callback=self.r6_ranked_context_menu_psn,
        ))

        self.bot.tree.add_command(app_commands.ContextMenu(
            name='Get Ranked Stats (UPlay)',
            callback=self.r6_ranked_context_menu_uplay,
        ))

        self.bot.tree.add_command(app_commands.ContextMenu(
            name='View Linked Accounts',
            callback=self.r6_linked_accounts_context_menu,
        ))

        self.env = environ.Env(
            PROD=(bool, False)
        )

        #PROD = self.env("PROD")

        #if PROD:
        self.proxy = {"http": f"http://{PROXY_URL}", "https": f"http://{PROXY_URL}"}
        # else:
        #     self.proxy = None

        self.session = AsyncSession(headers=self.default_headers, impersonate="chrome116", proxies=self.proxy)

        self.auths = auths
    
    # @property
    # def session(self):
    #     return AsyncSession(headers=self.default_headers, impersonate="chrome116", proxies=self.proxy)

    @discord.utils.cached_property
    def ratelimit_webhook(self) -> discord.Webhook:
        return discord.Webhook.from_url(RATELIMIT_WEBHOOK_URL, client=self.bot)

    async def get_id_or_reply(self, ctx: ContextU, id_or_username: str, platform: Platform, force: bool=False):
        if not ID_RE.match(id_or_username):
            if platform is Platform.ALL:
                return await ctx.reply(embed=makeembed_bot(title="Invalid Platform", description="You cannot select `All` as a platform unless you provide the userID/UUID of the user. Run this command again and specify a platform.",color=discord.Color.red()))
            #if platform.username_re.match(id_or_username):
            try:
                id = await self.get_id(platform, id_or_username, force=force)
            except ValueError:
                return await ctx.reply(embed=makeembed_bot(title="Invalid Username", description=f"Username `{id_or_username}` was not found.",color=discord.Color.red()))
            #else:
            #    return await ctx.reply(embed=makeembed_bot(title="Invalid Username", description=f"Username `{id_or_username}` was not found.",color=discord.Color.red()))
        else:
            id = id_or_username
        return id
    

    async def get_ubi_id_or_reply(self, ctx: ContextU, id_or_username: str, platform: Platform, force: bool=False):
        if not ID_RE.match(id_or_username):
            if platform is Platform.ALL:
                return await ctx.reply(embed=makeembed_bot(title="Invalid Platform", description="You cannot select `All` as a platform unless you provide the userID/UUID of the user. Run this command again and specify a platform.",color=discord.Color.red()))
            if platform.username_re.match(id_or_username):
                try:
                    id = await self.get_ubi_id(platform, id_or_username, force=force)
                except ValueError:
                    return await ctx.reply(embed=makeembed_bot(title="Invalid Username", description=f"Username `{id_or_username}` was not found.",color=discord.Color.red()))
            else:
                return await ctx.reply(embed=makeembed_bot(title="Invalid Username", description=f"Username `{id_or_username}` was not found.",color=discord.Color.red()))
        else:
            id = id_or_username
        return id

    async def alert_ratelimit(self, code: Union[HTTPCode, int], response):
        """Alerts the ratelimit webhook of a ratelimit."""
        url = response.url
        method = response.request.method
        code = HTTPCode(response.status_code)

        if isinstance(code, int):
            code = HTTPCode(code)
        
        if code.is_1xx:
            color = discord.Color.blurple()
        elif code.is_2xx:
            color = discord.Color.green()
        elif code.is_3xx:
            color = discord.Color.gold()
        elif code.is_4xx:
            if code.status == 429:
                color = discord.Color.brand_red()
            else:
                color = discord.Color.purple()
        elif code.is_5xx:
            color = discord.Color.red()
        else:
            color = discord.Color.light_gray()

        embed = makeembed_bot(
            title="Abnormal Request",
            description=f"`{code}` from `{url}` `[{method.upper()}]`",
            color=color
        )
        await self.ratelimit_webhook.send(embed=embed)

    async def _get(self, *args, **kwargs):
        # async with AsyncSession() as session:
        #     return await session.get(*args, **kwargs)
        #start = time.time()
        async with self.session as session:
            r = await session.get(*args, **kwargs)
            status_ = HTTPCode(r.status_code)
            requests_logger.info(
                f"[{r.request.method.upper() if hasattr(r.request, 'method') else 'GET'}] {status_} from {r.url} (Session 1) in {r.elapsed}s" 
            )
            if not status_.is_2xx:
                if r.status_code == 429:
                    wait_until = float(r.headers.get('retry-after'))
                    await asyncio.sleep(wait_until)
                await self.alert_ratelimit(status_, r)
            return r

    async def _get_json(self, url: str, *args, **kwargs) -> Optional[Union[dict, list]]:
        r = await self._get(url, *args, **kwargs)
        return json.loads(r.text)

    async def _get_json_or_empty(self, url: str, *args, **kwargs) -> Union[dict, list]:
        try:
            return await self._get_json(url, *args, **kwargs) # type: ignore
        except Exception as e: return {}

    @property
    def auth(self) -> Auth:
        """Get the current auth object to use for requests."""

        auth = self.auths[self.current_auth_index]
        if self.current_auth_index + 1 >= len(self.auths):
            self.current_auth_index = 0
        else:
            self.current_auth_index += 1
        return auth

    async def get_r6_user(self, name: Optional[str]=None, uid: Optional[str]=None, platform: Platform=Platform.UBI, fetch: bool=False, *args, **kwargs) -> Optional[RankedStatsV2]:
        """Get a Rainbow Six Siege user's information.
        Uses an LRU cache to store the user's information.
        This can be bypassed by passing True for the fetch kwarg.

        Args:
            name (Optional[str]): The username of the user.
            uid (Optional[str]): The id of the user.
            platform (Platform): The platform of the user.

        Returns:
            Optional[dict]: The user's information.
        """
        if fetch:
            return await self.fetch_r6_user(name=name, uid=uid, platform=platform, *args, **kwargs)
        else:
            return await self.get_maybe_cached_r6_user(name=name, uid=uid, platform=platform, *args, **kwargs)

    @async_lru.alru_cache(maxsize=128)
    async def get_maybe_cached_r6_user(self, name: Optional[str]=None, uid: Optional[str]=None, platform: Platform=Platform.UBI, *args, **kwargs):
        """Get a Rainbow Six Siege user's information.
        Uses an LRU cache to store the user's information.
        Calls the fetch_r6_user method.

        Args:
            name (Optional[str]): The username of the user.
            uid (Optional[str]): The id of the user.
            platform (Platform): The platform of the user.

        Returns:
            Optional[dict]: The user's information.
        """
        return await self.fetch_r6_user(name=name, uid=uid, platform=platform, *args, **kwargs)
    
    async def fetch_r6_user(self, name: Optional[str]=None, uid: Optional[str]=None, platform: Platform=Platform.UBI, *args, **kwargs):
        """Get a Rainbow Six Siege user's information.
        Fetches the user's information from the Ubisoft API.

        Args:
            name (Optional[str]): The username of the user.
            uid (Optional[str]): The id of the user.
            platform (Platform): The platform of the user.

        Returns:
            Optional[dict]: The user's information.
        """
        logger.debug(f"Fetching user: {name if name else uid} ({platform.route})")
        r = await self._get_json_or_empty(f"{API_BASEV2}/standard/profile/{platform.route}/{uid if uid else name}")
        if 'errors' in [x for x in r.keys()]:
            return None
        if isinstance(r, list):
            r = r[0]
        if not r:
            return None
        r = r.get(list(r.keys())[0])    
        return await RankedStatsV2.from_api(r)
        #player = await self.auth.get_player(name=name, uid=uid, platform=platform.route)
        #await RankedStats.from_player(player)
        #return player
    
    # async def fetch_addl_user_info(self, user: R6UserConnections):
    #     platform = Platform.from_str(user.platform)

    #     # matches
    #     r = await self._get_json_or_empty(f"{API_BASEV2}/standard/profile/{platform.route}/{user.request_id}")
    #     if 'errors' in [x for x in r.keys()]:
    #         return None
        
    #     # for match in r.get('data').get('matches'):
    #     #     for segment in match.get('segments')[0]:

    #     await Matches.bulk_from_api(r)
    
    async def get_r6_leaderboard(self, platform: Platform, season: int=CURRENT_SEASON_NUM, gamemode: Union[Gamemode, str, int]=Gamemode.RANKED, _filter: LeaderboardFilter=LeaderboardFilter.current_mmr) -> List[RankedStatsSeasonal]:
        """Get the R6 leaderboard for a given platform, season, and gamemode.

        Args:
            platform (Platform): Platform to get the leaderboard for. Pass None to get all platforms.
            gamemode (Union[Gamemode, str, int], optional): The gamemode to get the leaderboard for. Defaults to Gamemode.RANKED.
            season (int, optional): Season number. Defaults to CURRENT_SEASON_NUM.

        Returns:
            List[RankedStatsSeasonal]: The leaderboard. 
        """

        # https://api.tracker.gg/api/v1/r6siege/standard/leaderboards?type=rankedv2&platform=all&board=rankpoints&platformFamily=pc&gamemode={gamemode.route}&season={season}&skip=0&take=1000

        if not isinstance(gamemode, Gamemode):
            gamemode = Gamemode.from_str(gamemode)
        url = f"{API_BASEV2}/standard/leaderboards?type={gamemode.route}&platform={platform.route}&board={_filter.route}&platformFamily={'pc' if platform.is_pc else 'console'}&gamemode={gamemode.route}&season={season}&skip=0&take=1000"
        r = await self._get_json_or_empty(url)

        leaderboard = []

        for leaderboard_user in r.get('data',{}).get('items',{}):
            if not await R6UserConnections.from_leaderboard(leaderboard_user):
                resp = await self.get_r6_user(name=leaderboard_user.get('owner',{}).get('metadata',{}).get('platformUserHandle',None), platform=platform.route)
                if resp:
                    user = await R6UserConnections.create_from_r6tracker_resp(user)
                else:
                    user = await R6UserConnections.filter(name__iexact=leaderboard_user.get('owner',{}).get('metadata',{}).get('platformUserHandle',None), platform=platform.route).first()
            else:
                user = await R6UserConnections.filter(name__iexact=leaderboard_user.get('owner',{}).get('metadata',{}).get('platformUserHandle',None), platform=platform.route).first()
            
            stats = await RankedStatsSeasonal.filter(platform_connection=user, season=season).first()
            leaderboard.append(stats)
        return leaderboard

    async def get_r6_recently_encountered(self, user: R6UserConnections):
        #url = https://api.tracker.gg/api/v1/r6siege/stats/played-with/xbl/4fc78225-9c0b-4d07-831a-90b07c200e93
        url = f"{API_BASEV2}/standard/stats/played-with/{user.platform}/{user.userid}"
        r = await self._get_json_or_empty(url)

        encountered = []

        for player in r.get('data',{}):
            encounter = await PlayerEncounters.from_api(user, player)
            encountered.append(encounter)
        return encountered

    async def status(self) -> Optional[dict]:
        r = await self._get(f"https://game-status-api.ubisoft.com/v1/instances?appIds={','.join(R6_GAME_APPIDS)}")

        rr = await self._get("https://api.tracker.gg/api/v2/r6siege/standard/homepage")

        returnv = {}

        if r.status_code == 200:
            r = json.loads(r.text)
            for app in r:
                app['Platform'] = app['Platform'].title()
                if app['Platform'] == "Xboxone":
                    app['Platform'] = "Xbox One"
                returnv[app['Platform']] = app.get('Status')
        else:
            if r.status_code in range(200,300):
                returnv['Ubisoft Status Page'] = "Online"
            elif r.status_code in range(400,500):
                returnv['Ubisoft Status Page'] = "Client Error"
            elif r.status_code in range(500,600):
                returnv['Ubisoft Status Page'] = "Server Error"
            else:
                returnv['Ubisoft Status Page'] = "Unknown"
        
        if rr.status_code in range(200,300):
            returnv['R6 Tracker'] = "Online"
        elif rr.status_code in range(400,500):
            returnv['R6 Tracker'] = "Client Error"
        elif rr.status_code in range(500,600):
            returnv['R6 Tracker'] = "Server Error"
        else:
            returnv['R6 Tracker'] = "Unknown"
        return returnv

    async def xbox_get_user(self, username: str) -> Optional[dict]:
        session = aiohttp.ClientSession()
        headers = {
            'x-authorization': XBOX_API_KEY,
        }
        r = await session.get(f"https://xbl.io/api/v2/search/{parse.quote(username)}", headers=headers)
        data = await r.json()
        data = data.get('people')[0]
        return data
    
    async def xbox_get_user_pfp_url(self, username: str, fetch: bool=False) -> Optional[str]:
        if not XBOX_LIVE_RE.match(username):
            raise ValueError("Invalid Xbox Live Username")
        
        player = await R6UserConnections.filter(name__iexact=username, platform=Platform.XBOX.route).first()

        if not fetch:
            if player: 
                if player.pfp_url_last_updated:
                    if (datetime.datetime.now(tz=datetime.timezone.utc) - player.pfp_url_last_updated).days > 1:
                        return await self.xbox_get_user_pfp_url(username, True)

        data = await self.xbox_get_user(username)
        pfp_url = data.get('displayPicRaw', None)
        if pfp_url:
            if player:
                player.pfp_url = pfp_url
                player.pfp_url_last_updated = datetime.datetime.now(tz=datetime.timezone.utc)
                await player.save()
            # else:
            #     await R6UserConnections.create(name=username, platform=Platform.XBOX.route, pfp_url=pfp_url, pfp_url_last_updated=datetime.datetime.now())
        return pfp_url

    async def steam_get_user(self, steamid: int) -> Optional[dict]:
        session = aiohttp.ClientSession()
        r = await session.get(f"https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v2/?key={STEAM_API_KEY}&steamids={steamid}")
        data = await r.json()
        return data.get('response').get('players')[0]

    async def get_ubi_id(self, platform: Platform, username: str, force: bool=False) -> Optional[str]:
        """Get a user's id by their username.

        Args:
            platform (Union[Platform, str]): The platform to look up the user on.
            username (str): The username of the user.
            force (bool, optional): Whether to force the request to be made. Defaults to False.

        Returns:
            Optional[str]: The user's id. UPLAY ACC ID
        """        
        #platform: Platform = Platform.from_str(platformtype)
        if not platform.username_re.match(username):
            raise ValueError("Invalid Username")
        
        connection = await R6UserConnections.filter(name__iexact=username, platform=platform.route).first()
        r = {}
        if force or not connection:
            #r = await self._get_json_or_empty(f"{API_BASEV2}/standard/search?platform={platform.route}&query={parse.quote(username)}&autocomplete=true")
            r = await self._get_json_or_empty(f"{API_BASEV2}/standard/profile/{platform.route}/{parse.quote(username)}")
            if r:
                try:
                    await R6UserConnections.create_from_r6tracker_resp(r)
                except Exception as e:
                    raise ValueError("Failed to get user id. Doesn't exist?")
            connection = await R6UserConnections.filter(name__iexact=username, platform=platform.route).first()
        if not connection and not r.get('data',[]):
            raise ValueError("Failed to get user id. Doesn't exist?")

        if connection:
            return connection.userid
        elif r['data']['metadata']['uplayUserId']:
            return r['data']['metadata']['uplayUserId']
        #else:
        #    return r['profiles'][0]['profileId']
        return None

    async def get_id(self, platformtype: Platform, username: str, force: bool=False) -> Optional[str]:
        """Get a user's id by their username.

        Args:
            platform (Union[Platform, str]): The platform to look up the user on.
            username (str): The username of the user.
            force (bool, optional): Whether to force the request to be made. Defaults to False.

        Returns:
            Optional[str]: The user's id. UPLAY ACC ID
        """        
        #platform: Platform = Platform.from_str(platformtype)
        platform = platformtype

        # if not platform.username_re.match(username):
        #     raise ValueError("Invalid Username")
        
        connection = await R6UserConnections.filter(name__iexact=username, platform=platform.route).first()
        r = {}
        if force or not connection:
            #r = await self._get_json_or_empty(f"{API_BASEV2}/standard/search?platform={platform.route}&query={parse.quote(username)}&autocomplete=true")
            r = await self._get_json_or_empty(f"{API_BASEV2}/standard/profile/{platform.route}/{username.replace(' ','%20')}")
            if r: 
                try:
                    await R6UserConnections.create_from_r6tracker_resp(r)
                except Exception as e:
                    raise ValueError("Failed to get user id. Doesn't exist?")
            connection = await R6UserConnections.filter(name__iexact=username, platform=platform.route).first()
        if not connection and not r.get('data',[]):
            raise ValueError("Failed to get user id. Doesn't exist?")

        if connection:
            return str(connection.request_id)
        elif r['data']['platformInfo']['platformUserId']:
            return r['data']['platformInfo']['platformUserId']
        # elif r['data']['metadata']['uplayUserId']:
        #     return r['data']['metadata']['uplayUserId']
        #else:
        #    return r['profiles'][0]['profileId']
        return None

    async def get_username(self, platformtype: Union[Platform, str], id: str, force: bool=False) -> Optional[str]:
        """Get a user's username by their id.

        Args:
            platform (Union[Platform, str]): The platform to look up the user on.
            id (str): The id of the user.
            force (bool, optional): Whether to force the request to be made. Defaults to False.

        Returns:
            Optional[str]: The user's username.
        """        
        platform: Platform = Platform.from_str(platformtype)

        id = id.strip()
        if not platform.id_re.match(id):
            raise ValueError("Invalid ID")
        
        r = {}
        connection = await R6UserConnections.filter(userid=id, platform=platform.route).first()
        if force or not connection:
            r = await self._get_json_or_empty(f"{API_BASEV2}/standard/profile/{platform.route}/{id}")
            if r:
                await R6UserConnections.create_from_r6tracker_resp(r)
            else:
                return None
            connection = await R6UserConnections.filter(userid=id, platform=platform.route).first()
        if not connection and not r.get('profiles',[]):
            raise ValueError("Failed to get user id. Doesn't exist?")
        return connection.name if connection else None

    @commands.hybrid_command(name='support',description="Get support for the bot.")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def r6_support(self, ctx: ContextU):
        """
        Get support for the bot.
        """
        await ctx.reply(embed=makeembed_bot(title="Support", description="Need help or have a suggestion? Join the support server to get help or make a suggestion.", color=discord.Color.blurple()),view=URLButton(url=SUPPORT_SERVER, buttontext="Join Support Server"))

    @commands.hybrid_command(name='status',description="Get the status of the Rainbow Six Siege servers.")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def r6_status(self, ctx: ContextU):
        """
        Get the status of the Rainbow Six Siege servers.
        """ 
        await ctx.defer()

        data = await self.status()
        if not data:
            raise ValueError("Failed to load server status.")
        embed = makeembed_bot(title="Rainbow Six Siege Server Status", url="https://www.ubisoft.com/en-us/game/rainbow-six/siege/status", color=discord.Color.blurple())
        for key, value in data.items():
            emoji = ''
            if value == "Online":
                emoji = emojidict.get('green_circle')
            elif value in ["Degraded", "Client Error"] :
                emoji = emojidict.get('yellow_circle')
            elif value in ["Maintenance","Offline","Server Error"]:
                emoji = emojidict.get('red_circle')
            else:
                emoji = emojidict.get('blue_circle')
            embed.add_field(name=key, value=f"{emoji+' ' if emoji else ''}{value}", inline=False)
        await ctx.reply(embed=embed)

    # @commands.hybrid_command(name='level',description="Get the level of a user.")
    # @Cooldown(1, 5, BucketType.user)
    # @app_commands.allowed_installs(guilds=True, users=True)
    # @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    # @app_commands.describe(platform='The platform to search on.', username="The username or the ID of the user.")
    # async def r6_level(self, ctx: ContextU, platform: PlatformConverter, *, username: str):
    #     """
    #     Get the level of a user.
    #     """
    #     await ctx.defer()
      
    #     assert platform is not None and isinstance(platform, Platform)

    #     username = clean_username(username)

    #     if not ID_RE.match(username):
    #         if platform.username_re.match(username):
    #             try:
    #                 id = await self.get_id(platform, username)
    #             except ValueError:
    #                 return await ctx.reply(embed=makeembed_bot(title="Invalid Username", description=f"Username `{username}` was not found.",color=discord.Color.red()))
    #         else:
    #             return await ctx.reply(embed=makeembed_bot(title="Invalid Username", description=f"Username `{username}` was not found.",color=discord.Color.red()))
    #     else:
    #         id = username
    #     try:
    #         if id:
    #             try:
    #                 player = await self.get_r6_user(uid=id, platform=platform)
    #             except ValueError:
    #                 return await ctx.reply(embed=makeembed_bot(title="Invalid ID", description=f"ID `{id}` was not found.",color=discord.Color.red()))
    #         else:
    #             try:
    #                 player = await self.get_r6_user(name=username, platform=platform)
    #             except Exception as e:
    #                 return await ctx.reply(embed=makeembed_bot(title="Invalid Username", description=f"Username `{username}` was not found.",color=discord.Color.red()))
            
    #         assert player is not None

    #         #await player.load_progress()

    #         if not player:
    #             raise ValueError("Failed to get level")
    #         xp, level = player., player.level

    #         if level is None or xp is None:
    #             return await ctx.reply(embed=makeembed_bot(title="Invalid Username", description=f"Username `{username}` was not found.",color=discord.Color.red()))

    #         embed = makeembed_bot(title=f"Requested by {ctx.author}", color=platform.color)

    #         embed.add_field(name="Level", value=f"`{level}`", inline=True)
    #         embed.add_field(name="XP", value=f"`{xp}`", inline=True)
    #         embed.add_field(name='XP to level up', value=f"`{player.xp_to_level_up}`", inline=True)
    #         await ctx.reply(embed=embed)
    #     except Exception as e:
    #         traceback.print_exc()
    #         return await ctx.reply(embed=makeembed_bot(title="Invalid Username", description=f"Username `{username}` was not found.",color=discord.Color.red()))
    
    @commands.hybrid_command(name='level', description="Get the level of a user.")
    @Cooldown(1, 5, BucketType.user)
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(platform='The platform to search on.', username="The username or the ID of the user.", fetch="Whether to force statistics to be updated or not. Defaults to False.")
    async def r6_level(self, ctx: ContextU, platform: PlatformConverter, *, username: str, fetch: bool=False):
        await ctx.defer()

        assert platform is not None and isinstance(platform, Platform)

        id = await self.get_id_or_reply(ctx, username, platform, force=fetch)
        if id and not isinstance(id, str):
            return id
        
        player = await self.get_r6_user(uid=id, platform=platform, fetch=fetch)
        
        if not player:
            return await ctx.reply(embed=makeembed_bot(title="Invalid User", description=f"User `{username}` was not found.",color=discord.Color.red()))

        await player.fetch_related('user_connection')
        embed = makeembed_bot(title=f"{emojidict.get(platform.route)} {player.user_connection.name}'s Level", color=platform.color)
        embed.add_field(name="Level", value=f"`{player.clearance_level}`", inline=True)
        embed.add_field(name="Battle Pass Level", value=f"`{player.battlepass_level}`", inline=True)

        if player:
            #embed.add_field(name="First Seen", value=f"{dctimestamp(cached_info.created_at,'R')}", inline=True)
            embed.add_field(name="Last Updated", value=f"{dctimestamp(player.updated_at,'R')}", inline=True)

        view = URLButton(url=get_perma_r6_tracker_url(id, platform), buttontext="View on R6Tracker")
        return await ctx.reply(embed=embed, view=view)

    @commands.hybrid_command(name='link', description='Link your Discord account to your R6 account.')
    @Cooldown(1, 5, BucketType.user)
    async def r6_link(self, ctx: ContextU):
        """
        Link your Discord account to your R6 account.
        """
        await ctx.defer()

        if not await self.bot.is_owner(ctx.author):
            if await R6UserConnections.filter(platform='discord', platform_id=ctx.author.id).exists():
                return await ctx.reply(embed=makeembed_bot(title="Already Linked", description="Your Discord account is already linked.",color=discord.Color.yellow()))
        
        if ctx.guild:
            if ctx.guild.id == TOURNEY_SERVER:
                return await ctx.reply(embed=makeembed_bot(title="Link your Ubisoft and Discord acAccounts", 
                description=f"Go to <#{USERNAME_CHANNEL}> for more information on linking your account.",color=discord.Color.yellow()))
        
        account_info_url = "https://account.ubisoft.com/en-US/account-information"

        linked_accounts_screenshot = 'https://cdn.discordapp.com/attachments/1052116603250163712/1238913933486723146/Screen_Shot_2024-05-11_at_13.00.30.png?ex=66410403&is=663fb283&hm=af1975a09923892303ccca69e1181d5e024702372d558adeacd62b58e0ef86b8&'
        completed_linking_screenshot = 'https://cdn.discordapp.com/attachments/1052116603250163712/1238965465586601994/Screen_Shot_2024-05-11_at_16.25.18.png?ex=66413401&is=663fe281&hm=aa212a46504c54f7cdbc9caf5e60cdee35d4ba819bb1dfffea33e1a50dd62fec&'

        accounts_cmd = await self.get_command_mention('linked accounts')

        description = "### Instructions:\n"
        description += f"- Go to {dchyperlink(account_info_url, 'Ubisoft Account Information')} or click on the button below\n"
        description += "- Sign in to your Ubisoft Account\n"
        description += "- Scroll down on the page, look for the Linked Accounts section and click `Link` (see below screenshot)\n"
        description2 = "- Follow the instructions/prompts that it gives you, and once you see a message similar to the one in the below image, continue to the next step.\n"
        description3 = f"- Come back to Discord and run {accounts_cmd} with your Ubisoft username.\n"
        description3 += "- It should show up with your discord in one of the fields."

        #description = clean_str(description)
        emb = makeembed(title="Link your Ubisoft and your Discord Account.", description=description, image=linked_accounts_screenshot)
        emb2 = makeembed(description=description2, image=completed_linking_screenshot)
        emb3 = makeembed(description=description3)
        
        return await ctx.reply(embeds=[emb,emb2,emb3], view=URLButton(url="https://account.ubisoft.com/en-US/account-information", buttontext="Ubisoft Account Information"))

    async def r6_linked_accounts_cmd(self, ctx: ContextU, platform: Optional[Platform]=None, *, username: Optional[str]=None, discorduser: Optional[discord.User]=None, force: bool=False):
        """Get the linked accounts of a user.

        Args:
            ctx (ContextU): The context of the command.
            platform (Optional[Platform]): The platform to search on.
            username (Optional[str]): The username of the user.
            discorduser (Optional[discord.User]): The discord user to search for.
            force (bool): Whether to force the request to be made.
        """
        await ctx.defer()

        if username:
            username = clean_username(username)

        if not platform and not username and not discorduser:
            return await ctx.reply('You must provide a platform and a username or a discord user.')
        if (not platform or not username) and not discorduser:
            return await ctx.reply('You must provide a platform and a username.')
        if platform and username and discorduser:
            return await ctx.reply('You must provide a platform and a username or a discord user, not both.')
        
        if not username:
            assert discorduser is not None
        elif discorduser:
            assert username is not None and platform is not None

        if discorduser:
            ubi = await R6UserConnections.get_or_none(platform_id=discorduser.id, platform='discord')
            if not ubi:
                return await ctx.reply(embed=makeembed_bot(title="Invalid User", description=f"User `{discorduser}` was not found.",color=discord.Color.red()))
            id = ubi.userid
            setting = await Settings.filter(user_id=discorduser.id).first()
            if setting:
                try:
                    platform = Platform.from_str(setting.preferred_platform)
                    assert platform is not None
                except Exception as e:
                    platform = Platform.UBI
            else:
                platform = Platform.UBI
        elif platform and username:
            assert platform is not None
            id = await self.get_ubi_id_or_reply(ctx, username, platform, force=force)
            if not isinstance(id, str):
                return id
        # elif username:
        #     assert platform is not None
        #     if not ID_RE.match(username):
        #         if platform.username_re.match(username):
        #             try:
        #                 id = await self.get_id(platform, username)
        #             except ValueError:
        #                 return await ctx.reply(embed=makeembed_bot(title="Invalid Username", description=f"Username `{username}` was not found.",color=discord.Color.red()))
        #         else:
        #             return await ctx.reply(embed=makeembed_bot(title="Invalid Username", description=f"Username `{username}` was not found.",color=discord.Color.red()))
        #     else:
        #         id = username
        else:
            raise ValueError("Invalid Arguments")

        assert platform is not None

        try:
            if not id: 
                desc = f"Username `{username}` must have their UPlay linked to their {platform.proper_name} in order to look up their stats.\nR6Tracker may have their stats {dchyperlink(get_r6_tracker_url(username, platform),'here')}."
                return await ctx.reply(embed=makeembed_bot(title="Error", description=desc,color=discord.Color.yellow()))
            player = await self.get_r6_user(uid=id, platform=Platform.UBI, force=force)
            player_old = await self.auth.get_player(uid=id, platform=Platform.UPLAY.route) # type: ignore
            linked_accs = await player_old.load_linked_accounts()
            assert player is not None
        except ValueError:
            return await ctx.reply(embed=makeembed_bot(title="Invalid ID", description=f"ID `{id}` was not found.",color=discord.Color.red()))
        except AssertionError:
            return await ctx.reply(embed=makeembed_bot(title="Invalid ID", description=f"Ubisoft account for `{username}` was not found.\nTheir stats may be found on R6Tracker {dchyperlink(get_perma_r6_tracker_url(id if id else '', Platform.UPLAY),'here')}.",color=discord.Color.yellow()))

        accounts = await R6UserConnections.filter(userid=id).order_by('is_third_party','-platform')

        changed = False
        # update account info if it was changed
        # db_accounts = [x.platform for x in accounts]
        # returned_accounts = [x.platform_type for x in linked_accs]

        for linked_acc in linked_accs:
            saved_acc = discord.utils.find(lambda x: x.platform == linked_acc.platform_type, accounts)
            if not saved_acc:
                await R6UserConnections.create_from_api_obj(linked_acc)
                changed = True
                continue
            await saved_acc.fetch_related('profile')
            if linked_acc.name_on_platform != saved_acc.name \
                or linked_acc.profile_id != saved_acc.profile.userid \
                or linked_acc.id_on_platform != saved_acc.platform_id:
                #profile, _= await R6User.get_or_create(userid=linked_acc.user_id, defaults={'name': linked_acc.name_on_platform if linked_acc.platform_type == "uplay" else None})
                profile = await R6User.get_or_none(userid=linked_acc.user_id)
                if not profile:
                    profile = await R6User.create(userid=linked_acc.user_id, name=linked_acc.name_on_platform if linked_acc.platform_type == "uplay" else None)
                elif profile.name is None and linked_acc.platform_type == "uplay":
                    profile.name = linked_acc.name_on_platform
                    await profile.save()

                saved_acc.name = linked_acc.name_on_platform
                saved_acc.profile = profile
                saved_acc.platform_id = linked_acc.id_on_platform
                await saved_acc.save()
                changed = True

        if changed:
            accounts = await R6UserConnections.filter(userid=id).order_by('is_third_party','-platform')

        account = await accounts[0]
        await account.fetch_related('profile')
        embed = makeembed_bot(title=f"{account.profile.name or account.name}'s Profile", color=discord.Color.blurple())

        # sort accounts so Uplay is first, then PS then XBox
        accounts2 = [None for _ in range(3)]
        other_accounts = [None for _ in range(len(accounts))]
        
        for account in accounts:
            if account.platform.lower() in ['ubi']:
                accounts2[0] = account
            elif account.platform.lower() == 'xbl':
                accounts2[1] = account
                if not account.pfp_url:
                    pfp_url = await self.xbox_get_user_pfp_url(account.name) or None
                else: pfp_url = account.pfp_url
                
                embed.set_thumbnail(url=pfp_url)
            elif account.platform.lower() == 'psn':
                accounts2[2] = account
            else:
                other_accounts.append(account)
        accounts2: List[R6UserConnections] = [x for x in accounts2 if x is not None]
        accounts2.extend([x for x in other_accounts if x is not None])
    
        for account in accounts2:
            if not account.is_third_party and account.platform.lower() != "trackergg":
                pt = Platform.from_str(account.platform)
                assert pt is not None
                if discord.utils.find(lambda x: pt.proper_name == x.name, embed.fields):
                    continue
                embed.add_field(name=pt.proper_name, value=f"{emojidict.get(pt.proper_name.lower())} `{account.name}`", inline=False)
            else:
                if account.name:
                    account_name = account.name.title()
                else:
                    account_name = account.platform_id
                
                if account.platform == 'steam':
                    try:
                        account.name = (await self.steam_get_user(int(account.platform_id))).get('personaname') or account.name 
                        await account.save()
                    finally:
                        account_name = f"`{account.name}`"
                elif account.platform == 'discord':
                    # account_name = await self.bot.getorfetch_user(int(account.platform_id), None)
                    # if not account_name:
                    #     account_name = f"<@{account.platform_id}>"
                    # else:
                    #     account_name = f"{account_name.mention} (`{account.platform_id}`)"
                    account_name = f"<@{account.platform_id}> (`{account.platform_id}`)"
                    if account.manual:
                        account_name += "*"
                elif account.platform == 'trackergg':
                    continue
                    #account_name = f"[{account.name}]({account.platform_id})"
                else:
                    account_name = f"`{account.name}`"
                embed.add_field(name=account.platform.title(), value=f"{emojidict.get(account.platform.lower()) or ''} {account_name}", inline=False)
        embed.add_field(name="User ID", value=f"`{id}`", inline=False)
        await ctx.reply(embed=embed)
        #except Exception as e:
            #traceback.print_exc()
            #return await ctx.send(f"Failed to load profile: {e}")

    @commands.hybrid_group('linked', description="Get the linked accounts of a user.")
    @Cooldown(1, 5, BucketType.user)
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def r6_linked(self, ctx: ContextU):
        """
        Get the linked accounts of a user.
        """
        pass

    @r6_linked.command(name='accounts',description="Get the linked accounts of a user.")
    @Cooldown(1, 5, BucketType.user)
    @app_commands.describe(
        platform='The platform to search on.', 
        username="The username or the ID of the user. Not needed if you provide a Discord User.", 
        discorduser="The discord user to search for. Not nessesary if you provide a platform and username.", 
        force="Whether to force the request to be made. Mark this as True if you recently changed your linked accounts."
    )
    #@app_commands.allowed_installs(guilds=True, users=True)
    #@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def r6_profile(self, ctx: ContextU, platform: Optional[PlatformConverter]=None, *, username: Optional[str]=None, discorduser: Optional[discord.User]=None, force: bool=False):
        """
        Get the profile of a user.
        """
        return await self.r6_linked_accounts_cmd(ctx, platform, username=username, discorduser=discorduser, force=force)

    @commands.hybrid_group(name='lookup',description="Look up a user by username or ID to get information about them.")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def r6_lookup(self, ctx: ContextU):
        """
        Look up a user by username or ID to get information abuot them.
        """
        pass

    @r6_lookup.command(name='ranked',description="Get the ranked stats of a user.")
    @Cooldown(1, 5, BucketType.user)
    @app_commands.describe(platform='The platform to search on.', username="The username or the ID of the user.", fetch="Whether to force statistics to be updated or not. Defaults to False.")
    #@app_commands.autocomplete(username=username_autocomplete)
    async def r6_ranked(self, ctx: ContextU, platform: PlatformConverter, *, username: str, fetch: bool=False):
        """
        Get the rank of a user.
        """
        return await self.r6_lookup_cmd(ctx, 'ranked', platform, username=username, force=fetch)

    @r6_lookup.command(name='unranked',description="Get the unranked stats of a user.")
    @Cooldown(1, 5, BucketType.user)
    @app_commands.describe(platform='The platform to search on.', username="The username or the ID of the user.", fetch="Whether to force statistics to be updated or not. Defaults to False.")
    #@app_commands.autocomplete(username=username_autocomplete)
    async def r6_unranked(self, ctx: ContextU, platform: PlatformConverter, *, username: str, fetch: bool=False):
        """
        Get the unranked stats of a user.
        """
        return await self.r6_lookup_cmd(ctx, 'unranked', platform, username=username, force=fetch)


    @r6_lookup.command(name='casual',description="Get the casual stats of a user.")
    @Cooldown(1, 5, BucketType.user)
    @app_commands.describe(platform='The platform to search on.', username="The username or the ID of the user.", fetch="Whether to force statistics to be updated or not. Defaults to False.")
    #@app_commands.autocomplete(username=username_autocomplete)
    async def r6_casual(self, ctx: ContextU, platform: PlatformConverter, *, username: str, fetch: bool=False):
        """
        Get the casual stats of a user.
        """
        return await self.r6_lookup_cmd(ctx, 'casual', platform, username=username, force=fetch)

    @r6_lookup.command(name='warmup',description="Get the warmup stats of a user.")
    @Cooldown(1, 5, BucketType.user)
    @app_commands.describe(platform='The platform to search on.', username="The username or the ID of the user.", fetch="Whether to force statistics to be updated or not. Defaults to False.")
    #@app_commands.autocomplete(username=username_autocomplete)
    async def r6_warmup(self, ctx: ContextU, platform: PlatformConverter, *, username: str, fetch: bool=False):
        """
        Get the warmup stats of a user.
        """
        return await self.r6_lookup_cmd(ctx, 'warmup', platform, username=username, force=fetch)

    async def r6_lookup_cmd(self, ctx: ContextU, gamemode: str, platform: Platform, *, username: str, force: bool=False):
        await ctx.defer()
      
        assert platform is not None and isinstance(platform, Platform)

        if platform.is_pc: 
            platform = Platform.UBI

        username = clean_username(username)

        id = await self.get_id_or_reply(ctx, username, platform, force=force)
        if id and not isinstance(id, str):
            return id

        if not id: 
            desc = f"Username `{username}` must have their UPlay linked to their {platform.proper_name} in order to look up their stats.\nR6Tracker may have their stats {dchyperlink(get_r6_tracker_url(username, platform),'here')}."
            return await ctx.reply(embed=makeembed_bot(title="Error", description=desc,color=discord.Color.yellow()))

        db_player = await RankedStatsV2.filter(user_connection__request_id=id, user_connection__platform=platform.route).first()
        fetched = False

        _fetch = force

        if db_player:
            if discord.utils.utcnow() - db_player.updated_at > datetime.timedelta(hours=12): # update at least every 12 hours:
                _fetch = True
        else:
            _fetch = True

        player = None

        if _fetch:
            player = await self.fetch_r6_user(uid=id, platform=platform)
            fetched = True
        else:
            player = db_player
        
        #_, _, _, rank, _, = await player.load_ranked_v2()
        if force and not player and not _fetch: # update at least every 12 hours:
            #raise ValueError("Failed to get rank")
            return await ctx.reply(embed=makeembed_bot(title="Invalid Stats", description=f"Username `{username}` has not played Rainbow Six Siege recently.",color=discord.Color.red()))

        # if rank is None and getattr(player, profile_attr) is None:
        #     return await ctx.reply(embed=makeembed_bot(title="Invalid Stats", description=f"Username `{player.name}` does not have any statistics on {gamemode.title()}.",color=discord.Color.red()))

        #rank = getattr(player, profile_attr)

        # if not rank:
        #     return await ctx.reply(embed=makeembed_bot(title="Invalid Stats", description=f"Username `{player.name}` does not have any statistics on {gamemode.title()}.",color=discord.Color.red()))

        season_stats = await RankedStatsSeasonal.filter(ranked_stats=player, gamemode_name__iexact=gamemode, season=CURRENT_SEASON_NUM).first()
        if not season_stats and not fetched:
            player = await self.fetch_r6_user(uid=id, platform=platform)
            season_stats = await RankedStatsSeasonal.filter(ranked_stats=player, gamemode_name__iexact=gamemode, season=CURRENT_SEASON_NUM).first()
        #assert season_stats is not None
        if not player:
            await db_player.fetch_related('user_connection')
            player = db_player
        elif player is not None:
            await player.fetch_related('user_connection')

        if not season_stats:
            if player:
                return await ctx.reply(embed=makeembed_bot(title="Invalid Stats", description=f"Username `{player.user_connection.name}` does not have any statistics on {gamemode.title()} for this season.",color=discord.Color.red()))
            return await ctx.reply(embed=makeembed_bot(title="Invalid Stats", description=f"Username `{username}` does not have any statistics on {gamemode.title()} for this season.",color=discord.Color.red()))

        await season_stats.fetch_related('ranked_stats')
        connection = player.user_connection

        if gamemode == 'ranked':
            rankobj = R6Rank.from_mmr(season_stats.rankpoints)
            color = rankobj.color
        else:
            rankobj = None
            color = platform.color

        embed = makeembed_bot(
            color=color,
            title=f"{platform.emoji} {connection.name}'s {gamemode.title()} Stats", 
            #url=get_r6_tracker_url(player.name, platform),
            url=get_perma_r6_tracker_url(connection.request_id, platform),
            #description=f"Requested by {ctx.author}",
        )

        wins = getattr(season_stats, "matcheswon")
        losses = getattr(season_stats, "matcheslost")
        kills = getattr(season_stats, "kills")
        deaths = getattr(season_stats, "deaths")

        try: wl_ratio = wins/losses
        except ZeroDivisionError: wl_ratio = 0

        try: kd_ratio = kills/deaths
        except ZeroDivisionError: kd_ratio = 0

        if rankobj and gamemode == 'ranked':
            embed.add_field(name='Rank', value=f"`{rankobj.name}`", inline=True)
            embed.add_field(name='MMR', value=f"`{season_stats.rankpoints}`", inline=True)

            embed.set_thumbnail(url=rankobj.image_url)

        embed.add_field(name='Wins', value=f"`{wins}`", inline=True)
        embed.add_field(name='Losses', value=f"`{losses}`", inline=True)
        embed.add_field(name='W/L Ratio', value=f"`{wl_ratio:.2f}`", inline=True)

        embed.add_field(name='Abandons', value=f"`{season_stats.matchesabandoned}`", inline=True)
        embed.add_field(name='Kills', value=f"`{kills}`", inline=True)
        embed.add_field(name='Deaths', value=f"`{deaths}`", inline=True)
        embed.add_field(name='K/D Ratio', value=f"`{kd_ratio:.2f}`", inline=True)

        #cached_info = await RankedStatsSeasonal.filter(ranked_stats__user_connection__request_id=player.user_connection.request_id, platform_connection__platform=platform.route, season=CURRENT_SEASON_NUM).first()

        if season_stats:
            #embed.add_field(name="First Seen", value=f"{dctimestamp(cached_info.created_at,'R')}", inline=True)
            embed.add_field(name="Last Updated", value=f"{dctimestamp(season_stats.updated_at,'R')}", inline=True)

        view = URLButton(url=get_perma_r6_tracker_url(connection.request_id, platform), buttontext="View on R6Tracker")
        await ctx.reply(embed=embed, view=view)

        if not ctx.interaction:
            assert ctx.command is not None
            #embed.add_field(name=f"{emojidict.get('nerd')} Tip", value=f"You can use the slash command version of this command, for autocomplete and other additional features. Try it using {await self.get_command_mention(ctx.command.qualified_name)}.", inline=False)
            emb2 = makeembed_bot(description=f"{emojidict.get('nerd')} Tip: You can use the slash command version of this command, for autocomplete and other additional features. Try it using {await self.get_command_mention(ctx.command.qualified_name)}.")
            await ctx.reply(embed=emb2, delete_after=10.0)

    # async def r6_ranked_cmd(self, ctx: ContextU, player: RankedStatsV2, fetch: bool=False):
    #     await player.fetch_related('user','user_connection')
    #     platform = Platform.from_str(player.user_connection.platform)
    #     assert platform is not None
    
    #     try:
    #         #_, rank, _, _, _, = await player.load_ranked_v2()
    #         player_stats = player
    #         #player_stats = await self.get_r6_user(uid=player.id, platform=platform)
    #         if not player:
    #             raise ValueError("Failed to get rank")
    #         if player_stats is None:
    #             return await ctx.reply(embed=makeembed_bot(title="Invalid Stats", description=f"Username `{player.user_connection.name}` does not have any stats on ranked.",color=discord.Color.red()))
    #         season_stats = await RankedStatsSeasonal.filter(ranked_stats=player_stats, season=CURRENT_SEASON_NUM).first()
    #         assert season_stats is not None
    #         rankobj = R6Rank.from_mmr(season_stats.rankpoints)

    #         embed = makeembed_bot(color=rankobj.color,
    #             title=f"{platform.emoji} {player.user_connection.name}'s Ranked Stats", 
    #             #url=get_r6_tracker_url(player.name, platform),
    #             url=get_perma_r6_tracker_url(player.user_connection.request_id, platform),
    #             #description=f"Requested by {ctx.author}"
    #         )
    #         #attr = 'ranked_'

    #         wins = season_stats.matcheswon
    #         losses = season_stats.matcheslost
    #         kills = season_stats.kills
    #         deaths = season_stats.deaths

    #         try: wl_ratio = wins/losses
    #         except ZeroDivisionError: wl_ratio = 0

    #         try: kd_ratio = kills/deaths
    #         except ZeroDivisionError: kd_ratio = 0

    #         embed.add_field(name='Rank', value=f"`{rankobj.name}`", inline=True)
    #         embed.add_field(name='MMR', value=f"`{season_stats.rankpoints}`", inline=True)

    #         embed.add_field(name='Wins', value=f"`{wins}`", inline=True)
    #         embed.add_field(name='Losses', value=f"`{losses}`", inline=True)
    #         embed.add_field(name='W/L Ratio', value=f"`{wl_ratio:.2f}`", inline=True)

    #         embed.add_field(name='Abandons', value=f"`{season_stats.matchesabandoned}`", inline=True)
    #         embed.add_field(name='Kills', value=f"`{kills}`", inline=True)
    #         embed.add_field(name='Deaths', value=f"`{deaths}`", inline=True)
    #         embed.add_field(name='K/D Ratio', value=f"`{kd_ratio:.2f}`", inline=True)
    #         embed.set_thumbnail(url=rankobj.image_url)
            
    #         #cached_info = await RankedStatsSeasonal.filter(ranked_stats__user_connection__request_id=player.user_connection.request_id, platform_connection__platform=platform.route, season=CURRENT_SEASON_NUM).first()

    #         if season_stats:
    #             #embed.add_field(name="First Seen", value=f"{dctimestamp(cached_info.created_at,'R')}", inline=True)
    #             embed.add_field(name="Last Updated", value=f"{dctimestamp(season_stats.updated_at,'R')}", inline=True)

    #         await ctx.reply(embed=embed)

    #         if not ctx.interaction:
    #             assert ctx.command is not None
    #             #embed.add_field(name=f"{emojidict.get('nerd')} Tip", value=f"You can use the slash command version of this command, for autocomplete and other additional features. Try it using {await self.get_command_mention(ctx.command.qualified_name)}.", inline=False)
    #             emb2 = makeembed_bot(description=f"{emojidict.get('nerd')} Tip: You can use the slash command version of this command, for autocomplete and other additional features. Try it using {await self.get_command_mention(ctx.command.qualified_name)}.")
    #             await ctx.reply(embed=emb2, delete_after=10.0)
    #             await ctx.reply(embed=embed)

    #     except Exception as e:
    #         #traceback.print_exc()
    #         sentry_sdk.capture_exception(e)
    #         await player.fetch_related('user_connection')
    #         return await ctx.reply(embed=makeembed_bot(title="Invalid Username", description=f"Username `{username if not player else player.user_connection.name}` was not found.",color=discord.Color.red()))
    
    async def r6_ranked_context_menu_xbox(self, interaction: discord.Interaction, user: discord.User):
        return await self.r6_ranked_context_menu(interaction, user, Platform.XBOX)

    async def r6_ranked_context_menu_psn(self, interaction: discord.Interaction, user: discord.User):
        return await self.r6_ranked_context_menu(interaction, user, Platform.PSN)
    
    async def r6_ranked_context_menu_uplay(self, interaction: discord.Interaction, user: discord.User):
        return await self.r6_ranked_context_menu(interaction, user, Platform.UBI)

    async def r6_ranked_context_menu(self, interaction: discord.Interaction, user: discord.User, platform: Platform):
        ctx = await ContextU.from_interaction(interaction)

        await ctx.defer()

        connection = await R6UserConnections.filter(platform_id=user.id, platform='discord').first()
        if not connection:
            if ctx.guild:
                if ctx.guild.id == TOURNEY_SERVER:
                    return await ctx.reply(embed=makeembed_bot(title='Not Linked', description=f"User `{user}` has not linked their Discord to their Ubisoft account. They can link it by following the instructions in <#{USERNAME_CHANNEL}>.", color=discord.Color.red()))
            return await ctx.reply(embed=makeembed_bot(title='Not Linked', description=f"User `{user}` has not linked their Discord to their Ubisoft account.", color=discord.Color.red()))
            #return await ctx.reply(embed=makeembed_bot(title="Invalid User", description=f"User `{user}` was not found.",color=discord.Color.red()))

        await connection.fetch_related('profile')

        id = connection.profile.userid
        player = None
        #for connection in connection.profile:
        for connection in await R6UserConnections.filter(profile=connection.profile).order_by('is_third_party','created_at'):
            #if connection.is_third_party: continue
            platform_ = Platform.from_str(connection.platform)
            assert platform_ is not None
            if platform_ == platform:
                player = await self.get_r6_user(uid=id, platform=platform_)
                break

        if not player:
            return await ctx.reply(embed=makeembed_bot(title="Invalid User", description=f"User `{user}` was not found.",color=discord.Color.red()))
        await player.fetch_related('user_connection')
        return await self.r6_lookup_cmd(ctx, 'ranked', platform=platform, username=player.user_connection.name, force=False)
        # except Exception as e:
        #     #traceback.print_exc()
        #     sentry_sdk.capture_exception(e)
        #     return await ctx.reply(embed=makeembed_bot(title="Invalid User", description=f"User `{user}` was not found.",color=discord.Color.red()))
    
    async def r6_linked_accounts_context_menu(self, interaction: discord.Interaction, user: discord.User):
        ctx = await ContextU.from_interaction(interaction)
        return await self.r6_linked_accounts_cmd(ctx, discorduser=user)


    @commands.hybrid_command(name='previoususernames',description="View previous usernames of a user.")
    @Cooldown(1, 5, commands.BucketType.user)
    @app_commands.describe(platform='The platform to search on.', current_username="The username or the ID of the user.", fetch="Whether to force statistics to be updated or not. Defaults to False.")
    async def previous_usernames_cmd(self, ctx: ContextU, platform: PlatformConverter, current_username: str, fetch: bool=False):
        await ctx.defer()

        id = await self.get_id_or_reply(ctx, current_username, platform, force=fetch)
        if id and not isinstance(id, str):
            return id
        
        player = await self.get_r6_user(uid=id, platform=platform, fetch=fetch) # type: ignore

        if not player:
            return await ctx.reply(embed=makeembed_bot(title="Invalid User", description=f"User `{current_username}` was not found.",color=discord.Color.red()))

        await player.fetch_related('user_connection')

        previous_usernames = await NameChanges.filter(user=player.user).order_by('-timestamp')
        # if not previous_usernames:
        #     return await ctx.reply(embed=makeembed_bot(title="No Previous Usernames", description=f"User `{player.user_connection.name}` has not changed their username.",color=discord.Color.red()))

        # description = f"`{player.user_connection.name}` - Current\n"

        # for name_change in previous_usernames:
        #     description += f"`{name_change.name}` - {dctimestamp(name_change.timestamp,'D')}\n"

        name_change = None
        if previous_usernames:
            previous_timestamp = previous_usernames[0].timestamp
        else:
            previous_timestamp = None

        if previous_timestamp:
            description = f"`{player.user_connection.name}` - {dctimestamp(previous_timestamp,'D')} -> `Current`\n"
        else:
            description = f"`{player.user_connection.name}` - `Account Creation` -> `Current`\n"

        for index, name_change in enumerate(previous_usernames):
            previous_timestamp = previous_usernames[index+1].timestamp if index+1 < len(previous_usernames) else None
            if previous_timestamp:
                description += f"`{name_change.name}` - {dctimestamp(previous_timestamp,'D')} -> {dctimestamp(name_change.timestamp,'D')}\n"
                #previous_timestamp = name_change.timestamp
            else:
                description += f"`{getattr(name_change, 'name', player.user_connection.name)}` - `Account Creation` -> {dctimestamp(name_change.timestamp,'D')}\n"

        emb = makeembed_bot(author_icon_url=player.user_connection.pfp_url or None, author=f"{player.user_connection.name}'s Previous Usernames", description=description)
        view = URLButton(url=get_perma_r6_tracker_url(player.user_connection.request_id, platform), buttontext="View on R6Tracker")
        return await ctx.reply(embed=emb, view=view)

    @commands.hybrid_group(name='leaderboard',description="Get the leaderboard of who has the best statistics.")
    @Cooldown(1, 15, BucketType.user)
    async def r6_leaderboard(self, ctx: ContextU):
        pass

    @r6_leaderboard.command(name='global',description="Get the leaderboard of who has the best statistics.")
    @app_commands.describe(
        leaderboard_type='The gamemode to show a leaderboard for.',
        filter_by="The filter to sort by.",
        platform='The platform to search on.',
        ordering="Which way the results should be sorted. Ascending or Descending.",
    )
    async def r6_leaderboard_global(self, ctx: ContextU, 
        leaderboard_type: LeaderboardGamemodeConverter=Gamemode.RANKED, # type: ignore
        #leaderboard_type: Literal['ranked', 'casual', 'warmup', 'unranked']='ranked',
        #filter_by: Literal['Current MMR', 'Current Rank Points','Current Rank', 'Peak MMR', 'Peak Rank Points', 'Peak Rank', 'Wins', 'Losses', 'Kills', 'Deaths', 'Abandons']='Current MMR',
        filter_by: LeaderboardFilterConverter=LeaderboardFilter.current_mmr, # type: ignore
        platform: PlatformConverter=Platform.ALL, # type: ignore
        ordering: Literal['Ascending', 'Descending']='Descending'):
        """
        Get the leaderboard of who has the best statistics in this discord server.
        """
        return await self.r6_leaderboard_cmd(ctx, leaderboard_type=leaderboard_type, filter_by=filter_by, platform=platform, ordering=ordering) # type: ignore

    @r6_leaderboard.command(name='server',description="Get the leaderboard of who has the best statistics in this discord server.")
    @commands.guild_only()
    @app_commands.describe(
        leaderboard_type='The gamemode to show a leaderboard for.',
        filter_by="The filter to sort by.",
        platform='The platform to search on.',
        ordering="Which way the results should be sorted. Ascending or Descending.",
    )
    async def r6_leaderboard_server(self, ctx: ContextU, 
        leaderboard_type: Literal['ranked', 'casual', 'warmup', 'unranked']='ranked',
        filter_by: Literal['Current MMR', 'Current Rank Points','Current Rank', 'Peak MMR', 'Peak Rank Points', 'Peak Rank', 'Wins', 'Losses', 'Kills', 'Deaths', 'Abandons']='Current MMR',
        platform: PlatformConverter=Platform.ALL, # type: ignore
        ordering: Literal['Ascending', 'Descending']='Descending'):
        return await self.r6_leaderboard_server_cmd(ctx, leaderboard_type=leaderboard_type, filter_by=filter_by, platform=platform, ordering=ordering) # type: ignore

    async def r6_leaderboard_cmd(self, ctx: ContextU, 
        #leaderboard_type: Literal['ranked', 'casual', 'warmup', 'unranked']='ranked',
        leaderboard_type: Gamemode=Gamemode.RANKED, # type: ignore
        #filter_by: Literal['Current MMR', 'Current Rank Points','Current Rank', 'Peak MMR', 'Peak Rank Points', 'Peak Rank', 'Wins', 'Losses', 'Kills', 'Deaths', 'Abandons']='Current MMR',
        filter_by: LeaderboardFilter=LeaderboardFilter.current_mmr, # type: ignore
        #platform: Literal['All', 'Xbox', 'PSN', 'UPlay']='All', 
        platform: Platform=Platform.ALL, # type: ignore
        ordering: Literal['Ascending', 'Descending']='Descending'):
        """Look up the global leaderboard for ranked stats.
        
        Note that this leaderboard only shows for users that have been looked up using the bot."""

        await ctx.defer()

        # if platform not in ['Any','All']:
        #     platform_ = Platform.from_str(platform)
        #     assert platform_ is not None
        # else:
        #     platform_ = None

        _filter_by = filter_by.route

        filter_by: str = str(filter_by).lower().strip()

        if ordering.lower().strip() == 'descending':
            _direction = '-'
        else:
            _direction = ''

        # if filter_by == 'mmr':
        #     _filter_by = 'ranked_rankpoints'
        # elif filter_by == 'mmr' or filter_by == 'rank points':
        #     _filter_by = 'ranked_rankpoints'
        # elif filter_by == 'rank' or filter_by == 'rank points':
        #     _filter_by = 'ranked_rank'
        # if leaderboard_type == 'ranked':
        #     if filter_by in ['current mmr', 'current rank points','current rank']:
        #         _filter_by = 'rankpoints'
        #     elif filter_by in ['peak mmr', 'peak rank points', 'peak rank']:
        #         _filter_by = 'maxrankpoints'
        #     elif filter_by == 'wins':
        #         _filter_by = 'matcheswon'
        #     elif filter_by == 'losses':
        #         _filter_by = 'matcheslost'
        #     elif filter_by == 'kills':
        #         _filter_by = 'kills'
        #     elif filter_by == 'deaths':
        #         _filter_by = 'deaths'
        #     elif filter_by == 'abandons':
        #         _filter_by = 'matchesabandoned'
        #     else:
        #         return await ctx.reply(embed=makeembed_bot(title="Invalid Filter By", description=f"Filter by `{filter_by}` is invalid.",color=discord.Color.red()))
        # elif leaderboard_type == 'casual':
        #     if filter_by == 'wins':
        #         _filter_by = 'matcheswon'
        #     elif filter_by == 'losses':
        #         _filter_by = 'matcheslost'
        #     elif filter_by == 'kills':
        #         _filter_by = 'kills'
        #     elif filter_by == 'deaths':
        #         _filter_by = 'deaths'
        #     elif filter_by == 'abandons':
        #         _filter_by = 'matchesabandoned'
        #     else:
        #         return await ctx.reply(embed=makeembed_bot(title="Invalid Filter By", description=f"Filter by `{filter_by}` is invalid.",color=discord.Color.red()))

        # else:
        #     return await ctx.reply(embed=makeembed_bot(title="Invalid Leaderboard Type", description=f"Leaderboard type `{leaderboard_type}` is invalid.",color=discord.Color.red()))

        # if _filter_by == 'ranked_losses' and ordering.lower().strip() == 'ascending':
        #     _direction = '-'
        #     ordering = 'Descending'   

        ranked_stats = RankedStatsSeasonal.filter(season=CURRENT_SEASON_NUM, gamemode_name__iexact=leaderboard_type.name)
        if platform is not Platform.ALL:
            ranked_stats = ranked_stats.filter(platform_connection__platform=platform.route)
        ranked_stats = await ranked_stats.order_by(f'{_direction}{_filter_by}','created_at').prefetch_related('ranked_stats','platform_connection').all()

        if not ranked_stats or len(ranked_stats) == 0:
            if platform is not Platform.ALL:
                return await ctx.reply(embed=makeembed_bot(title="No Data", description=f"No players on {platform.proper_name} have been looked up.",color=discord.Color.red()))
            else:
                return await ctx.reply(embed=makeembed_bot(title="No Data", description="No players have been looked up.",color=discord.Color.red()))

        if platform is Platform.ALL:
            users = []
            ranked_stats2 = []
            for stats in ranked_stats:
                await stats.ranked_stats.fetch_related('user')
                #await stats.fetch_related('user')
                if stats.ranked_stats.user not in users:
                    users.append(stats.ranked_stats.user)
                    ranked_stats2.append(stats)
            ranked_stats = ranked_stats2

        pages = []

        tr = 0
        for stats in ranked_stats:
            # member = await self.bot.getorfetch_user(stats.user_id, None)
            # if not member:
            #     continue

            #await stats.fetch_related('user')

            _platform = Platform.from_route(stats.platform_connection.platform)
            assert _platform is not None

            if _filter_by in ['rankpoints', 'maxrankpoints']:
                if stats.maxrankpoints == 1000: # unranked
                    continue
            
            elif _filter_by in ['matchesabandoned', 'kills','deaths', 'matcheswon', 'matcheslost']:
                if (stats.kills== 0 and stats.deaths == 0): # skip inactive accs this season
                    continue
            
            tr += 1
            
            connections = R6UserConnections.filter(userid=stats.platform_connection.userid).order_by('is_third_party','created_at')

            discord_connection = await connections.filter(platform='discord').first()

            preferred_platform = None
            if discord_connection:
                if user_settings := await Settings.filter(user_id=discord_connection.platform_id).first():
                    if not user_settings.show_on_leaderboard:
                        continue
                    elif user_settings.preferred_platform != 'N/A':
                        try:
                            preferred_platform = Platform.from_str(user_settings.preferred_platform)
                            assert preferred_platform is not None
                        except Exception as e: pass                   

            if preferred_platform:
                platform_connection = await connections.filter(platform=preferred_platform.route).first()
            else:
                platform_connection = await connections.filter(platform=_platform.route).first()

            #platform_connection = await connections.filter(platform=_platform.route).first()

            #if not platform_connection: continue
            # if not platform_connection:
            #     platform_connection = await self.fetch_platform_connection(stats, _platform)

            #assert platform_connection is not None
            if not platform_connection:
                continue

            # if discord_connection:
            #     member = f'<@{discord_connection.platform_id}>'
            # else:
            #     member = None

            if tr in range(1,4):
                emoji = emojidict.get(str(humanize.ordinal(tr)))
            elif tr in range(4,11): 
                emoji = emojidict.get(str(tr))
            else:
                emoji = f'`{tr}`'

            desc = f"{emoji} "

            rank = None

            if _filter_by in ['rankpoints', 'maxrankpoints']: # don't have to change this to be for gamemode, we don't show rank anyway for non ranked
                #rank = R6Rank.from_mmr(stats.maxrankpoints)
                # if _filter_by == 'rankpoints':
                #     rank = R6Rank.from_mmr(stats.rankpoints)
                # elif _filter_by == 'maxrankpoints':
                #     rank = R6Rank.from_mmr(stats.maxrankpoints)
                rank  = R6Rank.from_mmr(getattr(stats, _filter_by))

                desc += f"{rank.emoji} "

            if platform is Platform.ALL:
                desc += f"{_platform.emoji} "

            #desc += f"{platform_connection.name} "
            #desc += dchyperlink(get_r6_tracker_url(platform_connection.name, _platform), platform_connection.name, f'View R6 Stats for {platform_connection.name}', suppress_embed=True) + " "
            desc += dchyperlink(get_perma_r6_tracker_url(str(platform_connection.request_id), _platform), f"`{platform_connection.name}`", f'View R6 Stats for {platform_connection.name}', suppress_embed=True) + " "
            # if member:
            #     desc += f" ({member}) "

            if leaderboard_type == 'ranked':
                if _filter_by in ['rankpoints', 'maxrankpoints']:
                    assert rank is not None
 
                    if _filter_by == 'rankpoints':
                        desc += f"(`{rank.name}`, `{getattr(stats, _filter_by)}` MMR)"

                elif _filter_by == 'wins':
                    desc += f"(`{stats.matcheswon}` win{plural(stats.matcheswon)})"
                elif _filter_by == 'losses':
                    desc += f"(`{stats.matcheslost}` loss{plural(stats.matcheslost,'es')})"
                elif _filter_by == 'kills':
                    desc += f"(`{stats.kills}` kill{plural(stats.kills)})"
                elif _filter_by == 'deaths':
                    desc += f"(`{stats.deaths}` death{plural(stats.deaths)})"
                elif _filter_by == 'abandons':
                    desc += f"(`{stats.matchesabandoned}` abandon{plural(stats.matchesabandoned)})"
            else:
                rank = R6Rank.from_mmr(stats.rankpoints)
                desc += f"(`{rank.name}`, `{stats.rankpoints}` MMR)"
            
            pages.append(desc)
            #desc = f"{emoji} {rank.emoji}({' '+member if member else ''}) ({stats.ranked_rank}, `{stats.ranked_rankpoints}` MMR)"
            #desc += f"> {emoji}: `{user.username}` (`{user.lookup_count}` lookup{'s' if abs(user.lookup_count) != 1 else ''})\n"
        title = f"{leaderboard_type.proper_name} Leaderboard"
        # if platform:
        #     title += f" for {platform.proper_name}"
        # else:
        #     title += " for All Platforms"

        title += f" for {platform.proper_name}"

        if _filter_by == 'rankpoints':
            title += " by Current MMR"
        elif _filter_by == 'maxrankpoints':
            title += " by Peak MMR"
        elif _filter_by == 'matcheswon':
            title += " by Wins"
        elif _filter_by == 'matcheslost':
            title += " by Losses"
        elif _filter_by == 'kills':
            title += " by Kills"
        elif _filter_by == 'deaths':
            title += " by Deaths"
        elif _filter_by == 'matchesabandoned':
            title += " by Abandons"
        else:
            title += " by Current MMR"

        if platform is not Platform.ALL:
            color = platform.color
        else:
            color = discord.Color.blurple()

        # leaderboard pages go by 100s

        pages = generate_pages(pages, title=title, color=color, items_per_page=15-1, url=get_r6_leaderboard_url(platform, gamemode=leaderboard_type))

        cmd_mention = await self.get_command_mention(f'lookup {leaderboard_type.name}')

        for emb in pages:
            emb.description = f"{emb.description}\n> {emojidict.get('pencil')} The leaderboard shows everybody that has been looked up using the bot. If you see people missing on this leaderboard, look them up with {cmd_mention}."

        #url = "https://r6.tracker.network/r6siege/leaderboards/rankedv2/all/rankpoints?page=1&platformFamily=all&season=33&gamemode=pvp_ranked"

        # generate this URL based on the platform and the gamemode


        # if url := get_r6_leaderboard_url(platform, gamemode=leaderboard_type):
        #     view = URLButton(url=url, buttontext="View Full Leaderboard")
        # else:
        #     view = None
    
        return await create_paginator(ctx, pages, paginator=FiveButtonPaginator, author_id=ctx.author.id, go_to_button=True)

    async def r6_leaderboard_server_cmd(self, ctx: ContextU, 
        platform: Platform=Platform.ALL,
        leaderboard_type: Literal['ranked', 'casual', 'warmup', 'unranked']='ranked',
        filter_by: Literal['Current MMR', 'Current Rank Points','Current Rank', 'Peak MMR', 'Peak Rank Points', 'Peak Rank', 'Wins', 'Losses', 'Kills', 'Deaths', 'Abandons']='Current MMR',
        ordering: Literal['Ascending', 'Descending']='Descending'):

        await ctx.defer()

        assert ctx.guild is not None

        _filter_by = ''

        filter_by: str = str(filter_by).lower().strip()

        if ordering.lower().strip() == 'descending':
            _direction = '-'
        else:
            _direction = ''

        # if filter_by == 'mmr':
        #     _filter_by = 'ranked_rankpoints'
        # elif filter_by == 'mmr' or filter_by == 'rank points':
        #     _filter_by = 'ranked_rankpoints'
        # elif filter_by == 'rank' or filter_by == 'rank points':
        #     _filter_by = 'ranked_rank'
        if leaderboard_type == 'ranked':
            if filter_by in ['current mmr', 'current rank points','current rank']:
                _filter_by = 'rankpoints'
            elif filter_by in ['peak mmr', 'peak rank points', 'peak rank']:
                _filter_by = 'maxrankpoints'
            elif filter_by == 'wins':
                _filter_by = 'matcheswon'
            elif filter_by == 'losses':
                _filter_by = 'matcheslost'
            elif filter_by == 'kills':
                _filter_by = 'kills'
            elif filter_by == 'deaths':
                _filter_by = 'deaths'
            elif filter_by == 'abandons':
                _filter_by = 'matchesabandoned'
            else:
                return await ctx.reply(embed=makeembed_bot(title="Invalid Filter By", description=f"Filter by `{filter_by}` is invalid.",color=discord.Color.red()))
        elif leaderboard_type == 'casual':
            if filter_by == 'wins':
                _filter_by = 'matcheswon'
            elif filter_by == 'losses':
                _filter_by = 'matcheslost'
            elif filter_by == 'kills':
                _filter_by = 'kills'
            elif filter_by == 'deaths':
                _filter_by = 'deaths'
            elif filter_by == 'abandons':
                _filter_by = 'matchesabandoned'
            else:
                return await ctx.reply(embed=makeembed_bot(title="Invalid Filter By", description=f"Filter by `{filter_by}` is invalid.",color=discord.Color.red()))
        else:
            return await ctx.reply(embed=makeembed_bot(title="Invalid Leaderboard Type", description=f"Leaderboard type `{leaderboard_type}` is invalid.",color=discord.Color.red()))
        

        member_count = ctx.guild.member_count if ctx.guild.member_count else ctx.guild.approximate_member_count
        if not member_count:
            return await ctx.reply("Error occured while fetching member count. Please try again later.")

        if member_count > 1000:
            return await ctx.reply("This command is not available for servers with more than 1000 members.")
        
        # if platform not in ['Any','All']:
        #     platform_ = Platform.from_str(platform)
        #     assert platform_ is not None
        # else:
        #     platform_ = None

        members = [m for m in ctx.guild.members if not m.bot]

        #connections = await R6UserConnections.filter(platform='discord').all()

        ranked_stats_dict: Dict[discord.Member, RankedStatsSeasonal] = {}
        #for connection in connections:
        for member in members:
            #connection = discord.utils.find(lambda x: x.platform_id == member.id and x.platform == 'discord', connections)
            connection = await R6UserConnections.filter(platform_id=member.id, platform='discord').first().prefetch_related('profile')
            if connection:
                #await connection.fetch_related('profile')
                linked_acc = R6UserConnections.filter(profile=connection.profile).order_by('is_third_party','created_at')

                user_settings = await Settings.filter(user_id=member.id).first()

                if user_settings:
                    if not user_settings.show_on_leaderboard:
                        continue
                    if user_settings.preferred_platform != "N/A":
                        preferred_platform = Platform.from_str(user_settings.preferred_platform)
                        assert preferred_platform is not None

                        if platform is not Platform.ALL and platform != preferred_platform:
                            continue

                        linked_acc = await linked_acc.filter(platform=preferred_platform.route).first()
                    elif platform:
                        linked_acc = await linked_acc.filter(platform=platform.route).first()
                    else:
                        linked_acc = await linked_acc.first()
                elif platform:
                    linked_acc = await linked_acc.filter(platform=platform.route).first()
                else:
                    linked_acc = await linked_acc.first()

                if not linked_acc: # if the discord connection doesn't have a linked account on the platform
                    continue

                #user = await R6User.filter(userid=connection.profile.userid).first()
                ranked_stats = RankedStatsSeasonal.filter(platform_connection=linked_acc, season=CURRENT_SEASON_NUM, gamemode_name__iexact=leaderboard_type).order_by(f'{_direction}{_filter_by}', 'created_at').prefetch_related('ranked_stats','platform_connection')
                if platform is not Platform.ALL:
                    ranked_stats = await ranked_stats.filter(platform_connection__platform=platform.route).first()
                else:
                    ranked_stats = await ranked_stats.first()

                if not ranked_stats:
                    await self.get_r6_user(uid=connection.profile.userid, platform=platform if platform else Platform.from_str(linked_acc.platform))

                    ranked_stats = RankedStatsSeasonal.filter(season=CURRENT_SEASON_NUM, gamemode_name__iexact=leaderboard_type).order_by(f'{_direction}{_filter_by}', 'created_at').prefetch_related('ranked_stats','platform_connection')
                    if platform is not Platform.ALL:
                        ranked_stats = await ranked_stats.filter(platform_connection__platform=platform.route).first()
                    else:
                        ranked_stats = await ranked_stats.first()

                    if not ranked_stats:
                        continue

                if _filter_by in ['rankpoints', 'maxrankpoints']:
                    if ranked_stats.maxrankpoints == 1000: # unranked
                        continue

                elif _filter_by in ['matchesabandons', 'kills', 'deaths', 'matcheswon', 'matcheslost']:
                    if (ranked_stats.kills == 0 and ranked_stats.deaths == 0): # skip inactive accs this season
                        continue
                # if not ranked_stats:
                #     player = await self.get_r6_user(uid=connection.profile.userid, platform=platform if platform else Platform.UPLAY)
                #     #await player.load_ranked_v2()
                #     ranked_stats = await RankedStats.from_player(player)
                ranked_stats_dict[member] = ranked_stats

        # def key(x: Tuple[discord.Member, RankedStats]):
        #     return getattr(x[1], f"{_filter_by}")
        #bot_logger.info(str(ranked_stats_dict))
        #print(ranked_stats_dict)

        ranked_stats_dict = dict(sorted(ranked_stats_dict.items(), key=lambda x: getattr(x[1], f"{_filter_by}"), reverse=True)) # type: ignore

        if not ranked_stats_dict or len(ranked_stats_dict) == 0:
            link_cmd = await self.get_command_mention('link')

            proper_name = platform.proper_name

            desc = f"No players on {proper_name} have linked their Discord to their Ubisoft {emojidict.get('skull')}.\n"

            if ctx.guild.id == TOURNEY_SERVER:
                desc += f"> If you are on {proper_name}, you can link your Discord to your Ubisoft by following the instructions in <#{USERNAME_CHANNEL}>."
            else:
                desc += f"> If you are on {proper_name}, you can link your Discord to your Ubisoft by running {link_cmd}."

            return await ctx.reply(embed=makeembed_bot(title="No Data", description=desc,color=discord.Color.red()))
        
        if platform is Platform.ALL:
            users = []
            ranked_stats2 = {}
            for member, stats in ranked_stats_dict.items():
                await stats.ranked_stats.fetch_related('user_connection')
                if stats.ranked_stats.user_connection not in users:
                    users.append(stats.ranked_stats.user_connection)
                    #ranked_stats2.append(stats)
                    ranked_stats2[member] = stats
            ranked_stats = ranked_stats2

        pages = []

        tr = 0
        for member, stats in ranked_stats_dict.items():
            # member = kv[0]
            # stats = kv[1]
            tr += 1

            if tr in range(1,4):
                emoji = emojidict.get(str(humanize.ordinal(tr)))
            elif tr in range(4,11):
                emoji = emojidict.get(str(tr))
            else:
                emoji = f'`{tr}`'
            
            #await stats.fetch_related('user')

            platform_connection = await R6UserConnections.filter(userid=stats.platform_connection.userid, platform=stats.platform_connection.platform).first()
            if not platform_connection:
                #platform_connection = await self.fetch_platform_connection(stats, platform if platform else Platform.from_str(stats.platform_connection.platform))
                #if not platform_connection: continue
                continue

            rank = R6Rank.from_mmr(stats.rankpoints)

            desc = f"{emoji} "

            if _filter_by in ['rankpoints', 'maxrankpoints']:
                desc += f"{rank.emoji} "

            _plat = Platform.from_str(platform_connection.platform)
            assert _plat is not None

            platform_emoji = _plat.emoji

            if not platform:
                desc += f"{platform_emoji} "

            #desc += f"{platform_connection.name} "
            #desc += dchyperlink(get_r6_tracker_url(platform_connection.name, _platform), platform_connection.name, f'View R6 Stats for {platform_connection.name}', suppress_embed=True) + " "
            desc += f"{member.mention} ({dchyperlink(get_perma_r6_tracker_url(str(stats.platform_connection.request_id), _plat), platform_connection.name, f'View R6 Stats for {platform_connection.name}', suppress_embed=True)}) "

            if _filter_by in ['rankpoints', 'maxrankpoints']:
                desc += f" `{rank.name}`, `{getattr(stats, _filter_by)}` MMR"

            elif _filter_by == 'matcheswon':
                desc += f"`{stats.matcheswon}` win{plural(stats.matcheswon)}"
            elif _filter_by == 'matcheslost':
                desc += f"`{stats.matcheslost}` loss{plural(stats.matcheslost,'es')}"
            elif _filter_by == 'kills':
                desc += f"`{stats.kills}` kill{plural(stats.kills)}"
            elif _filter_by == 'deaths':
                desc += f"`{stats.deaths}` death{plural(stats.deaths)}"
            elif _filter_by == 'matchesabandoned':
                desc += f"`{stats.matchesabandoned}` abandon{plural(stats.matchesabandoned)}"
            
            pages.append(desc)
            #desc = f"{emoji} {rank.emoji}({' '+member if member else ''}) ({stats.ranked_rank}, `{stats.ranked_rankpoints}` MMR)"
            #desc += f"> {emoji}: `{user.username}` (`{user.lookup_count}` lookup{'s' if abs(user.lookup_count) != 1 else ''})\n"
        title = f"{leaderboard_type.title()} Leaderboard for {platform.proper_name}"

        if _filter_by == 'rankpoints':
            title += " by Current MMR"
        elif _filter_by == 'maxrankpoints':
            title += " by Peak MMR"
        elif _filter_by == 'matcheswon':
            title += " by Wins"
        elif _filter_by == 'matcheslost':
            title += " by Losses"
        elif _filter_by == 'kills':
            title += " by Kills"
        elif _filter_by == 'deaths':
            title += " by Deaths"
        elif _filter_by == 'matchesabandoned':
            title += " by Abandons"
        else:
            title += " by Current MMR"
        
        if platform is not Platform.ALL:
            color = platform.color
        else:
            color = discord.Color.blurple()

        #pages = generate_pages(pages, title=title, color=color, items_per_page=15-1, url=get_r6_leaderboard_url(platform, gamemode=leaderboard_type) if platform else None)

        # if leaderboard_type == 'ranked':
        #     desc += f"({getattr(stats, _filter_by)}, `{getattr(stats, _filter_by)}` MMR)"
        #     #desc += f"> {emoji}: `{user.username}` (`{user.lookup_count}` lookup{'s' if abs(user.lookup_count) != 1 else ''})\n"
        #     pages.append(desc)
        # #embed = makeembed_bot(title=f"Ranked Leaderboard for {platform_.proper_name}", color=discord.Color.blurple())
        if platform:
            pages = generate_pages(pages, title=f"{platform.emoji+' ' if platform is not Platform.ALL else ''}{platform.proper_name} {leaderboard_type.title()} Leaderboard in {ctx.guild.name}", color=color, items_per_page=10)
        else:
            pages = generate_pages(pages, title=f"All Platforms {leaderboard_type.title()} Leaderboard in {ctx.guild.name}", color=color, items_per_page=10)
        link_cmd = await self.get_command_mention('link')

        lookup_ranked_cmd = await self.get_command_mention(f'lookup {leaderboard_type}')

        for emb in pages:
            #emb.description = f"{emb.description}\n> {emojidict.get('discord')} To appear on this leaderboard, link your account with {link_cmd}."
            if ctx.guild.id == TOURNEY_SERVER:
                emb.description = f"{emb.description}\n> {emojidict.get('discord')} To appear on this leaderboard, link your account by following the instructions in <#{USERNAME_CHANNEL}>. If you still don't show up, look yourself up using {lookup_ranked_cmd}."
            else:
                emb.description = f"{emb.description}\n> {emojidict.get('discord')} To appear on this leaderboard, link your account with {link_cmd}. If you still don't show up, look yourself up using {lookup_ranked_cmd}."

        return await create_paginator(ctx, pages, paginator=FiveButtonPaginator, author_id=ctx.author.id, go_to_button=True)

    async def r6_leaderboard_cmd_new(self, ctx: ContextU, 
        #leaderboard_type: Literal['ranked', 'casual', 'warmup', 'unranked']='ranked',
        leaderboard_type: Gamemode=Gamemode.RANKED, # type: ignore
        #filter_by: Literal['Current MMR', 'Current Rank Points','Current Rank', 'Peak MMR', 'Peak Rank Points', 'Peak Rank', 'Wins', 'Losses', 'Kills', 'Deaths', 'Abandons']='Current MMR',
        filter_by: LeaderboardFilter=LeaderboardFilter.current_mmr, # type: ignore
        #platform: Literal['All', 'Xbox', 'PSN', 'UPlay']='All', 
        platform: Platform=Platform.ALL, # type: ignore
        ordering: Literal['Ascending', 'Descending']='Descending'):
        """
        This function can be used in place of the r6_leaderbaord_cmd command. The only difference in this command is that it fetches the leaderboard from the API of R6Tracker and then generates the leaderboard.
        """

        await ctx.defer()

        # if platform not in ['Any','All']:
        #     platform_ = Platform.from_str(platform)
        #     assert platform_ is not None
        # else:
        #     platform_ = None

        _filter_by = ''

        #filter_by: str = str(filter_by).lower().strip()

        if ordering.lower().strip() == 'descending':
            _direction = '-'
        else:
            _direction = ''

        # if filter_by == 'mmr':
        #     _filter_by = 'ranked_rankpoints'
        # elif filter_by == 'mmr' or filter_by == 'rank points':
        #     _filter_by = 'ranked_rankpoints'
        # elif filter_by == 'rank' or filter_by == 'rank points':
        #     _filter_by = 'ranked_rank'
        # if leaderboard_type == 'ranked':
        #     if filter_by in ['current mmr', 'current rank points','current rank']:
        #         _filter_by = 'rankpoints'
        #     elif filter_by in ['peak mmr', 'peak rank points', 'peak rank']:
        #         _filter_by = 'maxrankpoints'
        #     elif filter_by == 'wins':
        #         _filter_by = 'matcheswon'
        #     elif filter_by == 'losses':
        #         _filter_by = 'matcheslost'
        #     elif filter_by == 'kills':
        #         _filter_by = 'kills'
        #     elif filter_by == 'deaths':
        #         _filter_by = 'deaths'
        #     elif filter_by == 'abandons':
        #         _filter_by = 'matchesabandoned'
        #     else:
        #         return await ctx.reply(embed=makeembed_bot(title="Invalid Filter By", description=f"Filter by `{filter_by}` is invalid.",color=discord.Color.red()))
        # elif leaderboard_type == 'casual':
        #     if filter_by == 'wins':
        #         _filter_by = 'matcheswon'
        #     elif filter_by == 'losses':
        #         _filter_by = 'matcheslost'
        #     elif filter_by == 'kills':
        #         _filter_by = 'kills'
        #     elif filter_by == 'deaths':
        #         _filter_by = 'deaths'
        #     elif filter_by == 'abandons':
        #         _filter_by = 'matchesabandoned'
        #     else:
        #         return await ctx.reply(embed=makeembed_bot(title="Invalid Filter By", description=f"Filter by `{filter_by}` is invalid.",color=discord.Color.red()))

        # else:
        #     return await ctx.reply(embed=makeembed_bot(title="Invalid Leaderboard Type", description=f"Leaderboard type `{leaderboard_type}` is invalid.",color=discord.Color.red()))

        if leaderboard_type != Gamemode.RANKED:
            if filter_by in LeaderboardFilter.ranked_filters():
                return await ctx.reply(embed=makeembed_bot(title="Invalid Filter By", description=f"Filter by `{filter_by}` is invalid for the gamemode `{leaderboard_type}`.",color=discord.Color.red()))

        leaderboard = await self.get_r6_leaderboard(platform=platform, gamemode=leaderboard_type, _filter=filter_by)

        for x in leaderboard:
            await x.fetch_related('ranked_stats','platform_connection')

        if not leaderboard or len(leaderboard) == 0:
            if platform is not Platform.ALL:
                return await ctx.reply(embed=makeembed_bot(title="No Data", description=f"No players on {platform.proper_name} have been looked up.",color=discord.Color.red()))
            else:
                return await ctx.reply(embed=makeembed_bot(title="No Data", description="No players have been looked up.",color=discord.Color.red()))

        if ordering == 'Ascending':
            leaderboard.reverse()

        if platform is Platform.ALL:
            users = []
            ranked_stats2 = []
            for stats in leaderboard:
                await stats.ranked_stats.fetch_related('user')
                #await stats.fetch_related('user')
                if stats.ranked_stats.user not in users:
                    users.append(stats.ranked_stats.user)
                    ranked_stats2.append(stats)
            leaderboard = ranked_stats2

        pages = []

        tr = 0
        for stats in leaderboard:
            # member = await self.bot.getorfetch_user(stats.user_id, None)
            # if not member:
            #     continue

            #await stats.fetch_related('user')

            _platform = Platform.from_route(stats.platform_connection.platform)
            assert _platform is not None

            if _filter_by in ['rankpoints', 'maxrankpoints']:
                if stats.maxrankpoints == 1000: # unranked
                    continue
            
            elif _filter_by in ['matchesabandoned', 'kills','deaths', 'matcheswon', 'matcheslost']:
                if (stats.kills== 0 and stats.deaths == 0): # skip inactive accs this season
                    continue
            
            tr += 1
            
            connections = R6UserConnections.filter(userid=stats.platform_connection.userid).order_by('is_third_party','created_at')

            discord_connection = await connections.filter(platform='discord').first()

            preferred_platform = None
            if discord_connection:
                if user_settings := await Settings.filter(user_id=discord_connection.platform_id).first():
                    if not user_settings.show_on_leaderboard:
                        continue
                    elif user_settings.preferred_platform != 'N/A':
                        try:
                            preferred_platform = Platform.from_str(user_settings.preferred_platform)
                            assert preferred_platform is not None
                        except Exception as e: pass                   

            if preferred_platform:
                platform_connection = await connections.filter(platform=preferred_platform.route).first()
            else:
                platform_connection = await connections.filter(platform=_platform.route).first()

            #platform_connection = await connections.filter(platform=_platform.route).first()

            #if not platform_connection: continue
            # if not platform_connection:
            #     platform_connection = await self.fetch_platform_connection(stats, _platform)

            #assert platform_connection is not None
            if not platform_connection:
                continue

            # if discord_connection:
            #     member = f'<@{discord_connection.platform_id}>'
            # else:
            #     member = None
            
            if tr in range(1,4):
                emoji = emojidict.get(str(humanize.ordinal(tr)))
            elif tr in range(4,11): 
                emoji = emojidict.get(str(tr))
            else:
                emoji = f'`{tr}`'
            
            desc = f"{emoji} "
            
            rank = None

            if _filter_by in ['rankpoints', 'maxrankpoints']: # don't have to change this to be for gamemode, we don't show rank anyway for non ranked
                #rank = R6Rank.from_mmr(stats.maxrankpoints)
                # if _filter_by == 'rankpoints':
                #     rank = R6Rank.from_mmr(stats.rankpoints)
                # elif _filter_by == 'maxrankpoints':
                #     rank = R6Rank.from_mmr(stats.maxrankpoints)
                rank  = R6Rank.from_mmr(getattr(stats, _filter_by))

                desc += f"{rank.emoji} "
            
            if platform is Platform.ALL:
                desc += f"{_platform.emoji} "
            
            #desc += f"{platform_connection.name} "
            #desc += dchyperlink(get_r6_tracker_url(platform_connection.name, _platform), platform_connection.name, f'View R6 Stats for {platform_connection.name}', suppress_embed=True) + " "
            desc += dchyperlink(get_perma_r6_tracker_url(str(platform_connection.request_id), _platform), platform_connection.name, f'View R6 Stats for {platform_connection.name}', suppress_embed=True) + " "
            # if member:
            #     desc += f" ({member}) "
            
            if leaderboard_type == 'ranked':
                if _filter_by in ['rankpoints', 'maxrankpoints']:
                    assert rank is not None
 
                    if _filter_by == 'rankpoints':
                        desc += f"(`{rank.name}`, `{getattr(stats, _filter_by)}` MMR)"
                
                elif _filter_by == 'wins':
                    desc += f"(`{stats.matcheswon}` win{plural(stats.matcheswon)})"
                elif _filter_by == 'losses':
                    desc += f"(`{stats.matcheslost}` loss{plural(stats.matcheslost,'es')})"
                elif _filter_by == 'kills':
                    desc += f"(`{stats.kills}` kill{plural(stats.kills)})"
                elif _filter_by == 'deaths':
                    desc += f"(`{stats.deaths}` death{plural(stats.deaths)})"
                elif _filter_by == 'abandons':
                    desc += f"(`{stats.matchesabandoned}` abandon{plural(stats.matchesabandoned)})"
            else:
                rank = R6Rank.from_mmr(stats.rankpoints)
                desc += f"(`{rank.name}`, `{stats.rankpoints}` MMR)"
            
            pages.append(desc)
            #desc = f"{emoji} {rank.emoji}({' '+member if member else ''}) ({stats.ranked_rank}, `{stats.ranked_rankpoints}` MMR)"
            #desc += f"> {emoji}: `{user.username}` (`{user.lookup_count}` lookup{'s' if abs(user.lookup_count) != 1 else ''})\n"
        title = f"{leaderboard_type.title()} Leaderboard"
        # if platform:
        #     title += f" for {platform.proper_name}"
        # else:
        #     title += " for All Platforms"

        title += f" for {platform.proper_name}"
        
        if _filter_by == 'rankpoints':
            title += " by Current MMR"
        elif _filter_by == 'maxrankpoints':
            title += " by Peak MMR"
        elif _filter_by == 'matcheswon':
            title += " by Wins"
        elif _filter_by == 'matcheslost':
            title += " by Losses"
        elif _filter_by == 'kills':
            title += " by Kills"
        elif _filter_by == 'deaths':
            title += " by Deaths"
        elif _filter_by == 'matchesabandoned':
            title += " by Abandons"
        else:
            title += " by Current MMR"
        
        if platform is not Platform.ALL:
            color = platform.color
        else:
            color = discord.Color.blurple()

        # leaderboard pages go by 100s

        pages = generate_pages(pages, title=title, color=color, items_per_page=15-1, url=get_r6_leaderboard_url(platform, gamemode=leaderboard_type))

        cmd_mention = await self.get_command_mention(f'lookup {leaderboard_type.name}')

        for emb in pages:
            emb.description = f"{emb.description}\n> {emojidict.get('pencil')} The leaderboard shows everybody that has been looked up using the bot. If you see people missing on this leaderboard, look them up with {cmd_mention}."

        #url = "https://r6.tracker.network/r6siege/leaderboards/rankedv2/all/rankpoints?page=1&platformFamily=all&season=33&gamemode=pvp_ranked"

        # generate this URL based on the platform and the gamemode


        # if url := get_r6_leaderboard_url(platform, gamemode=leaderboard_type):
        #     view = URLButton(url=url, buttontext="View Full Leaderboard")
        # else:
        #     view = None
    
        return await create_paginator(ctx, pages, paginator=FiveButtonPaginator, author_id=ctx.author.id, go_to_button=True)

    @commands.command(name='importusers',hidden=True)
    @commands.is_owner()
    async def import_users(self, ctx: ContextU, attachment: discord.Attachment):
        """
        Import users from a JSON file.
        """
        await ctx.defer()

        players: List[Tuple[Platform, str]] = []
        
        if str(attachment.content_type).split(';')[0] ==  'text/plain':
            data = await attachment.read()
            for line in data.decode().split('\n'):
                if not line: continue
                # username_here (xbox)
                # (xbox) username_here
                
                if '(' in line and ')' in line:
                    platform = line.split('(')[1].split(')')[0]
                    username = line.replace(f'({platform})','').strip()
                    platform_ = Platform.from_str(platform)
                    assert platform_ is not None
                    if (platform_, username) not in players:
                        players.append((platform_, username))
                else:
                    username = line.strip()
                    players.append((Platform.UBI, username))
        elif attachment.content_type == 'application/json':
            data = json.loads(data)
            # data = [{"platform": "xbox", "username": "username_here"}, {"platform": "uplay", "username": "username_here"}])]
            for user in data:
                platform = Platform.from_str(user.get('platform'))
                assert platform is not None and isinstance(platform, Platform)
                players.append((platform, user.get('username')))
        else:
            return await ctx.reply(f"Invalid file type. Please upload a JSON file or Text File, not {attachment.content_type}.")            

        sucesses = []
        failures = []
        for d in players:
            platform, username = d
            try:
                if ID_RE.match(username):
                    p = await self.get_r6_user(uid=username, platform=platform)
                else:
                    p = await self.get_r6_user(username, platform=platform)
                sucesses.append(p)
                await asyncio.sleep(random.randint(0,2))
            except Exception as e:
                failures.append(username)
                continue
        
        if len(sucesses) > 0 and len(failures) > 0:
            message = f"Imported {len(sucesses)} users. Failed to import {len(failures)} users."
        elif len(sucesses) > 0:
            message = f"Imported {len(sucesses)} users."
        elif len(failures) > 0:
            message = f"Failed to import {len(failures)} users."
        else:
            message = "No users were imported."
        import io
        if len(failures) > 0:
            f = discord.File(io.BytesIO('\n'.join(failures).encode()), filename='failures.txt')
        else: 
            f = None
        return await ctx.reply(message, file=f)
        #return await ctx.reply("Error occured while importing users.")

    # async def fetch_platform_connection(self, stats, _platform: Platform) -> Optional[R6UserConnections]:
    #     platform_connection = None
    #     try: 
    #         player: Player = await self.get_r6_user(uid=str(stats.user_connection.userid), platform=_platform)
    #         stats = await RankedStatsV2.from_player(player)
    #         player_uplay = await self.get_r6_user(uid=str(stats.user_connection.userid), platform=Platform.UPLAY)
    #         #inked_accs = await player_uplay.load_linked_accounts()

    #         await asyncio.sleep(.25) # ratelimiting

    #         for acc in linked_accs:
    #             await R6UserConnections.create_from_api_obj(acc)
    #         platform_connection = await R6UserConnections.filter(userid=stats.user.userid, platform=_platform.route).first()
    #     except Exception as e:
    #         trace = traceback.format_exc()

    #         times = 0
    #         while "HTTP 429: Too many calls per profile." in trace and times < 5:
    #             try:
    #                 await asyncio.sleep(15)
    #                 times += 5
    #                 player: Player = await self.get_r6_user(uid=str(stats.user.userid), platform=_platform)
    #                 stats = await RankedStats.from_player(player)
    #                 player_uplay = await self.get_r6_user(uid=str(stats.user.userid), platform=Platform.UPLAY)
    #                 linked_accs = await player_uplay.load_linked_accounts()
    #                 for acc in linked_accs:
    #                     await R6UserConnections.create_from_api_obj(acc)
    #                 platform_connection = await R6UserConnections.filter(userid=stats.user.userid, platform=_platform.route).first()
    #             except Exception as e:
    #                 trace = traceback.format_exc()
    #                 continue
    #             if times >= 5:
    #                 continue
    #     return platform_connection

    @tasks.loop(time=[datetime.time(hour=h, minute=_STARTUP.minute) for h in range(0,24)])
    async def reauth_session(self):
        # for auth in self.auths:
        #     try:
        #         await auth.close()
        #     finally:
        #         await auth.connect()
        #await self.auth.connect() 
        await self.session.close()
        self.session = AsyncSession(headers=self.default_headers, impersonate="chrome116", proxies=self.proxy)

async def teardown(bot: BotU):
    #commands.AutoShardedBot.on_error = old_on_error
    logging.getLogger().removeHandler(bot.logging_handler)
    #bot.tree.on_error = bot.old_tree_error  # type: ignore

async def setup(bot: BotU):
    # global EMAIL, PASSWORD, XBOX_API_KEY, STEAM_API_KEY

    # with open('apikeys.yml') as f:
    #     apikeys = dict(yaml.safe_load(f))
    #     XBOX_API_KEY = apikeys.get('xbox')
    #     STEAM_API_KEY = apikeys.get('steam')
    #     assert XBOX_API_KEY and STEAM_API_KEY

    # auths = []
    # for i in range(1, 5+1):
    #     with open(f'r6auth_00{i}.yml') as f:
    #         config = dict(yaml.safe_load(f))
    #         EMAIL = config.get('email')
    #         PASSWORD = config.get('password')
    #         assert EMAIL and PASSWORD
    #         auths.append(Auth(email=EMAIL, password=PASSWORD))
    
    # env = environ.Env(
    #     PROD=(bool, False)
    # )

    # PROD = env("PROD")
    # if PROD:
    #     await Tortoise.init(config_file="db.yml")
    # else:
    #     await Tortoise.init(config_file="db_beta.yml")
    # await Tortoise.generate_schemas()
    # for auth in auths:
    #     await auth.connect()
    # cog = ApiCogV2(bot, auths=auths)
    # await bot.add_cog(cog)
    pass
 