from datetime import datetime
import io
import json
import os
import random
import re
from re import Match
import requests
import shutil
import time
from urllib.parse import urlencode
from urllib.parse import quote

import discord
from discord import Member
from discord import Message
from discord.channel import TextChannel
from discord.ext import tasks
from discord.ext.commands import Bot

from utils import Settings

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
assert DISCORD_TOKEN, f"FATAL: discord token 'DISCORD_TOKEN' not found in env!"

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# set the command prefix and the bot's status
command_prefix = "/"
activity = discord.Activity(type=discord.ActivityType.watching, name=f"'get-command-prefix'")
# create the bot
bot = Bot(command_prefix=command_prefix, activity=activity, intents=intents)


COLOR_INFO = 0x3232FE
COLOR_ADMIN = 0xF1C40F
COLOR_ERROR = 0xFE3232


_lang_lut: dict[str, str] = {}
_cc_mapping: dict[str, str] = {}
_common_lang: list[str] = []
_commands: list[dict] = []
_admin_commands: list[dict] = []


@bot.event
async def on_ready():
    # create references to the (written) global data structures
    global _lang_lut
    global _cc_mapping
    global _common_lang
    global _commands
    global _admin_commands

    with open("language_data.json") as f:
        language_data = json.load(f)

    _lang_lut = language_data["lang_lut"]
    _cc_mapping = language_data["cc_mapping"]
    _common_lang = language_data["common_lang"]

    _commands = [
        {
            "name": "Help",
            "description": "Shows this help message",
            "usage": "help",
            "regex": r"help$",
            "function": _command_help,
        },
        {
            "name": "Translate",
            "description": "Translate from the server specific language " "to English",
            "usage": "translate <text>",
            "regex": r"translate (?P<text>.*)$",
            "function": _command_translate,
        },
        {
            "name": "Translate from/to",
            "description": "Translate from language (country-code) 1 " "to language (country-code) 2",
            "usage": "cc2cc <text>",
            "regex": r"(?P<src>[a-z]{2})2(?P<dst>[a-z]{2}) (?P<text>.*)$",
            "function": _command_translate_from_to,
        },
        {
            "name": "Generate wotd",
            "description": "Generate a fresh word-of-the-day",
            "usage": "wotd",
            "regex": r"wotd$",
            "function": _command_wotd,
        },
        {
            "name": "Wotd words left",
            "description": "Shows how many word-of-the-days are left",
            "usage": "wotd-words-left",
            "regex": r"wotd-words-left$",
            "function": _command_wotd_words_left,
        },
        {
            "name": "Languages",
            "description": "Show common languages with country code",
            "usage": "languages",
            "regex": r"languages$",
            "function": _command_languages,
        },
        {
            "name": "All languages",
            "description": "Show all supported languages with country code" " (warning: many)",
            "usage": "all-languages",
            "regex": r"all-languages$",
            "function": _command_all_languages,
        },
    ]

    _admin_commands = [
        {
            "name": "Help (admin commands)",
            "description": "Shows this help (admin commands) message",
            "usage": "help-admin",
            "regex": r"help-admin$",
            "function": _admin_command_help,
        },
        {
            "name": "Command prefix",
            "description": "Get or set the command prefix",
            "usage": "command-prefix [new-command-prefix]",
            "regex": r"command-prefix(?P<prefix>.*)$",
            "function": _admin_command_command_prefix,
        },
        {
            "name": "Server language",
            "description": "Get or set the server language",
            "usage": "server-language [new-server-language]",
            "regex": r"server-language(?P<language>.*)$",
            "function": _admin_command_server_language,
        },
        {
            "name": "WOTD language(s)",
            "description": "Get, set or clear the WOTD language(s)",
            "usage": "wotd-language "
            "[clear] OR\n"
            "[new-wotd-language-country-code] OR\n"
            "[wotd-language-cc-from]-[wotd-language-cc-to]",
            "regex": r"wotd-language(?P<language>.*)$",
            "function": _admin_command_wotd_language,
        },
        {
            "name": "WOTD channel",
            "description": "Get, set or clear the WOTD channel",
            "usage": "wotd-channel [new-wotd-channel-mention]/[clear]",
            "regex": r"wotd-channel(?P<channel>.*)$",
            "function": _admin_command_wotd_channel,
        },
    ]

    # start the background task
    await background_task_wotd.start()


