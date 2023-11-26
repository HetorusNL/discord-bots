import discord
import json
import os
from pathlib import Path

from discord import Message
from discord import Member
from discord.ext.commands import Bot
from discord.channel import TextChannel

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
assert DISCORD_TOKEN, f"FATAL: discord token 'DISCORD_TOKEN' not found in env!"

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# make sure that the data directory exists
Path("data/").mkdir(exist_ok=True)

# load data from disk
with open("data/backup.json", "r") as f:
    server_data: dict = json.load(f)
with open("data/help.json", "r") as f:
    help_cmds = json.load(f)

# set the command prefix and the bot's status
command_prefix = "s!"
activity = discord.Activity(type=discord.ActivityType.watching, name=f"'{command_prefix}help'")
MIN_REPORT_LEN = 32
# some constants
RED = discord.Color.from_rgb(254, 50, 50)
ORANGE = discord.Color.from_rgb(254, 164, 0)
L_BLUE = discord.Color.from_rgb(0, 191, 254)

# create the bot
bot = Bot(command_prefix=command_prefix, activity=activity, intents=intents)


@bot.event
async def on_ready():  # setting bot activity
    name = bot.user.name if bot.user else bot.user
    print(f"{name} ({bot.user}) has connected to discord!")


async def save_backup():
    with open("data/backup.json", "w") as f:  # save to data/backup.json
        json.dump(server_data, f, indent=4)
    return


async def strip_duplicates(guild_id: str):
    server_data[guild_id]["whitelist"] = list(set(server_data[guild_id]["whitelist"]))
    server_data[guild_id]["flagged_words"] = list(set(server_data[guild_id]["flagged_words"]))


async def send_report(message: Message, report):
    guild = message.guild
    if not guild:
        return

    if report:
        title = "🚨   Report   🚨"
        description = "This message has been forwarded from the currently set reports channel."
        color = RED
    else:
        title = "⚠️   Flagged Words Found   ⚠️"
        description = "This message has been forwarded because flagged words have been found in it."
        color = ORANGE

    channel: TextChannel = message.channel  # type:ignore
    embed = discord.Embed(title=title, description=description, color=color)
    embed.add_field(name="🧑  Author", value=message.author.mention, inline=False)
    embed.add_field(name="📑  Content", value=message.content, inline=False)
    embed.add_field(name="💬  Channel", value=channel.mention, inline=False)

    admin_chnl = discord.utils.get(guild.channels, id=server_data[str(guild.id)]["admin"])  # type:ignore
    if admin_chnl:
        admin_chnl: TextChannel = admin_chnl
        await admin_chnl.send(embed=embed)


@bot.event
async def on_member_join(member: Member):
    if member.bot:  # ignore bots
        return

    guild_id = str(member.guild.id)  # convert guild id to string for json file

    if not server_data[guild_id]["autorole"]:  # return if autorole disabled (if autorole == None)
        return

    # add role to new user
    autorole = server_data[guild_id]["autorole"]
    guild_autorole = discord.utils.get(member.guild.roles, id=server_data[guild_id]["autorole"])
    if not guild_autorole:
        print(f"failed to assign role {autorole} to new member!")
    await member.add_roles(autorole, reason="Automatically added upon joining the server.")


