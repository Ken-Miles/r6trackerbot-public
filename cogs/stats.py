"""
This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at http://mozilla.org/MPL/2.0/.

This file was sourced from [RoboDanny](https://github.com/Rapptz/RoboDanny).

Written by @danny on Discord
Taken from https://github.com/Rapptz/RoboDanny/blob/rewrite/cogs/stats.py
"""


from __future__ import annotations
import asyncio
from collections import Counter
import datetime
import gc
import io
import itertools
import json
import logging
import os
import re
import sys
import textwrap
import traceback
from typing import Any, Dict, Optional, TypedDict

import asyncpg
import discord
from discord import app_commands
from discord.ext import commands, tasks
from humanize import intcomma
import pkg_resources
import psutil
import pygit2
from tortoise import Tortoise
from tortoise.functions import Count
from typing_extensions import Annotated

from cogs.models import Blacklist, CommandInvocation, Commands
from cogs.ranks import Platform, SUPPORT_SERVER, plural
from cogs.ranksv2 import Platform as PlatformV2
from utils import (
    BotU,
    CogU,
    ContextU,
    Cooldown,
    FiveButtonPaginator,
    GITHUB_URL,
    STATS_WEBHOOK_URL,
    create_paginator,
    danny_formats,
    danny_time,
    dchyperlink,
    dctimestamp,
    emojidict,
    generate_pages,
)

log = logging.getLogger(__name__)

LOGGING_CHANNEL = 309632009427222529


class DataBatchEntry(TypedDict):
    guild: Optional[int]
    channel: int
    author: int
    used: str
    prefix: str
    command: str
    failed: bool
    app_command: bool
    args: list[str]
    kwargs: dict[str, Any]


class LoggingHandler(logging.Handler):
    def __init__(self, cog: Stats):
        self.cog: Stats = cog
        super().__init__(logging.INFO)

    def filter(self, record: logging.LogRecord) -> bool:
        return record.name in ('discord.gateway', 'cogs.splatoon')

    def emit(self, record: logging.LogRecord) -> None:
        self.cog.add_record(record)


_INVITE_REGEX = re.compile(r'(?:https?:\/\/)?discord(?:\.gg|\.com|app\.com\/invite)?\/[A-Za-z0-9]+')


def censor_invite(obj: Any, *, _regex=_INVITE_REGEX) -> str:
    return _regex.sub('[censored-invite]', str(obj))


def hex_value(arg: str) -> int:
    return int(arg, base=16)

def object_at(addr: int) -> Optional[Any]:
    for o in gc.get_objects():
        if id(o) == addr:
            return o
    return None