@bot.event
async def on_message(message: Message):
    # to execute commands, uncomment the line below
    # await bot.process_commands(message)
    # print(message.content)

    # to ignore bots, uncomment the lines below
    # if message.author.bot:  # ignore bots
    #    return

    # to delete the commands send by bots, set below to True
    delete_bot_commands = True

    # extract some usefull information before processing message
    if not isinstance(message.author, Member):
        await message.channel.send("ERROR: not a member!")
        return False
    guild_id: int = message.author.guild.id
    prefix = Settings.get(guild_id, "command_prefix")
    delete_bot_commands = delete_bot_commands and message.author.bot

    # make sure that we can get the bot's command_prefix in all guilds
    if message.content == "get-command-prefix":
        embed = discord.Embed(
            title="Command prefix",
            description=f"{prefix}",
            color=COLOR_INFO,
        )
        await message.channel.send(embed=embed)
        return

    # make sure that we can reset the bot's command_prefix in all guilds
    if message.content == "reset-command-prefix":
        if not await _ensure_authorized(message):
            return
        await _handle_command_prefix(message, prefix, "/", guild_id)
        return

    # process all commands
    for command in _commands:
        regex = r"^" + _escape_re(prefix) + command["regex"]
        match = re.match(regex, message.content)
        if match:
            # print("match command")
            await command["function"](message, match, message.author.guild.id)
            if delete_bot_commands:
                await message.delete()
            return

    # process all admin commands
    for command in _admin_commands:
        regex = r"^" + _escape_re(prefix) + command["regex"]
        match = re.match(regex, message.content)
        if match:
            # print("match admin command")
            if not await _ensure_authorized(message):
                return
            await command["function"](message, match, message.author.guild.id)
            if delete_bot_commands:
                await message.delete()
            return


def _escape_re(expression):
    # make sure to also escape / in the string
    return re.escape(expression)  # .replace("/", "\\/")


async def _ensure_authorized(message: Message):
    if not isinstance(message.author, Member):
        await message.channel.send("ERROR: not a member!")
        return False
    is_administrator = message.author.guild_permissions.administrator
    if not is_administrator:
        embed = discord.Embed(
            title="Not authorized!",
            description=f"**{message.author.name}** is not authorized " "to use this command!",
            color=COLOR_ERROR,
        )
        await message.channel.send(embed=embed)
        return False

    return True


# bot commands
async def _command_help(message: Message, match: Match, guild_id: int):
    prefix = Settings.get(guild_id, "command_prefix")
    embed = discord.Embed(
        title=f"Commands",
        description="The supported commands of this bot are:\n" f"(`{prefix}help-admin` for admin commands)",
        color=COLOR_INFO,
    )
    # add basic command (without prefix)
    embed.add_field(
        name="Get command prefix",
        value="Get the command prefix of the bot in this guild\n" "Usage: `get-command-prefix`",
        inline=False,
    )
    # add the rest of the commands
    for command in _commands:
        embed.add_field(
            name=command["name"],
            value=f'{command["description"]}\n' f'Usage: `{prefix}{command["usage"]}`',
            inline=False,
        )
    await message.channel.send(embed=embed)


async def _command_translate(message: Message, match: Match, guild_id: int):
    server_language = Settings.get(guild_id, "server_language")
    if not server_language:
        embed = discord.Embed(
            title=f"Translation ERROR",
            description=f"Translation server-language not set!",
            color=COLOR_ERROR,
        )
        await message.channel.send(embed=embed)
        return

    # we have a server_language at this point
    src = _map_cc(server_language)
    dst = _map_cc("en")
    text = match.groupdict().get("text")
    await _translate(message, src, dst, text)


async def _command_translate_from_to(message: Message, match: Match, guild_id: int):
    src = _map_cc(match.groupdict().get("src", ""))
    dst = _map_cc(match.groupdict().get("dst", ""))
    text = match.groupdict().get("text")
    await _translate(message, src, dst, text)


