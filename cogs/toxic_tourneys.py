from __future__ import annotations
import asyncio
import random
import re
from typing import List, Optional, Tuple

import discord
from discord import SelectDefaultValue, SelectDefaultValueType, app_commands, ui
from discord.ext import commands

from cogs.error_handler import makeembed_failedaction, makeembed_successfulaction
from cogs.models import (
    R6UserConnections,
    SavedMessages,
    Settings,
    Tournaments,
    TourneyParticipants,
    TourneyTeams,
)
from cogs.ranksv2 import Platform
from main import PROD
from utils import (
    BotU,
    CogU,
    ContextU,
    Cooldown,
    CustomBaseView,
    USERNAME_CHANNEL,
    emojidict,
    makeembed_bot,
    prompt,
)

TOXIC_TOURNEYS_GUILD_ID = 1155984358537171054
TOXIC_TOURNEYS_SIGNUPS = 1155984359099215975

BOT_TESTER_ROLE = 1265453453321179177

RANDOM_TEAM_NAMES = [
    'In a come up',
    'Egirls',
    'Mcdonalds Cashiers',
    'Part Timers',
    'We forgot our name',
    'Tallest Midgets',
    'blitz all over their face',
    'Diddy party',
    'Cheesy4Skin',
]

async def update_current_participant_embed(self) -> None:
    if hasattr(self.view, 'message') and isinstance(getattr(self.view, 'message', None), discord.Message):
        message = getattr(self.view, 'message', None)
        assert isinstance(message, discord.Message)
        emb = message.embeds[0]
        field = discord.utils.find(lambda f: f.name == "# of Participants", emb.fields)
        name = "# of Participants"
        if not field:
            field = discord.utils.find(lambda f: f.name == "# of Teams", emb.fields)
            name = "# of Teams"
        field_index = emb.fields.index(field)
        emb.set_field_at(field_index, name=name, value=str(len(await self.tourney.all_participants())) if name == "# of Participants" else str(len(await TourneyTeams.filter(tournament=self.tourney))) if name == "# of Teams" else '0')
        await message.edit(embed=emb)

class TeamCreateModal(discord.ui.Modal):
    team_name = ui.TextInput(label='Team Name', style=discord.TextStyle.short, custom_id='team_name', placeholder='Enter a team name...', min_length=3, max_length=50, required=True)

    team_description = ui.TextInput(label='Team Description', style=discord.TextStyle.long, custom_id='team_description', placeholder='Enter your team description...', min_length=3, max_length=250, required=False)

    def __init__(self, view: TeamCreateView, tourney: Tournaments, user: discord.abc.User, title: str="Create a Team", custom_id: Optional[str]=None, team: Optional[TourneyTeams]=None, *args, **kwargs) -> None:
        self.view = view
        self.tourney = tourney
        self.user = user
        if not custom_id:
            custom_id = f"team_create:{tourney.id}:{user.id}"
        
        super().__init__(title=title, timeout=None, custom_id=custom_id, *args, **kwargs)

        if team:
            self.team_name.default = team.name
            self.team_description.default = team.description

            
    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True, ephemeral=True)

        team_name = self.team_name.value
        team_description = self.team_description.value
        
        return await self.view.on_modal_submit(interaction, team_name, team_description)


