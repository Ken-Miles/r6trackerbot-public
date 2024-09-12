from __future__ import annotations
import datetime
from enum import Enum
import traceback
from typing import Any, Dict, List, Optional, Tuple, Type, Union

import dateparser
import discord
import environ
from siegeapi import Player
from siegeapi.player import LinkedAccount
from tortoise import Tortoise, fields
from tortoise.models import Model
from typing_extensions import Self

from utils.custom_constants import CURRENT_SEASON

IGNORED_FIELDS = ("id", "created_at", "updated_at", "IGNORED_FIELDS", "Meta", 'userid', 'user_id', 'username', 'request_id', 'season')

class Base(Model):
    id = fields.BigIntField(pk=True, unique=True, generated=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        abstract = True


class AuthStorage(Base):
    sessionid = fields.CharField(max_length=100, blank=True)
    key = fields.CharField(max_length=3000, null=True)
    new_key = fields.CharField(max_length=3000, blank=True)
    spaceid = fields.CharField(max_length=100, blank=True)
    profileid = fields.CharField(max_length=100, blank=True)
    userid = fields.CharField(max_length=100, blank=True)
    expiration = fields.DatetimeField(max_length=100, null=True)
    new_expiration = fields.DatetimeField(max_length=100, null=True)

    class Meta:
        table = "AuthStorage"


class R6User(Base):
    userid = fields.UUIDField(max_length=50, unique=True)
    name = fields.CharField(max_length=100, null=True)
    platform = fields.CharField(max_length=100, default="uplay")
    # platform_id = fields.CharField(max_length=100)

    class Meta:
        table = "R6User"


class R6UserConnections(Base):
    userid = fields.CharField(max_length=100)
    name = fields.CharField(max_length=100, null=True)
    platform = fields.CharField(max_length=100)
    platform_id = fields.CharField(max_length=100,null=True)
    profile = fields.ForeignKeyField("my_app.R6User", related_name="connections")
    request_id = fields.UUIDField(max_length=100, null=True)
    """The request ID of the player's stats. In other words, the unique UUID of the player if third party=False"""

    pfp_url = fields.CharField(max_length=255, null=True)
    pfp_url_last_updated = fields.DatetimeField(null=True)
    is_third_party = fields.BooleanField(default=False)
    """Whether the linked account is anything besides PSN, XBOX, or UPLAY."""

    manual = fields.BooleanField(default=False)
    """Whether the account was linked manually or automatically."""

    linked_by = fields.BigIntField(null=True)
    """The Discord ID of the user who linked the account."""

    @classmethod
    async def create_from_r6tracker_resp(cls, resp: dict):
        if len(resp) == 1 and isinstance(resp, list):
            resp = resp[0]
        elif len(resp) == 1 and isinstance(resp, dict):
            resp = resp.get(list(resp.keys())[0])
        
        connection = resp.get('platformInfo')
        userinfo = resp.get('userInfo')
        metadata = resp.get('metadata')

        # if connection.get("userId", None) is None:
        #     continue
        if connection.get('platformUserId',None):
            profile = await R6User.filter(userid=metadata.get("uplayUserId"),).first()
            if not profile:
                profile = await R6User.create(
                    userid=metadata.get("uplayUserId"),
                    name=connection.get("platformUserIdentifier")
                    if connection.get("platformSlug") in ["uplay","ubi"]
                    else None,
                )
            elif profile.name is None and connection.get("platformSlug") in ["uplay", "ubi"]:
                profile.name = connection.get("platformUserIdentifier")
                await profile.save()

            if not await cls.filter(
                userid=metadata.get("uplayUserId"),
                platform=connection.get("platformSlug"),
            ).exists():
                await cls.create(
                    userid=metadata.get("uplayUserId"),
                    name=connection.get("platformUserHandle"),
                    platform=connection.get("platformSlug"),
                    platform_id=connection.get("platformUserIdentifier"),
                    request_id=connection.get("platformUserId"),
                    # profileid=connection.get('profileId'),
                    # profile=await R6User.get_or_create(userid=connection.get('profileId'),name=connection.get('profileId')),
                    profile=profile,
                    is_third_party=(
                        connection.get("platformSlug")
                        not in ("psn", "xbl", "uplay",'ubi')
                    ),
                    pfp_url=connection.get("avatarUrl"),
                    pfp_url_last_updated=datetime.datetime.now(),
                )
        
            return await cls.update_or_create(
                userid=metadata.get("uplayUserId"),
                platform='trackergg',
                defaults={
                    'profile': profile,
                    'platform_id': userinfo.get('userId',None),
                    'name': userinfo.get('username',None),
                    'pfp_url': userinfo.get('customAvatarUrl',None),
                    'pfp_url_last_updated': datetime.datetime.now(),
                }
            )

    @staticmethod
    async def create_from_api_resp(resp: dict):
        if len(resp) == 1 and isinstance(resp, list):
            resp = resp[0]
        elif len(resp) == 1 and isinstance(resp, dict):
            resp = resp.get(list(resp.keys())[0])

        for connection in resp:
            if connection.get("userId", None) is None:
                continue
            try:
                # profile, _ = await R6User.update_or_create(
                #     userid=connection.get("userId"),
                #     defaults={'name': connection.get("nameOnPlatform") if connection.get("platformType") in ["uplay", "ubi"] else None},
                # )
                profile = await R6User.filter(userid=connection.get("userId")).first()
                if not profile:
                    profile = await R6User.create(
                        userid=connection.get("userId"),
                        name=connection.get("nameOnPlatform")
                        if connection.get("platformType") in ["uplay", "ubi"]
                        else None,
                    )
                elif profile.name is None and connection.get("platformType") in ["uplay", "ubi"]:
                    profile.name = connection.get("nameOnPlatform")
                    await profile.save()

                if not await R6UserConnections.filter(
                    userid=connection.get("userId"),
                    platform=connection.get("platformType"),
                ).exists():
                    await R6UserConnections.create(
                        userid=connection.get("userId"),
                        name=connection.get("nameOnPlatform"),
                        platform=connection.get("platformType"),
                        platform_id=connection.get("idOnPlatform"),
                        # profileid=connection.get('profileId'),
                        # profile=await R6User.get_or_create(userid=connection.get('profileId'),name=connection.get('profileId')),
                        #request_id=connection.get("userId"),
                        profile=profile,
                        is_third_party=(
                            connection.get("platformType")
                            not in ("psn", "xbl", "uplay", "ubi")
                        ),
                    )
            except:
                pass

    @classmethod
    async def from_leaderboard(cls, data: dict):
        # {
        #         "id": "evilgrandpaa",
        #         "owner": {
        #             "id": "evilgrandpaa",
        #             "type": "player",
        #             "metadata": {
        #                 "platformId": 2,
        #                 "platformSlug": "psn",
        #                 "platformUserHandle": "EvilGrandpaa",
        #                 "platformUserIdentifier": "EvilGrandpaa",
        #                 "countryCode": "US",
        #                 "pictureUrl": "https://avatars.trackercdn.com/api/avatar/2/EvilGrandpaa.png",
        #                 "avatarUrl": "https://avatars.trackercdn.com/api/avatar/2/EvilGrandpaa.png",
        #                 "customAvatarFrameInfo": null,
        #                 "isPremium": false,
        #                 "twitch": "evilgrandpaaa",
        #                 "twitter": null,
        #                 "isLive": "twitch",
        #                 "additionalIcon": null
        #             },
        #             "stats": [
        #                 {
        #                     "metadata": {
        #                         "key": "MatchesPlayed",
        #                         "name": "Matches Played",
        #                         "description": null,
        #                         "categoryKey": null,
        #                         "categoryName": null,
        #                         "isReversed": false,
        #                         "iconUrl": null,
        #                         "color": null,
        #                         "value": null,
        #                         "displayValue": null
        #                     },
        #                     "percentile": null,
        #                     "rank": null,
        #                     "displayPercentile": null,
        #                     "displayRank": null,
        #                     "description": null,
        #                     "value": 266,
        #                     "displayValue": "266"
        #                 }
        #             ]
        #         },
        #         "value": 240,
        #         "displayValue": "240",
        #         "rank": 1,
        #         "percentile": null,
        #         "iconUrl": null
        #     },

        user = await cls.filter(userid=data.get("owner").get("metadata").get("platformUserHandle")).first()

        if not user:
            return None
        
        user.name = data.get("owner").get("metadata").get("platformUserHandle")
        user.pfp_url = data.get("owner").get("metadata").get("avatarUrl")
        user.pfp_url_last_updated = datetime.datetime.now()
        await user.save()
        return user

    @classmethod
    async def create_from_api_obj(cls, obj: LinkedAccount):
        if not await cls.filter(
            userid=obj.user_id, platform=obj.platform_type
        ).exists():
            #profile, _= await R6User.get_or_create(userid=obj.user_id, defaults={'name': obj.name_on_platform if obj.platform_type in ["uplay", "ubi"] else None})
            profile = await cls.filter(userid=obj.user_id).first()
            r6user = await R6User.filter(userid=obj.user_id).first()
            if not r6user:
                r6user = await R6User.create(userid=obj.user_id, name=obj.name_on_platform if obj.platform_type in ["uplay", "ubi"] else None)
            #if not profile:
                #profile = await cls.create(userid=obj.user_id, profile=r6user, platform=obj.platform_type, name=obj.name_on_platform, request_id=obj.id_on_platform, platform_id=obj.id_on_platform, is_third_party=(obj.platform_type not in ["psn", "xbl", "uplay", "ubi"]))
            if profile:
                if profile.name is None and obj.platform_type in ["uplay", "ubi"]:
                    profile.name = obj.name_on_platform
                await profile.save()
            
            await cls.create(
                userid=obj.user_id,
                name=obj.name_on_platform,
                platform=obj.platform_type,
                platform_id=obj.id_on_platform,
                #profileid=obj.profile_id,
                profile=r6user,
                is_third_party=(obj.platform_type not in ("psn", "xbl", "uplay", "ubi")),
            )

    class Meta:
        table = "R6UserConnections"


class Playtime(Base):
    userid = fields.CharField(max_length=100, unique=True)
    clearance_level = fields.BigIntField(null=True)
    pve_time_played = fields.BigIntField(null=True)
    pvp_time_played = fields.BigIntField(null=True)
    total_time_played = fields.BigIntField(null=True)
    start_date = fields.DatetimeField(null=True)
    last_modified = fields.DatetimeField(null=True)

    class Meta:
        table = "Playtime"


class ArchivedPlaytime(Playtime):
    userid = fields.CharField(max_length=100)

    class Meta:
        table = "ArchivedPlaytime"


class RankedStats(Base):
    #user_id = fields.CharField(max_length=100)
    user = fields.ForeignKeyField("my_app.R6User", related_name="stats")
    platform = fields.CharField(max_length=100)

    request_id = fields.UUIDField(max_length=100, null=True)

    casual_kills = fields.BigIntField(null=True)
    casual_deaths = fields.BigIntField(null=True)
    casual_wins = fields.BigIntField(null=True)
    casual_losses = fields.BigIntField(null=True)
    casual_abandons = fields.BigIntField(null=True)
    casual_max_rank = fields.CharField(max_length=50, null=True)
    casual_max_rank_points = fields.BigIntField(null=True)
    casual_rank = fields.CharField(max_length=50, null=True)
    casual_rank_points = fields.BigIntField(null=True)
    event_kills = fields.BigIntField(null=True)
    event_deaths = fields.BigIntField(null=True)
    event_wins = fields.BigIntField(null=True)
    event_losses = fields.BigIntField(null=True)
    event_abandons = fields.BigIntField(null=True)
    event_max_rank = fields.CharField(max_length=50, null=True)
    event_max_rank_points = fields.BigIntField(null=True)
    event_rank = fields.CharField(max_length=50, null=True)
    event_rank_points = fields.BigIntField(null=True)
    warmup_kills = fields.BigIntField(null=True)
    warmup_deaths = fields.BigIntField(null=True)
    warmup_wins = fields.BigIntField(null=True)
    warmup_losses = fields.BigIntField(null=True)
    warmup_abandons = fields.BigIntField(null=True)
    warmup_max_rank = fields.CharField(max_length=50, null=True)
    warmup_max_rank_points = fields.BigIntField(null=True)
    warmup_rank = fields.CharField(max_length=50, null=True)
    warmup_rank_points = fields.BigIntField(null=True)
    standard_kills = fields.BigIntField(null=True)
    standard_deaths = fields.BigIntField(null=True)
    standard_wins = fields.BigIntField(null=True)
    standard_losses = fields.BigIntField(null=True)
    standard_abandons = fields.BigIntField(null=True)
    standard_max_rank = fields.CharField(max_length=50, null=True)
    standard_max_rank_points = fields.BigIntField(null=True)
    standard_rank = fields.CharField(max_length=50, null=True)
    standard_rank_points = fields.BigIntField(null=True)
    ranked_kills = fields.BigIntField(null=True)
    ranked_deaths = fields.BigIntField(null=True)
    ranked_wins = fields.BigIntField(null=True)
    ranked_losses = fields.BigIntField(null=True)
    ranked_abandons = fields.BigIntField(null=True)
    ranked_max_rank = fields.CharField(max_length=50, null=True)
    ranked_max_rank_points = fields.BigIntField(null=True)
    ranked_rank = fields.CharField(max_length=50, null=True)
    ranked_rank_points = fields.BigIntField(null=True)

    season_number = fields.CharField(max_length=6,default=CURRENT_SEASON)

    @staticmethod
    async def create_from_dict(data: dict):
        await __class__.create(
            casual_kills=data.get("casual", {}).get("kills", None),
            casual_deaths=data.get("casual", {}).get("deaths", None),
            casual_wins=data.get("casual", {})
            .get("match_outcomes", {})
            .get("wins", None),
            casual_losses=data.get("casual", {})
            .get("match_outcomes", {})
            .get("losses", None),
            casual_abandons=data.get("casual", {})
            .get("match_outcomes", {})
            .get("abandons", None),
            casual_max_rank=data.get("casual", {}).get("max_rank", None),
            casual_max_rank_points=data.get("casual", {}).get("max_rank_points", None),
            casual_rank=data.get("casual", {}).get("rank", None),
            casual_rank_points=data.get("casual", {}).get("rank_points", None),
            event_kills=data.get("event", {}).get("kills", None),
            event_deaths=data.get("event", {}).get("deaths", None),
            event_wins=data.get("event", {})
            .get("match_outcomes", {})
            .get("wins", None),
            event_losses=data.get("event", {})
            .get("match_outcomes", {})
            .get("losses", None),
            event_abandons=data.get("event", {})
            .get("match_outcomes", {})
            .get("abandons", None),
            event_max_rank=data.get("event", {}).get("max_rank", None),
            event_max_rank_points=data.get("event", {}).get("max_rank_points", None),
            event_rank=data.get("event", {}).get("rank", None),
            event_rank_points=data.get("event", {}).get("rank_points", None),
            warmup_kills=data.get("warmup", {}).get("kills", None),
            warmup_deaths=data.get("warmup", {}).get("deaths", None),
            warmup_wins=data.get("warmup", {})
            .get("match_outcomes", {})
            .get("wins", None),
            warmup_losses=data.get("warmup", {})
            .get("match_outcomes", {})
            .get("losses", None),
            warmup_abandons=data.get("warmup", {})
            .get("match_outcomes", {})
            .get("abandons", None),
            warmup_max_rank=data.get("warmup", {}).get("max_rank", None),
            warmup_max_rank_points=data.get("warmup", {}).get("max_rank_points", None),
            warmup_rank=data.get("warmup", {}).get("rank", None),
            warmup_rank_points=data.get("warmup", {}).get("rank_points", None),
            standard_kills=data.get("standard", {}).get("kills", None),
            standard_deaths=data.get("standard", {}).get("deaths", None),
            standard_wins=data.get("standard", {})
            .get("match_outcomes", {})
            .get("wins", None),
            standard_losses=data.get("standard", {})
            .get("match_outcomes", {})
            .get("losses", None),
            standard_abandons=data.get("standard", {})
            .get("match_outcomes", {})
            .get("abandons", None),
            standard_max_rank=data.get("standard", {}).get("max_rank", None),
            standard_max_rank_points=data.get("standard", {}).get(
                "max_rank_points", None
            ),
            standard_rank=data.get("standard", {}).get("rank", None),
            standard_rank_points=data.get("standard", {}).get("rank_points", None),
            ranked_kills=data.get("ranked", {}).get("kills", None),
            ranked_deaths=data.get("ranked", {}).get("deaths", None),
            ranked_wins=data.get("ranked", {})
            .get("match_outcomes", {})
            .get("wins", None),
            ranked_losses=data.get("ranked", {})
            .get("match_outcomes", {})
            .get("losses", None),
            ranked_abandons=data.get("ranked", {})
            .get("match_outcomes", {})
            .get("abandons", None),
            ranked_max_rank=data.get("ranked", {}).get("max_rank", None),
            ranked_max_rank_points=data.get("ranked", {}).get("max_rank_points", None),
            ranked_rank=data.get("ranked", {}).get("rank", None),
            ranked_rank_points=data.get("ranked", {}).get("rank_points", None),
            user_id=data.get("platform_families_full_profiles", {}).get("userid", None),
        )

    @classmethod
    async def from_player(cls, player: Player):
        unranked, ranked, casual, warmup, events = await player.load_ranked_v2()
        #user, _ = await R6User.get_or_create(userid=player.uid, defaults={'name': player.name if player._platform in ["uplay", "ubi"] else None})
        user = await R6User.filter(userid=player.uid).first()
        if not user:
            user = await R6User.create(userid=player.uid, name=player.name if player._platform in ["uplay", "ubi"] else None)
        elif user.name is None and player._platform in ["uplay", "ubi"]:
            user.name = player.name
            await user.save()
        kwargs: Dict[str, Union[str, int, float, R6User]] = {
            #"user_id": str(player.uid),
            'user': user,
            "platform": str(player._platform),
            'request_id': player.id,
        }

        if casual:
            kwargs.update(
                {
                    "casual_kills": casual.kills,
                    "casual_deaths": casual.deaths,
                    "casual_wins": casual.wins,
                    "casual_losses": casual.losses,
                    "casual_abandons": casual.abandons,
                    "casual_max_rank": casual.max_rank,
                    "casual_max_rank_points": casual.max_rank_points,
                    "casual_rank": casual.rank,
                    "casual_rank_points": casual.rank_points,
                }
            )

        if events:
            kwargs.update(
                {
                    "event_kills": events.kills,
                    "event_deaths": events.deaths,
                    "event_wins": events.wins,
                    "event_losses": events.losses,
                    "event_abandons": events.abandons,
                    "event_max_rank": events.max_rank,
                    "event_max_rank_points": events.max_rank_points,
                    "event_rank": events.rank,
                    "event_rank_points": events.rank_points,
                }
            )

        if warmup:
            kwargs.update(
                {
                    "warmup_kills": warmup.kills,
                    "warmup_deaths": warmup.deaths,
                    "warmup_wins": warmup.wins,
                    "warmup_losses": warmup.losses,
                    "warmup_abandons": warmup.abandons,
                    "warmup_max_rank": warmup.max_rank,
                    "warmup_max_rank_points": warmup.max_rank_points,
                    "warmup_rank": warmup.rank,
                    "warmup_rank_points": warmup.rank_points,
                }
            )

        if unranked:
            kwargs.update(
                {
                    "standard_kills": unranked.kills,
                    "standard_deaths": unranked.deaths,
                    "standard_wins": unranked.wins,
                    "standard_losses": unranked.losses,
                    "standard_abandons": unranked.abandons,
                    "standard_max_rank": unranked.max_rank,
                    "standard_max_rank_points": unranked.max_rank_points,
                    "standard_rank": unranked.rank,
                    "standard_rank_points": unranked.rank_points,
                }
            )

        if ranked:
            kwargs.update(
                {
                    "ranked_kills": ranked.kills,
                    "ranked_deaths": ranked.deaths,
                    "ranked_wins": ranked.wins,
                    "ranked_losses": ranked.losses,
                    "ranked_abandons": ranked.abandons,
                    "ranked_max_rank": ranked.max_rank,
                    "ranked_max_rank_points": ranked.max_rank_points,
                    "ranked_rank": ranked.rank,
                    "ranked_rank_points": ranked.rank_points,
                }
            )
        
        if await cls.filter(user=user, platform=kwargs.get("platform")).exists():
            stats = await cls.get(user=user, platform=kwargs.get("platform"))
            await stats.update_from_dict(kwargs)
            await stats.save() 
        else:
            stats = await cls.create(**kwargs)
        
        return stats
    class Meta:
        table = "RankedStats"
        unique_together = ("user_id", "platform")

class GamemodeType(Enum):
    RANKED = 'ranked'
    CASUAL = 'casual'
    EVENT = 'event'
    STANDARD = 'standard'
    QUICKPLAY = CASUAL

    @classmethod
    def from_str(cls, s: str):
        s = s.lower().strip()
        for instance in cls:
            if instance.value.lower().strip() == s:
                return instance
        raise ValueError(f"Bad str passed to from_str (doesn't match any enum objects for class {cls.__name__})")
    
class RankedStatsSeasonal(Base):
    """Season specific stats for a user.
    A seperate instance of this object should exist for each gamemode"""

    platform_connection = fields.ForeignKeyField('my_app.R6UserConnections')
    ranked_stats = fields.ForeignKeyField('my_app.RankedStatsV2',null=True)

    expiry_date = fields.DatetimeField(null=True)

    season = fields.IntField()
    season_name = fields.CharField(max_length=50)
    season_short = fields.CharField(max_length=5)
    season_color = fields.CharField(max_length=20)

    gamemode = fields.CharField(max_length=50)
    gamemode_name = fields.CharField(max_length=50)

    # each of these fields have a %ile attached with them, not sure if ill save that
    kills = fields.BigIntField(null=True)
    deaths = fields.BigIntField(null=True)
    kdratio = fields.FloatField(null=True)
    killspergame = fields.FloatField(null=True)
    matchesplayed = fields.BigIntField(null=True)
    matcheswon = fields.BigIntField(null=True)
    matcheslost = fields.BigIntField(null=True)
    matchesabandoned = fields.BigIntField(null=True)
    winpercentage = fields.FloatField(null=True)
    rankpoints = fields.BigIntField(null=True)
    maxrankpoints = fields.BigIntField(null=True)

    _raw = fields.JSONField(null=True)
    """Raw metadata of the user."""
    
    @classmethod
    async def from_api(cls, platform_connection: R6UserConnections, data: dict, ranked_stats: Optional[RankedStatsV2]=None) -> Self:
        """Generate a seasnoal object based off an API response.

        Args:
            platform_connection (R6UserConnections): The platform connection of the user.
            data (dict): API data.
            ranked_stats (Optional[RankedStatsV2], optional): User's ranked stats. Defaults to None.

        Returns:
            Self: The created object.
        """
        data['expiryDate'] = dateparser.parse(data['expiryDate'])

        instance, _ = await cls.update_or_create(
            platform_connection=platform_connection,
            ranked_stats=ranked_stats,
            season=data['attributes']['season'],
            gamemode=data['attributes']['gamemode'],
            defaults={
                'season_name': data['metadata']['seasonName'],
                'season_short': data['metadata']['shortName'],
                'season_color': data['metadata']['color'],
                'expirydate': data['expiryDate'],
                'gamemode_name': data['metadata']['gamemodeName'],
                'kills': data.get('stats',{}).get('kills',{'value': None})['value'],
                'deaths': data.get('stats',{}).get('deaths',{'value': None})['value'],
                'kdratio': data.get('stats',{}).get('kdRatio',{'value': None})['value'],
                'killspergame': data.get('stats',{}).get('killsPerGame',{'value': None})['value'],
                'matchesplayed': data.get('stats',{}).get('matchesPlayed',{'value': None})['value'],
                'matcheswon': data.get('stats',{}).get('matchesWon',{'value': None})['value'],
                'matcheslost': data.get('stats',{}).get('matchesLost',{'value': None})['value'],
                'matchesabandoned': data.get('stats',{}).get('matchesAbandoned',{'value': None})['value'],
                'winpercentage': data.get('stats',{}).get('winPercentage',{'value': None})['value'],
                'rankpoints': data.get('stats',{}).get('mmr',{}).get('value',None) or data.get('stats',{}).get('rankPoints',{}).get('value',None),
                'maxrankpoints': data.get('stats',{}).get('maxRankPoints',{}).get('value',None),
                '_raw': data,
            }
        )

        return instance
    
    class Meta:
        table = "RankedStatsSeasonal"

class RankedStatsV2(Base):
    """This class is a new one to start new stats tracking for the new ranking provider (TrackerNetwork)."""

    user_connection = fields.ForeignKeyField('my_app.R6UserConnections', related_name='ranked_statsv2')
    """The platform connection for these ranking stats."""

    user = fields.ForeignKeyField('my_app.R6User', null=True)

    trackergg_connection = fields.ForeignKeyField('my_app.R6UserConnections',null=True, related_name='trackergg_connections')
    """The associated trackergg account for this user. The connection should be for trackergg."""
    # we could have seperate tables for each category but

    api_last_updated = fields.DatetimeField(null=True)

    expiry_date = fields.DatetimeField(null=True)

    battlepass_level = fields.BigIntField(null=True)

    clearance_level = fields.BigIntField(null=True)
    """This is the user's level in the game."""

    is_overwolf_app_user = fields.BooleanField(default=False)

    overview_matchesplayed = fields.BigIntField(null=True)
    overview_matcheswon = fields.BigIntField(null=True)
    overview_matcheslost = fields.BigIntField(null=True)
    overview_matchesabandoned = fields.BigIntField(null=True)
    overview_timeplayed = fields.BigIntField(null=True)
    overview_kills = fields.BigIntField(null=True)
    overview_deaths = fields.BigIntField(null=True)
    overview_attacker_roundswon = fields.BigIntField(null=True)
    overview_attacker_teamkillsinobj = fields.BigIntField(null=True)
    overview_attacker_enemykillsinobj = fields.BigIntField(null=True)
    overview_attacker_teamkillsoutobj = fields.BigIntField(null=True)
    overview_defender_roundswon = fields.BigIntField(null=True)
    overview_defender_teamkillsinobj = fields.BigIntField(null=True)
    overview_defender_enemykillsinobj = fields.BigIntField(null=True)
    overview_defender_teamkillsoutobj = fields.BigIntField(null=True)
    overview_defender_enemykillsoutobj = fields.BigIntField(null=True)
    overview_headshots = fields.BigIntField(null=True)
    overview_headshotsmissed = fields.BigIntField(null=True)
    overview_headshotpercentage = fields.FloatField(null=True)
    overview_wallbangs = fields.BigIntField(null=True)
    overview_damagedealt = fields.BigIntField(null=True)
    overview_assists = fields.BigIntField(null=True)
    overview_teamkills = fields.BigIntField(null=True)
    overview_playstyle_attacker_breacher = fields.BigIntField(null=True)
    overview_playstyle_attacker_entryfragger = fields.BigIntField(null=True)
    overview_playstyle_attacker_intelprovider = fields.BigIntField(null=True)
    overview_playstyle_attacker_roamclearer = fields.BigIntField(null=True)
    overview_playstyle_attacker_supporter = fields.BigIntField(null=True)
    overview_playstyle_attacker_utilityclearer = fields.BigIntField(null=True)
    overview_playstyle_defender_debuffer = fields.BigIntField(null=True)
    overview_playstyle_defender_entrydenier = fields.BigIntField(null=True)
    overview_playstyle_defender_intelprovider = fields.BigIntField(null=True)
    overview_playstyle_defender_supporter = fields.BigIntField(null=True)
    overview_playstyle_defender_trapper = fields.BigIntField(null=True)
    overview_playstyle_defender_utilitydenier = fields.BigIntField(null=True)
    overview_kdratio = fields.FloatField(null=True)
    overview_killspermatch = fields.FloatField(null=True)
    overview_killspermin = fields.FloatField(null=True)
    overview_winpercentage = fields.FloatField(null=True)
    overview_timealive = fields.BigIntField(null=True)
    """Mesured in seconds."""

    ranked_matchesplayed = fields.BigIntField(null=True)
    ranked_matcheswon = fields.BigIntField(null=True)
    ranked_matcheslost = fields.BigIntField(null=True)
    ranked_matchesabandoned = fields.BigIntField(null=True)
    ranked_timeplayed = fields.BigIntField(null=True)
    ranked_kills = fields.BigIntField(null=True)
    ranked_deaths = fields.BigIntField(null=True)
    ranked_kdratio = fields.FloatField(null=True)
    ranked_killspermatch = fields.FloatField(null=True)
    ranked_winpercentage = fields.FloatField(null=True)
    
    event_matchesplayed = fields.BigIntField(null=True)
    event_matcheswon = fields.BigIntField(null=True)
    event_matcheslost = fields.BigIntField(null=True)
    event_abandoned = fields.BigIntField(null=True)
    event_timeplayed = fields.BigIntField(null=True)
    event_kills = fields.BigIntField(null=True)
    event_deaths = fields.BigIntField(null=True)
    event_kdratio = fields.FloatField(null=True)
    event_killspermatch = fields.FloatField(null=True)
    event_winpercentage = fields.FloatField(null=True)

    quickplay_matchesplayed = fields.BigIntField(null=True)
    quickplay_matcheswon = fields.BigIntField(null=True)
    quickplay_matcheslost = fields.BigIntField(null=True)
    quickplay_abandoned = fields.BigIntField(null=True)
    quickplay_timeplayed = fields.BigIntField(null=True)
    quickplay_kills = fields.BigIntField(null=True)
    quickplay_deaths = fields.BigIntField(null=True)
    quickplay_kdratio = fields.FloatField(null=True)
    quickplay_killspermatch = fields.FloatField(null=True)
    quickplay_winpercentage = fields.FloatField(null=True)



    _raw = fields.JSONField(null=True)
    """Raw metadata of the user."""

    @classmethod
    async def from_api(cls,  data: dict, platform_connection: Optional[R6UserConnections]=None,trackergg_connection: Optional[R6UserConnections]=None) -> Self:

        if not trackergg_connection:
            if data['userInfo']['userId'] is not None and not trackergg_connection:
                trackergg_connection = await R6UserConnections.filter(platform='trackergg',platform_id=data['userInfo']['userId']).first()
        user, _ = await R6User.get_or_create(userid=data['metadata']['uplayUserId'])


        if not platform_connection:
            platform_connection, _ = await R6UserConnections.get_or_create(
                request_id=data['platformInfo']['platformUserId'],
                defaults={
                    'platform': data['platformInfo']['platformSlug'],
                    'platform_id': data['platformInfo']['platformUserId'],
                    'userid': data['metadata']['uplayUserId'],
                    'name': data['platformInfo']['platformUserHandle'],
                    'profile': user,
                    'pfp_url': data['platformInfo']['avatarUrl'],
                    'pfp_url_last_updated': datetime.datetime.now() if data['platformInfo']['avatarUrl'] else None,
                    'is_third_party': data['platformInfo']['platformSlug'] not in ['psn','xbl','uplay','ubi'],
                    'manual': False,
                    'linked_by': None,
                }
            )
        #overview = data['overview']['segments'][0]
        overview = discord.utils.find(lambda x: x['type'] == 'overview', data['segments']) or {}

        #ranked = data['ranked']['segments'][1]
        ranked = discord.utils.find(lambda x: x['type'] == 'gamemode' and x['attributes']['gamemode'] == 'pvp_ranked', data['segments']) or {}
        #event = data['event']['segments'][2]
        event = discord.utils.find(lambda x: x['type'] == 'gamemode' and x['attributes']['gamemode'] == 'pvp_event', data['segments']) or {}
        #quickplay = data['quickplay']['segments'][3]
        quickplay = discord.utils.find(lambda x: x['type'] == 'gamemode' and x['attributes']['gamemode'] == 'pvp_quickplay', data['segments']) or {}

        expiry_date = dateparser.parse(overview['expiryDate'])

        metadata = data['metadata']
        
        instance, _ = await cls.update_or_create(
            user_connection=platform_connection,
            defaults={
                    'user': user,
                    'trackergg_connection': trackergg_connection,

                    'expiry_date': expiry_date,

                    'api_last_updated': dateparser.parse(metadata.get('lastUpdated','') or '') or None,

                    'clearance_level': metadata.get('clearanceLevel',None),

                    'battlepass_level': metadata.get('battlepassLevel',None),

                    'is_overwolf_app_user': metadata.get('isOverwolfAppUser',False),

                    'overview_matchesplayed': overview.get('stats',{}).get('matchesPlayed',{'value': None})['value'],
                    'overview_matcheswon': overview.get('stats',{}).get('matchesWon',{'value': None})['value'],
                    'overview_matcheslost': overview.get('stats',{}).get('matchesLost',{'value': None})['value'],
                    'overview_matchesabandoned': overview.get('stats',{}).get('matchesAbandoned',{'value': None})['value'],
                    'overview_timeplayed': overview.get('stats',{}).get('timePlayed',{'value': None})['value'],
                    'overview_kills': overview.get('stats',{}).get('kills',{'value': None})['value'],
                    'overview_deaths': overview.get('stats',{}).get('deaths',{'value': None})['value'],
                    'overview_attacker_roundswon': overview.get('stats',{}).get('attackerRoundsWon',{'value': None})['value'],
                    'overview_attacker_teamkillsinobj': overview.get('stats',{}).get('attackerTeamKillsInObj',{'value': None})['value'],
                    'overview_attacker_enemykillsinobj': overview.get('stats',{}).get('attackerEnemyKillsInObj',{'value': None})['value'],
                    'overview_attacker_teamkillsoutobj': overview.get('stats',{}).get('attackerTeamKillsOutObj',{'value': None})['value'],
                    'overview_defender_roundswon': overview.get('stats',{}).get('defenderRoundsWon',{'value': None})['value'],
                    'overview_defender_teamkillsinobj': overview.get('stats',{}).get('defenderTeamKillsInObj',{'value': None})['value'],
                    'overview_defender_enemykillsinobj': overview.get('stats',{}).get('defenderEnemyKillsInObj',{'value': None})['value'],
                    'overview_defender_teamkillsoutobj': overview.get('stats',{}).get('defenderTeamKillsOutObj',{'value': None})['value'],
                    'overview_defender_enemykillsoutobj': overview.get('stats',{}).get('defenderEnemyKillsOutObj',{'value': None})['value'],
                    'overview_headshots': overview.get('stats',{}).get('headshots',{'value': None})['value'],
                    'overview_headshotsmissed': overview.get('stats',{}).get('headshotsMissed',{'value': None})['value'],
                    'overview_headshotpercentage': overview.get('stats',{}).get('headshotPercentage',{'value': None})['value'],
                    'overview_wallbangs': overview.get('stats',{}).get('wallbangs',{'value': None})['value'],
                    'overview_damagedealt': overview.get('stats',{}).get('damageDealt',{'value': None})['value'],
                    'overview_assists': overview.get('stats',{}).get('assists',{'value': None})['value'],
                    'overview_teamkills': overview.get('stats',{}).get('teamKills',{'value': None})['value'],
                    'overview_playstyle_attacker_breacher': overview.get('stats',{}).get('playstyleAttackerBreacher',{'value': None})['value'],
                    'overview_playstyle_attacker_entryfragger': overview.get('stats',{}).get('playstyleAttackerEntryFragger',{'value': None})['value'],
                    'overview_playstyle_attacker_intelprovider': overview.get('stats',{}).get('playstyleAttackerIntelProvider',{'value': None})['value'],
                    'overview_playstyle_attacker_roamclearer': overview.get('stats',{}).get('playstyleAttackerRoamClearer',{'value': None})['value'],
                    'overview_playstyle_attacker_supporter': overview.get('stats',{}).get('playstyleAttackerSupporter',{'value': None})['value'],
                    'overview_playstyle_attacker_utilityclearer': overview.get('stats',{}).get('playstyleAttackerUtilityClearer',{'value': None})['value'],
                    'overview_playstyle_defender_debuffer': overview.get('stats',{}).get('playstyleDefenderDebuffer',{'value': None})['value'],
                    'overview_playstyle_defender_entrydenier': overview.get('stats',{}).get('playstyleDefenderEntryDenier',{'value': None})['value'],
                    'overview_playstyle_defender_intelprovider': overview.get('stats',{}).get('playstyleDefenderIntelProvider',{'value': None})['value'],
                    'overview_playstyle_defender_supporter': overview.get('stats',{}).get('playstyleDefenderSupporter',{'value': None})['value'],
                    'overview_playstyle_defender_trapper': overview.get('stats',{}).get('playstyleDefenderTrapper',{'value': None})['value'],
                    'overview_playstyle_defender_utilitydenier': overview.get('stats',{}).get('playstyleDefenderUtilityDenier',{'value': None})['value'],
                    'overview_kdratio': overview.get('stats',{}).get('kdRatio',{'value': None})['value'],
                    'overview_killspermatch': overview.get('stats',{}).get('killsPerMatch',{'value': None})['value'],
                    'overview_killspermin': overview.get('stats',{}).get('killsPerMin',{'value': None})['value'],
                    'overview_winpercentage': overview.get('stats',{}).get('winPercentage',{'value': None})['value'],
                    'overview_timealive': overview.get('stats',{}).get('timeAlive',{'value': None})['value'],

                    'ranked_matchesplayed': ranked.get('stats',{}).get('matchesPlayed',{}).get('value',None),
                    'ranked_matcheswon': ranked.get('stats',{}).get('matchesWon',{'value': None})['value'],
                    'ranked_matcheslost': ranked.get('stats',{}).get('matchesLost',{'value': None})['value'],
                    'ranked_matchesabandoned': ranked.get('stats',{}).get('matchesAbandoned',{'value': None})['value'],
                    'ranked_timeplayed': ranked.get('stats',{}).get('timePlayed',{'value': None})['value'],
                    'ranked_kills': ranked.get('stats',{}).get('kills',{'value': None})['value'],
                    'ranked_deaths': ranked.get('stats',{}).get('deaths',{'value': None})['value'],
                    'ranked_kdratio': ranked.get('stats',{}).get('kdRatio',{'value': None})['value'],
                    'ranked_killspermatch': ranked.get('stats',{}).get('killsPerMatch',{'value': None})['value'],
                    'ranked_winpercentage': ranked.get('stats',{}).get('winPercentage',{'value': None})['value'],

                    'event_matchesplayed': event.get('stats',{}).get('matchesPlayed',{'value': None})['value'],
                    'event_matcheswon': event.get('stats',{}).get('matchesWon',{'value': None})['value'],
                    'event_matcheslost': event.get('stats',{}).get('matchesLost',{'value': None})['value'],
                    'event_abandoned': event.get('stats',{}).get('matchesAbandoned',{'value': None})['value'],
                    'event_timeplayed': event.get('stats',{}).get('timePlayed',{'value': None})['value'],
                    'event_kills': event.get('stats',{}).get('kills',{'value': None})['value'],
                    'event_deaths': event.get('stats',{}).get('deaths',{'value': None})['value'],
                    'event_kdratio': event.get('stats',{}).get('kdRatio',{'value': None})['value'],
                    'event_killspermatch': event.get('stats',{}).get('killsPerMatch',{'value': None})['value'],
                    'event_winpercentage': event.get('stats',{}).get('winPercentage',{'value': None})['value'],

                    'quickplay_matchesplayed': quickplay.get('stats',{}).get('matchesPlayed',{'value': None})['value'],
                    'quickplay_matcheswon': quickplay.get('stats',{}).get('matchesWon',{'value': None})['value'],
                    'quickplay_matcheslost': quickplay.get('stats',{}).get('matchesLost',{'value': None})['value'],
                    'quickplay_abandoned': quickplay.get('stats',{}).get('matchesAbandoned',{'value': None})['value'],
                    'quickplay_timeplayed': quickplay.get('stats',{}).get('timePlayed',{'value': None})['value'],
                    'quickplay_kills': quickplay.get('stats',{}).get('kills',{'value': None})['value'],
                    'quickplay_deaths': quickplay.get('stats',{}).get('deaths',{'value': None})['value'],
                    'quickplay_kdratio': quickplay.get('stats',{}).get('kdRatio',{'value': None})['value'],
                    'quickplay_killspermatch': quickplay.get('stats',{}).get('killsPerMatch',{'value': None})['value'],
                    'quickplay_winpercentage': quickplay.get('stats',{}).get('winPercentage',{'value': None})['value'],

                    '_raw': data,
            }
        )

        await NameChanges.bulk_from_api(user, metadata.get('nameChanges',[]))

        for segment in data['segments']:
            if segment['type'] == 'season':
                await RankedStatsSeasonal.from_api(platform_connection=platform_connection, data=segment, ranked_stats=instance)
        return instance
    
    class Meta:
        table = "RankedStatsV2"

class PastRankedPoints(Base):
    """This model is similar to RankedStatsV2, but this only shows ranked stats current and past."""

    user_connection = fields.ForeignKeyField('my_app.R6UserConnections', related_name='past_ranked_points')
    """The platform connection for these ranking stats."""

    date = fields.DatetimeField()
    """Date given by the API for the stats."""

    rank_points = fields.BigIntField(default=1000)
    """The rank points of the user."""

    rank_name = fields.CharField(max_length=50)
    """The rank name of the user."""

    _raw = fields.JSONField(null=True)
    """Raw metadata of the user."""

    @classmethod
    async def bulk_from_api(cls, user_connection: R6UserConnections, data: List[Tuple[str, Dict[str, Optional[Any]]]]) -> List[Self]:
        instances = []
        for tup in data:
            instances.append(await cls.from_api(user_connection, tup))
        return instances

    @classmethod
    async def from_api(cls, user_connection: R6UserConnections, data: Tuple[str, Dict[str, Optional[Any]]]) -> Self:
        date = dateparser.parse(data[0])
        stats = data[1]

        instance, _ = await cls.update_or_create(
            user_connection=user_connection,
            defaults={
                'date': date,
                'rank_points': stats.get('value',-1),
                'rank_name': stats.get('metadata',{}).get('rank',-1),
                '_raw': stats,
            }
        )
        return instance
    
    class Meta:
        table_name = "PastRankedPoints"

class NameChanges(Base):
    """This model is used to store name changes of a user."""

    user = fields.ForeignKeyField('my_app.R6User', related_name='name_changes')
    """The user that changed their name."""

    name = fields.CharField(max_length=100)
    """The name the user changed to."""

    timestamp = fields.DatetimeField()
    """The date the user changed their name."""

    @classmethod
    async def bulk_from_api(cls, user: R6User, data: List[dict]) -> List[Self]:
        instances = []
        for name_change in data or []:
            instances.append(await cls.from_api(user, name_change))
        return instances

    @classmethod
    async def from_api(cls, user: R6User, data: dict) -> Self:
        name = data['name']
        timestamp = dateparser.parse(data['timestamp'])

        instance, _ = await cls.update_or_create(
            user=user,
            timestamp=timestamp,
            defaults={
                'name': name,
            }
        )
        return instance

    class Meta:
        table = "NameChanges"

class Matches(Base):
    """Represents a match in Rainbow Six Siege."""

    match_id = fields.UUIDField(unique=True)
    gamemode = fields.CharField(max_length=50)
    datacenter = fields.CharField(max_length=50, null=True)

    timestamp = fields.DatetimeField()
    gamemode_name = fields.CharField(max_length=50)
    has_overwolf_roster = fields.BooleanField(default=False)
    has_session_data = fields.BooleanField(default=False)
    is_rollback = fields.BooleanField(default=False)

    _raw = fields.JSONField(null=True)

    @classmethod
    async def bulk_from_api(cls, data: list[dict]):
        for match in data.get('data',data):
            await cls.from_api(match)
    
    @classmethod
    async def from_api(cls, data: dict):
        """Make sure to fetch all related users before calling this."""

        match, _ = await cls.update_or_create(
            match_id=data['attributes']['id'],
            defaults={
                'gamemode': data['attributes'].get('gamemode',None),
                'datacenter': data['attributes'].get('datacenter',None), 
                'timestamp': dateparser.parse(data['attributes'].get('metadata',{}).get('timestamp',None)),
                'gamemode_name': data['attributes'].get('metadata',{}).get('gamemodeName',None),
                'has_overwolf_roster': data['attributes'].get('metadata',{}).get('hasOverwolfRoster',False),
                'has_session_data': data['attributes'].get('metadata',{}).get('hasSessionData',False),
                'is_rollback': data['attributes'].get('metadata',{}).get('isRollback',False),
            }
        )

        for segment in data['metadata']['segments']:
            platform_connection = await R6UserConnections.filter(request_id=segment['metadata']['platformUserId']).first()
            if not platform_connection:
                if segment.get('metadata',{}).get('platformSlug',None):
                    platform_connection = await R6UserConnections.create(
                        platform=segment['metadata']['platformSlug'], 
                        name=segment['metadata']['platformUserHandle'], 
                        platform_id=segment['metadata']['platformUserIdentifier'],
                        request_id=segment['metadata']['platformUserId'],

                        pfp_url=segment['metadata']['avatarUrl'], pfp_url_last_updated=datetime.datetime.now())
                raise ValueError("Fetch all the Users first.")
            
            await platform_connection.fetch_related('profile')

            await MatchSegments.from_api(match, platform_connection.profile, platform_connection, segment)

        return match

    async def segments(self):
        return await MatchSegments.filter(match=self)

    class Meta:
        table = "Matches"

class MatchSegments(Base):
    """This model stores player-specific information to a match, such as K/D, performance, etc"""

    match = fields.ForeignKeyField('my_app.Matches')

    user = fields.ForeignKeyField('my_app.R6User')

    platform_connection = fields.ForeignKeyField('my_app.R6UserConnections')

    platform_family = fields.CharField(max_length=10, null=True)
    """This will either be PC or Console."""

    result = fields.CharField(max_length=10, null=True)
    """Usually WIN/Loss"""

    status = fields.CharField(max_length=20, null=True)
    """The status of the user for this match. Usually Connected, but can be Disconnected, abandoned, etc"""

    has_extra_stats = fields.BooleanField(default=False)

    # stats

    matches_played = fields.BigIntField(default=1)
    """Unsure why this exists. Should always be 1..."""

    wins = fields.BigIntField(default=0, null=True)
    """How many games were won. This basically means whether they won, but decided to make it a number..."""

    losses = fields.BigIntField(default=0, null=True)
    """How many games were lost. This basically means whether they lost, but decided to make it a number..."""
    
    abandons = fields.BigIntField(default=0, null=True)
    """Whether the match was abandoned? Unsure exactly what this is..."""

    kills = fields.BigIntField(default=0, null=True)
    """How many kills this player got."""

    deaths = fields.BigIntField(default=0, null=True)
    """How many deaths this player got."""

    rank = fields.BigIntField(null=True)
    """Unsure what this is..."""

    rank_points = fields.BigIntField(null=True)
    """The amount of rank points the player had after the match."""

    top_rank_position = fields.BigIntField(null=True)
    """Unsure what this is as well...."""

    rank_points_delta = fields.BigIntField(null=True)
    """The change in rank points after the match. Can be pos/neg."""

    rank_previous = fields.BigIntField(null=True)
    """The rank points the player had before the match. Not always present...."""

    top_rank_position_previous = fields.BigIntField(null=True)
    """The top rank position the player had before the match. Not always present...."""

    kd_ratio = fields.FloatField(null=True)
    """K/D ratio of the player."""

    win_percent = fields.FloatField(null=True)
    """Win percentage of the player."""

    kills_per_minute = fields.FloatField(null=True)
    """Kills per minute of the player."""

    damage_done = fields.BigIntField(null=True)

    match_score = fields.BigIntField(null=True)

    playtime = fields.BigIntField(null=True)
    """Mesured in seconds,"""

    extra_data = fields.JSONField(null=True)
    """Extra data that is not covered by the fields above."""

    _raw = fields.JSONField(null=True)

    @classmethod
    async def from_api(cls, match: Matches, user: R6User, platform_connection: R6UserConnections, data: dict) -> Self:
        """Create a MatchSegments object from an API response.

        Args:
            match (Matches): The match object.
            user (R6User): The user object.
            platform_connection (R6UserConnections): The platform connection object.
            data (dict): The API response.

        Returns:
            Self: The created object.
        """
        instance, _ = await cls.update_or_create(
            match=match,
            user=user,
            platform_connection=platform_connection,
            defaults={
                'platform_family': data.get('metadata', {}).get('platformFamily',None),
                'result': data.get('metadata', {}).get('result', None),
                'status': data.get('metadata', {}).get('status', None),
                'has_extra_stats': data.get('metadata', {}).get('hasExtraStats', None),
                'matches_played': data.get('stats', {}).get('matchesPlayed', {}).get('value', None),
                'wins': data.get('stats', {}).get('wins', {}).get('value', None),
                'losses': data.get('stats', {}).get('losses', {}).get('value', None),
                'abandons': data.get('stats', {}).get('abandons', {}).get('value', None),
                'kills': data.get('stats', {}).get('kills', {}).get('value', None),
                'deaths': data.get('stats', {}).get('deaths', {}).get('value', None),
                'rank': data.get('stats', {}).get('rank', {}).get('value', None),
                'rank_points': data.get('stats', {}).get('rankPoints', {}).get('value', None),
                'top_rank_position': data.get('stats', {}).get('topRankPosition', {}).get('value', None),
                'rank_points_delta': data.get('stats', {}).get('rankPointsDelta', {}).get('value', None),
                'rank_previous': data.get('stats', {}).get('rankPrevious',{}).get('value',None),
                'top_rank_position_previous': data.get('stats', {}).get('topRankPositionPrevious',{}).get('value',None),
                'kd_ratio': data.get('stats', {}).get('kdRatio', {}).get('value', None),
                'win_percent': data.get('stats', {}).get('winPercent', {}).get('value', None),
                'kills_per_minute': data.get('stats', {}).get('killsPerMinute', {}).get('value', None),
                'damage_done': data.get('stats', {}).get('damageDone',{}).get('value',None),
                'match_score': data.get('stats', {}).get('matchScore',{}).get('value',None),
                'playtime': data.get('stats', {}).get('playtime',{}).get('value',None),
                'extra_data': data.get('stats', None),
                '_raw': data,
            }
        )
        return instance
    
    class Meta:
        table = "MatchSegments"

    # healed = fields.BigIntField(null=True)

    # barricades_installed = fields.BigIntField(null=True)

    # installed_cameras = fields.BigIntField(null=True)

    # attacker_install_cameras = fields.BigIntField(null=True)

    # defender_install_cameras = fields.BigIntField(null=True)

    # deployed_reinforcements = fields.BigIntField(null=True)

    # installed_entry_denial = fields.BigIntField(null=True)

    # installed_traps = fields.BigIntField(null=True)

    # attacker_installed_traps = fields.BigIntField(null=True)

    # defender_installed_traps = fields.BigIntField(null=True)

    # tampered_observation_tools = fields.BigIntField(null=True)

    # attacker_tampered_observation_tools = fields.BigIntField(null=True)

    # defender_tampered_observation_tools = fields.BigIntField(null=True)

    # traps_destroyed = fields.BigIntField(null=True)

    # attacker_traps_destroyed = fields.BigIntField(null=True)

    # defender_traps_destroyed = fields.BigIntField(null=True)

    # reinforcements_breached = fields.BigIntField(null=True)

    # reinforcement_breached_score = fields.BigIntField(null=True)

    # revived = fields.BigIntField(null=True)

    # times_triggered = fields.BigIntField(null=True)

    # enemies_trapped = fields.BigIntField(null=True)

    # attacker_enemies_trapped = fields.BigIntField(null=True)

    # defender_enemies_trapped = fields.BigIntField(null=True)

    # gadgets_pinged = fields.BigIntField(null=True)

    # distance_travelled = fields.BigIntField(null=True)

    # attacker_distance_travelled = fields.BigIntField(null=True)

    # defender_distance_travelled = fields.BigIntField(null=True)

    # destroyed_barricades_and_hatches = fields.BigIntField(null=True)

    # drones_destroyed = fields.BigIntField(null=True)

    # attacker_drones_destroyed = fields.BigIntField(null=True)

    # defender_drones_destroyed = fields.BigIntField(null=True)

    # scan_assists = fields.BigIntField(null=True)

    # all_cameras_destroyed = fields.BigIntField(null=True)

    # attacker_cameras_destroyed = fields.BigIntField(null=True)

    # defender_cameras_destroyed = fields.BigIntField(null=True)

    # attacker_defender_tag_team = fields.BigIntField(null=True)

    # there is more but too much for me
    # fuck data entry i hate it

class PlayerEncounters(Base):
    encountering_player = fields.ForeignKeyField('my_app.R6UserConnections', related_name='encountering_player')
    """The player that has encountered this person, as in this player encountered x for y times"""

    encountered_player = fields.ForeignKeyField('my_app.R6UserConnections', related_name='encountered_player')
    """The player the encountering_player encountered."""

    count = fields.BigIntField()

    rank = fields.BigIntField()
    """The ranking of this user in terms of how many times they have been seen by the encountering player."""

    is_banned = fields.BooleanField(default=False)
    
    lastest_match = fields.DatetimeField()

    season_num = fields.IntField()

    @classmethod
    async def from_api(cls, encountering_player: R6UserConnections, data: dict):
        encountered_player = await R6UserConnections.get_or_create(
            platform=data['platformSlug'],
            request_id=data['profileId'],
            userid=data['uplayUserId'],
            defaults={
                'name': data['name'],
            }
        )

        instance, _ = await cls.get_or_create(
            encountering_player=encountering_player,
            encountered_player=encountered_player,
            defaults={
                'count': data['count'],
                'rank': data['rank'],
                'is_banned': data['isBanned'],
                'lastest_match': dateparser.parse(data['latestMatch']),
                'season_num': data['season'],
            }
        )

        return instance

    @classmethod
    async def get_encounter(cls, encountering_player: R6UserConnections, encountered_player: R6UserConnections) -> Optional[Self]:
        return await cls.filter(encountering_player=encountering_player, encountered_player=encountered_player).first()

    class Meta:
        table_name = 'PlayerEncounters'


class SettingsInfo(Base):
    name = fields.CharField(max_length=100)
    description = fields.CharField(max_length=100)

    valuetype = fields.CharField(max_length=100)
    """The type of the value. Can be 'str', 'int', 'bool', 'float', 'datetime', 'date', 'time', 'duration'."""

    emoji = fields.CharField(max_length=100, null=True)
    """The emoji to use for the setting."""

    min_value = fields.IntField(null=True)
    """The minimum value for the setting."""

    max_value = fields.IntField(null=True)
    """The maximum value for the setting."""

    active = fields.BooleanField(default=True)
    """Whether the setting is active."""

    @classmethod
    async def all_active(cls):
        return await cls.filter(active=True)

    class Meta:
        table = "SettingsInfo"

class Settings(Base):
    user_id = fields.BigIntField(unique=True)
    username = fields.CharField(max_length=100)


    preferred_platform = fields.CharField(max_length=5,default='N/A')
    show_on_leaderboard = fields.BooleanField(default=True)

    prefix = fields.CharField(max_length=5, default="!")
    use_custom_prefix = fields.BooleanField(default=False)

    show_prefix_command_tips = fields.BooleanField(default=True)

    language = fields.CharField(max_length=5, default="en")
    timezone = fields.CharField(max_length=50, default="UTC")
    color = fields.CharField(max_length=7, default="#7289DA")

    @property
    def all_settings(self) -> Dict[str, Tuple[Union[str, int, bool], Type]]:
        """All Settings for a user. 

        Returns:
            Dict[str, Tuple[Union[str, int, bool], Type]]: Returns a dictionary:
            {
                "setting_name": (setting_value, setting_type)
            }
        """        
        settings: Dict[str, Tuple[Union[str, int, bool], Type]] = {}

        for attr in self._meta.fields:
            if attr not in IGNORED_FIELDS:
                settings[attr] = getattr(self, attr), type(getattr(self, attr))
        return settings

    def get_setting_value(self, setting: str) -> str:
        """Get the name of a setting.

        Args:
            setting (str): The setting to get the name for.

        Returns:
            str: The setting name.
        """        
        return getattr(self, setting)

    def set_setting_value(self, setting: str, value: Union[str, int, bool]) -> None:
        """Set a setting for a user.

        Args:
            setting (str): The setting to set.
            value (Union[str, int, bool]): The value to set the setting to.
        """        
        return setattr(self, setting, value)

    def get_setting_type(self, setting: str) -> Type:
        """Get a setting for a user.

        Args:
            setting (str): The setting to get.

        Returns:
            Union[str, int, bool]: The setting value.
        """        
        return type(getattr(self, setting))

    async def get_setting_info_for(self, setting: str) -> Optional[SettingsInfo]:
        """Get the settings info for a setting.

        Args:
            setting (str): The setting to get the info for.

        Returns:
            Optional[SettingsInfo]: The settings info.
        """
        return await SettingsInfo.filter(name=setting).first()

    class Meta:
        table = "Settings"

class CommandInvocation(Base):
    transaction_id = fields.UUIDField(null=True)

    command_id = fields.BigIntField()

    prefix = fields.CharField(max_length=25, null=True)
    is_slash = fields.BooleanField(default=False)

    user_id = fields.BigIntField()
    guild_id = fields.BigIntField(null=True)
    channel_id = fields.BigIntField(null=True)    
    
    command = fields.CharField(max_length=100)

    args = fields.JSONField()
    kwargs = fields.JSONField()
    timestamp = fields.DatetimeField()

    completed = fields.BooleanField(null=True)
    completion_timestamp = fields.DatetimeField(null=True)

    error = fields.CharField(max_length=255, null=True)

    class Meta:
        table = "CommandInvocation"

class Votes(Base):
    user_id = fields.BigIntField()
    username = fields.CharField(max_length=100, null=True)
    avatar = fields.TextField(null=True)

    site = fields.CharField(max_length=255)
    """The site the user voted on."""

    timestamp = fields.DatetimeField()
    """The time the user voted."""

    loggedby = fields.CharField(max_length=100)
    """Who logged the vote. Webhook or Bot."""

    is_weekend = fields.BooleanField(default=False)
    """Whether the vote was on a weekend."""
    
    addl_data = fields.JSONField(null=True)
    """Additional data about the vote."""

    _raw = fields.JSONField(null=True)

    async def last_vote(self):
        return await __class__.filter(user_id=self.user_id).order_by("-timestamp").first()

    @classmethod
    async def voted_recently(cls, user_id: int, site: str, hours: int = 12):
        delta = datetime.timedelta(hours=hours)
        return await cls.filter(user_id=user_id, site=site, timestamp__gte=delta).exists()

    class Meta:
        table = "Votes"

class WebhookAuthorization(Base):
    site = fields.CharField(max_length=100)
    """The site the webhook is for."""

    authorization = fields.CharField(max_length=255)

    class Meta:
        table = "WebhookAuthorization"

class Commands(Base):
    # id SERIAL PRIMARY KEY,
    # guild_id BIGINT,
    # channel_id BIGINT,
    # author_id BIGINT,
    # used TIMESTAMP,
    # prefix TEXT,
    # command TEXT,
    # failed BOOLEAN
    # app_command BOOLEAN NOT NULL DEFAULT FALSE
    # args TEXT,

    guild_id = fields.BigIntField(null=True)
    @property
    def guild(self):
        return self.guild_id

    channel_id = fields.BigIntField(null=True)
    @property
    def channel(self):
        return self.channel_id

    author_id = fields.BigIntField()
    @property
    def author(self):
        return self.author_id
    
    @property
    def user_id(self):
        return self.author_id

    used = fields.DatetimeField()
    uses = fields.BigIntField(default=1)
    prefix = fields.CharField(max_length=23)
    command = fields.CharField(max_length=100)
    command_id = fields.BigIntField(null=True)
    failed = fields.BooleanField(default=False)
    app_command = fields.BooleanField(default=False)
    args = fields.JSONField(null=True)
    kwargs = fields.JSONField(null=True)
    transaction_id = fields.UUIDField(null=True)

    @classmethod
    async def bulk_insert(cls, bulk_data: list[dict]):
        # self._data_batch.append(
        #         {
        #             'guild': guild_id,
        #             'channel': ctx.channel.id,
        #             'author': ctx.author.id,
        #             'used': message.created_at.isoformat(), # created_at 
        #             'prefix': ctx.prefix,
        #             'command': command,
        #             'failed': ctx.command_failed,
        #             'app_command': is_app_command,
        #             'args': ctx.args,
        #             'kwargs': ctx.kwargs,
        #         }
        #     )
        if not bulk_data:
            return
        
        #models_list = []

        for data in bulk_data:
            if data.get("guild",None):
                data["guild_id"] = data.pop("guild")
            if data.get("channel",None):
                data["channel_id"] = data.pop("channel")
            if data.get("author",None):
                data["author_id"] = data.pop("author")
            #models_list.append(cls(**data))
            #data['uses'] = await cls.filter(guild_id=data.get("guild_id"), command=data.get("command")).count() + 1
            await cls.create(**data)
        #await cls.bulk_create(models_list, batch_size=1000)
        
    class Meta:
        table = "Commands"

class Blacklist(Base):
    """Table relating blacklisted users and/or guilds."""
    offender_id = fields.BigIntField()
    offender_name = fields.CharField(max_length=100, null=True)
    type = fields.CharField(max_length=10, default="user")
    """Type of blacklist. Either 'user' or 'guild'."""

    reason = fields.CharField(max_length=255, null=True)
    timestamp = fields.DatetimeField()

    @classmethod
    async def add(cls, user: Union[discord.abc.User, discord.Guild], reason: Optional[str]=None) -> Self:
        instance, _ = await cls.update_or_create(
            defaults={
                'offender_id': user.id,
                'offender_name': user.name,
                'type': 'user' if isinstance(user, discord.abc.User) else 'guild',
                'reason': reason,
                'timestamp': datetime.datetime.now(),
            }
        )
        return instance

    @classmethod
    async def remove(cls, id: int, type: str='user') -> bool:
        instance = await cls.filter(offender_id=id, type=type).first()
        if instance:
            await instance.delete()
        return not instance

    @classmethod
    async def is_blacklisted(cls, id: int, type: str='user') -> bool:
        return await cls.filter(offender_id=id, type=type).exists()

    @classmethod
    async def blacklisted(cls, id: int, type: str='user') -> Optional[Self]:
        return await cls.filter(offender_id=id, type=type).first()

    class Meta:
        table = "Blacklist"

class ReportedErrors(Base):
    """Errors Reported to my private forum via that menu thing."""

    error_id = fields.UUIDField()

    user_id = fields.BigIntField()

    forum_id = fields.BigIntField()
    forum_post_id = fields.BigIntField()
    forum_initial_message_id = fields.BigIntField()

    error_message = fields.TextField(null=True)

    resolved = fields.BooleanField(default=False)

    class Meta:
        table = "ReportedErrors"


# Models for Toxic Tourneys

class SavedMessages(Base):
    """Messages that the bot has saved for later use."""

    name = fields.CharField(max_length=100)

    guild_id = fields.BigIntField(null=True)
    channel_id = fields.BigIntField()
    message_id = fields.BigIntField()

    author_id = fields.BigIntField()
    author_name = fields.CharField(max_length=100, null=True)
    
    @classmethod
    async def save_message(cls, message: discord.Message, name: str):
        await cls.create(
            name=name,
            guild_id=message.guild.id if message.guild else None,
            channel_id=message.channel.id,
            message_id=message.id,
            author_id=message.author.id,
            author_name=str(message.author),
        )
    

    @classmethod
    async def get_message(cls, guild_id: Optional[int], channel_id: int, message_id: int) -> Optional[Self]:
        return await cls.filter(guild_id=guild_id, channel_id=channel_id, message_id=message_id).first()

    class Meta:
        table = "SavedMessages"

class Tournaments(Base):
    """Toxic Tourneys"""

    name = fields.CharField(max_length=100)
    description = fields.TextField(null=True)

    team_size = fields.IntField(null=True)

    author_id = fields.BigIntField()
    author_name = fields.CharField(max_length=100, null=True)

    max_teams = fields.IntField(default=-1)
    """-1 = no limit"""

    random_teams = fields.BooleanField(default=False)

    current_participants = fields.IntField(default=0)

    ended = fields.BooleanField(default=False)

    #participants = fields.ManyToManyField('my_app.TourneyParticipants', related_name='tournament')

    async def all_participants(self) -> List[TourneyParticipants]:
        return await TourneyParticipants.filter(tournament=self)
    
    @classmethod
    async def create_tournament(cls, message: discord.Message, author: discord.User, start_time: datetime.datetime, end_time: datetime.datetime, max_teams: int):
        await cls.create(
            name=f"Tournament {message.id}",
            description=message.content,
            guild_id=message.guild.id,
            channel_id=message.channel.id,
            message_id=message.id,
            author_id=author.id,
            author_name=str(author),
            start_time=start_time,
            end_time=end_time,
            max_teams=max_teams,
            current_participants=0,
        )

    @classmethod
    async def get_tournament(cls, guild_id: int, channel_id: int, message_id: int) -> Optional[Self]:
        return await cls.filter(guild_id=guild_id, channel_id=channel_id, message_id=message_id).first()

    async def end_tournament(self):
        self.ended = True
        await self.save()
    
    async def add_participant(self, user: discord.abc.User, user_connection: R6UserConnections):
        await TourneyParticipants.create(
            tournament=self,
            user_id=user.id,
            user_connection=user_connection,
        )
        self.current_participants += 1
        await self.save()

    async def remove_participant(self, user: discord.abc.User):
        await TourneyParticipants.filter(tournament=self, user_id=user.id).delete()
        self.current_participants -= 1
        await self.save()

    async def get_participant(self, user: discord.abc.User) -> Optional[TourneyParticipants]:
        return await TourneyParticipants.filter(tournament=self, user_id=user.id).first()

    async def create_team(self, name: str, leader: discord.abc.User, leader_connection: R6UserConnections, description: Optional[str]=None):
        leader_obj,  _ = await TourneyParticipants.get_or_create(
            tournament=self,
            user_id=leader.id,
            defaults={
                'user_connection': leader_connection,
                'is_team_leader': True
            }
        )

        team = await TourneyTeams.create_team(
            tournament=self,
            name=name,
            leader=leader_obj,
            description=description,
        )
        leader_obj.team = team
        self.current_participants += 1
        await self.save()
        await leader_obj.save()
        return team

    async def add_team(self, team: TourneyTeams):
        self.current_participants += len(await team.all_team_members())
        await self.save()
    
    async def get_team(self, name: Optional[str]=None, leader: Optional[discord.abc.User]=None) -> Optional[TourneyTeams]:
        if name:
            return await TourneyTeams.filter(tournament=self, name=name).first()
        elif leader:
            leader_obj = await TourneyParticipants.filter(tournament=self, user_id=leader.id, is_team_leader=True).prefetch_related('team').first()
            return leader_obj.team if leader_obj else None
    
    async def remove_team(self, team: TourneyTeams):
        self.current_participants -= len(await team.all_team_members())
        await self.save()
    
        
    class Meta:
        table = "Tournaments"

class TourneyTeams(Base):
    tournament = fields.ForeignKeyField('my_app.Tournaments', related_name='teams')

    name = fields.CharField(max_length=100)
    description = fields.TextField(null=True)

    #leader = fields.ForeignKeyField('my_app.TourneyParticipants', related_name='team_leader')

    #team_members = fields.ManyToManyField('TourneyParticipants', related_name='team_members')

    async def leader(self) -> TourneyParticipants:
        return await TourneyParticipants.get(team=self, is_team_leader=True)

    async def all_team_members(self) -> List[TourneyParticipants]:
        return await TourneyParticipants.filter(team=self)
    
    @classmethod
    async def create_team(cls, tournament: Tournaments, name: str, leader: TourneyParticipants, description: Optional[str]=None):
        leader.is_team_leader = True
        await leader.save()
        return await cls.create(
            tournament=tournament,
            name=name,
            description=description,
        )
    
    @classmethod
    async def get_team(cls, tournament: Tournaments, name: Optional[str]=None, leader: Optional[discord.abc.User]=None) -> Optional[Self]:
        if name:
            return await cls.filter(tournament=tournament, name=name).first()
        elif leader:
            leader_obj = await TourneyParticipants.filter(tournament=tournament, user_id=leader.id, is_team_leader=True).prefetch_related('team').first()
            return leader_obj.team if leader_obj else None

    async def add_member(self, user: discord.abc.User, user_connection: R6UserConnections):
        return await TourneyParticipants.create(
            tournament=self.tournament,
            team=self,
            user_id=user.id,
            user_connection=user_connection,
        )
    
    async def get_member(self, user: discord.abc.User) -> Optional[TourneyParticipants]:
        return await TourneyParticipants.filter(tournament=self.tournament, team=self, user_id=user.id).first()
    
    async def remove_member(self, user: Optional[discord.abc.User]=None, user_id: Optional[int]=None):
        user_id = user_id or (user.id if user else None)
        return await TourneyParticipants.filter(tournament=self.tournament, user_id=user_id).delete()

    class Meta:
        table = "TourneyTeams"

class TourneyParticipants(Base):
    """Participants in a tournament."""

    tournament = fields.ForeignKeyField('my_app.Tournaments', related_name='participants')

    team = fields.ForeignKeyField('my_app.TourneyTeams', related_name='team_members', null=True)
    is_team_leader = fields.BooleanField(default=False)

    user_id = fields.BigIntField()
    user_connection = fields.ForeignKeyField('my_app.R6UserConnections', related_name='tourney_participant')


    class Meta:
        table = "TourneyParticipants"

class Alerts(Base):
    alert_title = fields.CharField(max_length=100)

    alert_message = fields.TextField()

    alert_type = fields.CharField(max_length=100, null=True)

    is_active = fields.BooleanField(default=True)

    @classmethod
    async def active_alerts(cls) -> List[Self]:
        return await cls.filter(is_active=True)
    
    @classmethod
    async def unviewed_alerts(cls, user_id: int) -> List[Self]:
        alerts_viewed = [x.alert for x in await AlertViewings.filter(user_id=user_id).prefetch_related('alert')]
        return [x for x in await cls.active_alerts() if x not in alerts_viewed]

    async def has_viewed_alert(self, user_id: int) -> int:
        """Returns number of unviewed alerts."""
        return await AlertViewings.has_viewed(user_id, self)

    async def viewed_alert(self, user_id: int):
        """Method to mark alert as viewed by a user."""
        return await AlertViewings.viewed_alert(user_id, self)

    class Meta:
        table = "Alerts"

class AlertViewings(Base):
    user_id = fields.BigIntField()

    alert = fields.ForeignKeyField('my_app.Alerts', related_name='viewings')

    @classmethod
    async def has_viewed(cls, user_id: int, alert: Alerts) -> int:
        """Returns number of unviewed alerts."""
        return await cls.filter(user_id=user_id, alert=alert).count()

    @classmethod
    async def viewed_alert(cls, user_id: int, alert: Alerts):
        await cls.create(user_id=user_id, alert=alert)

    class Meta:
        table = "AlertViewings"


async def setup(*args):
    env = environ.Env(
        PROD=(bool, False)
    )

    PROD = env("PROD")
    if PROD:
        await Tortoise.init(config_file="db.yml")
    else:
        await Tortoise.init(config_file="db_beta.yml")
    await Tortoise.generate_schemas()