async def _translate(message: Message, src, dst, text):
    # generate the url for the translate API call
    url = "https://translate.googleapis.com/translate_a/single?"
    params = {"client": "gtx", "sl": src, "tl": dst, "dt": "t", "q": text}
    encoded = urlencode(params, quote_via=quote)
    url += encoded

    # send the request
    response = requests.get(url)

    # parse the result
    # verify status code is correct
    if response.status_code != 200:
        await _send_error(message, f"translate API status code: {response.status_code}!")
        return
    response_headers = response.headers.get("content-type")
    if not response_headers:
        await _send_error(message, f"translate API returns wrong content-type!")
        return
    # verify application content is JSON
    if "application/json" not in response_headers:
        await _send_error(message, f"translate API doesn't return JSON data!")
        return
    # verify that we can access response.json()[0][0][0] (the translation)
    try:
        if text != "":
            response.json()[0][0][0]
    except:
        await _send_error(message, f"translation result is not available!")
        return

    # show the actual translation
    translation = ""
    for sentence in response.json()[0]:
        translation += sentence[0]
    link = (
        f"[Click here to listen on google translate]"
        f"(https://translate.google.com/?op=translate&"
        f"sl={src}&tl={dst}&text={quote(text)})"
    )

    # map the src/dst language to the actual language names (if available)
    src = _lang_lut.get(src) or src
    dst = _lang_lut.get(dst) or dst
    embed = (
        discord.Embed(
            title=f"Translation",
            color=COLOR_INFO,
        )
        .add_field(name=f"{src}", value=f"{text}", inline=False)
        .add_field(name=f"{dst}", value=f"{translation}", inline=False)
        .add_field(name=f"Link", value=f"{link}", inline=False)
    )
    await message.channel.send(embed=embed)


async def _command_wotd(message: Message, match: Match, guild_id: int):
    channel: TextChannel = message.channel  # type:ignore
    await _generate_wotd(guild_id, force=True, msg_channel=channel)


async def _command_wotd_words_left(message: Message, match: Match, guild_id: int):
    channel: TextChannel = message.channel  # type:ignore
    if not await _verify_wotd_requirements(guild_id, channel):
        # no wotd channel or languageconfigured, return
        return

    file_extension = Settings.get(guild_id, "wotd_type")
    filename = f"guild_data/{guild_id}-wotd.{file_extension}"
    # count the lines in the file
    with io.open(filename, encoding="utf-8") as f:
        lines = f.readlines()
        embed = discord.Embed(
            title=f"WOTD words left",
            color=COLOR_INFO,
            description=f"{len(lines)}",
        )
        await message.channel.send(embed=embed)


async def _command_languages(message: Message, match: Match, guild_id: int):
    title = "Common languages"
    cc_list = _common_lang
    await _send_language_embed(message, title, cc_list)


async def _command_all_languages(message: Message, match: Match, guild_id: int):
    title = "Supported languages"
    cc_list = list(_lang_lut.keys())
    await _send_language_embed(message, title, cc_list)


# bot admin commands
async def _admin_command_help(message: Message, match: Match, guild_id: int):
    prefix = Settings.get(guild_id, "command_prefix")
    embed = discord.Embed(
        title=f"Admin commands",
        description="The supported admin commands of this bot are:",
        color=COLOR_ADMIN,
    )
    # add basic admin command (without prefix)
    embed.add_field(
        name="Reset command prefix",
        value="Reset the command prefix of the bot in this guild to: /\n" "Usage: `reset-command-prefix`",
        inline=False,
    )
    # add the rest of the admin commands
    for command in _admin_commands:
        embed.add_field(
            name=command["name"],
            value=f'{command["description"]}\n' f'Usage: `{prefix}{command["usage"]}`',
            inline=False,
        )
    await message.channel.send(embed=embed)


async def _admin_command_command_prefix(message: Message, match: Match, guild_id: int):
    prefix = str(Settings.get(guild_id, "command_prefix"))
    new_prefix: str = match.groupdict().get("prefix", "")
    new_prefix = new_prefix.strip()
    await _handle_command_prefix(message, prefix, new_prefix, guild_id)


