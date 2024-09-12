import datetime
from typing import Any, Optional

import discord
from discord import Object, app_commands
from discord.ext import commands

from cogs.models import CommandInvocation, Commands, ReportedErrors
from cogs.ranksv2 import PlatformConverter, get_r6_tracker_url
from utils import BotU, CogU, ContextU, emojidict, makeembed, makeembed_bot

MANUAL_REVIEW_FORUM = 1253173059339288625

NORMAL_TAG_SOLVED = 1253175132256604200
NORMAL_TAG_COMPLETED = 1253174036477902933
NORMAL_TAG_ACCEPTED = 1171666153274343564
NORMAL_TAG_PENDING = 1253173654918008953
NORMAL_TAG_DENIED = 1253173460876656740
NORMAL_TAG_OTHER = 1253174183089668096

GUILDS = [1029151630215618600]

RESPONSE_REQUEST_WEBHOOK = "https://discord.com/api/webhooks/1268286302445375528/BB5wmwJzF2eVePaYlTIn68lvpZYeWaMcQSLj2sHZAY1cLJUawwO0oT3ISpIM9GA3Zaub"


def format_request_num(num: Any) -> str:
    return f"`{num}`"

class ManualReviewCog(CogU, hidden=True):
    def __init__(self, bot: BotU):
        self.bot = bot
    
    
    @commands.hybrid_group(name='request',description='Commands for managing error reports.')#,guilds=GUILDS)
    @commands.is_owner()
    #@Cooldown(1, 5, BucketType.user)
    @commands.guild_only()
    @app_commands.guilds(*GUILDS)
    async def request(self, ctx: commands.Context):
        """Commands for managing error reports."""
        pass
    
    @request.command(name='reply',description='Reply to a error report.')#,guilds=GUILDS)
    @commands.is_owner()
    @commands.guild_only()
    @app_commands.describe(
    message='The message to send to the user.',
    annonymous='Whether or not to perform this action annonymously.',
    attachment1='An Attachment to send to the user.',attachment2='An Attachment to send to the user.',attachment3='An Attachment to send to the user.',
    attachment4='An Attachment to send to the user.',attachment5='An Attachment to send to the user.',attachment6='An Attachment to send to the user.',
    attachment7='An Attachment to send to the user.',attachment8='An Attachment to send to the user.',attachment9='An Attachment to send to the user.',
    attachment10='An Attachment to send to the user.',
    )
    async def reply(self, ctx: commands.Context, *, message: str, annonymous: bool=False, 
        attachment1: Optional[discord.Attachment]=None,attachment2: Optional[discord.Attachment]=None,attachment3: Optional[discord.Attachment]=None,
        attachment4: Optional[discord.Attachment]=None,attachment5: Optional[discord.Attachment]=None,attachment6: Optional[discord.Attachment]=None,
        attachment7: Optional[discord.Attachment]=None,attachment8: Optional[discord.Attachment]=None,attachment9: Optional[discord.Attachment]=None,
        attachment10: Optional[discord.Attachment]=None):
        """Replies to an active error report."""

        await ctx.defer()
        try:
            request = await ReportedErrors.filter(forum_post_id=ctx.channel.id).first()
            assert request is not None

            if len(message) > 2000:
                return await ctx.reply("Your message is too long.")

            user = await self.bot.getorfetch_user(request.user_id,ctx.guild)

            dm = await self.bot.getorfetch_dm(user)

            replyer = str(ctx.author) if not annonymous else 'The Developers'

            # desc = f"""> {emojidict.get('person')} | Reply from {replyer}:\n"""
            
            # desc += f"> ```{message}```\n"
            desc = message

            desc += f"\n> To reply, put `[#{format_request_num(request.error_id)}]` at the beginning of your message.\n"
            
            emb = makeembed(
                author=replyer,
                author_icon_url=ctx.author.avatar.url if not annonymous else None,
                timestamp=datetime.datetime.now(),
                description=desc,
                footer=f"Reported Error #{request.error_id}",
                color=discord.Colour.brand_green()
            )

            # attachments: Optional[Union[discord.File, List[discord.File]]] = []
            # for x in [attachment1, attachment2, attachment3, attachment4, attachment5, attachment6, attachment7, attachment8, attachment9, attachment10]:
            #     if x is not None: attachments.append(await x.to_file())
            files = []
            for x in [attachment1, attachment2, attachment3, attachment4, attachment5, attachment6, attachment7, attachment8, attachment9, attachment10]:
                if x is not None: 
                    files.append(await x.to_file())
            
            # if len(attachments) == 1:
            #     attachments = attachments[0]
            try:
                #await dm.send(content=str(message), embed=emb, files=attachments)
                await dm.send(embed=emb, files=files)
            except discord.Forbidden:
                return await ctx.reply("I was unable to DM the user.")
            
            await ctx.reply("Successfully sent message to user.")

        except AssertionError:
            return await ctx.reply("This command can only be run in a error report thread.")

    @request.command(name='complete',description='Complete a error report.')#,guilds=GUILDS)
    @commands.is_owner()
    @commands.guild_only()
    @app_commands.describe(annonymous='Whether or not to perform this action annonymously.')
    async def solved(self, ctx: commands.Context, reason: Optional[str]=None, annonymous: bool=False):
        """Marks a error report as complete."""
        await ctx.defer()

        try:
            thread: discord.Thread = ctx.channel # type: ignore

            request = await ReportedErrors.filter(forum_post_id=ctx.channel.id).first()

            if request is None:
                return await ctx.reply("This thread is not a error report.")
            
            request.resolved = True
            await request.save()

            try:
                dm = await self.bot.getorfetch_dm(await self.bot.getorfetch_user(request.user_id,ctx.guild))
                desc = f"Your error report `#{format_request_num(request.error_id)}` has been marked as completed{f' by {ctx.author} ({ctx.author.mention})' if annonymous else ''}."
                if reason:
                    desc += f"\nReason: `{reason}`"
                emb = makeembed(
                    title='Your error report has been completed.',
                    description=desc,
                    color=discord.Colour.dark_gray(),
                    timestamp=datetime.datetime.now(),
                    footer=f"Reported Error #{format_request_num(request.error_id)}",
                )
                await dm.send(embed=emb)
            except Exception:
                await ctx.reply("I was unable to DM the user.")
            
            m = thread.starter_message
            if m is None:
                m = [x async for x in thread.history(limit=1,oldest_first=True)][0]
            
            emb = m.embeds[0].copy()
            emb.set_field_at(3,name='Status',value='Completed',inline=True)
            emb.color = discord.Colour.brand_green()

            await m.edit(content=m.content,embed=emb)

            await ctx.reply(f"Successfully marked error review `#{format_request_num(request.error_id)}` as completed.")
            
            await thread.edit(
                archived=True,
                locked=True,
                applied_tags=[Object(NORMAL_TAG_COMPLETED), Object(NORMAL_TAG_SOLVED)], # type: ignore
                reason=f'Marked as complete by {ctx.author}.',
            )
        except AssertionError:
            return await ctx.reply("This command can only be run in a error report thread.")

    @request.command(name='deny',description='Deny a error report.')#,guilds=GUILDS)
    @commands.is_owner()
    @commands.guild_only()
    @app_commands.describe(annonymous='Whether or not to perform this action annonymously.')
    async def deny(self, ctx: commands.Context, reason: Optional[str]=None, annonymous: bool=False):
        """Denies a error report."""
        await ctx.defer()

        try:
            assert isinstance(ctx.channel, discord.Thread)

            thread: discord.Thread = ctx.channel
            
            if not await ReportedErrors.filter(forum_post_id=ctx.channel.id).exists():
                return await ctx.reply("This thread is not a error report.")
            
            request = await ReportedErrors.filter(forum_post_id=ctx.channel.id).first()

            if request is None:
                return await ctx.reply("This thread is not a error report.")
            
            if request.resolved:
                return await ctx.reply("This request has already been completed.")

            request.resolved = True
            await request.save()

            try:
                dm = await self.bot.getorfetch_dm(await self.bot.getorfetch_user(request.user_id,ctx.guild))
                desc = f"Your error report `#{format_request_num(request.error_id)}` has been marked as denied{f' by {ctx.author} ({ctx.author.mention})' if annonymous else ''}."
                if reason:
                    desc += f"\nReason: `{reason}`"
                emb = makeembed(
                    title='Your error report has been denied.',
                    description=desc,
                    color=discord.Colour.brand_red(),
                    timestamp=datetime.datetime.now(),
                    footer=f"Reported Error #{format_request_num(request.error_id)}",
                )
                await dm.send(embed=emb)
            except Exception:
                await ctx.reply("I was unable to DM the user.")
            
            # m = thread.starter_message
            # if m is None:
            #     m = [x async for x in thread.history(limit=1,oldest_first=True)][0]
            
            # # emb = m.embeds[0].copy()
            # # emb.set_field_at(3,name='Status',value='Denied',inline=True)
            # emb.color = discord.Colour.brand_red()

            await m.edit(content=m.content,embed=emb)
            
            await thread.edit(
                archived=True,
                locked=True,
                applied_tags=[Object(id=NORMAL_TAG_DENIED),Object(id=NORMAL_TAG_SOLVED)], # type: ignore
                reason=f'Marked as denied by {ctx.author}.',
            )
            await ctx.reply(f"Successfully marked request `#{format_request_num(request.error_id)}` as denied.")
        except AssertionError:
            return await ctx.reply("This command can only be run in a error report thread.")

    @request.command(name='reopen',description='Reopen a error report.')#,guilds=GUILDS)
    @commands.is_owner()
    @commands.guild_only()
    @app_commands.describe(annonymous='Whether or not to perform this action annonymously.')
    async def reopen(self, ctx: commands.Context, reason: Optional[str]=None, annonymous: bool=False):
        """Reopen a closed error report."""
        await ctx.defer()

        thread: discord.Thread = ctx.channel # type: ignore

        request = await ReportedErrors.filter(forum_post_id=ctx.channel.id).first()

        if request is None:
            return await ctx.reply("This thread is not a error report.")

        if not request.resolved:
            return await ctx.reply("This request is still open.")
        
        request.resolved = False
        await request.save()

        try:
            dm = await self.bot.getorfetch_dm(await self.bot.getorfetch_user(request.user_id,ctx.guild))
            desc = f"Your error report `#{format_request_num(request.error_id)}` has been reopened{f' by {ctx.author} ({ctx.author.mention})' if annonymous else ''}."
            if reason:
                desc += f"\nReason: `{reason}`"
            emb = makeembed(
                title='Your error report has been reopened.',
                description=desc,
                color=discord.Colour.orange(),
                timestamp=datetime.datetime.now(),
                footer=f"Reported Error #{format_request_num(request.error_id)}",
            )
            await dm.send(embed=emb)
        except Exception:
            await ctx.reply("I was unable to DM the user.")
        
        # m = thread.starter_message
        # if m is None:
        #     m = [x async for x in thread.history(limit=1,oldest_first=True)][0]
        
        # emb = m.embeds[0].copy()

        # emb.set_field_at(2,name='Claimed By',value=ctx.author.mention,inline=True)
        # emb.set_field_at(3,name='Status',value='In Progress',inline=True)
        # emb.color = discord.Colour.dark_gold()

        # await m.edit(content=m.content,embed=emb)

        await thread.edit(
            archived=False,
            locked=False,
        )

        await ctx.reply(f"Successfully reopened request `#{format_request_num(request.error_id)}`.")
        

    @commands.Cog.listener()
    async def on_message(self, msg: discord.Message):
        if msg.author.bot: return
        if msg.guild is None: # dm command
            assert isinstance(msg.channel, discord.DMChannel)

            if not msg.content.startswith('[#'):
                return

            # print(msg.content)
            # print(msg.content[2:])
            # print(msg.content.index(']')+1)
            # print(msg.content[msg.content.index(']'):])
            # print(msg.content[msg.content.index(']')+1:].strip())

            request_num = msg.content[2:msg.content.index(']')].strip('0').strip()

            request = await ReportedErrors.filter(request_num=request_num).first()

            if request is None:
                return await msg.reply("I was unable to find that request.")
            
            if request.resolved:
                return await msg.reply("This request has already been completed.")
            
            if request.user_id != msg.author.id:
                return await msg.reply("You did not make this request.")
            
            if msg.content.replace(f'[#{format_request_num(request_num)}]','').strip() == '':
                return await msg.reply("You must provide a message.")
            
            thread= await self.bot.getorfetch_thread(request.forum_post_id, await self.bot.getorfetch_guild(GUILDS[0]))
            assert thread is not None and isinstance(thread, discord.Thread)

            content = msg.content.replace(f'[#{format_request_num(request_num)}] ','').strip()

            try:

                wb = discord.Webhook.from_url(RESPONSE_REQUEST_WEBHOOK,client=self.bot)

                files = []

                for x in msg.attachments:
                    if x is not None:
                        files.append(await x.to_file())
                    
                await wb.send(
                    content=content,
                    username=str(msg.author),
                    avatar_url=msg.author.avatar.url,
                    thread=Object(id=request.forum_post_id),
                    wait=True,
                    files=files,
                )

                await msg.add_reaction(emojidict.get(True))
            except Exception:
                await msg.add_reaction(emojidict.get(False))
                await msg.reply('I had problems sending your message. Try sending it again. If this continues please alert The Developers.')
        
        elif isinstance(msg.channel, discord.Thread) and msg.channel.parent_id == MANUAL_REVIEW_FORUM:
            if not msg.content.startswith('areply') and not msg.content.startswith('reply'): return
            if await ReportedErrors.filter(forum_post_id=msg.channel.id).exists() and not (await ReportedErrors.filter(forum_post_id=msg.channel.id).first()).resolved:
                request = await ReportedErrors.filter(forum_post_id=msg.channel.id).first()
                assert request is not None
                
                annonymous = msg.content.startswith('areply ')

                user = await self.bot.getorfetch_user(request.user_id,msg.guild)

                dm = await self.bot.getorfetch_dm(user)

                replyer = str(msg.author) if not annonymous else 'The Developers'

                # desc = f"""> {emojidict.get('person')} | Reply from {replyer}:\n"""
                
                # desc += f"> ```{message}```\n"
                message = msg.content.replace('areply ','').replace('reply ','')

                desc = message

                desc += f"\n> To reply, put `[#{format_request_num(request.error_id)}]` at the beginning of your message.\n"
                
                emb = makeembed_bot(
                    author=replyer,
                    author_icon_url=msg.author.avatar.url if not annonymous else None,
                    timestamp=datetime.datetime.now(),
                    description=desc,
                    footer=f"Reported Error #{format_request_num(request.error_id)}",
                    color=discord.Colour.brand_green()
                )

                # if len(attachments) == 1:
                #     attachments = attachments[0]
                try:
                    #await dm.send(content=str(message), embed=emb, files=attachments)
                    await dm.send(embed=emb, files=[await x.to_file() for x in msg.attachments])
                except Exception:
                    return await msg.reply("I was unable to DM the user.")
                
                await msg.reply("Successfully sent message to user.")

    @commands.group(name='commandinvocation', description='Command invocation', aliases=['ci'],hidden=True)
    @commands.is_owner()
    @commands.guild_only()
    async def commandinvocation(self, ctx: commands.Context):
        """Commands for managing command invocations."""
        pass

    @commandinvocation.command(name='list',description='List command invocations.',aliases=['ls'])
    # @app_commands.describe(
    #     user='The user to list command invocations for.',
    #     guild='The guild to list invocations for.',
    #     channel='The channel to list invocations for.',
    #     limit='The number of invocations to list.',
    #     offset='The number of invocations to skip.',
    # )
    async def list_commandinvocation(self, ctx: commands.Context, user: Optional[discord.User]=None, guild: Optional[discord.Guild]=None, channel: Optional[discord.TextChannel]=None, limit: int=10, offset: int=0):
        """List command invocations."""
        await ctx.defer()
        query = {}
        if user is not None:
            query['author'] = user.id
        if guild is not None:
            query['guild'] = guild.id
        if channel is not None:
            query['channel'] = channel.id
        
        invocations = await Commands.filter(**query).limit(limit).offset(offset)
        
        if not invocations:
            return await ctx.reply("No invocations found.")
        
        emb = makeembed(
            title='Command Invocations',
            description='\n'.join([f"`{x.used.strftime('%Y-%m-%d %H:%M:%S')}` | `{x.command_id}` | `{x.command}` | `{x.author}` | `{x.guild_id}` | `{x.channel_id}`" for x in invocations]),
            color=discord.Colour.dark_gold(),
            timestamp=datetime.datetime.now(),
            footer=f"Showing {len(invocations)} of {await Commands.filter(**query).count()} invocations.",
        )
        await ctx.reply(embed=emb)

    @commandinvocation.command(name='get',description='Get a command invocation.',aliases=['g'])
    async def get_commandinvocation(self, ctx: commands.Context, transaction_id: str):
        """Get a command invocation."""
        await ctx.defer()
        invocation = await Commands.filter(transaction_id=transaction_id).first()
        if invocation is None:
            invocation = await CommandInvocation.filter(transaction_id=transaction_id).first()
            if invocation is None:
                return await ctx.reply("No invocation found.")
        
        emb = makeembed(
            title='Command Invocation',
            description=f"```{invocation.command}```",
            color=discord.Colour.dark_gold(),
            timestamp=datetime.datetime.now(),
            footer=f"Command ID: {invocation.command_id}",
        )
        emb.add_field(name='Command',value=invocation.command).add_field(name='User ID',value=invocation.user_id,inline=True).add_field(name='Guild ID',value=invocation.guild_id,inline=True).add_field(name='Channel ID',value=invocation.channel_id,inline=True)
        emb.add_field(name='Slash Command',value=invocation.prefix == '/',inline=True)#.add_field(name='Transaction ID',value=invocation.transaction_id,inline=True)
        emb.add_field(name='Args', value=f'`{invocation.args}`').add_field(name='Kwargs',value=f"`{invocation.kwargs}`")
        emb.add_field(name='DB', value=f'`{"Commands" if isinstance(invocation, Commands) else "CommandInvocation"}`').add_field(name='Error',value=f"`{getattr(invocation, 'error', 'N/A')}`")
        await ctx.reply(embed=emb)
    
    @commands.command(name='r6tracker',description="Get the R6 Tracker link for a user.",hidden=True)
    @commands.is_owner()
    async def r6tracker_link(self, ctx: ContextU, user: str, platform: PlatformConverter):
        await ctx.defer()

        await ctx.reply(get_r6_tracker_url(user, platform))

async def setup(bot: BotU):
    cog = ManualReviewCog(bot)
    await bot.add_cog(cog)