class Stats(CogU):
    """Bot usage statistics."""

    def __init__(self, bot: BotU):
        self.bot: BotU = bot
        self.process = psutil.Process()
        self._batch_lock = asyncio.Lock()
        self._data_batch: list[DataBatchEntry] = []
        self.bulk_insert_loop.add_exception_type(asyncpg.PostgresConnectionError)
        self.bulk_insert_loop.start()
        self._logging_queue = asyncio.Queue()
        self.logging_worker.start()

    @property
    def display_emoji(self) -> discord.PartialEmoji:
        return discord.PartialEmoji(name='\N{BAR CHART}')

    async def bulk_insert(self) -> None:
        # query = """INSERT INTO commands (guild_id, channel_id, author_id, used, prefix, command, failed, app_command)
        #            SELECT x.guild, x.channel, x.author, x.used, x.prefix, x.command, x.failed, x.app_command
        #            FROM jsonb_to_recordset($1::jsonb) AS
        #            x(
        #                 guild BIGINT,
        #                 channel BIGINT,
        #                 author BIGINT,
        #                 used TIMESTAMP,
        #                 prefix TEXT,
        #                 command TEXT,
        #                 failed BOOLEAN,
        #                 app_command BOOLEAN
        #             )
        #         """

        # if self._data_batch:
        #     await self.bot.pool.execute(query, self._data_batch)
        #     total = len(self._data_batch)
        #     if total > 1:
        #         log.info('Registered %s commands to the database.', total)
        #     self._data_batch.clear()
        if self._data_batch:
            await Commands.bulk_insert(self._data_batch) # type: ignore
            total = len(self._data_batch)
            if total > 1:
                log.info('Registered %s commands to the database.', total)
            self._data_batch.clear()

    async def cog_unload(self):
        self.bulk_insert_loop.stop()
        self.logging_worker.cancel()

    @tasks.loop(seconds=10.0)
    async def bulk_insert_loop(self):
        if not self._data_batch:
            return
        async with self._batch_lock:
            await self.bulk_insert()

    @tasks.loop(seconds=0.0)
    async def logging_worker(self):
        record = await self._logging_queue.get()
        await self.send_log_record(record)

    async def register_command(self, ctx: ContextU) -> None:
        if ctx.command is None:
            return

        command = ctx.command.qualified_name
        is_app_command = ctx.interaction is not None
        self.bot.command_stats[command] += 1
        self.bot.command_types_used[is_app_command] += 1
        message = ctx.message
        destination = None
        if ctx.guild is None:
            destination = 'Private Message'
            guild_id = None
        else:
            destination = f'#{message.channel} ({message.guild})'
            guild_id = ctx.guild.id

        if ctx.interaction and ctx.interaction.command:
            content = f'/{ctx.interaction.command.qualified_name}'
        else:
            content = message.content

        log.info(f'{message.created_at}: {message.author} in {destination}: {content}')
        args = []
        kwargs = {}

        for key, value in ctx.kwargs.items():
            try:
                json.dumps(value) # ensure it's json serializable
                kwargs[key] = value
            except TypeError:
                if isinstance(value, (PlatformV2, Platform)):
                    kwargs[key] = value.route
                continue
    
        for entry in ctx.args:            
            try:
                if isinstance(entry, (PlatformV2, Platform)):
                    entry = entry.route
                json.dumps(entry) # ensure it's json serializable
                args.append(entry)
            except TypeError:
                continue
        
        while True:
            transaction = (await CommandInvocation.filter(command_id=ctx.interaction.id if ctx.interaction else ctx.message.id, user_id=ctx.author.id, timestamp=message.created_at).first())
            if transaction:
                transaction_id = transaction.transaction_id
                break
            await asyncio.sleep(5)

        async with self._batch_lock:
            self._data_batch.append(
                {
                    'guild': guild_id,
                    'channel': ctx.channel.id,
                    'author': ctx.author.id,
                    'used': message.created_at, # created_at 
                    'prefix': ctx.prefix,
                    'command': command,
                    'failed': ctx.command_failed,
                    'app_command': is_app_command,
                    'args': args,
                    'kwargs': kwargs,
                    'command_id': ctx.interaction.id if ctx.interaction else ctx.message.id,
                    'transaction_id': transaction_id,
                } # type: ignore
            )
        # await Commands.create(
        #     guild_id=guild_id,
        #     channel=ctx.channel.id,
        #     author_id=ctx.author.id,
        #     used=message.created_at,
        #     prefix=ctx.prefix,
        #     command=command,
        #     failed=ctx.command_failed,
        #     app_command=is_app_command,
        #     args=ctx.args,
        #     kwargs=ctx.kwargs,
        # )

    @commands.Cog.listener()
    async def on_command(self, ctx: ContextU):
        await self.register_command(ctx)

    # @commands.Cog.listener()
    # async def on_command_completion(self, ctx: ContextU):
    #     await self.register_command(ctx)

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        command = interaction.command
        # Check if a command is found and it's not a hybrid command
        # Hybrid commands are already counted via on_command_completion
        if (
            command is not None
            and interaction.type is discord.InteractionType.application_command
            and not command.__class__.__name__.startswith('Hybrid')  # Kind of awful, but it'll do
        ):
            # This is technically bad, but since we only access Command.qualified_name and it's
            # available on all types of commands then it's fine
            ctx = await ContextU.from_interaction(interaction)
            ctx.command_failed = interaction.command_failed or ctx.command_failed
            await self.register_command(ctx)

    @commands.Cog.listener()
    async def on_socket_event_type(self, event_type: str):
        self.bot.socket_stats[event_type] += 1

    @commands.Cog.listener()
    async def on_ready(self):
        # if not hasattr(self, 'uptime'):
        #     self.uptime = discord.utils.utcnow()
        if not hasattr(self, 'uptime'):
            self.uptime = discord.utils.utcnow()

        log.info('Ready: %s (ID: %s)', self.bot.user, self.bot.user.id)

    async def on_shard_resumed(self, shard_id: int):
        log.info('Shard ID %s has resumed...', shard_id)
        self.bot.resumes[shard_id].append(discord.utils.utcnow())

    @discord.utils.cached_property
    def webhook(self) -> discord.Webhook:
        #wh_id, wh_token = self.bot.config.stat_webhook
        #hook = discord.Webhook.partial(id=wh_id, token=wh_token, session=self.bot.session)
        hook = discord.Webhook.from_url(STATS_WEBHOOK_URL, client=self.bot)
        return hook

    @commands.command(name='commandstats', hidden=True)
    @commands.is_owner()
    async def commandstats(self, ctx: ContextU, limit: int = 12):
        """Shows command stats.

        Use a negative number for bottom instead of top.
        This is only for the current session.
        """
        await ctx.defer()

        counter = self.bot.command_stats
        total = sum(counter.values())
        slash_commands = self.bot.command_types_used[True]

        delta = discord.utils.utcnow() - self.uptime
        minutes = delta.total_seconds() / 60
        cpm = total / minutes

        if limit > 0:
            common = counter.most_common(limit)
            title = f'Top {limit} Commands'
        else:
            common = counter.most_common()[limit:]
            title = f'Bottom {limit} Commands'

        lines = []
        for index, (command, value) in enumerate(common, 1):
            lines.append(f'{index}. {command}: `{value}` uses')
        pages = generate_pages(lines, title=title)
        for page in pages:
            if page.description:
                page.description += f"\n\n`{total}` total commands used (`{slash_commands}` slash command uses) (`{cpm:.2f}`/minute)"
        
        return await create_paginator(ctx, pages, FiveButtonPaginator, go_to_button=True)
        # pages = generate_pages(common, title=title, )
        # source = FieldPageSource(common, inline=True, clear_description=False)
        # source.embed.title = title
        # source.embed.description = f'{total} total commands used ({slash_commands} slash command uses) ({cpm:.2f}/minute)'

        # pages = RoboPages(source, ctx=ctx, compact=True)
        # await pages.start()



    @commands.command(name='socketstats', hidden=True)
    async def socketstats(self, ctx: ContextU):
        delta = discord.utils.utcnow() - self.uptime
        minutes = delta.total_seconds() / 60
        total = sum(self.bot.socket_stats.values())
        cpm = total / minutes
        await ctx.reply(f'{total} socket events observed ({cpm:.2f}/minute):\n{self.bot.socket_stats}')

    def get_bot_uptime(self, *, brief: bool = False) -> str:
        return danny_time.human_timedelta(self.uptime, accuracy=None, brief=brief, suffix=False)

    @commands.hybrid_command(name='uptime')
    async def uptime_cmd(self, ctx: ContextU):
        """Tells you how long the bot has been up for."""
        if not hasattr(self, 'uptime'):
            return await ctx.reply('Bot has not connected to the gateway yet.', delete_after=10, ephemeral=True)
        await ctx.reply(f'Bot has been up since {dctimestamp(self.uptime,"R")}.', ephemeral=True)
        #await ctx.reply(f'Uptime: **{self.get_bot_uptime()}** (since {dctimestamp(self.uptime,"R")})')

    def format_commit(self, commit: pygit2.Commit) -> str:
        short, _, _ = commit.message.partition('\n')
        short_sha2 = commit.hex[0:6]
        commit_tz = datetime.timezone(datetime.timedelta(minutes=commit.commit_time_offset))
        commit_time = datetime.datetime.fromtimestamp(commit.commit_time).astimezone(commit_tz)

        # [`hash`](url) message (offset)
        offset = danny_time.format_relative(commit_time.astimezone(datetime.timezone.utc))
        return f"{dchyperlink(f'{GITHUB_URL}/commit/{commit.hex}',f'`{short_sha2}`', )} {short} ({offset})"
        #return f'[`{short_sha2}`](https://github.com/Rapptz/RoboDanny/commit/{commit.hex}) {short} ({offset})'

    def get_last_commits(self, count=3):
        repo = pygit2.Repository('.git')
        commits = list(itertools.islice(repo.walk(repo.head.target, pygit2.GIT_SORT_TOPOLOGICAL), count))
        return '\n'.join(self.format_commit(c) for c in commits)

    @commands.hybrid_command(name='about')
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def about(self, ctx: ContextU):
        """Tells you information about the bot itself."""

        if not hasattr(self, 'uptime'):
            return await ctx.reply('Bot has not connected to the gateway yet.',ephemeral=True, delete_after=10)

        revision = self.get_last_commits()
        embed = discord.Embed(description='Latest Changes:\n' + revision)
        embed.title = 'Official Bot Server Invite'
        embed.url = f'{SUPPORT_SERVER}'
        embed.colour = discord.Colour.blurple()

        embed.set_author(name=str(self.bot.owner), icon_url=self.bot.owner.display_avatar.url) # type: ignore

        # statistics
        total_members = 0
        total_unique = len(self.bot.users)

        text = 0
        voice = 0
        guilds = 0
        for guild in self.bot.guilds:
            guilds += 1
            if guild.unavailable:
                continue

            total_members += guild.member_count or 0
            for channel in guild.channels:
                if isinstance(channel, discord.TextChannel):
                    text += 1
                elif isinstance(channel, discord.VoiceChannel):
                    voice += 1

        embed.add_field(name='Members', value=f'`{intcomma(total_members)}` total\n`{intcomma(total_unique)}` unique')
        embed.add_field(name='Channels', value=f'`{intcomma(text + voice)}` total\n`{intcomma(text)}` text\n`{intcomma(voice)}` voice')

        memory_usage = self.process.memory_full_info().uss / 1024**2
        cpu_usage = self.process.cpu_percent() / psutil.cpu_count()
        embed.add_field(name='Process', value=f'`{memory_usage:.2f}` MiB\n`{cpu_usage:.2f}`% CPU')

        version = pkg_resources.get_distribution('discord.py').version
        embed.add_field(name='Guilds', value=f"`{intcomma(guilds)}`")
        embed.add_field(name='Commands Run', value=f"`{intcomma(sum(self.bot.command_stats.values()))}`")
        embed.add_field(name='Uptime', value=self.get_bot_uptime(brief=True))
        embed.set_footer(text=f'Made with discord.py v{version}', icon_url='http://i.imgur.com/5BFecvA.png')
        embed.timestamp = discord.utils.utcnow()
        await ctx.reply(embed=embed)

    async def censor_object(self, obj: str | discord.abc.Snowflake) -> str:
        if not isinstance(obj, str) and await Blacklist.is_blacklisted(obj.id):
            return '[censored]'
        return censor_invite(obj)

    async def show_guild_stats(self, ctx: ContextU) -> None:
        lookup = (
            '\N{FIRST PLACE MEDAL}',
            '\N{SECOND PLACE MEDAL}',
            '\N{THIRD PLACE MEDAL}',
            '\N{SPORTS MEDAL}',
            '\N{SPORTS MEDAL}',
        )

        embed = discord.Embed(title='Server Command Stats', colour=discord.Colour.blurple())

        # total command uses
        # query = "SELECT COUNT(*), MIN(used) FROM "Commands" WHERE guild_id=$1;"
        # count: tuple[int, datetime.datetime] = await ctx.db.fetchrow(query, ctx.guild.id)  # type: ignore

        qs = Commands.filter(guild_id=ctx.guild.id).order_by('used')

        count = await qs.count(), getattr((await qs.first()), 'used', None)

        embed.description = f'`{intcomma(count[0])}` commands used.'
        if count[1]:
            timestamp = count[1].replace(tzinfo=datetime.timezone.utc)
        else:
            timestamp = discord.utils.utcnow()
        

        embed.set_footer(text='Tracking command usage since').timestamp = timestamp

        # query = """SELECT command,
        #                   COUNT(*) as "uses"
        #            FROM "Commands"
        #            WHERE guild_id=$1
        #            GROUP BY command
        #            ORDER BY "uses" DESC
        #            LIMIT 5;
        #         """

        # records = await ctx.db.fetch(query, ctx.guild.id)

        
        records = await Commands.filter(guild_id=ctx.guild.id).group_by('command').order_by('-used')

        records_dict = {}
        for record in records:
            if record.command not in records_dict.keys():
                records_dict[record.command] = 1
            else:
                records_dict[record.command] += 1
            if len(records_dict) >= 5:
                break
        # records_dict: Dict[Commands, int] = {
        #     record: await Commands.filter(guild_id=ctx.guild.id, command=record.command).count() for record in records
        # }

        value = (
            '\n'.join(f'{lookup[index]}: {command} (`{intcomma(uses)}` uses)' for (index, (command, uses)) in enumerate(records_dict.items()))
            or 'No Commands'
        )

        embed.add_field(name='Top Commands', value=value, inline=True)

        # query = """SELECT command,
        #                   COUNT(*) as "uses"
        #            FROM "Commands"
        #            WHERE guild_id=$1
        #            AND used > (CURRENT_TIMESTAMP - INTERVAL '1 day')
        #            GROUP BY command
        #            ORDER BY "uses" DESC
        #            LIMIT 5;
        #         """

        # records = await ctx.db.fetch(query, ctx.guild.id)
        
        records = await Commands.filter(guild_id=ctx.guild.id, used__gt=(discord.utils.utcnow() - datetime.timedelta(days=1))).group_by('command').order_by('-used')
        
        records_dict = {}
        for record in records:
            if record.command not in records_dict.keys():
                records_dict[record.command] = 1
            else:
                records_dict[record.command] += 1
            if len(records_dict) >= 5:
                break
        

        value = (
            '\n'.join(f'{lookup[index]}: {command} (`{intcomma(uses)}` use{plural(uses)})' for (index, (command, uses)) in enumerate(records_dict.items()))
            or 'No Commands.'
        )
        embed.add_field(name='Top Commands Today', value=value, inline=True)
        embed.add_field(name='\u200b', value='\u200b', inline=True)

        # query = """SELECT author_id,
        #                   COUNT(*) AS "uses"
        #            FROM "Commands"
        #            WHERE guild_id=$1
        #            GROUP BY author_id
        #            ORDER BY "uses" DESC
        #            LIMIT 5;
        #         """

        # records = await ctx.db.fetch(query, ctx.guild.id)

        records = await Commands.filter(guild_id=ctx.guild.id).group_by('author').order_by('-used')
        records_dict = {}
        for record in records:
            if record.author_id not in records_dict.keys():
                records_dict[record.author_id] = 1
            else:
                records_dict[record.author_id] += 1
            if len(records_dict) >= 5:
                break
        

        value = (
            '\n'.join(
                f'{lookup[index]}: <@{author_id}> (`{intcomma(uses)}` bot use{plural(uses)})' for (index, (author_id, uses)) in enumerate(records_dict.items())
            )
            or 'No bot users.'
        )

        embed.add_field(name='Top Command Users', value=value, inline=True)

        # query = """SELECT author_id,
        #                   COUNT(*) AS "uses"
        #            FROM "Commands"
        #            WHERE guild_id=$1
        #            AND used > (CURRENT_TIMESTAMP - INTERVAL '1 day')
        #            GROUP BY author_id
        #            ORDER BY "uses" DESC
        #            LIMIT 5;
        #         """

        # records = await ctx.db.fetch(query, ctx.guild.id)

        records = await Commands.filter(guild_id=ctx.guild.id, used__gt=(discord.utils.utcnow() - datetime.timedelta(days=1))).group_by('author').order_by('-used')

        records_dict = {}
        for record in records:
            if record.author_id not in records_dict.keys():
                records_dict[record.author_id] = 1
            else:
                records_dict[record.author_id] += 1
            if len(records_dict) >= 5:
                break

        value = (
            '\n'.join(
                f'{lookup[index]}: <@{author_id}> (`{intcomma(uses)}` bot use{plural(uses)})' for (index, (author_id, uses)) in enumerate(records_dict.items())
            )
            or 'No command users.'
        )

        embed.add_field(name='Top Command Users Today', value=value, inline=True)
        await ctx.reply(embed=embed)

    async def show_member_stats(self, ctx: ContextU, member: discord.Member) -> None:
        lookup = (
            '\N{FIRST PLACE MEDAL}',
            '\N{SECOND PLACE MEDAL}',
            '\N{THIRD PLACE MEDAL}',
            '\N{SPORTS MEDAL}',
            '\N{SPORTS MEDAL}',
            '\N{SPORTS MEDAL}',
        )

        embed = discord.Embed(title='Command Stats', colour=member.colour)
        embed.set_author(name=str(member), icon_url=member.display_avatar.url)

        # total command uses
        # query = "SELECT COUNT(*), MIN(used) FROM "Commands" WHERE guild_id=$1 AND author_id=$2;"
        # count: tuple[int, datetime.datetime] = await ctx.db.fetchrow(query, ctx.guild.id, member.id)  # type: ignore

        qs = Commands.filter(guild_id=ctx.guild.id, author_id=member.id).order_by('used')
        count = await qs.count(), getattr((await qs.first()), 'used', None)

        embed.description = f'`{intcomma(count[0])}` commands used.'
        if count[1]:
            timestamp = count[1].replace(tzinfo=datetime.timezone.utc)
        else:
            timestamp = discord.utils.utcnow()

        embed.set_footer(text='First command used').timestamp = timestamp

        # query = """SELECT command,
        #                   COUNT(*) as "uses"
        #            FROM "Commands"
        #            WHERE guild_id=$1 AND author_id=$2
        #            GROUP BY command
        #            ORDER BY "uses" DESC
        #            LIMIT 5;
        #         """

        # records = await ctx.db.fetch(query, ctx.guild.id, member.id)

        records = await Commands.filter(guild_id=ctx.guild.id, author_id=member.id).group_by('command').order_by('-used')
        records_dict = {}
        for record in records:
            if record.command not in records_dict.keys():
                records_dict[record.command] = 1
            else:
                records_dict[record.command] += 1
            if len(records_dict) >= 5:
                break


        value = (
            '\n'.join(f'{lookup[index]}: {record} (`{intcomma(uses)}` uses)' for (index, (record, uses)) in enumerate(records_dict.items()))
            or 'No Commands'
        )

        embed.add_field(name='Most Used Commands', value=value, inline=False)

        # query = """SELECT command,
        #                   COUNT(*) as "uses"
        #            FROM "Commands"
        #            WHERE guild_id=$1
        #            AND author_id=$2
        #            AND used > (CURRENT_TIMESTAMP - INTERVAL '1 day')
        #            GROUP BY command
        #            ORDER BY "uses" DESC
        #            LIMIT 5;
        #         """

        # records = await ctx.db.fetch(query, ctx.guild.id, member.id)

        records = await Commands.filter(guild_id=ctx.guild.id, author_id=member.id, used__gt=(discord.utils.utcnow() - datetime.timedelta(days=1))).group_by('command').order_by('-used')

        records_dict = {}
        for record in records:
            if record.command not in records_dict.keys():
                records_dict[record.command] = 1
            else:
                records_dict[record.command] += 1
            if len(records_dict) >= 5:
                break

        value = (
            '\n'.join(f'{lookup[index]}: {command} (`{intcomma(uses)}` uses)' for (index, (command, uses)) in enumerate(records_dict.items()))
            or 'No Commands'
        )

        embed.add_field(name='Most Used Commands Today', value=value, inline=False)
        await ctx.reply(embed=embed)

    @commands.group(invoke_without_command=True)
    @commands.guild_only()
    #@commands.cooldown(1, 30.0, type=commands.BucketType.member)
    @Cooldown(1, 30, commands.BucketType.member)
    async def stats(self, ctx: ContextU, *, member: Optional[discord.Member] = None):
        """Tells you command usage stats for the server or a member."""
        await ctx.defer()
        if member is None:
            await self.show_guild_stats(ctx)
        else:
            await self.show_member_stats(ctx, member)

    @stats.command(name='global')
    @commands.is_owner()
    async def stats_global(self, ctx: ContextU):
        """Global all time command statistics."""

        # query = "SELECT COUNT(*) FROM "Commands";"
        # total: tuple[int] = await ctx.db.fetchrow(query)  # type: ignore
        total = await Commands.all().count()

        e = discord.Embed(title='Command Stats', colour=discord.Colour.blurple())
        e.description = f'`{intcomma(total)}` commands used.'

        lookup = (
            '\N{FIRST PLACE MEDAL}',
            '\N{SECOND PLACE MEDAL}',
            '\N{THIRD PLACE MEDAL}',
            '\N{SPORTS MEDAL}',
            '\N{SPORTS MEDAL}',
        )

        # query = """SELECT command, COUNT(*) AS "uses"
        #            FROM "Commands"
        #            GROUP BY command
        #            ORDER BY "uses" DESC
        #            LIMIT 5;
        #         """

        # records = await ctx.db.fetch(query)
        records = await Commands.all().group_by('command').order_by('-used')
        records_dict = {}
        for record in records:
            if record.command not in records_dict.keys():
                records_dict[record.command] = 1
            else:
                records_dict[record.command] += 1
            if len(records_dict) >= 5:
                break
    
        value = '\n'.join(f'{lookup[index]}: {command} (`{intcomma(uses)}` uses)' for (index, (command, uses)) in enumerate(records_dict.items()))
        e.add_field(name='Top Commands', value=value, inline=False)

        # query = """SELECT guild_id, COUNT(*) AS "uses"
        #            FROM "Commands"
        #            GROUP BY guild_id
        #            ORDER BY "uses" DESC
        #            LIMIT 5;
        #         """

        # records = await ctx.db.fetch(query)

        records = await Commands.all().group_by('guild').order_by('-used')

        records_dict = {}
        for record in records:
            if record.guild_id not in records_dict.keys():
                records_dict[record.guild_id] = 1
            else:
                records_dict[record.guild_id] += 1
            if len(records_dict) >= 5:
                break

        value = []
        for (index, (guild_id, uses)) in enumerate(records_dict.items()):
            if guild_id is None:
                guild = 'Private Message'
            else:
                guild = await self.censor_object(self.bot.get_guild(guild_id) or f'<Unknown {guild_id}>')

            emoji = lookup[index]
            value.append(f'{emoji}: {guild} (`{intcomma(uses)}` uses)')

        e.add_field(name='Top Guilds', value='\n'.join(value), inline=False)

        # query = """SELECT author_id, COUNT(*) AS "uses"
        #            FROM "Commands"
        #            GROUP BY author_id
        #            ORDER BY "uses" DESC
        #            LIMIT 5;
        #         """

        # records = await ctx.db.fetch(query)
        
        records = await Commands.all().group_by('author').order_by('-used')
        
        records_dict = {}
        for record in records:
            if record.author_id not in records_dict.keys():
                records_dict[record.author_id] = 1
            else:
                records_dict[record.author_id] += 1
            if len(records_dict) >= 5:
                break
        
        value = []
        for (index, (author_id, uses)) in enumerate(records_dict.items()):
            user = await self.censor_object(self.bot.get_user(author_id) or f'<Unknown {author_id}>')
            emoji = lookup[index]
            value.append(f'{emoji}: {user} (`{intcomma(uses)}` uses)')

        e.add_field(name='Top Users', value='\n'.join(value), inline=False)
        await ctx.reply(embed=e)

    @stats.command(name='today')
    @commands.is_owner()
    async def stats_today(self, ctx: ContextU):
        """Global command statistics for the day."""

        # query = "SELECT failed, COUNT(*) FROM "Commands" WHERE used > (CURRENT_TIMESTAMP - INTERVAL '1 day') GROUP BY failed;"
        # total = await ctx.db.fetch(query)
        
        records = await Commands.filter(used__gt=(discord.utils.utcnow() - datetime.timedelta(days=1))).group_by('failed').annotate(count=Count('failed')).values('failed', 'count')
        total = [(record.get('failed'), int(record.get('count'))) for record in records]
        failed = 0
        success = 0
        question = 0
        for state, count in total:
            if state is False:
                success += count
            elif state is True:
                failed += count
            else:
                question += count

        e = discord.Embed(title='Last 24 Hour Command Stats', colour=discord.Colour.blurple())
        e.description = (
            f'{failed + success + question} commands used today. '
            f'(`{intcomma(success)}` succeeded, `{intcomma(failed)}` failed, `{intcomma(question)}` unknown)'
        )

        lookup = (
            '\N{FIRST PLACE MEDAL}',
            '\N{SECOND PLACE MEDAL}',
            '\N{THIRD PLACE MEDAL}',
            '\N{SPORTS MEDAL}',
            '\N{SPORTS MEDAL}',
        )

        # query = """SELECT command, COUNT(*) AS "uses"
        #            FROM "Commands"
        #            WHERE used > (CURRENT_TIMESTAMP - INTERVAL '1 day')
        #            GROUP BY command
        #            ORDER BY "uses" DESC
        #            LIMIT 5;
        #         """

        # records = await ctx.db.fetch(query)
        records = await Commands.filter(used__gt=(discord.utils.utcnow() - datetime.timedelta(days=1))).group_by('command').order_by('-used')

        records_dict: Dict[str, int] = {}
        for record in records:
            if record.command not in records_dict.keys():
                records_dict[record.command] = 1
            else:
                records_dict[record.command] += 1
            if len(records_dict) >= 5:
                break

        value = '\n'.join(f'{lookup[index]}: {command} (`{intcomma(uses)}` uses)' for (index, (command, uses)) in enumerate(records_dict.items()))
        e.add_field(name='Top Commands', value=value, inline=False)

        # query = """SELECT guild_id, COUNT(*) AS "uses"
        #            FROM "Commands"
        #            WHERE used > (CURRENT_TIMESTAMP - INTERVAL '1 day')
        #            GROUP BY guild_id
        #            ORDER BY "uses" DESC
        #            LIMIT 5;
        #         """

        # records = await ctx.db.fetch(query)

        records_dict = {}
        for record in records:
            if record.guild_id not in records_dict.keys():
                records_dict[record.guild_id] = 1
            else:
                records_dict[record.guild_id] += 1
        
        value = []

        for (index, (guild_id, uses)) in enumerate(records_dict.items()):
            if guild_id is None:
                guild = 'Private Message'
            else:
                guild = await self.censor_object(self.bot.get_guild(guild_id) or f'<Unknown {guild_id}>')
            emoji = lookup[index]
            value.append(f'{emoji}: {guild} (`{intcomma(uses)}` uses)')

        e.add_field(name='Top Guilds', value='\n'.join(value), inline=False)

        # query = """SELECT author_id, COUNT(*) AS "uses"
        #            FROM "Commands"
        #            WHERE used > (CURRENT_TIMESTAMP - INTERVAL '1 day')
        #            GROUP BY author_id
        #            ORDER BY "uses" DESC
        #            LIMIT 5;
        #         """

        # records = await ctx.db.fetch(query)

        records = await Commands.filter(used__gt=(discord.utils.utcnow() - datetime.timedelta(days=1))).group_by('author').order_by('-used')
        
        records_dict = {}
        for record in records:
            if record.author_id not in records_dict.keys():
                records_dict[record.author_id] = 1
            else:
                records_dict[record.author_id] += 1
            if len(records_dict) >= 5:
                break

        value = []
        for (index, (author_id, uses)) in enumerate(records_dict.items()):
            user = await self.censor_object(await self.bot.getorfetch_user(author_id, None) or f'<Unknown {author_id}>')
            emoji = lookup[index]
            value.append(f'{emoji}: {user} (`{intcomma(uses)}` uses)')

        e.add_field(name='Top Users', value='\n'.join(value), inline=False)
        await ctx.reply(embed=e)

    async def send_guild_stats(self, e: discord.Embed, guild: discord.Guild):
        e.add_field(name='Name', value=guild.name)
        e.add_field(name='ID', value=guild.id)
        e.add_field(name='Shard ID', value=guild.shard_id or 'N/A')
        if not guild.owner and guild.owner_id:
            owner = await self.bot.getorfetch_user(guild.owner_id, None)
        else:
            owner = guild.owner
        
        e.add_field(name='Owner', value=f'{owner} (ID: `{guild.owner_id}`)')

        bots = sum(m.bot for m in guild.members)
        total = guild.member_count or 1
        e.add_field(name='Members', value=str(intcomma(total)))
        e.add_field(name='Bots', value=f'{intcomma(bots)} ({bots/total:.2%})')

        if guild.icon:
            e.set_thumbnail(url=guild.icon.url)

        if guild.me:
            e.timestamp = guild.me.joined_at
        
        e.set_footer(text=f'Server count is now {intcomma(len(self.bot.guilds))}.',icon_url=self.bot.user.display_avatar.url)
        
        await self.webhook.send(embed=e)

    @stats_today.before_invoke
    @stats_global.before_invoke
    async def before_stats_invoke(self, ctx: ContextU):
        await ctx.typing()

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        e = discord.Embed(colour=0x53DDA4, title='New Guild')  # green colour
        await self.send_guild_stats(e, guild)

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild):
        e = discord.Embed(colour=0xDD5F53, title='Left Guild')  # red colour
        await self.send_guild_stats(e, guild)

    @commands.Cog.listener()
    async def on_command_error(self, ctx: ContextU, error: Exception) -> None:
        await self.register_command(ctx)
        if not isinstance(error, (commands.CommandInvokeError, commands.ConversionError)):
            return

        error = error.original
        if isinstance(error, (discord.Forbidden, discord.NotFound, )):#menus.MenuError)):
            return

        e = discord.Embed(title='Command Error', colour=0xCC3366)
        e.add_field(name='Name', value=ctx.command.qualified_name)
        e.add_field(name='Author', value=f'{ctx.author} (ID: {ctx.author.id})')

        fmt = f'Channel: {ctx.channel} (ID: {ctx.channel.id})'
        if ctx.guild:
            fmt = f'{fmt}\nGuild: {ctx.guild} (ID: {ctx.guild.id})'

        e.add_field(name='Location', value=fmt, inline=False)
        e.add_field(name='Content', value=textwrap.shorten(ctx.message.content, width=512))

        exc = ''.join(traceback.format_exception(type(error), error, error.__traceback__, chain=False))
        e.description = f'```py\n{exc}\n```'
        e.timestamp = discord.utils.utcnow()
        await self.webhook.send(embed=e)

    def add_record(self, record: logging.LogRecord) -> None:
        # if self.bot.config.debug:
        #     return
        self._logging_queue.put_nowait(record)

    async def send_log_record(self, record: logging.LogRecord) -> None:
        attributes = {'INFO': '\N{INFORMATION SOURCE}\ufe0f', 'WARNING': '\N{WARNING SIGN}\ufe0f'}

        emoji = attributes.get(record.levelname, '\N{CROSS MARK}')
        #dt = datetime.datetime.utcfromtimestamp(record.created)
        dt = datetime.datetime.fromtimestamp(record.created, tz=datetime.timezone.utc)
        msg = textwrap.shorten(f'{emoji} {dctimestamp(dt)} {record.message}', width=1990)
        if record.name == 'discord.gateway':
            username = 'Gateway'
            avatar_url = 'https://i.imgur.com/4PnCKB3.png'
        else:
            username = f'{record.name} Logger'
            avatar_url = discord.utils.MISSING

        await self.webhook.send(msg, username=username, avatar_url=avatar_url)

    @commands.command(hidden=True)
    @commands.is_owner()
    async def bothealth(self, ctx: ContextU):
        """Various bot health monitoring tools."""

        # This uses a lot of private methods because there is no
        # clean way of doing this otherwise.
        HEALTHY = discord.Colour(value=0x43B581)
        UNHEALTHY = discord.Colour(value=0xF04947)
        WARNING = discord.Colour(value=0xF09E47)
        total_warnings = 0

        embed = discord.Embed(title='Bot Health Report', colour=HEALTHY)

        # Check the connection pool health.
        # pool = self.bot.pool
        # total_waiting = len(pool._queue._getters)  # type: ignore
        # current_generation = pool._generation

        # description = [
        #     f'Total `Pool.acquire` Waiters: {total_waiting}',
        #     f'Current Pool Generation: {current_generation}',
        #     f'Connections In Use: {len(pool._holders) - pool._queue.qsize()}',  # type: ignore
        # ]

        
        description = [

        ]

        # questionable_connections = 0
        # connection_value = []
        # for index, holder in enumerate(pool._holders, start=1):
        #     generation = holder._generation
        #     in_use = holder._in_use is not None
        #     is_closed = holder._con is None or holder._con.is_closed()
        #     display = f'gen={holder._generation} in_use={in_use} closed={is_closed}'
        #     questionable_connections += any((in_use, generation != current_generation))
        #     connection_value.append(f'<Holder i={index} {display}>')

        #joined_value = '\n'.join(connection_value)
        #embed.add_field(name='Connections', value=f'```py\n{joined_value}\n```', inline=False)

        spam_control = self.bot.spam_control
        being_spammed = [str(key) for key, value in spam_control._cache.items() if value._tokens == 0]

        description.append(f'''Current Spammers: {", ".join(['`'+str(x)+'`' for x in being_spammed]) if being_spammed else "`None`"}''')
        #description.append(f'Questionable Connections: {questionable_connections}')

        #total_warnings += questionable_connections
        if being_spammed:
            embed.colour = WARNING
            total_warnings += 1

        all_tasks = asyncio.all_tasks(loop=self.bot.loop)
        event_tasks = [t for t in all_tasks if 'Client._run_event' in repr(t) and not t.done()]

        cogs_directory = os.path.dirname(__file__)
        tasks_directory = os.path.join('discord', 'ext', 'tasks', '__init__.py')
        inner_tasks = [t for t in all_tasks if cogs_directory in repr(t) or tasks_directory in repr(t)]

        bad_inner_tasks = ", ".join(f'`{hex(id(t))}`' for t in inner_tasks if t.done() and t._exception is not None)
        total_warnings += bool(bad_inner_tasks)
        embed.add_field(name='Inner Tasks', value=f'Total: `{len(inner_tasks)}`\nFailed: `{bad_inner_tasks or "None"}`')
        embed.add_field(name='Events Waiting', value=f'Total: `{len(event_tasks)}`', inline=False)

        command_waiters = len(self._data_batch)
        is_locked = self._batch_lock.locked()
        description.append(f'Commands Waiting: `{command_waiters}`, Batch Locked: {emojidict.get(is_locked)}')

        memory_usage = self.process.memory_full_info().uss / 1024**2
        cpu_usage = self.process.cpu_percent() / psutil.cpu_count()
        embed.add_field(name='Process', value=f'`{memory_usage:.2f}` MiB\n`{cpu_usage:.2f}`% CPU', inline=False)

        global_rate_limit = not self.bot.http._global_over.is_set()
        description.append(f'Global Rate Limit: {emojidict.get(global_rate_limit)}')

        if command_waiters >= 8:
            total_warnings += 1
            embed.colour = WARNING

        if global_rate_limit or total_warnings >= 9:
            embed.colour = UNHEALTHY

        embed.set_footer(text=f'{total_warnings} warning(s)')
        embed.description = '\n'.join(description)
        await ctx.reply(embed=embed)

    @commands.command(hidden=True)
    @commands.is_owner()
    async def gateway(self, ctx: ContextU):
        """Gateway related stats."""

        yesterday = discord.utils.utcnow() - datetime.timedelta(days=1)

        # fmt: off
        identifies = {
            shard_id: sum(1 for dt in dates if dt > yesterday)
            for shard_id, dates in self.bot.identifies.items()
        }
        resumes = {
            shard_id: sum(1 for dt in dates if dt > yesterday)
            for shard_id, dates in self.bot.resumes.items()
        }
        # fmt: on

        total_identifies = sum(identifies.values())

        builder = [
            f'Total RESUMEs: {sum(resumes.values())}',
            f'Total IDENTIFYs: {total_identifies}',
        ]

        issues = 0
        if isinstance(self.bot, commands.AutoShardedBot):
            shard_count = len(self.bot.shards)
            if total_identifies > (shard_count * 10):
                issues = 2 + (total_identifies // 10) - shard_count
            else:
                issues = 0

            for shard_id, shard in self.bot.shards.items():
                badge = None
                # Shard WS closed
                # Shard Task failure
                # Shard Task complete (no failure)
                if shard.is_closed():
                    badge = emojidict.get('offline')
                    issues += 1
                elif shard._parent._task and shard._parent._task.done():
                    exc = shard._parent._task.exception()
                    if exc is not None:
                        badge = '\N{FIRE}'
                        issues += 1
                    else:
                        badge = '\U0001f504'

                if badge is None:
                    badge = emojidict.get('online')

                stats = []
                identify = identifies.get(shard_id, 0)
                resume = resumes.get(shard_id, 0)
                if resume != 0:
                    stats.append(f'R: {resume}')
                if identify != 0:
                    stats.append(f'ID: {identify}')

                if stats:
                    builder.append(f'Shard ID {shard_id}: {badge} ({", ".join(stats)})')
                else:
                    builder.append(f'Shard ID {shard_id}: {badge}')

        if issues == 0:
            colour = 0x43B581
        #elif issues < len(self.bot.shards) // 4:
        #    colour = 0xF09E47
        else:
            colour = 0xF04947

        embed = discord.Embed(colour=colour, title='Gateway (last 24 hours)')
        embed.description = '\n'.join(builder)
        embed.set_footer(text=f'{issues} warnings')
        await ctx.reply(embed=embed)

    @commands.command(hidden=True, aliases=['cancel_task'])
    @commands.is_owner()
    async def debug_task(self, ctx: ContextU, memory_id: Annotated[int, hex_value]):
        """Debug a task by a memory location."""
        task = object_at(memory_id)
        if task is None or not isinstance(task, asyncio.Task):
            return await ctx.reply(f'Could not find Task object at {hex(memory_id)}.')

        if ctx.invoked_with == 'cancel_task':
            task.cancel()
            return await ctx.reply(f'Cancelled task object {task!r}.')

        paginator = commands.Paginator(prefix='```py')
        fp = io.StringIO()
        frames = len(task.get_stack())
        paginator.add_line(f'# Total Frames: {frames}')
        task.print_stack(file=fp)

        for line in fp.getvalue().splitlines():
            paginator.add_line(line)

        for page in paginator.pages:
            await ctx.send(page)

    async def tabulate_query(self, ctx: ContextU, records: list[Commands], *args: Any):
        #records = await ctx.db.fetch(query, *args)

        if len(records) == 0:
            return await ctx.reply('No results found.')
        headers = list(records[0].__dict__.keys())
        table = danny_formats.TabularData()
        table.set_columns(headers)

        # def format_datetimes(dt: datetime.datetime) -> str:
        #     return dctimestamp(dt)
        
        table.add_rows(list(r.__dict__.values()) for r in records)
        render = table.render()

        fmt = f'```\n{render}\n```'
        if len(fmt) > 2000:
            fp = io.BytesIO(fmt.encode('utf-8'))
            await ctx.reply('Too many results...', file=discord.File(fp, 'results.txt'))
        else:
            await ctx.reply(fmt)

    @commands.group(hidden=True, invoke_without_command=True)
    @commands.is_owner()
    async def command_history(self, ctx: ContextU):
        """Command history."""
        query = """SELECT
                    id,
                    CASE failed
                        WHEN TRUE THEN command || ' [!]'
                        ELSE command
                    END AS "command",
                    to_char(used, 'Mon DD HH12:MI:SS AM') AS "invoked",
                    author_id,
                    guild_id
                   FROM "Commands"
                   ORDER BY used DESC
                   LIMIT 15;
                """
        conn = Tortoise.get_connection('default')
        query = await conn.execute_query(query, [])
        results = []
        for row in query[1]:
            results.append(await Commands.get(id=row.get('id')))

        #await self.tabulate_query(ctx, await Commands.filter(author_id=user_id).group_by('command').order_by('-used').limit(20))
        await self.tabulate_query(ctx, results)
        # await self.tabulate_query(ctx, query)
        await self.tabulate_query(ctx, await Commands.all().order_by('-used').limit(15))

    @command_history.command(name='for')
    @commands.is_owner()
    async def command_history_for(self, ctx: ContextU, days: Annotated[int, Optional[int]] = 7, *, command: str):
        """Command history for a command."""

        query = """SELECT *, t.success + t.failed AS "total"
                   FROM (
                       SELECT guild_id,
                              SUM(CASE WHEN failed THEN 0 ELSE 1 END) AS "success",
                              SUM(CASE WHEN failed THEN 1 ELSE 0 END) AS "failed"
                       FROM "Commands"
                       WHERE command=$1
                       AND used > (CURRENT_TIMESTAMP - $2::interval)
                       GROUP BY guild_id
                   ) AS t
                   ORDER BY "total" DESC
                   LIMIT 30;
                """
        
        conn = Tortoise.get_connection('default')
        query = await conn.execute_query(query, [command, days])
        results = []
        for row in query[1]:
            results.append(await Commands.get(id=row.get('id')))

        #await self.tabulate_query(ctx, await Commands.filter(author_id=user_id).group_by('command').order_by('-used').limit(20))
        await self.tabulate_query(ctx, results)

        # await self.tabulate_query(ctx, query, command, datetime.timedelta(days=days))
        await self.tabulate_query(ctx, await Commands.filter(command=command, used__gt=(discord.utils.utcnow() - datetime.timedelta(days=days))).group_by('guild').order_by('-used').limit(30))

    @command_history.command(name='guild', aliases=['server'])
    @commands.is_owner()
    async def command_history_guild(self, ctx: ContextU, guild_id: Optional[int]=None):
        """Command history for a guild."""

        if not guild_id:
            guild_id = ctx.guild.id
        assert guild_id is not None

        query = """SELECT
                        id,
                        CASE failed
                            WHEN TRUE THEN command || ' [!]'
                            ELSE command
                        END AS "command",
                        channel_id,
                        author_id,
                        used
                   FROM "Commands"
                   WHERE guild_id=$1
                   ORDER BY used DESC
                   LIMIT 15;
                """
        # await self.tabulate_query(ctx, query, guild_id)
        conn = Tortoise.get_connection('default')
        query = await conn.execute_query(query, [guild_id])
        results = []
        for row in query[1]:
            results.append(await Commands.get(id=row.get('id')))

        #await self.tabulate_query(ctx, await Commands.filter(author_id=user_id).group_by('command').order_by('-used').limit(20))
        await self.tabulate_query(ctx, results)

    @command_history.command(name='user', aliases=['member'])
    @commands.is_owner()
    async def command_history_user(self, ctx: ContextU, user_id: int):
        """Command history for a user."""

        query = """SELECT
                        id,
                        CASE failed
                            WHEN TRUE THEN command || ' [!]'
                            ELSE command
                        END AS "command",
                    *
                   FROM "Commands"
                   WHERE author_id=$1
                   ORDER BY used DESC
                   LIMIT 20;
                """
        # await self.tabulate_query(ctx, query, user_id)
        conn = Tortoise.get_connection('default')
        query = await conn.execute_query(query, [user_id])
        results = []
        for row in query[1]:
            results.append(await Commands.get(id=row.get('id')))

        #await self.tabulate_query(ctx, await Commands.filter(author_id=user_id).group_by('command').order_by('-used').limit(20))
        await self.tabulate_query(ctx, results)

    @command_history.command(name='log')
    @commands.is_owner()
    async def command_history_log(self, ctx: ContextU, days: int = 7):
        """Command history log for the last N days."""

        # query = """SELECT command, COUNT(*)
        #            FROM "Commands"
        #            WHERE used > (CURRENT_TIMESTAMP - $1::interval)
        #            GROUP BY command
        #            ORDER BY 2 DESC
        #         """

        all_commands = {c.qualified_name: 0 for c in self.bot.walk_commands()}

        #records = await ctx.db.fetch(query, datetime.timedelta(days=days))
        records = await Commands.filter(used__gt=(discord.utils.utcnow() - datetime.timedelta(days=days))).group_by('command','used', 'kwargs', 'uses', 'args').order_by('-used')
        records_dict = {}
        for record in records:
            if record.command not in records_dict.keys():
                records_dict[record.command] = 1
            else:
                records_dict[record.command] += 1

        for name, uses in records_dict.items():
            if name in all_commands:
                all_commands[name] = uses

        as_data = sorted(all_commands.items(), key=lambda t: t[1], reverse=True)
        table = danny_formats.TabularData()
        table.set_columns(['Command', 'Uses'])
        table.add_rows(tup for tup in as_data)
        render = table.render()

        embed = discord.Embed(title='Summary', colour=discord.Colour.green())
        embed.set_footer(text='Since').timestamp = discord.utils.utcnow() - datetime.timedelta(days=days)

        top_ten = '\n'.join(f'{command}: {uses}' for command, uses in records[:10])
        bottom_ten = '\n'.join(f'{command}: {uses}' for command, uses in records[-10:])
        embed.add_field(name='Top 10', value=top_ten)
        embed.add_field(name='Bottom 10', value=bottom_ten)

        unused = ', '.join(name for name, uses in as_data if uses == 0)
        if len(unused) > 1024:
            unused = 'Way too many...'

        embed.add_field(name='Unused', value=unused, inline=False)

        await ctx.reply(embed=embed, file=discord.File(io.BytesIO(render.encode()), filename='full_results.txt'))

    @command_history.command(name='cog')
    @commands.is_owner()
    async def command_history_cog(self, ctx: ContextU, days: Annotated[int, Optional[int]] = 7, *, cog_name: Optional[str] = None):
        """Command history for a cog or grouped by a cog."""

        interval = datetime.timedelta(days=days)
        if cog_name is not None:
            cog = self.bot.get_cog(cog_name)
            if cog is None:
                return await ctx.reply(f'Unknown cog: {cog_name}')

            # query = """SELECT *, t.success + t.failed AS "total"
            #            FROM (
            #                SELECT command,
            #                       SUM(CASE WHEN failed THEN 0 ELSE 1 END) AS "success",
            #                       SUM(CASE WHEN failed THEN 1 ELSE 0 END) AS "failed"
            #                FROM "Commands"
            #                WHERE command = any($1::text[])
            #                AND used > (CURRENT_TIMESTAMP - $2::interval)
            #                GROUP BY command
            #            ) AS t
            #            ORDER BY "total" DESC
            #            LIMIT 30;
            #         """
            # return await self.tabulate_query(ctx, query, [c.qualified_name for c in cog.walk_commands()], interval)
            return await self.tabulate_query(ctx, await Commands.filter(command__in=[c.qualified_name for c in cog.walk_commands()], used__gt=(discord.utils.utcnow() - interval)).group_by('command').order_by('-used').limit(30))

        # A more manual query with a manual grouper.
        # query = """SELECT *, t.success + t.failed AS "total"
        #            FROM (
        #                SELECT command,
        #                       SUM(CASE WHEN failed THEN 0 ELSE 1 END) AS "success",
        #                       SUM(CASE WHEN failed THEN 1 ELSE 0 END) AS "failed"
        #                FROM "Commands"
        #                WHERE used > (CURRENT_TIMESTAMP - $1::interval)
        #                GROUP BY command
        #            ) AS t;
        #         """

        # class Count:
        #     __slots__ = ('success', 'failed', 'total')

        #     def __init__(self):
        #         self.success = 0
        #         self.failed = 0
        #         self.total = 0

        #     def add(self, record):
        #         self.success += record['success']
        #         self.failed += record['failed']
        #         self.total += record['total']

        # data = defaultdict(Count)
        # records = await ctx.db.fetch(query, interval)
        # for record in records:
        #     command = self.bot.get_command(record['command'])
        #     if command is None or command.cog is None:
        #         data['No Cog'].add(record)
        #     else:
        #         data[command.cog.qualified_name].add(record)

        # table = formats.TabularData()
        # table.set_columns(['Cog', 'Success', 'Failed', 'Total'])
        # data = sorted([(cog, e.success, e.failed, e.total) for cog, e in data.items()], key=lambda t: t[-1], reverse=True)

        # table.add_rows(data)
        # render = table.render()
        # await ctx.safe_send(f'```\n{render}\n```')


old_on_error = commands.AutoShardedBot.on_error


async def on_error(self, event: str, *args: Any, **kwargs: Any) -> None:
    (exc_type, exc, tb) = sys.exc_info()
    # Silence command errors that somehow get bubbled up far enough here
    if isinstance(exc, commands.CommandInvokeError):
        return

    e = discord.Embed(title='Event Error', colour=0xA32952)
    e.add_field(name='Event', value=event)
    trace = "".join(traceback.format_exception(exc_type, exc, tb))
    e.description = f'```py\n{trace}\n```'
    e.timestamp = discord.utils.utcnow()

    args_str = ['```py']
    for index, arg in enumerate(args):
        args_str.append(f'[{index}]: {arg!r}')
    args_str.append('```')
    e.add_field(name='Args', value='\n'.join(args_str), inline=False)
    hook = self.get_cog('Stats').webhook
    try:
        await hook.send(embed=e)
    except:
        pass


async def on_app_command_error(interaction: discord.Interaction, error: discord.app_commands.AppCommandError, /) -> None:
    command = interaction.command
    error = getattr(error, 'original', error)

    if isinstance(error, (discord.Forbidden, discord.NotFound, )):#menus.MenuError)):
        return

    hook = interaction.client.get_cog('Stats').webhook  # type: ignore
    e = discord.Embed(title='App Command Error', colour=0xCC3366)

    if command is not None:
        if command._has_any_error_handlers():
            return

        e.add_field(name='Name', value=command.qualified_name)

    e.add_field(name='User', value=f'{interaction.user} (ID: {interaction.user.id})')

    fmt = f'Channel: {interaction.channel} (ID: {interaction.channel_id})'
    if interaction.guild:
        fmt = f'{fmt}\nGuild: {interaction.guild} (ID: {interaction.guild.id})'

    e.add_field(name='Location', value=fmt, inline=False)
    e.add_field(name='Namespace', value=' '.join(f'{k}: {v!r}' for k, v in interaction.namespace), inline=False)

    exc = ''.join(traceback.format_exception(type(error), error, error.__traceback__, chain=False))
    e.description = f'```py\n{exc}\n```'
    e.timestamp = interaction.created_at

    try:
        await hook.send(embed=e)
    except:
        pass


async def setup(bot: BotU):
    if not hasattr(bot, 'command_stats'):
        bot.command_stats = Counter()

    if not hasattr(bot, 'socket_stats'):
        bot.socket_stats = Counter()

    if not hasattr(bot, 'command_types_used'):
        bot.command_types_used = Counter()

    cog = Stats(bot)
    await bot.add_cog(cog)
    bot.logging_handler = handler = LoggingHandler(cog)
    logging.getLogger().addHandler(handler)
    commands.AutoShardedBot.on_error = on_error
    bot.old_tree_error = bot.tree.on_error  # type: ignore
    bot.tree.on_error = on_app_command_error


async def teardown(bot: BotU):
    commands.AutoShardedBot.on_error = old_on_error
    logging.getLogger().removeHandler(bot.logging_handler)
    bot.tree.on_error = bot.old_tree_error  # type: ignore
    del bot.logging_handler