@bot.event
async def on_message(message: Message):
    if message.author.bot:  # ignore bots
        return

    if type(message.author) is not Member:
        print(f"illegal message received from {message.author}")
        return

    guild = message.guild
    if not guild:
        return
    guild_id = str(guild.id)  # convert guild id to string for json file

    user_can_manage_messages = message.channel.permissions_for(message.author).manage_messages

    # check if guild added to server_data
    if guild_id not in server_data.keys():
        server_data[guild_id] = {}

        await save_backup()

    # commands
    if message.content.startswith(command_prefix):
        args = message.content.split(" ")

        if args[0] == f"{command_prefix}set" and user_can_manage_messages:
            embed = discord.Embed()

            # set new report and admin channels
            if args[1] == "channels" and args[3] == "to":
                server_data[guild_id]["report"] = int(args[2][2:-1])
                server_data[guild_id]["admin"] = int(args[4][2:-1])

                await save_backup()

                embed.title = "Channels set!"
                report_channel = discord.utils.get(guild.channels, id=server_data[guild_id]["report"])
                if not report_channel:
                    print(f'report_channel: {server_data[guild_id]["report"]} does not exist!')
                    return
                admin_channel = discord.utils.get(guild.channels, id=server_data[guild_id]["admin"])
                if not admin_channel:
                    print(f'admin_channel: {server_data[guild_id]["admin"]} does not exist!')
                    return
                embed.description = f"Messages from {report_channel.mention} will automatically be redirected to {admin_channel.mention} as reports.\n\nOld configuration has been erased."
                embed.color = L_BLUE

            # set new flagged words
            elif args[1] == "flagged" and args[2] == "words":
                server_data[guild_id]["flagged_words"] = []
                for word in args[3:]:
                    server_data[guild_id]["flagged_words"].append(word.lower())

                await strip_duplicates(guild_id)
                await save_backup()

                embed.title = "Flagged words set!"
                embed.description = f"New `flagged words` list has been created. You can see the new `flagged words` list under the command `{command_prefix}show flagged words`.\n\nOld configuration has been erased."
                embed.color = L_BLUE

            # set new whitelist
            elif args[1] == "whitelist":
                server_data[guild_id]["whitelist"] = []
                for channel in args[2:]:
                    server_data[guild_id]["whitelist"].append(int(channel[2:-1]))

                await strip_duplicates(guild_id)
                await save_backup()

                embed.title = "Whitelist set!"
                embed.description = f"New whitelist has been created. You can see the new whitelist under the command `{command_prefix}show whitelist`.\n\nOld configuration has been erased."
                embed.color = L_BLUE

            # set new autorole
            elif args[1] == "autorole":
                server_data[guild_id]["autorole"] = int(args[2][3:-1])

                await save_backup()

                embed.title = "Autorole set!"
                embed.description = f"New autorole has been created. You can see the new autorole under the command `{command_prefix}show autorole`.\n\nOld configuration has been erased."
                embed.color = L_BLUE

            await message.channel.send(embed=embed)

        elif args[0] == f"{command_prefix}add" and user_can_manage_messages:
            embed = discord.Embed()

            # add new flagged words
            if args[1] == "flagged" and args[2] == "words":
                for word in args[3:]:
                    server_data[guild_id]["flagged_words"].append(word.lower())

                await strip_duplicates(guild_id)
                await save_backup()

                embed.title = "Flagged words added!"
                embed.description = f"New flagged words have been added to the `flagged words` list. You can see the new `flagged words` list under the command `{command_prefix}show flagged words`."
                embed.color = L_BLUE

            # add new whitelisted channels
            elif args[1] == "whitelist":
                for channel in args[2:]:
                    server_data[guild_id]["whitelist"].append(int(channel[2:-1]))

                await strip_duplicates(guild_id)
                await save_backup()

                embed.title = "Channels added!"
                embed.description = f"New channels have been added to the whitelist. You can see the new whitelist under the command `{command_prefix}show whitelist`."
                embed.color = L_BLUE

            await message.channel.send(embed=embed)

        elif args[0] == f"{command_prefix}remove" and user_can_manage_messages:
            embed = discord.Embed()

            # remove specified flagged words
            if args[1] == "flagged" and args[2] == "words":
                for word in args[3:]:
                    if word in server_data[guild_id]["flagged_words"]:
                        server_data[guild_id]["flagged_words"].remove(word)

                await save_backup()

                embed.title = "Flagged words removed!"
                embed.description = f"Specified flagged words have been removed from the `flagged words` list. You can see the new `flagged words` list under the command `{command_prefix}show flagged words`."
                embed.color = L_BLUE

            # remove specified whitelisted channels
            elif args[1] == "whitelist":
                for channel in args[2:]:
                    if int(channel[2:-1]) in server_data[guild_id]["whitelist"]:
                        server_data[guild_id]["whitelist"].remove(int(channel[2:-1]))

                await save_backup()

                embed.title = "Channels removed!"
                embed.description = f"Specified channels have been removed from the whitelist. You can see the new whitelist under the command `{command_prefix}show whitelist`."
                embed.color = L_BLUE

            # remove existing autorole
            elif args[1] == "autorole":
                server_data[guild_id]["autorole"] = None

                await save_backup()

                embed.title = "Autorole removed!"
                embed.description = f"Autorole has been disabled. New members will not be given any roles from now on."
                embed.color = L_BLUE

            await message.channel.send(embed=embed)

        elif args[0] == f"{command_prefix}show":
            # list all flagged words
            if args[1] == "flagged" and args[2] == "words":
                title = f"Flagged words on {guild.name}"
                description = "\n".join(server_data[guild_id]["flagged_words"])

            # list all whitelist channels
            elif args[1] == "whitelist":
                # we assume that all channels configured exist and have a mention
                channel_names = []
                for whitelist_channel in server_data[guild_id]["whitelist"].copy():
                    channel = discord.utils.get(guild.channels, id=whitelist_channel)
                    if channel:
                        channel_names.append(channel.mention)
                    else:
                        channel_names.append(f"broken-channel ({whitelist_channel})!")
                        print(f"removing broken channel {whitelist_channel}...")
                        try:
                            server_data[guild_id]["whitelist"].remove(whitelist_channel)
                            await save_backup()
                            print("removed channel!")
                        except:
                            print("channel removal failed!")

                title = f"Whitelisted channels on {guild.name}"
                description = "\n".join(channel_names)

            # show current autorole
            elif args[1] == "autorole":
                title = f"Autorole on {guild.name}"
                description = f"Autorole disabled. See `{command_prefix}help admin` for more information."

                if server_data[guild_id]["autorole"]:
                    autorole = discord.utils.get(guild.roles, id=server_data[guild_id]["autorole"])
                    if autorole:
                        description = f"Current autorole: *{autorole.name}*\n\nThis role will automatically be assigned to new members."
            # invalid/not implemented command
            else:
                return

            embed = discord.Embed(title=title, description=description, color=L_BLUE)
            await message.channel.send(embed=embed)

        elif args[0] == f"{command_prefix}help":
            # show member help message
            if len(args) == 1:
                embed = discord.Embed(
                    title="Available Commands",
                    description=f"Type `{command_prefix}help admin` for restricted commands.",
                    color=L_BLUE,
                )

                for cmd in help_cmds["member"]:
                    embed.add_field(name=f"{command_prefix}{cmd[0]}", value=cmd[1], inline=False)

                await message.channel.send(embed=embed)

            # show admin help message
            elif args[1] == "admin":
                embed = discord.Embed(
                    title="Available Administrator Commands",
                    description=f"Type `{command_prefix}help` for publically available commands.",
                    color=L_BLUE,
                )

                for cmd in help_cmds["admin"]:
                    embed.add_field(name=f"{command_prefix}{cmd[0]}", value=cmd[1], inline=False)

                await message.channel.send(embed=embed)

        return  # don't perform checks on a command

    # check for whitelisted channels, ignore if channel on whitelist
    for chnl in server_data[guild_id]["whitelist"]:
        if message.channel.id == chnl:
            return

    # if message in report channel, forward to admin channel
    if message.channel.id == server_data[guild_id]["report"]:
        await message.delete()

        if len(message.content) <= MIN_REPORT_LEN:
            title = "Your report has not been submitted."
            description = f"The message must be longer than {MIN_REPORT_LEN} characters."
        else:
            title = "Your report has been submitted."
            description = "Thank you for your cooperation!"
            await send_report(message, True)

        embed = discord.Embed(title=title, description=description, color=L_BLUE)
        await message.author.send(embed=embed)

        return

    # if flagged words in message, forward to admin channel
    for word in server_data[guild_id]["flagged_words"]:
        if word in message.content.lower():
            await send_report(message, False)
            return


bot.run(DISCORD_TOKEN)