class TeamCreateView(CustomBaseView):
    tourney: Tournaments
    selected_users: List[discord.abc.User]

    def __init__(self, tourney: Tournaments, user: discord.abc.User, team: Optional[TourneyTeams]=None, team_members: List[TourneyParticipants]=[], *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.tourney = tourney
        self.user = user
        self.team = team

        self.user_select.min_values = self.tourney.team_size
        self.user_select.max_values = self.tourney.team_size

        if team:
            self.user_select.default_values = [SelectDefaultValue(id=x.user_id, type=SelectDefaultValueType.user) for x in team_members]
        else:
            self.user_select.default_values = [SelectDefaultValue(id=user.id, type=SelectDefaultValueType.user)]
        # max_values and min_values should be self.tourney.team_size

    @ui.select(cls=ui.UserSelect, placeholder="Select a user...", )
    async def user_select(self, interaction: discord.Interaction, select: ui.UserSelect):
        await interaction.response.defer(thinking=True, ephemeral=True)

        self.selected_users = select.values # type: ignore

        await interaction.followup.send("Saved selected users.", ephemeral=True)
    
    @ui.button(label="Edit Team", style=discord.ButtonStyle.gray, custom_id="edit", emoji=emojidict.get('notepad'))
    async def edit_button(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user != self.user:
            return await interaction.response.send_message("This button is not for you.", ephemeral=True)        
        
        await interaction.response.send_modal(TeamCreateModal(view=self, tourney=self.tourney, user=interaction.user, team=self.team))

    @ui.button(label="Deregister", style=discord.ButtonStyle.red, custom_id="cancel", emoji=emojidict.get(False))
    async def cancel_button(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer(thinking=True, ephemeral=True)
        if interaction.user != self.user:
            return await interaction.followup.send("This button is not for you.", ephemeral=True)        
        
        if await prompt(interaction, "Are you sure you want to deregister from the tournament?", delete_after=True, author_id=interaction.user.id):
            if self.team:
                for member in await self.team.all_team_members():
                   await self.team.remove_member(user_id=member.user_id)
                await self.team.delete()
            else:
                await self.tourney.remove_participant(user=interaction.user)
            #await interaction.message.delete()
            if hasattr(interaction, 'message'):
                await interaction.message.delete()
            elif self.message is not None:
                await self.message.delete()

            await interaction.followup.send(embed=makeembed_successfulaction(description="Deregistered from the tournament."), ephemeral=True)
            await update_current_participant_embed(self)
        else:
            await interaction.followup.send(embed=makeembed_failedaction(description="Did not deregister from the tournament."), ephemeral=True)

    async def on_modal_submit(self, interaction: discord.Interaction, team_name: str, team_description: Optional[str]) -> None:
        if not (user_connection := await R6UserConnections.filter(platform='discord', platform_id=interaction.user.id).first()):
            return await interaction.followup.send(embed=makeembed_failedaction(description=f'You must link your R6 account to Discord before you can sign up. Go to <#{USERNAME_CHANNEL}> and follow the instructions.'), ephemeral=True)

        if settings := (await Settings.filter(user_id=interaction.user.id).first()):
            preferred_platform = Platform.from_str(settings.preferred_platform)
        else:
            preferred_platform = Platform.from_str((await R6UserConnections.filter(userid=user_connection.userid).order_by('created_at', '-is_third_party').first()).platform)

        leader_platform_user_connection = await R6UserConnections.filter(userid=user_connection.userid, platform=preferred_platform.route).first()
        if not leader_platform_user_connection:
            return await interaction.followup.send(embed=makeembed_failedaction(description="Cannot find your preferred platform. Try using /settings and setting your preferred platform."), ephemeral=True)
        
        if not self.selected_users:
            return await interaction.followup.send(embed=makeembed_failedaction(description="You must select users before creating a team."), ephemeral=True)
        
        no_connection_users = []

        selected_users: List[Tuple[discord.abc.User, R6UserConnections]] = []

        for user in self.selected_users:
            if not (user_connection := await R6UserConnections.filter(platform='discord', platform_id=user.id).first()):
                no_connection_users.append(user)
                continue
            
            if (participant := await self.tourney.get_participant(user=user)):
                await participant.fetch_related('team')
                if participant.team and participant.team != self.team:
                    return await interaction.followup.send(embed=makeembed_failedaction(description=f"A user you selected, {user.mention}, is already on a different team."), ephemeral=True)

            if (settings := await Settings.filter(user_id=user.id).first()) and settings.preferred_platform != 'n/a':
                preferred_platform = Platform.from_str(settings.preferred_platform)
            else:
                preferred_platform = Platform.from_str((await R6UserConnections.filter(userid=user_connection.userid).order_by('created_at', '-is_third_party').first()).platform)

            platform_user_connection = await R6UserConnections.filter(userid=user_connection.userid, platform=preferred_platform.route).first()
            
            if not platform_user_connection:
                no_connection_users.append(user)
            else:
                selected_users.append((user, platform_user_connection))

        if no_connection_users:
            return await interaction.followup.send(embed=makeembed_failedaction(description=f"The following users you selected do not have their R6 account linked: {', '.join([u.mention for u in no_connection_users])}\n\nHave each of these users go to <#{USERNAME_CHANNEL}> and follow the instructions in that channel."), ephemeral=True)
        
        if self.team:
            team = self.team
            self.team.name = team_name
            self.team.description = team_description # type: ignore
            await self.team.save()
        else:
            team = await self.tourney.create_team(name=team_name, description=team_description, leader=interaction.user, leader_connection=leader_platform_user_connection)

        for team_member in await team.all_team_members():
            if team_member.user_id not in [x[0].id for x in selected_users]:
                await team.remove_member(user_id=team_member.user_id)
        
        for user_tuple in selected_users:
            user = user_tuple[0]
            user_connection = user_tuple[1]

            if not await team.get_member(user=user):
                await team.add_member(user=user, user_connection=user_connection)
        
        await interaction.followup.send(embed=makeembed_successfulaction(description=f"Team `{team.name}` has been created with {len(selected_users)} member{'s' if len(selected_users) != 1 else ''}."), ephemeral=True)


class SignupButton(discord.ui.DynamicItem[discord.ui.Button], template=r'button:tourney_signup:(?P<id>[0-9]+)'):
    def __init__(self, tourney_id: int):
        self.tourney_id = tourney_id

        super().__init__(
            discord.ui.Button(
                label="Sign Up",
                style=discord.ButtonStyle.success,
                custom_id=f"button:tourney_signup:{tourney_id}",
                emoji=f"{emojidict.get('notepad')}"
            ),
        )

    @classmethod
    async def from_custom_id(cls, interaction: discord.Interaction, item: discord.ui.Item, match: re.Match[str], /):
        tourney_id = int(match['id'])
        return cls(tourney_id)

    # async def interaction_check(self, interaction: discord.Interaction) -> bool:
    #     # Only allow the user who created the button to interact with it.
    #     #return interaction.user.id == self.user_id
    #     return True

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True, ephemeral=True)

        self.view.message = interaction.message

        self.tourney = await Tournaments.filter(id=self.tourney_id).first()

        if not self.tourney:
            await interaction.followup.send(embed=makeembed_failedaction(description='Tournament does not exist.'), ephemeral=True)
            await interaction.message.delete()
        
        assert self.tourney

        member = interaction.user

        if self.tourney.ended or (self.tourney.current_participants >= self.tourney.max_teams > 0):
            return await interaction.followup.send(embed=makeembed_failedaction(description='Tournament is closed or full.'), ephemeral=True)

        # ensure the user has their r6 linked
        if not (user_connection := await R6UserConnections.filter(platform='discord', platform_id=member.id).first()):
            return await interaction.followup.send(embed=makeembed_failedaction(description=f'You must link your R6 account to Discord before you can sign up. Go to <#{USERNAME_CHANNEL}> and follow the instructions.'), ephemeral=True)

        if (settings := await Settings.filter(user_id=member.id).first()):
            preferred_platform = Platform.from_str(settings.preferred_platform)
        else:
            preferred_platform = Platform.from_str((await R6UserConnections.filter(userid=user_connection.userid).order_by('created_at', '-is_third_party').first()).platform)

        platform_user_connection = await R6UserConnections.filter(userid=user_connection.userid, platform=preferred_platform.route).first()

        if not platform_user_connection:
            return await interaction.followup.send(embed=makeembed_failedaction(description="Cannot find your preferred platform. Try using /settings and setting your preferred platform."), ephemeral=True)
        
        if self.tourney.team_size == 1 or self.tourney.random_teams:
            if await self.tourney.get_participant(user=member):
                # try:
                #     await self.tourney.remove_participant(user=member)
                #     await interaction.followup.send("You have been deregistered for this tournament. Click the button again to sign up.", ephemeral=True)
                # except Exception as e:
                #     await interaction.followup.send(embed=makeembed_failedaction(title='Failed to deregister for the tournament.'), ephemeral=True)
                if await prompt(interaction, "You are already signed up for this tournament. Would you like to deregister?", delete_after=True, author_id=member.id):
                    await self.tourney.remove_participant(user=member)
                    await interaction.followup.send(embed=makeembed_successfulaction(description='Deregistered from the tournament.'), ephemeral=True)
                else:
                    await interaction.followup.send(embed=makeembed_successfulaction(description='Did not deregister from the tournament.'), ephemeral=True)
            else:
                await self.tourney.add_participant(user=member, user_connection=platform_user_connection)
                await interaction.followup.send(embed=makeembed_successfulaction(description=f'You have been signed up for the tournament as {emojidict.get(preferred_platform.route)} `{platform_user_connection.name}`.'), ephemeral=True)
        else:
            team = await self.tourney.get_team(leader=member)
            if team and await team.leader() != member:
                return await interaction.followup.send(embed=makeembed_failedaction(description="You are on a team already. Hit View Participants to view more information."), ephemeral=True)
            
            if team:
                team_members = await team.all_team_members() if team else []
            else:
                team_members = []

            embed = makeembed_bot(
                title="Create a Team" if not team else "Edit Team",
                description="Select members for your team. You must select the correct number of members for your team size. To save changes, click Edit Team and hit Save.",
                color=discord.Color.brand_green(),
            )
            await interaction.followup.send(embed=embed, view=TeamCreateView(tourney=self.tourney, user=member, team=team, team_members=team_members), ephemeral=True)
        await update_current_participant_embed(self)

class ViewParticipantsButton(discord.ui.DynamicItem[discord.ui.Button], template=r'button:tourney_view:(?P<id>[0-9]+)'):
    def __init__(self, tourney_id: int):
        self.tourney_id = tourney_id

        super().__init__(
            discord.ui.Button(
                label="View Participants",
                style=discord.ButtonStyle.blurple,
                custom_id=f"button:tourney_view:{tourney_id}",
                emoji="👀"
            ),
        )
    
    @classmethod
    async def from_custom_id(cls, interaction: discord.Interaction, item: discord.ui.Item, match: re.Match[str], /):
        tourney_id = int(match['id'])
        return cls(tourney_id)

    # async def interaction_check(self, interaction: discord.Interaction) -> bool:
    #     # Only allow the user who created the button to interact with it.
    #     #return interaction.user.id == self.user_id
    #     return True

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True, ephemeral=True)

        self.view.message = interaction.message

        self.tourney = await Tournaments.filter(id=self.tourney_id).first()
        if not self.tourney:
            return await interaction.followup.send(embed=makeembed_failedaction(description='Tournament does not exist.'), ephemeral=True)
        
        assert self.tourney

        if self.tourney.team_size == 1 \
            or (self.tourney.random_teams and not self.tourney.ended): # if random teams and not ended, show participants
            participants = await self.tourney.all_participants()

            participant_str = ''

            for p in participants:
                await p.fetch_related('user_connection')
                platform = Platform.from_str(p.user_connection.platform)
                participant_str += f"<@{p.user_id}> ({emojidict.get(platform.route)} `{p.user_connection.name}`)\n"
            
            if not participants:
                participant_str = f"{emojidict.get(False)} No participants signed up currently."

            emb = makeembed_bot(
                title=f"`{len(participants)}` participants for `{self.tourney.name}`",
                description=participant_str,
                color=discord.Color.brand_green() if participants else discord.Color.brand_red(),
            )
        
        else:
            teams = await TourneyTeams.filter(tournament=self.tourney)

            team_str = ''

            for team in teams:
                team_str += f"`{team.name}` (ID `{team.id}`)\n"
                for member in await team.all_team_members():
                    await member.fetch_related('user_connection')
                    platform = Platform.from_str(member.user_connection.platform)
                    team_str += f"- <@{member.user_id}> ({emojidict.get(platform.route)} `{member.user_connection.name}`)\n"
                team_str += '\n'
            
            if not teams:
                team_str = f"{emojidict.get(False)} No teams signed up currently."

            emb = makeembed_bot(
                title=f"`{len(teams)}` teams (`{sum([len(await x.all_team_members()) for x in teams])}` team members) for `{self.tourney.name}`",
                description=team_str,
                color=discord.Color.brand_green() if teams else discord.Color.brand_red(),
            )

        await interaction.followup.send(embed=emb, ephemeral=True)

        await update_current_participant_embed(self)

class CloseTourneyButton(discord.ui.DynamicItem[discord.ui.Button], template=r'button:tourney_close:(?P<id>[0-9]+)'):
    def __init__(self, tourney_id: int):
        self.tourney_id = tourney_id

        super().__init__(
            discord.ui.Button(
                label="Close Signups",
                style=discord.ButtonStyle.red,
                custom_id=f"button:tourney_close:{tourney_id}",
                emoji=emojidict.get(False)
            ),
        )
    
    @classmethod
    async def from_custom_id(cls, interaction: discord.Interaction, item: discord.ui.Item, match: re.Match[str], /):
        tourney_id = int(match['id'])
        return cls(tourney_id)

    # async def interaction_check(self, interaction: discord.Interaction) -> bool:
    #     # Only allow the user who created the button to interact with it.
    #     #return interaction.user.id == self.user_id
    #     return True

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True, ephemeral=True)

        assert interaction.guild

        if not interaction.user.guild_permissions.administrator or await interaction.client.is_owner(interaction.user):
            return await interaction.followup.send(embed=makeembed_failedaction(description="You must have the `Administrator` permission to close signups for a tournament."), ephemeral=True)

        self.view.message = interaction.message

        self.tourney = await Tournaments.filter(id=self.tourney_id).first()

        if not self.tourney:
            return await interaction.followup.send(embed=makeembed_failedaction(description='Tournament does not exist.'), ephemeral=True)

        await self.tourney.end_tournament()

        msg = interaction.message

        view = CustomBaseView.from_message(msg) # type: ignore

        for item in view.children:
            if isinstance(item, discord.ui.Button):
                if str(item.label).lower() == 'Sign Up'.lower():
                    item.disabled = True
                elif str(item.label).lower() == 'Close Signups'.lower():
                    item.disabled = True
                elif str(item.label).lower() == 'Shuffle Teams'.lower():
                    item.disabled = False
        
        await msg.edit(view=view)

        emb = makeembed_successfulaction(description=f"Closed tournament {self.tourney.name}.")

        await interaction.followup.send(embed=emb, ephemeral=True)

        await update_current_participant_embed(self)

