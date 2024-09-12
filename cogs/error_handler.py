from __future__ import annotations
import time
from typing import Dict, List, Optional, Union

import discord
from discord.ext import commands
from sentry_sdk import capture_exception, push_scope

from cogs.models import Blacklist, CommandInvocation, ReportedErrors
from cogs.ranks import SUPPORT_SERVER
from main import PROD
from utils import (
    BotU,
    CogU,
    ContextU,
    CustomBaseView,
    URLButton,
    dchyperlink,
    dctimestamp,
    generate_transaction_id,
    makeembed_bot,
    makeembed_failedaction,
    makeembed_successfulaction,
    prompt,
)

ERROR_FORUM = 1253173059339288625
TESTING_GUILD = 1029151630215618600

permission_proper_names: Dict[str, str] = {
    "add_reactions": "Add Reactions",
    "administrator": "Administrator",
    "attach_files": "Attach Files",
    "ban_members": "Ban Members",
    "change_nickname": "Change Nickname",
    "connect": "Connect",

    # master only
    "create_polls": "Create Polls",
    "create_events": "Create Events",
    "create_expressions": "Create Expressions",
    "create_instant_invite": "Create Instant Invite",
    "create_private_threads": "Create Private Threads",
    "create_public_threads": "Create Public Threads",
    "deafen_members": "Deafen Members",
    "embed_links": "Embed Links",

    "external_emojis": "Use External Emojis",
    "external_stickers": "Use External Stickers",

    "kick_members": "Kick Members",
    "manage_channels": "Manage Channels",
    
    "manage_emojis": "Manage Emojis",
    "manage_emojis_and_stickers": "Manage Emojis And Stickers",

    "manage_events": "Manage Events",
    "manage_expressions": "Manage Expressions",
    "manage_guild": "Manage Server",
    "manage_messages": "Manage Messages",
    "manage_nicknames": "Manage Nicknames",

    "manage_permissions": "Manage Permissions",
    "manage_roles": "Manage Roles",

    "manage_threads": "Manage Threads",
    "manage_webhooks": "Manage Webhooks",
    "mention_everyone": "Mention Everyone",
    "moderate_members": "Moderate Members",
    "move_members": "Move Members",
    "mute_members": "Mute Members",
    "priority_speaker": "Priority Speaker",
    "read_message_history": "Read Message History",
    "read_messages": "Read Messages",
    "request_to_speak": "Request To Speak",
    "send_messages": "Send Messages",
    "send_messages_in_threads": "Send Messages In Threads",
    "send_tts_messages": "Send TTS Messages",
    "send_voice_messages": "Send Voice Messages",
    "speak": "Speak",
    "stream": "Stream",
    "use_application_commands": "Use Application Commands",
    "use_embedded_activities": "Use Embedded Activities",

    "use_external_emojis": "Use External Emojis",
    "use_external_stickers": "Use External Stickers",

    "use_external_sounds": "Use External Sounds",
    "use_soundboard": "Use Soundboard",
    
    "use_voice_activation": "Use Voice Activity",

    # master branch only
    "use_external_apps": "Use External Apps",

    "view_audit_log": "View Audit Log",
    "view_channel": "View Channel",
    "view_guild_insights": "View Server Insights",
}

