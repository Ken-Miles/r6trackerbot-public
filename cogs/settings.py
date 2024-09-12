import traceback
from typing import List, Optional, Type, Union

import discord
from discord import app_commands
from discord.ext import commands
from discord.ext.commands import BucketType, UserInputError
import environ
from tortoise import Tortoise

from cogs.models import Settings, SettingsInfo
from utils import CogU, ContextU, Cooldown, emojidict, makeembed_bot


def clean_setting_name(s: str) -> str:
    return s.replace('_', ' ').title().strip()

class SettingsCog(CogU, name="Settings"):
    """Various settings for the bot."""

    def __init__(self, bot) -> None:
        self.bot = bot

    @commands.hybrid_command(name='settings',description='Settings for the bot.')
    @Cooldown(1, 5, BucketType.user)
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def settings(self, ctx: ContextU):
        settings, _ = await Settings.get_or_create(user_id=ctx.author.id, defaults={'username': ctx.author.name}) 
        if not ctx.interaction and ctx.guild:
            assert ctx.command is not None
            return await ctx.reply(f"To view settings, you must either use DMs or use the slash command version of this command: {await self.get_command_mention(ctx.command)}", ephemeral=True)
        return await ctx.reply(view=SettingsView(settings, ctx.author, (await SettingsInfo.all())),ephemeral=True)

class SettingsDropdown(discord.ui.Select):
    def __init__(self, user_setting: Settings, user: discord.abc.User, setting_info: Optional[List[SettingsInfo]]=None, timeout: Optional[float]=None):
        # if setting_info and all(setting_info):
        #     options = [
        #         discord.SelectOption(label=setting.name, value=setting.name, description=setting.description, emoji=setting.emoji, default=False)
        #         for setting in setting_info
        #     ]
        # else:
        #     options = [
        #         discord.SelectOption(label=clean_setting_name(k), value=k,default=False)
        #         for k, v in user_setting.all_settings.items()
        #     ]
        options = []
        
        for k, v in user_setting.all_settings.items():
            if setting_info:
                specific_setting_info = discord.utils.find(lambda x: x.name == k, setting_info)
                if specific_setting_info:
                    if not specific_setting_info.active:
                        continue
                    options.append(discord.SelectOption(label=clean_setting_name(specific_setting_info.name), value=k, description=specific_setting_info.description[:100], emoji=specific_setting_info.emoji, default=False)
                    )
                else:
                    options.append(discord.SelectOption(label=clean_setting_name(k), value=k,default=False))
            else:
                options.append(discord.SelectOption(label=clean_setting_name(k), value=k,default=False))
        self.user = user
        self.user_setting = user_setting
        self.setting_info = setting_info
        super().__init__(placeholder="Select a setting", min_values=1, max_values=1, custom_id='e', options=options)

    async def callback(self, interaction: discord.Interaction):
        try:
            if interaction.user.id != self.user.id: raise UserInputError
            
            # all_settings = self.user_setting.all_settings
            # all_settings_rev = {v: k for k, v in all_settings}
            # selected_setting: Tuple[str, Tuple[Union[str, int, bool], Type]] = all_settings_rev[all_settings[int(self.values[0])]], all_settings[int(self.values[0])]
                #new = DBUserSettings(setting_id=setting_.id,userid=interaction.user.id,username=interaction.user.name,value=setting_.default,valuetype=setting_.valuetype)
                #await new.save()
            
            selected_setting = self.values[0]

            selected_setting_type = self.user_setting.get_setting_type(selected_setting)

            specific_setting_info = discord.utils.find(lambda x: x.name == selected_setting, self.setting_info) # type: ignore

            if selected_setting_type == bool:
                view = ChangeSettingsViewBool(self.user_setting, selected_setting, self.user, specific_setting_info)
            else:
                view = ChangeSettingsView(self.user_setting, selected_setting, self.user, specific_setting_info)
            await interaction.response.edit_message(view=view,embed=view.to_embed())
        except UserInputError:
            await interaction.response.send_message("You can't use this! Use ", ephemeral=True)
        except:
            traceback.print_exc()

class SettingsView(discord.ui.View):
    def __init__(self, setting: Settings, user: discord.abc.User, setting_info: Optional[List[SettingsInfo]]=None, timeout: Optional[float]=None):
        super().__init__()
        self.add_item(SettingsDropdown(setting, user, setting_info=setting_info, timeout=timeout))

# class ChangeSettingView(discord.ui.View):
#     value: Union[bool,int,str,float]
#     settings: Settings
#     user: discord.User
#     user_settings: DBUserSettings