async def _admin_command_server_language(message: Message, match: Match, guild_id: int):
    language = str(Settings.get(guild_id, "server_language"))
    language = _map_cc(language)
    new_language: str = match.groupdict().get("language")  # type:ignore
    if not new_language:  # new_language is either a str, or None
        await _send_error(message, f"FATAL: _admin_command_server_language, no language in match!")
        return
    new_language: str = new_language
    new_language = new_language.strip()
    new_language = _map_cc(new_language)
    await _handle_server_language(message, language, new_language, guild_id)


async def _admin_command_wotd_language(message: Message, match: Match, guild_id: int):
    wotd_language = str(Settings.get(guild_id, "wotd_language"))
    wotd_language = _map_cc(wotd_language)
    # support a tsv list with from-to languages
    language: str = match.groupdict().get("language", "")
    input_language = language.strip()
    is_tsv = False
    new_wotd_language = ""
    new_wotd_language_from = ""
    new_wotd_language_to = ""
    if "-" in input_language:
        is_tsv = True
        new_wotd_language_from = input_language.split("-")[0]
        new_wotd_language_from = _map_cc(new_wotd_language_from)
        new_wotd_language_to = input_language.split("-")[1]
        new_wotd_language_to = _map_cc(new_wotd_language_to)
    else:
        language: str = match.groupdict().get("language", "")
        new_wotd_language = language.strip()
        new_wotd_language = _map_cc(new_wotd_language)

    if new_wotd_language or new_wotd_language_from:
        # handle the case where a new wotd language is provided
        if new_wotd_language == "clear":
            # clear the wotd language from the settings file
            Settings.delete(guild_id, "wotd_language")
            embed = discord.Embed(
                title=f"WOTD language",
                description=f"WOTD language is cleared!",
                color=COLOR_ADMIN,
            )
            await message.channel.send(embed=embed)
            # remove the wotd file if available
            filename = f"guild_data/{guild_id}-wotd.txt"
            if os.path.isfile(filename):
                os.remove(filename)
            filename = f"guild_data/{guild_id}-wotd.tsv"
            if os.path.isfile(filename):
                os.remove(filename)
            return
        if is_tsv:
            if _lang_lut.get(new_wotd_language_from):
                # handle valid new wotd languages
                if not Settings.get(guild_id, "wotd_channel"):
                    # make sure that a wotd channel is already configured
                    embed = discord.Embed(
                        title=f"WOTD language",
                        description=f"WOTD channel not configured yet!",
                        color=COLOR_ERROR,
                    )
                    await message.channel.send(embed=embed)
                    return
                src_filename = f"data/wotd-list-" f"{new_wotd_language_from}-{new_wotd_language_to}.tsv"
                if os.path.isfile(src_filename):
                    # remove the (previous) wotd file if available
                    filename = f"guild_data/{guild_id}-wotd.txt"
                    if os.path.isfile(filename):
                        os.remove(filename)
                    filename = f"guild_data/{guild_id}-wotd.tsv"
                    if os.path.isfile(filename):
                        os.remove(filename)
                    # handle languages which do have a wotd list
                    # copy the wotd language file
                    dst_filename = f"guild_data/{guild_id}-wotd.tsv"
                    shutil.copyfile(src_filename, dst_filename)
                    # update the settings file with the wotd language
                    Settings.set(guild_id, "wotd_language", new_wotd_language_from)
                    Settings.set(guild_id, "wotd_to_language", new_wotd_language_to)
                    Settings.set(guild_id, "wotd_type", "tsv")
                    # send embed with the result
                    embed = discord.Embed(
                        title=f"WOTD language",
                        description=f"Set WOTD language to: "
                        f"{_lang_lut[new_wotd_language_from]}-"
                        f"{_lang_lut[new_wotd_language_to]}",
                        color=COLOR_ADMIN,
                    )
                    await message.channel.send(embed=embed)
                else:
                    # handle languages for which no wotd list exist
                    embed = discord.Embed(
                        title=f"WOTD language",
                        description=f"WOTD list does not exist for: "
                        f"{_lang_lut[new_wotd_language_from]}-"
                        f"{_lang_lut[new_wotd_language_to]}",
                        color=COLOR_ERROR,
                    )
                    await message.channel.send(embed=embed)
                return
        else:
            if _lang_lut.get(new_wotd_language):
                # handle valid new wotd languages
                if not Settings.get(guild_id, "wotd_channel"):
                    # make sure that a wotd channel is already configured
                    embed = discord.Embed(
                        title=f"WOTD language",
                        description=f"WOTD channel not configured yet!",
                        color=COLOR_ERROR,
                    )
                    await message.channel.send(embed=embed)
                    return
                src_filename = f"data/wotd-list-{new_wotd_language}.txt"
                if os.path.isfile(src_filename):
                    # remove the (previous) wotd file if available
                    filename = f"guild_data/{guild_id}-wotd.txt"
                    if os.path.isfile(filename):
                        os.remove(filename)
                    filename = f"guild_data/{guild_id}-wotd.tsv"
                    if os.path.isfile(filename):
                        os.remove(filename)
                    # handle languages which do have a wotd list
                    # copy the wotd language file
                    dst_filename = f"guild_data/{guild_id}-wotd.txt"
                    shutil.copyfile(src_filename, dst_filename)
                    # update the settings file with the wotd language
                    Settings.set(guild_id, "wotd_language", new_wotd_language)
                    Settings.set(guild_id, "wotd_type", "txt")
                    # send embed with the result
                    embed = discord.Embed(
                        title=f"WOTD language",
                        description=f"Set WOTD language to: " f"{_lang_lut[new_wotd_language]}",
                        color=COLOR_ADMIN,
                    )
                    await message.channel.send(embed=embed)
                else:
                    # handle languages for which no wotd list exist
                    embed = discord.Embed(
                        title=f"WOTD language",
                        description=f"WOTD list does not exist for: " f"{_lang_lut[new_wotd_language]}",
                        color=COLOR_ERROR,
                    )
                    await message.channel.send(embed=embed)
                return
        # handle invalid new wotd languages
        embed = discord.Embed(
            title=f"WOTD language",
            description=f"Invalid WOTD language provided: "
            f"{new_wotd_language_from if is_tsv else new_wotd_language}",
            color=COLOR_ERROR,
        )
        await message.channel.send(embed=embed)
    else:
        # handle the case where the current wotd language is displayed
        if _lang_lut.get(wotd_language):
            # show the wotd language, since it is found and valid
            embed = discord.Embed(
                title=f"WOTD language",
                description=f"{_lang_lut[wotd_language]}",
                color=COLOR_ADMIN,
            )
            await message.channel.send(embed=embed)
        else:
            # handle the case where no wotd language is provided yet
            embed = discord.Embed(
                title=f"WOTD language",
                description=f"No WOTD language configured yet!",
                color=COLOR_ADMIN,
            )
            await message.channel.send(embed=embed)