permission_descriptions: Dict[str, str] = {
    "add_reactions": "Allows members to add new emoji reactions to a message. If this permission is disabled, members can still react using any existing reactions on a message.",
    "administrator": "Members with this permission will have every permission and will also bypass all channel specific permissions or restrictions (for example, these members would get access to all private channels). **This is a dangerous permission to grant**.",
    "attach_files": "Allows members to upload files or media in text channels.",
    "ban_members": "Allows members to permanently ban and delete the message history of other members from this server.",
    "change_nickname": "Allows members to change their own nickname, a custom name for just this server.",
    "connect": "Allows members to join voice channels and hear others.",
    "create_events": "Allows members to create events.",
    "create_expressions": "Allows members to add custom emoji, stickers, and sounds in this server.",
    "create_instant_invite": "Allows members to invite new people to this server.",
    "create_private_threads": "Allow members to create invite-only threads.",
    "create_public_threads": "Allow members to create threads that everyone in a channel can view.",
    "deafen_members": "Allows members to deafen other members in voice channels, which means they won't be able to speak or hear others.",
    "embed_links": "Allows links that members share to show embedded content in text channels.",
    "external_emojis": "Allows members to use emoji from other servers, if they're a Discord Nitro member.",
    "external_stickers": "Allows members to use emoji from other servers, if they're a Discord Nitro member.",
    "kick_members": "Allows members to remove other members from this server. Kicked members will be able to rejoin if they have another invite.",
    "manage_channels": "Allows members to create, edit, or delete channels.",
    "manage_emojis": "Allows members to edit or remove custom emoji, stickers, and sounds in this server.",
    "manage_emojis_and_stickers": "Allows members to edit or remove custom emoji, stickers, and sounds in this server.",
    "manage_events": "Allows members to edit and cancel events.",
    "manage_expressions": "Allows members to edit or remove custom emoji, stickers, and sounds in this server.",
    "manage_guild": "Allow members to change this server's name, switch regions, view all invites, add apps to this server and create and update AutoMod rules.",
    "manage_messages": "Allows members to delete messages by other members or pin any message.",
    "manage_nicknames": "Allows members to change the nicknames of other members.",
    "manage_permissions": "Members with this permission can change this channel's permissions.",
    "manage_roles": "Allows members to create new roles and edit or delete roles lower than their highest role. Also allows members to change permissions of individual channels that they have access to.",
    "manage_threads": "Allows members to rename, delete, close, and turn on slow mode for threads. They can also view private threads.",
    "manage_webhooks": "Allows members to create, edit, or delete webhooks, which can post messages from other apps or sites into this server.",
    "mention_everyone": "Allows members to use @everyone (everyone in the server) or @here (only online members in that channel). They can also @mention all roles, even if the role's 'Allow anyone to mention this role' permission is disabled.",
    "moderate_members": "When you put a user in timeout they will not be able to send messages in chat, reply within threads, react to messages, or speak in voice or Stage channels.",
    "move_members": "Allows members to disconnect or move other members between voice channels that the member with this permission has access to.",
    "mute_members": "Allows members to mute other members in voice channels for everyone.",
    "priority_speaker": "Allows members to be more easily heard in voice channels. When activated, the volume of others without this permission will be automatically lowered.",
    "read_message_history": "Allows members to read previous messages sent in channels. If this permission is disabled, members only see messages sent when they are online and focused on that channel.",
    "read_messages": "Allows members to view channels and messages in this server.",
    "request_to_speak": "Allow requests to speak in Stage channels. Stage moderators manually approve or deny each request.",
    "send_messages": "Allows members to send messages in text channels.",
    "send_messages_in_threads": "Allow members to send messages in threads.",
    "send_tts_messages": "Allows members to send text-to-speech messages by starting a message with /tts. These messages can be heard by anyone focused on the channel.",
    "send_voice_messages": "Allows members to send voice messages.",
    "speak": "Allows members to talk in voice channels. If this permission is disabled, members are default muted until somebody with the 'Mute Members' permission un-mutes them.",
    "stream": "Allows members to share their video, screen share, or stream a game in this server.",
    "use_application_commands": "Members with this permission can use commands from applications, including slash commands and context menu commands.",
    "use_embedded_activities": "Allows members to use Activities.",
    "use_external_emojis": "Allows members to use emoji from other servers, if they're a Discord Nitro member.",
    "use_external_sounds": "Allows members to use sounds from other servers, if they're a Discord Nitro member.",
    "use_external_stickers": "Allows members to use stickers from other servers, if they're a Discord Nitro member.",
    "use_soundboard": "Allows members to send sounds from server soundboard.",
    "use_voice_activation": "Allows members to speak in voice channels by simply talking. If this permission is disabled, members are required to use Push-to-talk. Good for controlling background noise or noisy members.",
    "view_audit_log": "Allows members to view a record of who made which changes in this server.",
    "view_channel": "Allows members to view channels by default (excluding private channels).",
    "view_guild_insights": "Allows members to view Server Insights, which shows data on community growth, engagement, and more. This will allow them to see certain data about channel activity, even for channels they cannot access.",
}

