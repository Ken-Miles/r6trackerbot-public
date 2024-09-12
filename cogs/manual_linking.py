from __future__ import annotations
import datetime
import logging
from typing import Literal, Optional, Union

import discord
from discord.app_commands import AppCommandError
from discord.ext import commands

from cogs.models import R6User, R6UserConnections
from cogs.ranks import ID_RE, clean_username
from cogs.ranks import ApiCog
from cogs.ranksv2 import ApiCogV2, Platform
from utils import (
    BotU,
    CTX_MENU_GUILDS,
    CogU,
    ContextU,
    USERNAME_CHANNEL,
    emojidict,
    makeembed_bot,
    makeembed_successfulaction,
    makeembed_failedaction,
)
class ManualLinking(CogU, name="Manual Linking", hidden=True):
    bot: BotU
    rank_cog: ApiCog

    def __init__(self, bot: BotU):
        self.bot = bot

        self.bot.tree.add_command(
            discord.app_commands.ContextMenu(
                name="Link Discord to Xbox",
                callback=self.link_discord_xbox_ctx_menu,
            ),
            guilds=CTX_MENU_GUILDS,
        )
        self.bot.tree.add_command(
            discord.app_commands.ContextMenu(
                name="Link Discord to PSN",
                callback=self.link_discord_ps_ctx_menu,
            ),
            guilds=CTX_MENU_GUILDS,
        )
        self.bot.tree.add_command(
            discord.app_commands.ContextMenu(
                name="Link Discord to UPlay",
                callback=self.link_discord_uplay_ctx_menu,
            ),
            guilds=CTX_MENU_GUILDS,
        )

        self.linking_last_posted = datetime.datetime.now()

    @commands.command(
        name="linkdiscord",
        description="Link your Discord account to your R6 account.",
        hidden=True,
    )
    @commands.is_owner()
    async def link_discord_cmd(
        self,
        ctx: ContextU,
        discorduser: discord.User,
        id_or_username: str,
        platform: Literal["UPlay", "Xbox", "PSN"] = "UPlay",
    ):
        """
        Link your Discord account to your R6 account.
        """
        assert isinstance(discorduser, discord.abc.User)
        await self.link_discord(
            ctx, discorduser, id_or_username, None, Platform.from_str(platform), ctx.author
        )
        await ctx.message.delete()

    @commands.hybrid_command(name="unlink", description="Unlink your Discord account from your R6 account.")
    async def unlink(
        self, ctx: ContextU, 
    ):
        """
        Unlink your Discord account from your R6 account.
        """
        await ctx.defer(ephemeral=True)

        if not await R6UserConnections.filter(platform="discord", platform_id=ctx.author.id).exists():
            return await ctx.reply(
                embed=makeembed_failedaction(
                    title="Not Linked",
                    description="Your Discord account is not linked to any R6 account.",
                    color=discord.Color.red(),
                ),
            )
        
        connection = await R6UserConnections.filter(platform="discord", platform_id=ctx.author.id).first()
        if connection:
            await connection.delete()

        await ctx.reply(
            embed=makeembed_successfulaction(
                description="Your Discord account has been unlinked from your R6 account.",
            ),
        )

    @commands.hybrid_command(name="unlinkdiscord", description="Unlink your Discord account from your R6 account.", hidden=True)
    @commands.is_owner()
    async def unlink_discord(
        self, ctx: ContextU, user: discord.User,
    ):
        """
        Unlink your Discord account from your R6 account.
        """
        await ctx.defer(ephemeral=True)

        if not await R6UserConnections.filter(platform="discord", platform_id=user.id).exists():
            return await ctx.reply(
                embed=makeembed_failedaction(
                    title="Not Linked",
                    description="Your Discord account is not linked to any R6 account.",
                    color=discord.Color.red(),
                ),
            )
        
        connection = await R6UserConnections.filter(platform="discord", platform_id=user.id).first()
        if connection:
            await connection.delete()

        await ctx.reply(
            embed=makeembed_successfulaction(
                description="Your Discord account has been unlinked from your R6 account.",
            ),
        )

    async def link_discord(
        self,
        ctx: Union[ContextU, discord.Message],
        discord_user: discord.abc.User,
        username_or_id: str,
        message: Optional[discord.Message],
        platform: Platform = Platform.UPLAY,
        linked_by: Optional[Union[discord.abc.User, int]] = None,
    ) -> bool:
        if await R6UserConnections.filter(
            platform="discord", platform_id=discord_user.id
        ).exists():
            await ctx.reply(
                f"{discord_user.mention}",
                embed=makeembed_bot(
                    title="Already Linked",
                    description="Your Discord account is already linked.",
                    color=discord.Color.yellow(),
                ),
                #delete_after=10,
            )
            if message:
                await message.delete()
            return False

        username_or_id = clean_username(username_or_id)

        id = None

        if not ID_RE.match(username_or_id):
            if platform.username_re.match(username_or_id):
                try:
                    id = await self.rank_cog.get_ubi_id(platform, username_or_id)
                except ValueError:
                    await ctx.reply(
                        f"{discord_user.mention}",
                        embed=makeembed_bot(
                            title="Invalid Username",
                            description=f"Username `{username_or_id}` was not found.",
                            color=discord.Color.red(),
                        ),
                    )
                    return False
            else:
                await ctx.reply(
                    f"{discord_user.mention}",
                    embed=makeembed_bot(
                        title="Invalid Username",
                        description=f"Username `{username_or_id}` was not found.",
                        color=discord.Color.red(),
                    ),
                    #delete_after=10,
                )
                return False
        else:
            id = username_or_id

        assert id is not None
        # if platform != Platform.UPLAY:
        #     connection = await R6UserConnections.filter(platform=platform.route, platform_id=username_or_id).first()
        #     if connection:
        #         await connection.fetch_related('profile')
        #         id = connection.profile.userid

        # await ctx.reply(embed=makeembed_bot(title="Invalid Platform", description="Only Uplay accounts can be linked.",color=discord.Color.red()),delete_after=10)
        # return False

        profile = await R6User.filter(userid=id).first()
        if not profile:
            await ctx.reply(
                f"{discord_user.mention}",
                embed=makeembed_bot(
                    title="Invalid Ubisoft ID",
                    description=f"Ubisoft ID `{id}` was not found.",
                    color=discord.Color.red(),
                ),
                #delete_after=10,
            )
            return False

        if linked_by is not None:
            if isinstance(linked_by, discord.abc.User):
                linked_by = linked_by.id
            await R6UserConnections.create(
                userid=id,
                platform="discord",
                platform_id=discord_user.id,
                name=discord_user.name,
                profile=profile,
                is_third_party=True,
                manual=True,
                linked_by=linked_by,
            )
        else:
            await R6UserConnections.create(
                userid=id,
                platform="discord",
                platform_id=discord_user.id,
                name=discord_user.name,
                profile=profile,
                is_third_party=True,
                manual=True,
            )

        await ctx.reply(
            f"{discord_user.mention}",
            embed=makeembed_bot(
                title=f"{emojidict.get(True,':check:')} Linked",
                description=f"The Discord account {discord_user.mention} has been linked to {platform.emoji} username `{username_or_id}`.",
                color=discord.Color.green(),
            ),
            #delete_after=10,
            allowed_mentions=discord.AllowedMentions.none(),
        )
        if message:
            await message.add_reaction(emojidict.get(True, ":white_check_mark:"))
        return True

    #@commands.is_owner()
    async def link_discord_xbox_ctx_menu(
        self, interaction: discord.Interaction, message: discord.Message
    ):
        return await self.link_discord_ctx_menu(
            await ContextU.from_interaction(interaction),
            message,
            Platform.XBOX,
        )

    #@commands.is_owner()
    async def link_discord_ps_ctx_menu(
        self, interaction: discord.Interaction, message: discord.Message
    ):
        return await self.link_discord_ctx_menu(
            await ContextU.from_interaction(interaction), message, Platform.PSN
        )

    #@commands.is_owner()
    async def link_discord_uplay_ctx_menu(
        self, interaction: discord.Interaction, message: discord.Message
    ):
        return await self.link_discord_ctx_menu(
            await ContextU.from_interaction(interaction), message, Platform.UPLAY
        )

    async def link_discord_ctx_menu(
        self, ctx: Union[ContextU, discord.Message], message: discord.Message, platform: Platform
    ):
        # ctx = await ContextU.from_interaction(interaction)
        if isinstance(ctx, commands.Context):
            await ctx.defer()

        content = message.content

        content = (
            content.strip()
            .replace("`", "")
            .replace("'", "")
            .replace('"', "")
            # .replace(" ", "")
            .replace("\n", "")
            .replace("\r", "")
        )
        if ":" in content:
            content = content.split(":")[-1].strip()

        # if not content:
        #     return await ctx.reply(embed=makeembed_bot(title="Invalid Ubisoft ID", description="No Ubisoft ID was found.",color=discord.Color.red()),delete_after=10)

        if platform.username_re.match(content):
            _ = await self.link_discord(
                ctx, message.author, content, message, platform, ctx.author
            )
        else:
            await ctx.reply(
                embed=makeembed_bot(
                    title="Invalid Username",
                    description=f"The username `{content}` is invalid.",
                    color=discord.Color.red(),
                ),
                delete_after=10,
            )
            await message.delete()

    async def get_rank_cog(self) -> ApiCog:
        await self.bot.wait_until_ready()

        if not hasattr(self, "rank_cog") or self.rank_cog is None:
            #self._rank_cog: Optional[commands.Cog] = self.bot.get_cog("R6 Commands") if self.bot.get_cog("R6 Commands")  else self.bot.get_cog("R6 Commands V2")
            self._rank_cog: Optional[commands.Cog] = self.bot.get_cog("R6 Commands V2") if self.bot.get_cog("R6 Commands V2") else self.bot.get_cog("R6 Commands")
            if not self._rank_cog:
                logging.error("Rank cog not found.")
                raise commands.ExtensionError("Rank cog not found.", name=self.__cog_name__)
            try:
                assert self._rank_cog is not None
            except AssertionError: 
                #traceback.print_exc()
                logging.error("Rank cog is None.")
                raise commands.ExtensionError("Rank cog is None.", name=self.__cog_name__)
            
        # if not isinstance(self._rank_cog, ApiCog):
        #     logging.error("Rank cog is not an instance of ApiCog. (type: %s)", type(self._rank_cog).__name__)
        #     raise commands.ExtensionError("Rank cog is not an instance of ApiCog. (type: %s)", type(self._rank_cog), name=self.__cog_name__)
        self.rank_cog: ApiCog = self._rank_cog # type: ignore
        return self.rank_cog

    @commands.Cog.listener()
    async def on_ready(self):
        await self.get_rank_cog()
    
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        if message.guild is None:
            return

        if discord.Object(message.guild.id) not in CTX_MENU_GUILDS:
            return
        
        if message.channel.id == USERNAME_CHANNEL:
            emb = makeembed_bot(
                title="Linking Instructions",
                description="**This is not a chat channel. Any offtopic messages will be deleted.**\nOnly type your username __once__. Your account will be linked when I get the chance.\nTo link your Discord account to your R6 account, type your username in this chat in the format shown below:\n\n`UPlay: your_username`\n`Xbox: your_username`\n`PSN: your_username`\n\nMake sure to include the platform name before your username, and to use a `:` to seperate them.\n\nExample: `UPlay: Pengu`",
                color=discord.Color.blue(),
            )

            if await R6UserConnections.filter(platform="discord", platform_id=message.author.id).exists() and not message.author.guild_permissions.manage_messages:
                await message.reply(
                    f"{message.author.mention}",
                    embed=makeembed_bot(
                        title="This is not a chat channel.",
                        description="You have already linked your Discord and Ubisoft account. Please refrain from speaking here.",
                        color=discord.Color.red(),
                    ),
                    delete_after=10,
                )
                await message.delete()
            
            if self.linking_last_posted + datetime.timedelta(seconds=10) < datetime.datetime.now():
                members = sorted(message.guild.members, key=lambda m: m.name)

                #unlinked_members = [m for m in message.guild.members if not await R6UserConnections.filter(platform="discord", platform_id=m.id).exists() and not m.bot]
                unlinked_members = []
                for member in members:
                    if not await R6UserConnections.filter(platform="discord", platform_id=member.id).exists() and not member.bot:
                        unlinked_members.append(member)

                unlinked = "\n".join(f'{m.mention} ({m.name})' for m in unlinked_members)
                emb2 = makeembed_bot(
                    title="Unlinked Users",
                    description=f"The following people still need to link their Discord to their Ubisoft:\n\n{unlinked}",
                    color=discord.Color.orange(),
                )

                history = [m async for m in message.channel.history(limit=10)]

                for m in history:
                    if m.author == self.bot.user:
                        if m.embeds:
                            if m.embeds[0].title == emb.title:
                                await m.delete()
                                break
                await message.channel.send(embeds=[emb,emb2])
                #await message.channel.send(embed=emb)
                self.linking_last_posted = datetime.datetime.now()


                if not await R6UserConnections.filter(platform="discord", platform_id=message.author.id).exists() and not message.author.guild_permissions.manage_messages:
                    if any(x in message.content.lower() for x in ['uplay', 'ubi']):
                        await self.link_discord_ctx_menu(message, message, Platform.UBI)
                    elif any(x in message.content.lower() for x in ['xbox','xbl']):
                        await self.link_discord_ctx_menu(message, message, Platform.XBOX)
                    elif any(x in message.content.lower() for x in ['psn','playstation','ps']):
                        await self.link_discord_ctx_menu(message, message, Platform.PSN)
                    else:
                        await message.reply(
                            embed=makeembed_bot(
                                title="Invalid Platform",
                                description="Please specify a platform in your message.",
                                color=discord.Color.red(),
                            ),
                        )
                        await message.delete()

            

    async def cog_app_command_error(self, interaction: discord.Interaction, error: AppCommandError):
        print(error, type(error))
        #if isinstance(error, discord)


async def setup(bot: BotU):
    cog = ManualLinking(bot)
    await bot.add_cog(cog)