async def _admin_command_wotd_channel(message: Message, match: Match, guild_id: int):
    wotd_channel = Settings.get(guild_id, "wotd_channel")
    new_wotd_channel = match.groupdict().get("channel", "").strip()

    if new_wotd_channel:
        # handle the case where a new wotd channel is provided
        if new_wotd_channel == "clear":
            # clear the wotd channel (and language) from the settings file
            Settings.delete(guild_id, "wotd_channel")
            Settings.delete(guild_id, "wotd_language")
            embed = discord.Embed(
                title=f"WOTD channel",
                description=f"WOTD channel (and language) is cleared!",
                color=COLOR_ADMIN,
            )
            await message.channel.send(embed=embed)
        else:
            # handle new wotd channel
            regex = r"<#[^0-9]?(?P<channel>[0-9]*)>"
            chan_match = re.match(regex, new_wotd_channel)
            if chan_match:
                # handle valid channel mention
                # update the settings file with the wotd channel
                channel_str: str = chan_match.groupdict().get("channel", "")
                channel = int(channel_str)
                Settings.set(guild_id, "wotd_channel", channel)
                # send embed with the result
                embed = discord.Embed(
                    title=f"WOTD channel",
                    description=f"Set WOTD channel to: " f"<#{channel}>",
                    color=COLOR_ADMIN,
                )
                await message.channel.send(embed=embed)
            else:
                # handle invalid channel
                embed = discord.Embed(
                    title=f"WOTD channel",
                    description=f"Invalid channel (mention) provided: " f"{new_wotd_channel}",
                    color=COLOR_ERROR,
                )
                await message.channel.send(embed=embed)
    else:
        # handle the case where the current wotd channel is displayed
        if wotd_channel:
            # show the wotd channel, since it is found and valid
            embed = discord.Embed(
                title=f"WOTD channel",
                description=f"<#{wotd_channel}>",
                color=COLOR_ADMIN,
            )
            await message.channel.send(embed=embed)
        else:
            # handle the case where no wotd channel is provided yet
            embed = discord.Embed(
                title=f"WOTD channel",
                description=f"No WOTD channel configured yet!",
                color=COLOR_ADMIN,
            )
            await message.channel.send(embed=embed)