class ShuffleTeamsButton(discord.ui.DynamicItem[discord.ui.Button], template=r'button:tourney_shuffle:(?P<id>[0-9]+)'):
    def __init__(self, tourney_id: int):
        self.tourney_id = tourney_id

        super().__init__(
            discord.ui.Button(
                label="Shuffle Teams",
                style=discord.ButtonStyle.blurple,
                custom_id=f"button:tourney_shuffle:{tourney_id}",
                emoji=emojidict.get('shuffle'),
                disabled=True,
            ),
        )
    
    @classmethod
    async def from_custom_id(cls, interaction: discord.Interaction, item: discord.ui.Item, match: re.Match[str], /):
        tourney_id = int(match['id'])
        return cls(tourney_id)

    # async def interaction_check(self, interaction: discord.Interaction) -> bool:
    #     # Only allow the user who created the button to interact with it.
    #     #return interaction.user.id == self.user_id
    #     return True

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True, ephemeral=True)

        assert interaction.guild

        if not interaction.user.guild_permissions.administrator or await interaction.client.is_owner(interaction.user):
            return await interaction.followup.send(embed=makeembed_failedaction(description="You must have the `Administrator` permission to shuffle teams for a tournament."), ephemeral=True)

        self.view.message = interaction.message

        self.tourney = await Tournaments.filter(id=self.tourney_id).first()

        if not self.tourney:
            return await interaction.followup.send(embed=makeembed_failedaction(description='Tournament does not exist.'), ephemeral=True)

        if not self.tourney.ended:
            return await interaction.followup.send(embed=makeembed_failedaction(description="You must close signups before shuffling teams."), ephemeral=True)

        # generate teams of size self.tourney.team_size from participants
        participants = await self.tourney.all_participants()

        if not participants:
            return await interaction.followup.send(embed=makeembed_failedaction(description="No participants to shuffle."), ephemeral=True)
        
        if not self.tourney.random_teams:
            return await interaction.followup.send(embed=makeembed_failedaction(description="This tournament does not have random teams enabled."), ephemeral=True)
        
        if self.tourney.team_size == 1:
            return await interaction.followup.send(embed=makeembed_failedaction(description="This tournament is not team-based."), ephemeral=True)

        if difference := (len(participants) % self.tourney.team_size) != 0:
            return await interaction.followup.send(embed=makeembed_failedaction(description=f"Participants must be divisible by the team size of {self.tourney.team_size}. (Currently have {len(participants)}, need to remove {difference}.)"), ephemeral=True)

        new_participants = participants.copy()
        random.shuffle(new_participants)

        for p in new_participants:
            await p.fetch_related('user_connection')
            await p.user_connection.fetch_related('profile')

        team_names = RANDOM_TEAM_NAMES.copy()

        current_team: List[TourneyParticipants] = []

        teams = []

        for i, p in enumerate(new_participants):
            current_team.append(p)
            if len(current_team) == self.tourney.team_size:
                if len(team_names) != 0:
                    team_name = random.choice(team_names)
                    team_names.remove(team_name)
                else:
                    team_name = f"Team {i+1}"

                team = await self.tourney.create_team(name=team_name, leader=current_team[0].user_connection.profile, leader_connection=current_team[0].user_connection)
                current_team.remove(current_team[0])
                for member in current_team:
                    await team.add_member(user=member.user_connection.profile, user_connection=member.user_connection)
                current_team = []
                teams.append(team)

        msg = interaction.message

        view = CustomBaseView.from_message(msg) # type: ignore

        await msg.edit(view=view)

        emb = makeembed_successfulaction(description=f"Shuffled teams for tournament {self.tourney.name}.")

        team_str = ''

        for team in teams:
            team_str += f"`{team.name}` (ID `{team.id}`)\n"
            for member in await team.all_team_members():
                await member.fetch_related('user_connection')
                platform = Platform.from_str(member.user_connection.platform)
                team_str += f"- <@{member.user_id}> ({emojidict.get(platform.route)} `{member.user_connection.name}`)\n"
            team_str += '\n'
        
        if not teams:
            team_str = f"{emojidict.get(False)} No teams signed up currently."

        emb2 = makeembed_bot(
            title=f"`{len(teams)}` teams (`{sum([len(await x.all_team_members()) for x in teams])}` team members) for `{self.tourney.name}`",
            description=team_str,
            color=discord.Color.brand_green() if teams else discord.Color.brand_red(),
        )

        await interaction.followup.send(embeds=[emb,emb2], ephemeral=True)

        await update_current_participant_embed(self)