def get_permission_proper_names(permissions: Union[discord.Permissions, List[str]], sep: str=", ") -> str:
    """Gets a list of permission names from a discord.Permissions object.
    It returns a list seperated byt the `sep` argument for all permissions set to True.

    Args:
        permissions (Union[discord.Permissions, List[str]]) The permissions object or list of missing permissions.
        sep (Optional[str], optional): The seperator to use for the string. Defaults to ", ".

    Returns:
        str: The string of permission names.
    """ 
    if isinstance(permissions, list):
        perms: discord.Permissions = discord.Permissions(**{p: False for p in permissions})
    else:
        perms = permissions

    return sep.join(
        [
            permission_proper_names.get(p, '') 
            for p in dir(perms)
            if isinstance((getattr(perms, p)), bool) \
            and not getattr(perms, p, None)
        ]
    )

class ReportErrorView(CustomBaseView):
    message: Optional[discord.Message] = None

    def __init__(self, reporting_user: discord.abc.User, error_id: str, error_forum: discord.ForumChannel,  addl_buttons: List[discord.ui.Button]=[], *args, **kwargs):
        if 'message' not in kwargs:
            kwargs['message'] = None

        super().__init__(*args, **kwargs)
        self.error_id = error_id
        self.error_forum = error_forum
        self.reporting_user = reporting_user

        for button in addl_buttons:
            self.add_item(button)

    @discord.ui.button(label="Report Error", style=discord.ButtonStyle.red)
    async def report_error(self, interaction: discord.Interaction, button: discord.ui.Button,):
        await interaction.response.defer(thinking=True, ephemeral=True)

        if not self.reporting_user:
            return await interaction.followup.send("You must be the user who ran this command to report this error.")
        
        if await Blacklist.is_blacklisted(self.reporting_user.id):
            if isinstance(interaction.client, BotU):
                support_server_cmd = await interaction.client.get_command_mention("support")
            else:
                support_server_cmd = "`/support`"
            return await interaction.followup.send(f"You are blacklisted from reporting errors. If you believe this is a mistake, please contact the developers in the support server. See {support_server_cmd} for more information.")

        confirm = await prompt(
            interaction,
            "Are you sure that you want to report this error? Note that misuse/spam of this feature may result in a blacklist.",
            author_id=interaction.user.id,
            delete_after=True,
        )

        if confirm:
            emb = makeembed_bot(
                title="Error Report",
                color=discord.Color.red(),
            )
            emb.add_field(name="Error ID", value=f"`{self.error_id}`")
            emb.add_field(name="User", value=f"{self.reporting_user.mention} (`{self.reporting_user.name}`)")
            emb.add_field(name="Guild", value=f"`{interaction.guild.name}` (`{interaction.guild.id}`)" if interaction.guild else "DMs".strip())
            emb.add_field(name="Channel", value=f"`#{interaction.channel.name}` (`{interaction.channel.id}`)" if interaction.channel else "DMs")
            emb.add_field(name="Message", value=f"{dchyperlink(self.message.jump_url, 'Jump to Message')}" if self.message else "No message")
            #emb.add_field(name="Command", value=f"`{ctx.command.name}`")

            unconfirmed_bug_tag = discord.utils.find(lambda t: t.name.lower() == "Potential Bug".lower(), self.error_forum.available_tags)
            applied_tags = [unconfirmed_bug_tag] if unconfirmed_bug_tag else []

            thread, message = await self.error_forum.create_thread(
                name=f"{self.reporting_user.mention} ({self.reporting_user.name}) `{self.error_id}`",
                embed=emb,
                reason=f"Error reported by {self.reporting_user.id}",
                applied_tags=applied_tags,
            )

            reported_error = await ReportedErrors.create(
                error_id=str(self.error_id),
                user_id=self.reporting_user.id,

                forum_id=self.error_forum.id,
                forum_post_id=thread.id,
                forum_initial_message_id=message.id,
                error_message=None,
            )

            emb = makeembed_successfulaction(description="The error has been reported to the developers. Thank you for your help.")
            msg = await interaction.followup.send(embed=emb, ephemeral=True, wait=True)

            assert isinstance(interaction.client, BotU)
            ch = await interaction.client.getorfetch_dm(interaction.user)

            try:
                emb = makeembed_bot(f'Reported Error: `{self.error_id}`',description=f"You just submitted an error for manual review (`{self.error_id}`). A Developer  will be back with you in up to 48 hours either with followup questions or a success message.")
                await ch.send(embed=emb)
            except:
                await msg.reply("The bot just tried to DM you, but your DM settings are closed. Please open them or you will be unable to recieve updates and questions relating to your error request..",)
            
            button.disabled = True
        elif confirm is None:
            emb = makeembed_failedaction(
                description="Not reporting error: Timed out."
            )
        else:
            emb = makeembed_failedaction(
                description="Not reporting error: Did not confirm."
            )
        
        await interaction.followup.send(embed=emb, ephemeral=True)