#     def __init__(self, setting: Settings, user: discord.User):
#         super().__init__(timeout=60)
#         self.setting = setting
#         if setting.valuetype == "bool":
#             self.value = False
#             self.add_item(Boolean(self, self.value, False))
#             self.add_item(BooleanButton(self, not self.value, True))
#         elif setting.valuetype == "int":
#             self.value = 0
#         elif setting.valuetype == "str":
#             self.value = ""
#         elif setting.valuetype == 'float':
#             self.value = 0.0
#         self.user = user
    
#     async def callback(self, interaction: discord.Interaction, value: Union[bool,int,str,float]):
#         if interaction.user.id != self.user.id:
#             return
#         self.user_settings.__setattr__(self.setting.name, value)
#         await self.user_settings.save()
#         self.clear_items()
#         self.stop()
    
#     async def get_user_settings(self) -> Optional[DBUserSettings]:
#         return await DBUserSettings.get_or_none(id=self.user.id)
    
class ChangeSettingsViewBool(discord.ui.View):
    def __init__(self, setting: Settings, setting_name: str, user: discord.abc.User, setting_info: Optional[SettingsInfo]=None, timeout: Optional[float]=None):
        super().__init__(timeout=timeout)
        self.setting = setting
        self.setting_name = setting_name
        self.user = user
        
        self.setting_info = setting_info

        if setting.get_setting_value(setting_name) == True: # there is a reason, it must be the boolean value True (not a truthy value)
            self.value = True
        elif setting.get_setting_value(setting_name) == False:
            self.value = False
        else:
            raise ValueError(f"Invalid value for setting {setting_name}")
        
        self.update_buttons()
    
    def to_embed(self) -> discord.Embed:
        if self.setting_info is None:
            return makeembed_bot(title=f"Setting: {clean_setting_name(self.setting_name)}", description=f"Current value: {emojidict.get(self.value)}")
        return makeembed_bot(title=f"Setting: {clean_setting_name(self.setting_info.name)}", description=f" > {self.setting_info.description[:1970]}\nCurrent value: {emojidict.get(self.value)}")

    @discord.ui.button(label="Enabled", style=discord.ButtonStyle.green, custom_id="enabled",emoji=emojidict.get(True))
    async def enabled_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            if interaction.user.id != self.user.id:
                return
            self.value = True
            
            await self.update_setting(interaction)
        except:
            traceback.print_exc()

    @discord.ui.button(label="Disabled", style=discord.ButtonStyle.red,custom_id="disabled",emoji=emojidict.get(False))
    async def disabled_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            if interaction.user.id != self.user.id:
                return
            self.value = False

            await self.update_setting(interaction)
        except:
            traceback.print_exc()
    
    def update_buttons(self):
        if self.value:
            self.enabled_button.disabled = True
            self.disabled_button.disabled = False
        else:
            self.enabled_button.disabled = False
            self.disabled_button.disabled = True

    async def update_setting(self, interaction: discord.Interaction):
        self.update_buttons()
        self.setting.set_setting_value(self.setting_name, self.value)
        await self.setting.save()
        await interaction.response.edit_message(view=self,embed=self.to_embed())

    @discord.ui.button(label="Back", style=discord.ButtonStyle.blurple, custom_id="back", emoji=emojidict.get('back'))
    async def back(self, interaction: discord.Interaction, _: discord.ui.Button):
        try:
            if interaction.user.id != self.user.id:
                return
            await interaction.response.edit_message(view=SettingsView(self.setting, self.user, (await SettingsInfo.all())),embed=None)
            self.stop()
        except:
            traceback.print_exc()

    @discord.ui.button(label="Close", style=discord.ButtonStyle.grey, custom_id="cancel",emoji=emojidict.get('no'))
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            if interaction.user.id != self.user.id:
                return
            await interaction.response.edit_message(view=None)
            if interaction.message:
                try:
                    await interaction.message.delete()
                except discord.NotFound:
                    pass
        except:
            traceback.print_exc()