class SignupsView(CustomBaseView):
    tourney: Tournaments

    def __init__(self, tourney: Tournaments, *args, **kwargs):
        self.tourney = tourney
        kwargs['timeout'] = None
        super().__init__(*args, **kwargs)
        self.add_item(SignupButton(tourney.id))
        self.add_item(ViewParticipantsButton(tourney.id))
        self.add_item(CloseTourneyButton(tourney.id))

        if tourney.random_teams:
            self.add_item(ShuffleTeamsButton(tourney.id))

class ToxicTourneysCog(CogU, name='Toxic Tourneys', hidden=True):
    bot: BotU
    toxic_guild: discord.Guild
    toxic_signups: discord.TextChannel

    def __init__(self, bot: BotU):
        self.bot = bot

        #self.bot.add_view(SignupsView())
        self.bot.add_dynamic_items(SignupButton, ViewParticipantsButton, CloseTourneyButton, ShuffleTeamsButton)

    @commands.Cog.listener()
    async def on_ready(self):
        self.toxic_guild = await self.bot.getorfetch_guild(TOXIC_TOURNEYS_GUILD_ID)
        self.toxic_signups = await self.bot.getorfetch_textchannel(TOXIC_TOURNEYS_SIGNUPS, self.toxic_guild)

    @commands.hybrid_group(name='tournament', description='Tournament Commands', aliases=['tourney'])
    @app_commands.guild_only()
    @app_commands.guilds(TOXIC_TOURNEYS_GUILD_ID, 1029151630215618600)
    async def tournament(self, ctx: ContextU):
        pass

    @tournament.command(name='create', description='Create a tournament', aliases=['make'])
    @Cooldown(1, 60, commands.BucketType.user)
    @commands.has_permissions(manage_guild=True)
    @commands.guild_only()
    @app_commands.describe(
        name="The name of the tournament.",
        team_size="The size of each team. Defaults to 1.",
        max_teams="The maximum number of participants or teams. Default is unlimited.",
        description="The description of the tournament.",
        random_teams="Whether to randomize teams. Defaults to False.",
    )
    async def create(self, ctx: ContextU, name: str, team_size: int=1, max_teams: Optional[int]=-1, random_teams: bool=False,  *, description: Optional[str]=None):
        await ctx.defer(ephemeral=True)

        tourney = await Tournaments.create(name=name, team_size=team_size, max_teams=max_teams, description=description, random_teams=random_teams, guild_id=ctx.guild.id, author_id=ctx.author.id, author_name=ctx.author.display_name)

        emb = makeembed_bot(
            title=f"Created Tournament: {name} (ID: {tourney.id})",
            description="To sign up, click the button below.",
            color=discord.Color.brand_green(),  
        )

        if tourney.team_size == 1:
            emb.add_field(name="# of Participants", value=f"{tourney.current_participants}")
        else:
            emb.add_field(name="# of Teams", value=f"{len(await TourneyTeams.filter(tournament=tourney))}")

        if tourney.max_teams > 0:
            emb.add_field(name="Max Teams", value=f"{tourney.max_teams if tourney.max_teams > 0 else 'Unlimited'}")
        emb.add_field(name="Team Size", value=f"{tourney.team_size}")   
        emb.add_field(name="Description", value=f"{tourney.description if tourney.description else 'No description.'}")

        m = await self.toxic_signups.send(embed=emb, view=SignupsView(tourney=tourney))

        await ctx.reply(embed=makeembed_successfulaction(description=f"Tournament Created. Find it here: {m.jump_url}"), ephemeral=True)

        await SavedMessages.save_message(m, name=f"Tourney_{tourney.id}")


    @tournament.command(name='close', description='Close a tournament.', aliases=['end','c'])
    @Cooldown(1, 60, commands.BucketType.user)
    @commands.has_permissions(manage_guild=True)
    async def close(self, ctx: ContextU, tourney_id: int):
        await ctx.defer()

        tourney = await Tournaments.get(id=tourney_id)

        await tourney.end_tournament()

        msg_obj = await SavedMessages.filter(name=f"Tourney_{tourney.id}")
        for m in msg_obj:
            try:
                msg = await self.toxic_signups.fetch_message(m.message_id)

                view = CustomBaseView.from_message(msg) # type: ignore

                for item in view.children:
                    if isinstance(item, discord.ui.Button):
                        if str(item.label).lower() == 'Sign Up'.lower():
                            item.disabled = True
                        elif str(item.label).lower() == 'Close Signups'.lower():
                            item.disabled = True
                
                await msg.edit(view=view)
            except: 
                continue

        await ctx.reply(f"Closed tournament {tourney.name}.", ephemeral=True)
    
    @tournament.command(name='delete', description='Delete a tournament', aliases=['remove','d'])
    @Cooldown(1, 60, commands.BucketType.user)
    @commands.has_permissions(manage_guild=True)
    async def delete(self, ctx: ContextU, tourney_id: int):
        await ctx.defer()

        tourney = await Tournaments.get(id=tourney_id)

        await tourney.delete()

        msg_obj = await SavedMessages.filter(name=f"Tourney_{tourney.id}")
        for m in msg_obj:
            try:
                msg = await self.toxic_signups.fetch_message(m.message_id)
                
                await msg.delete()

                # view = CustomBaseView.from_message(msg) # type: ignore

                # for item in view.children:
                #     if isinstance(item, discord.ui.Button):
                #         if str(item.label).lower() == 'Sign Up'.lower():
                #             item.disabled = True
                #         elif str(item.label).lower() == 'Close Signups'.lower():
                #             item.disabled = True
                
                #await msg.edit(view=view)
            except: continue

        await msg.edit(view=view)

        await ctx.reply(f"Deleted tournament {tourney.name}.", ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not hasattr(self, 'toxic_signups') or not hasattr(self, 'toxic_guild'):
            return

        if message.guild == self.toxic_guild:
            if message.channel == self.toxic_signups:
                if not message.author.guild_permissions.manage_guild and not message.author.bot and not message.author.get_role(1265453453321179177):
                    await message.reply(f"{message.author.mention}: We switched to a new signup system. Instead of entering your gamertag here, try clicking the button at the top to sign up instead.", delete_after=10)
                    await asyncio.sleep(5)
                    await message.delete()

    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload: discord.RawMessageDeleteEvent):
        # if not hasattr(self, 'toxic_signups') or not hasattr(self, 'toxic_guild'):
        #     return

        saved_message = await SavedMessages.filter(channel_id=TOXIC_TOURNEYS_SIGNUPS, message_id=payload.message_id).first()
        if not saved_message:
            return
        
        tourney_id = int(saved_message.name.split('_')[1])
        tourney = await Tournaments.get(id=tourney_id)

        emb = makeembed_bot(
            title=f"Created Tournament: {tourney.name} (ID: {tourney.id})",
            description="To sign up, click the button below.",
            color=discord.Color.brand_green(),
        )

        emb.add_field(name="# of Participants", value=f"{tourney.current_participants}")
        emb.add_field(name="Max Teams", value=f"{tourney.max_teams if tourney.max_teams > 0 else 'Unlimited'}")
        emb.add_field(name='TEST', value='TEST', inline=False)
        emb.remove_field(len(emb.fields)-1)
        emb.add_field(name="Team Size", value=f"{tourney.team_size}")
        emb.add_field(name="Description", value=f"{tourney.description if tourney.description else 'No description.'}")

        m = await self.toxic_signups.send(embed=emb, view=SignupsView(tourney=tourney))

        saved_message.message_id = m.id
        await saved_message.save()

        # find who deleted the message

        culprit = None

        actions = [m async for m in self.toxic_guild.audit_logs(action=discord.AuditLogAction.message_delete, limit=2)]
        for action in actions:
            if action.target.id == payload.message_id:
                culprit = action.user

        await self.toxic_signups.send(f"Resent the tourney signup. The original message was deleted by {culprit if culprit else 'a Moderator.'}. This message will resend should it be deleted again.", delete_after=10)

    # cog check
    async def cog_check(self, ctx: commands.Context) -> bool:
        if hasattr(self, 'toxic_guild'):
            return ctx.guild == self.toxic_guild or await self.bot.is_owner(ctx.author)
        elif ctx.guild:
            return ctx.guild.id == TOXIC_TOURNEYS_GUILD_ID or await self.bot.is_owner(ctx.author)
        else:
            return False

    
async def setup(bot: BotU):
    if PROD:    
        cog = ToxicTourneysCog(bot)
        await bot.add_cog(cog)
    else:
        pass
    #pass