# utility functions
async def _send_error(message: Message, error: str):
    if not isinstance(message.author, Member):
        await message.channel.send("ERROR: not a member!")
        return False
    # get Administrator role
    role = discord.utils.find(lambda r: r.name == "Administrators", message.author.guild.roles)
    # send the error message
    mention = role.mention if role else "@Administrators"
    embed = discord.Embed(
        title="Translation ERROR",
        description=f"{error}",
        color=COLOR_ERROR,
    )
    await message.channel.send(embed=embed)

    # mention the Administrator role since it doesn't work in embeds
    # await message.channel.send(f"{mention}")  # TODO: uncomment


def _map_cc(cc: str):
    # apply country-code mapping to the supplied cc if available
    if _cc_mapping.get(cc):
        return _cc_mapping[cc]
    return cc


async def _handle_command_prefix(message: Message, prefix: str | None, new_prefix: str, guild_id: int):
    if new_prefix:
        # a prefix is supplied, override the old one
        embed = (
            discord.Embed(title="Changed command prefix", color=COLOR_ADMIN)
            .add_field(name="Old prefix", value=f"{prefix}")
            .add_field(name="New prefix", value=f"{new_prefix}")
        )
        await message.channel.send(embed=embed)
        Settings.set(guild_id, "command_prefix", new_prefix)
    else:
        # no prefix is supplied, simply print the prefix
        embed = discord.Embed(
            title="Command prefix",
            description=f"{prefix}",
            color=COLOR_ADMIN,
        )
        await message.channel.send(embed=embed)


async def _handle_server_language(message: Message, language: str, new_language: str, guild_id: int):
    if new_language:
        # a language is supplied, override the old one if valid
        if _lang_lut.get(new_language):
            embed = discord.Embed(
                title="Server language",
                description=f"Set to {_lang_lut[new_language]}",
                color=COLOR_ADMIN,
            )
            Settings.set(guild_id, "server_language", new_language)
        else:
            embed = discord.Embed(
                title="Server language",
                description=f"Invalid server language supplied!",
                color=COLOR_ERROR,
            )
        await message.channel.send(embed=embed)
    else:
        # no language is supplied, simply print the language
        if language:
            language = _lang_lut[language]
        else:
            language = "No server language configured!"

        embed = discord.Embed(
            title="Server language",
            description=f"{language}",
            color=COLOR_ADMIN,
        )
        await message.channel.send(embed=embed)


async def _send_language_embed(message: Message, title: str, cc_list: list[str]):
    # split in 25 field chunks (max embed number of fields)
    chunks = [cc_list[i : i + 25] for i in range(0, len(cc_list), 25)]
    for index, chunk in enumerate(chunks):
        chunked = f" ({index+1}/{len(chunks)})" if len(chunks) > 1 else ""
        embed = discord.Embed(
            title=title,
            description=f"List of all {title.lower()} with their country " f"codes{chunked}",
            color=COLOR_INFO,
        )
        for cc in chunk:
            value = cc
            # add mapping (if exists) to the cc value
            if cc in _cc_mapping.keys():
                value = f"{cc} / {_cc_mapping[cc]}"
                cc = _cc_mapping[cc]
            embed.add_field(name=_lang_lut[cc], value=value)
        await message.channel.send(embed=embed)