class ErrorHandler(CogU, hidden=True):
    bot: BotU

    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_command_error(self, ctx: ContextU, error: commands.CommandError):
        """The event triggered when an error is raised while invoking a command.
        Parameters
        ------------
        ctx: commands.Context
            The context used for command invocation.
        error: commands.CommandError
            The Exception raised.
        """

        invocation = await CommandInvocation.filter(command_id=ctx.interaction.id if ctx.interaction else ctx.message.id).first()

        if invocation:
            error_id = invocation.transaction_id
        else:
            error_id = generate_transaction_id(guild_id=ctx.guild.id if ctx.guild else 0, user_id=ctx.author.id)

        # This prevents any commands with local handlers being handled here in on_command_error.
        if hasattr(ctx.command, "on_error"):
            return

        # This prevents any cogs with an overwritten cog_command_error being handled here.
        cog = ctx.cog
        if cog:
            if cog._get_overridden_method(cog.cog_command_error) is not None:
                return

        view = None

        ignored = (commands.CommandNotFound, commands.NotOwner)

        # Allows us to check for original exceptions raised and sent to CommandInvokeError.
        # If nothing is found. We keep the exception passed to on_command_error.
        error = getattr(error, "original", error)

        kwargs = {
            "ephemeral": True,
            "delete_after": 10.0 if not ctx.interaction else None,
        }
        # kwargs = {}

        message = None

        # Anything in ignored will return and prevent anything happening.
        if isinstance(error, ignored):
            return

        if isinstance(error, commands.DisabledCommand):
            message = f"{ctx.command} has been disabled."

        elif isinstance(error, commands.NoPrivateMessage):
            kwargs = {}
            message = f"{ctx.command} can not be used in Private Messages."

        # elif isinstance(error, commands.MissingPermissions):
        #     message = f"You are missing the following permissions: {', '.join(error.missing_permissions)}"

        # elif isinstance(error, commands.BotMissingPermissions):
        #     message = f"I am missing the following permissions: {', '.join(error.missing_permissions)}"

        elif isinstance(error, (commands.MissingPermissions, commands.BotMissingPermissions)):
            #missing_perms = discord.Permissions(**{p: False for p in error.missing_permissions})
            #missing_perms_str = f"`{get_permission_proper_names(missing_perms, sep='`, `')}`"
            missing_perms_str = f"`{get_permission_proper_names(error.missing_permissions, sep='`, `')}`"
            message = f"{'You are' if isinstance(error, commands.MissingPermissions) else 'I am'} missing the following permissions: {missing_perms_str}"

        elif isinstance(error, commands.NotOwner):
            message = "You must be the owner of this bot to use this command."

        elif isinstance(error, commands.BadArgument):
            # message = 'Invalid argument. Please try again.'
            message = str(error)

        elif isinstance(error, commands.CommandOnCooldown):
            message = f"This command is on cooldown. Please try again {dctimestamp(int(time.time()+error.retry_after)+1,'R')}."

        elif isinstance(error, commands.MissingRequiredArgument):
            message = str(error)
            #message = f"Missing required argument: `{error.param.name}`"

        elif isinstance(error, commands.TooManyArguments):
            message = "Too many arguments. Please try again."

        elif isinstance(error, commands.CheckFailure):
            message = str(error) or "The check for this command failed. You most likely do not have permission to use this command or are using it in the wrong channel."

        # elif isinstance(error, commands.CommandInvokeError):
        #     #message = f"An error occured while running this command. Please try again later."
        #     #traceback.print_exc()
        #     message = str(message)
        #     capture_exception(error)

        # verification errors
        # elif isinstance(error, NotLinked):
        #     message = 'You need to have your roblox account linked to do this..'
        # elif isinstance(error, AlreadyLinked):
        #     message = 'You already have your roblox account linked.'

        else:
            # All other Errors not returned come here. And we can just print the default TraceBack.
            # print(
            #     "Ignoring exception in command {}:".format(ctx.command), file=sys.stderr
            # )
            # traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)
            try:
                with push_scope() as scope:
                    # scope.set_tag("error_id", er)
                    if ctx.guild:
                        scope.set_tag("guild_id", ctx.guild.id)
                        if ctx.guild.shard_id:
                            scope.set_tag("shard_id", ctx.guild.shard_id)
                    scope.set_tag("user_id", ctx.author.id)
                    #scope.set_tag("transaction_id", error_id)
                    scope.set_tag("error_id", str(error_id))
                    scope.set_level("error")
                    scope.set_context("command", str(ctx.command.name))
                    scope.set_context("args", ctx.args or [])
                    scope.set_context("kwargs", ctx.kwargs or {})
                    capture_exception(error)
            except Exception as e:
                import traceback
                traceback.print_exc()

            kwargs['delete_after'] = None

            if isinstance(error, commands.CommandError):
                message = str(error)
            else:
                message = f"An error occured while running this command. Please try again later.\n\nIf this is a reoccuring issue, please report this error in the {dchyperlink(SUPPORT_SERVER, 'support server')}. Ensure you include the error ID specified below."
            view = URLButton(SUPPORT_SERVER, "Join the Support Server")

            if PROD:
                if not await Blacklist.is_blacklisted(ctx.author.id):
                    view = ReportErrorView(ctx.author, str(error_id), self.error_forum, addl_buttons=[discord.ui.Button(label="Join the Support Server", style=discord.ButtonStyle.url, url=SUPPORT_SERVER)], message=ctx.message)
            else:
                #import traceback
                #traceback.print_exc()
                print(error, type(error))

        emb = makeembed_failedaction(
            description=message,
            footer=f"Error ID: {error_id}",
            timestamp=discord.utils.utcnow(),
        )

        await ctx.reply(embed=emb, view=view, **kwargs)

    @commands.Cog.listener()
    async def on_ready(self):
        self.error_forum = await self.bot.getorfetch_forum(ERROR_FORUM, await self.bot.getorfetch_guild(TESTING_GUILD))

    # @commands.Cog.listener()
    # async def on_command_error(self, ctx: ContextU, error: Union[commands.CommandError, Exception]):
    #     ignored = (commands.CommandNotFound, commands.UserInputError)
    #     delete_after = (10.0 if not ctx.interaction else None)
    #     kwargs = {'ephemeral': True, 'delete_after': delete_after}
    #     if isinstance(error, ignored): return
    #     elif isinstance(error, commands.CommandInvokeError):
    #         traceback.print_exc()
    #     elif isinstance(error, InvalidUsernameException):
    #         await ctx.reply("Please enter a valid roblox username.")
    #     elif isinstance(error, commands.CommandOnCooldown):
    #         await ctx.reply(f"Command is on cooldown. Try again {dctimestamp(int(round(error.retry_after+time.time()+1)), 'R')}.",**kwargs)
    #     elif isinstance(error, commands.NotOwner):
    #         await ctx.reply("You're not my father (well creator...)",**kwargs)
    #     else:
    #         await ctx.reply(str(error),**kwargs)
    #         traceback.print_exc()

    #  @commands.Cog.listener()
    #     async def on_command_error(self, ctx: commands.Context, error: Union[commands.CommandError, Exception]):
    #         ignored = (commands.CommandNotFound, commands.UserInputError)
    #         delete_after = (10.0 if not ctx.interaction else None)
    #         kwargs = {'ephemeral': True, 'delete_after': delete_after}
    #         if isinstance(error, ignored): return
    #         elif isinstance(error, commands.CommandInvokeError):
    #             worker_important_logger.warning(traceback.format_exc())
    #         elif isinstance(error, InvalidUsernameException):
    #             await ctx.reply("Please enter a valid roblox username.")
    #         elif isinstance(error, commands.CommandOnCooldown):
    #             await ctx.reply(f"Command is on cooldown. Try again {dctimestamp(int(round(error.retry_after+time.time())), 'R')}.",**kwargs)
    #         elif isinstance(error, commands.NotOwner):
    #             await ctx.reply("You're not my father (well creator...)",**kwargs)
    #         else:
    #             await ctx.reply(str(error),**kwargs)
    #             worker_important_logger.warning(traceback.format_exc())


async def setup(bot):
    await bot.add_cog(ErrorHandler(bot))