class ChangeSettingsView(discord.ui.View):
    def __init__(self, setting: Settings, setting_name: str, user: discord.abc.User, setting_info: Optional[SettingsInfo]=None, timeout: Optional[float]=None):
        super().__init__(timeout=timeout)
        self.setting = setting
        #self.usersetting = usersetting
        self.user = user
        
        assert hasattr(self.setting, setting_name)

        self.setting_name = setting_name

        self.setting_info = setting_info

        #self.value = self.usersetting.value
        #self.isint = self.setting.valuetype == 'int'
        #self.isfloat = self.setting.valuetype == 'float'
        #self.isstr = self.setting.valuetype == 'str'
    
    def to_embed(self) -> discord.Embed:
        setting_value = self.setting.get_setting_value(self.setting_name)
        if self.setting_info is None:
            return makeembed_bot(title=f"Setting: {clean_setting_name(self.setting_name)}", description=f"Current value: `{setting_value}`")
        return makeembed_bot(title=f"Setting: {clean_setting_name(self.setting_info.name)}", description=f" > {self.setting_info.description[:1970]}\nCurrent value: `{setting_value}`")

    @discord.ui.button(label="Change Value", style=discord.ButtonStyle.gray, custom_id="enabled",emoji=emojidict.get('pencilpaper'))
    async def changenumber(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.response.send_modal(ChangeSettingModal(self, tipe=self.setting.get_setting_type(self.setting_name), setting_info=self.setting_info))
        except:
            traceback.print_exc()

    async def on_new_value(self, interaction: discord.Interaction, value: Union[bool,int,str]):
        self.setting.set_setting_value(self.setting_name, value)
        #print(self.setting_name, value)
        await self.setting.save()
        await interaction.response.edit_message(view=self,embed=self.to_embed())

    @discord.ui.button(label="Back", style=discord.ButtonStyle.blurple, custom_id="back",emoji=emojidict.get('back'))
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            if interaction.user.id != self.user.id:
                return
            await interaction.response.edit_message(view=SettingsView(await Settings.get(user_id=self.user.id), self.user, setting_info=(await SettingsInfo.all())),embed=None)
            self.stop()
        except:
            traceback.print_exc()

    @discord.ui.button(label="Close", style=discord.ButtonStyle.grey, custom_id="cancel",emoji=emojidict.get('no'))
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            if interaction.user.id != self.user.id:
                return
            await interaction.response.edit_message(view=None)
            if interaction.message:
                await interaction.message.delete()
        except:
            traceback.print_exc()

class ChangeSettingModal(discord.ui.Modal):
    def __init__(self, view: ChangeSettingsView, tipe: Type, title: str="Change Value", setting_info: Optional[SettingsInfo]=None, timeout: Optional[float]=None):
        super().__init__(title=title, timeout=timeout)
        self.view = view
        self.setting_type = tipe
        self.min = None
        self.max = None

        if tipe is str:
            if setting_info:
                self.min = setting_info.min_value
                self.max = setting_info.max_value
                self.input = discord.ui.TextInput(label='Enter a value', min_length=self.min, max_length=self.max, placeholder="Enter a value", custom_id="text")
            else:
                self.input = discord.ui.TextInput(label='Enter a value', placeholder="Enter a value", custom_id="text")
        else:
            self.input = discord.ui.TextInput(label='Enter a value',placeholder="Enter a value", custom_id="number")
        
        self.add_item(self.input)

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.user.id != self.view.user.id:
            return
        if not self.input.value:
            return await interaction.response.send_message('You need to enter a value!', ephemeral=True)
        
        if self.setting_type is int:
            int(self.input.value)
            if self.input.value.find('.') != -1:
                return await interaction.response.send_message('You need to enter an integer!', ephemeral=True)
        elif self.setting_type is float:
            try:
                float(self.input.value)
            except:
                return await interaction.response.send_message('You need to enter a decimal!', ephemeral=True)
        if self.min is not None or self.max is not None and self.setting_type:
            if self.min is not None:
                if self.min > float(self.input.value):
                    return await interaction.response.send_message(f'You need to enter a number greater than {self.min}!', ephemeral=True)
            if self.max is not None:
                if self.max < float(self.input.value):
                    return await interaction.response.send_message(f'You need to enter a number less than {self.max}!', ephemeral=True)
        
        if self.setting_type is int:
            returnv = int(self.input.value)
        elif self.setting_type is float:
            returnv = float(self.input.value)
        else:
            returnv = self.input.value
        
        await self.view.on_new_value(interaction,returnv)
 

async def setup(bot: commands.Bot):
    env = environ.Env(
        PROD=(bool, False)
    )

    PROD = env("PROD")
    
    if PROD:
        await Tortoise.init(config_file="db.yml")
    else:
        await Tortoise.init(config_file="db_beta.yml")
    await Tortoise.generate_schemas()
    cog = SettingsCog(bot)
    await bot.add_cog(cog)
    #pass