async def _get_wotd_from_file(guild_id: int):
    file_extension = Settings.get(guild_id, "wotd_type")
    filename = f"guild_data/{guild_id}-wotd.{file_extension}"
    # generate word and remove from the current wordlist
    with io.open(filename, encoding="utf-8") as f:
        lines = f.readlines()
        if not lines:
            print(f"wotd list empty for guild: {guild_id}")
            return (False, "")
        wotd = random.choice(lines)
        lines.remove(wotd)

    # save the wordlist with the word removed
    with io.open(filename, "w", encoding="utf-8") as f:
        f.writelines(lines)

    return (True, wotd)


async def _verify_wotd_requirements(guild_id: int, channel: TextChannel | None = None):
    # verify that the wotd_channel and wotd_language is available
    # otherwise let the user know in the message channel
    if not Settings.get(guild_id, "wotd_channel"):
        if channel:
            embed = discord.Embed(
                title=f"WOTD channel",
                description=f"No WOTD channel configured yet!",
                color=COLOR_ERROR,
            )
            await channel.send(embed=embed)
        return False
    if not Settings.get(guild_id, "wotd_language"):
        if channel:
            embed = discord.Embed(
                title=f"WOTD language",
                description=f"No WOTD language configured yet!",
                color=COLOR_ERROR,
            )
            await channel.send(embed=embed)
        return False

    return True


async def _generate_wotd(guild_id: int, force=False, msg_channel: TextChannel | None = None):
    # generate a wotd if no wotd is generated today,
    # or when forced via wotd command

    if not await _verify_wotd_requirements(guild_id, msg_channel):
        # no wotd channel or languageconfigured, return
        return
    today = str(datetime.fromtimestamp(time.time()).date())
    if not force and (today == Settings.get(guild_id, "wotd_date")):
        # wotd already shown today, and not forced to show one
        return

    # update settings file with today
    Settings.set(guild_id, "wotd_date", today)
    # get guild and channel
    guild = bot.get_guild(guild_id)
    if not guild:
        embed = discord.Embed(
            title=f"WOTD language",
            description=f"FATAL: could not get guild from guild_id!",
            color=COLOR_ERROR,
        )
        if msg_channel:
            await msg_channel.send(embed=embed)
        return
    channel: TextChannel = guild.get_channel(int(str(Settings.get(guild_id, "wotd_channel"))))  # type:ignore
    if not channel:
        embed = discord.Embed(
            title=f"WOTD language",
            description=f"FATAL: could not get wotd_channel for this guild_id!",
            color=COLOR_ERROR,
        )
        if msg_channel:
            await msg_channel.send(embed=embed)
        return
    # get wotd from file
    result, wotd = await _get_wotd_from_file(guild_id)
    wotd = wotd.strip()
    if not result:
        # wotd list is empty
        embed = discord.Embed(
            title=f"WOTD list is empty!",
            color=COLOR_ERROR,
        )
        await channel.send(embed=embed)
        return

    # we do have a valid wotd here, send it to the guild
    print(f"wotd for guild: {guild_id} is: {wotd}")
    cc = str(Settings.get(guild_id, "wotd_language"))
    language = _lang_lut[cc]
    if Settings.get(guild_id, "wotd_type") == "tsv":
        to_cc = str(Settings.get(guild_id, "wotd_to_language"))
        to_language = _lang_lut[to_cc]
        from_word = wotd.split("\t")[0]
        to_word = wotd.split("\t")[1]
        embed = (
            discord.Embed(
                title=f"{language} word of the day {today}",
                color=COLOR_INFO,
            )
            .add_field(name=f"{language}", value=f"{from_word}", inline=False)
            .add_field(name=f"{to_language}", value=f"{to_word}", inline=False)
        )
        await channel.send(embed=embed)
    else:
        embed = discord.Embed(
            title=f"{language} word of the day {today}",
            description=f"{wotd}",
            color=COLOR_INFO,
        )
        await channel.send(embed=embed)

        # send the translate command to translate the wotd
        command = f"{Settings.get(guild_id, 'command_prefix')}{cc}2en {wotd}"
        await channel.send(command)


@tasks.loop(seconds=10.0)
async def background_task_wotd():
    if not bot.is_ready():
        return

    try:
        settings = Settings.load_settings_file()
        for guild_id in settings.get("guilds", []):
            await _generate_wotd(guild_id)
    except Exception as e:
        print(str(e))  # print the exception for debugging purposes


bot.run(DISCORD_TOKEN)
