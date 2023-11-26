from datetime import datetime
import json
import hashlib
import os
from pathlib import Path
import random
import re
import requests
import time

import discord
from discord import Member
from discord import Message
from discord.channel import TextChannel
from discord.ext import tasks
from discord.ext.commands import Bot
from discord.ext.commands import Context

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
API_KEY = os.getenv("API_KEY")
API_URL_WB = os.getenv("API_URL_WB")
DISCORD_GUILD = os.getenv("DISCORD_GUILD")
assert DISCORD_TOKEN, f"FATAL: discord token 'DISCORD_TOKEN' not found in env!"
assert API_KEY, f"FATAL: SMMO API 'API_KEY' not found in env!"
assert API_URL_WB, f"FATAL: SMMO API 'API_URL_WB' not found in env!"
assert DISCORD_GUILD, f"FATAL: discord target guild name 'DISCORD_GUILD' not found in env!"

# make sure that the data directory exists
Path("data/").mkdir(exist_ok=True)

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# set the command prefix and the bot's status
command_prefix = ">"
activity = discord.Activity(type=discord.ActivityType.watching, name=f"'{command_prefix}help'")
# create the bot
bot = Bot(command_prefix=command_prefix, activity=activity, intents=intents)


_bot_initialized = False
_last_notified_boss = 0
_notify_before_sec = 0
_morse_dict = {}
_wb_commands = {}


@bot.event
async def on_ready():
    # create references to the (written) global data structures
    global _bot_initialized
    global _morse_dict
    global _wb_commands

    _bot_initialized = True
    _unserialize_from_disk()

    with open("morse_dict.json") as f:
        _morse_dict = json.load(f)

    _wb_commands = {
        "next": {
            "func": _wb_cmd_next,
            "help": "show when the next world boss is attackable [info]",
            "admin": False,
        },
        "all": {
            "func": _wb_cmd_all,
            "help": "show all upcoming world bosses [info]",
            "admin": False,
        },
        "notify-sec": {
            "func": _wb_notify_sec,
            "help": "set the number of seconds to notify before actual wb",
            "admin": True,
        },
        "cycle": {
            "func": _wb_perform_notify_task,
            "help": "manually invoke the cyclic wb notify task",
            "admin": True,
        },
    }

    # start the background task
    await smmo_bot_background_task.start()


def _serialize_to_disk():
    obj = {
        "last_notified_boss": _last_notified_boss,
        "notify_before_sec": _notify_before_sec,
    }
    with open("data/db.json", "w") as f:
        json.dump(obj, f)


def _unserialize_from_disk():
    # create references to the (written) global data structures
    global _last_notified_boss
    global _notify_before_sec

    try:
        with open("data/db.json", "r") as f:
            json.load(f)
    except:
        # database doesn't exist, create an empty one
        print("ERROR: failed to open db.json!")
        print("resetting database to default...")
        with open("data/db.json", "w") as f:
            json.dump({}, f)
    with open("data/db.json", "r") as f:
        obj: dict = json.load(f)
        _last_notified_boss = obj.get("last_notified_boss", 0)
        _notify_before_sec = obj.get("notify_before_sec", 0)


@bot.event
async def on_message(message: Message):
    # make sure that commands are executed as well
    await bot.process_commands(message)

    if message.author.bot:  # ignore bots
        return

    # message from the creator
    if "げんきですか" in message.content:
        if "mahol" in message.content.lower() or "まほる" in message.content.lower():
            if message.author.id == 151397544079917056:
                await message.channel.send(f"はい、げんきです！")
                await message.channel.send(f"(yes, I'm fine!)")
                await message.channel.send(f":thumbsup:")
            else:
                await message.channel.send(f"you're not the creator/parent!")

    # make bot repeat a sentence
    if message.author.id == 151397544079917056:
        if "mahol, repeat:" in message.content:
            output = message.content.replace("mahol, repeat:", "")
            await message.channel.send(output.strip())
            await message.delete()

    hotword = None
    if "KOOHII" in message.content or "コーヒー" in message.content:
        hotword = "KOOHII"
    elif "COFFEE" in message.content:
        hotword = "COFFEE"
    elif "TEA" in message.content:
        hotword = "TEA"

    if hotword:
        if hotword == "KOOHII":
            await message.channel.send(f"コーヒーおください")
        else:
            if "?" in message.content:
                await message.channel.send("What an absurd question. " f"Absolutely it's time for {hotword}, always!")
            else:
                await message.channel.send(f"Did someone mention {hotword}??")
        emoji_list = [
            742343615497502750,
            742131952634560573,
            745579354934870117,
            745579356234973204,
            745579357074096249,
        ]
        emoji = random.choice(emoji_list)
        await message.channel.send(f"{bot.get_emoji(emoji)}")

    await _try_morse(message)


async def _try_morse(message: Message):
    match = re.match(
        r">morse\s*(dot=(?P<dot>[^\s]))?\s*(dash=(?P<dash>[^\s]))?\s*" r"(?P<morse>.*)",
        message.content,
    )

    if not match:
        return

    gd = match.groupdict()

    output = ""
    for letter in gd["morse"]:
        if _morse_dict.get(letter.lower()):
            morse = _morse_dict.get(letter.lower(), "")
            translate_dict = {
                ".": gd.get("dot") or ".",
                "-": gd.get("dash") or "-",
            }
            morse = "".join([translate_dict.get(i, "") for i in morse])
        else:
            morse = letter
        output += morse + " " * 3

    output = f"`{output.strip()}`"
    embed = (
        discord.Embed(title="Morse")
        .add_field(name="Text", value=f'`{gd["morse"]}`', inline=False)
        .add_field(name="Translation", value=output, inline=False)
    )
    await message.channel.send(embed=embed)


async def _ensure_authorized(ctx: Context):
    # bot must be initialized
    if not _bot_initialized:
        await ctx.send("ERROR: bot is not initialized!")
        return False

    if not ctx.guild:
        await ctx.send("ERROR: no guild!")
        return False

    # verify user is part of Administrators
    role = discord.utils.find(lambda r: r.name == "Administrators", ctx.guild.roles)
    if not isinstance(ctx.message.author, Member):
        await ctx.send("ERROR: not a member!")
        return False

    if role not in ctx.message.author.roles:
        await ctx.send(f"{ctx.message.author.name} you are not authorized to use" " this bot or command!")
        return False

    return True


@bot.command(name="sum", help="calculate the sum of all inputs")
async def handle_sum(ctx: Context, *args):
    try:
        ints = map(float, args)
        await ctx.send(f"the calculated sum is: {sum([*ints])}")
    except:
        await ctx.send(f"ERROR: {[*args]} are invalid arguments for the sum command!")


@bot.command(
    name="pfp",
    help="fetch the profile picture of current user or [mention]",
)
async def handle_pfp(ctx: Context, *args):
    if len(args) < 1:
        user_id = ctx.author.id
    elif len(args) == 1:
        match = re.match(r"<@[^0-9]?(?P<user_id>[0-9]*)>", args[0])
        if not match or not match.groupdict().get("user_id"):
            embed = discord.Embed(
                title=f"ERROR",
                description="Invalid mention supplied to command!",
                color=0xFE3232,
            )
            await ctx.send(embed=embed)
            return
        user_id = match.groupdict()["user_id"]
    else:  # len(args) > 1
        embed = discord.Embed(
            title=f"ERROR",
            description="Only supply an optional mention to this command!",
            color=0xFE3232,
        )
        await ctx.send(embed=embed)
        return

    if not ctx.guild:
        embed = discord.Embed(
            title=f"ERROR",
            description="Invalid discord server!",
            color=0xFE3232,
        )
        await ctx.send(embed=embed)
        return
    # we have a user_id
    user = ctx.guild.get_member(int(user_id))
    if not user:
        embed = discord.Embed(
            title=f"ERROR",
            description="Invalid user supplied!",
            color=0xFE3232,
        )
        await ctx.send(embed=embed)
        return
    pfp = user.avatar
    embed = discord.Embed(
        title=f"Profile picture of {str(user.name)}",
        color=0x3232FE,
    )
    embed.set_image(url=(pfp))
    await ctx.send(embed=embed)


@bot.command(name="ship", help="provides rating of ships")
async def handle_ship(ctx: Context, *args):
    async def send_invalid_arguments():
        usage = [
            "ship yourself with someone/something else:",
            "`ship <mention>|<thing>`",
            "",
            "ship someone/something with someone/something else:",
            "`ship <mention1>|<thing1> [and] <mention2>|<thing2>`",
        ]
        embed = discord.Embed(
            title=f"ERROR",
            description="Invalid arguments to ship command!",
            color=0xFE3232,
        ).add_field(name="Usage", value="\n".join(usage), inline=False)
        await ctx.send(embed=embed)

    # validate that a correct number and position of arguments
    arglen = len(args)
    if arglen < 1 or arglen > 3 or (arglen == 3 and "and" not in args[1]):
        await send_invalid_arguments()
        return

    # we have arguments
    argstr = " ".join(args)
    # match id_1 OR thing_1 and optionally match id_2 OR thing_2
    match = re.match(
        r"(<@[^0-9]?(?P<id_1>[0-9]*)>|(?P<thing_1>[\S]*))"
        r"(( and)? (<@[^0-9]?(?P<id_2>[0-9]*)>|(?P<thing_2>[\S]*)))?",
        argstr,
    )
    if not match:
        await send_invalid_arguments()
        return

    if not ctx.guild:
        embed = discord.Embed(
            title=f"ERROR",
            description="Invalid discord server!",
            color=0xFE3232,
        )
        await ctx.send(embed=embed)
        return
    # we have either 1 or 2 id's
    gd = match.groupdict()
    id_1 = gd.get("id_1")
    thing_1 = gd.get("thing_1") or ""
    id_2 = gd.get("id_2")
    thing_2 = gd.get("thing_2") or ""
    hash_1 = int(hashlib.md5(thing_1.encode("utf-8")).hexdigest(), 16)
    hash_2 = int(hashlib.md5(thing_2.encode("utf-8")).hexdigest(), 16)
    value_1 = id_1 or (hash_1 if thing_1 else None)
    value_2 = id_2 or (hash_2 if thing_2 else None)
    user_1 = None
    user_2 = None
    if id_1 or id_2:
        user_1 = ctx.guild.get_member(int(id_1)) if id_1 else None
        user_2 = ctx.guild.get_member(int(id_2)) if id_2 else None
        if (id_1 and not user_1) or (id_2 and not user_2):
            embed = discord.Embed(
                title=f"ERROR",
                description="Invalid mention provided to ship command!",
                color=0xFE3232,
            )
            await ctx.send(embed=embed)
            return
    name_1 = user_1.display_name if user_1 else thing_1
    name_2 = user_2.display_name if user_2 else thing_2

    # make sure to use author if no 2 arguments are supplied
    if not value_2:
        value_2 = ctx.author.id
        name_2 = ctx.guild.get_member(int(value_2))
        if name_2:
            name_2 = name_2.display_name

    if not value_1:
        embed = discord.Embed(
            title=f"ERROR",
            description="Invalid value provided to ship command!",
            color=0xFE3232,
        )
        await ctx.send(embed=embed)
        return
    # we have 2 valid names and values here, calculate and display rating
    s = int(value_1) + int(value_2)
    rate = s % 11
    msg = f"**{name_1}** and **{name_2}**"
    embed = discord.Embed(
        description=f":thinking: I'd give {msg} a **{rate}/10**",
        color=0x3232FE,
    )

    await ctx.send(embed=embed)


@bot.command(name="wb", help="wb related commands, type wb help for info")
async def handle_wb(ctx: Context, *args):
    if len(args):
        wb_command = _wb_commands.get(args[0])
        if wb_command:
            if wb_command["admin"]:
                if not await _ensure_authorized(ctx):
                    return
            await wb_command["func"](ctx, args)
            return

    # else, either no argument or no valid command, print help
    await _print_wb_help(ctx)


async def _print_wb_help(ctx: Context):
    wb_cmds = _wb_commands.items()
    cmds_pub = {k: v for k, v in wb_cmds if not v["admin"]}.items()
    cmds_adm = {k: v for k, v in wb_cmds if v["admin"]}.items()

    help_msg = "```World Boss - Help menu\n\n"
    help_msg += "Public commands:\n"
    help_msg += "\n".join([f'{k} - {v["help"]}' for k, v in cmds_pub])
    help_msg += "\n\nAdmin commands:\n"
    help_msg += "\n".join([f'{k} - {v["help"]}' for k, v in cmds_adm])
    help_msg += "```"
    await ctx.send(help_msg)


async def _wb_cmd_next(ctx: Context, args):
    data = _fetch_wb_data()
    if data:
        next_wb = data[0]
        show_info = len(args) > 1 and args[1] == "info"
        msg = _wb_generate_msg(next_wb, True, show_info)
    else:
        msg = "there are currently no world bosses available"

    await ctx.send(msg)


async def _wb_cmd_all(ctx: Context, args):
    data = _fetch_wb_data()
    info = len(args) > 1 and args[1] == "info"
    msg = "\n".join([_wb_generate_msg(d, False, info) for d in data])
    if not msg:
        msg = "there are currently no world bosses available"
    await ctx.send(msg)


async def _wb_notify_sec(ctx: Context, args):
    # create references to the (written) global data structures
    global _notify_before_sec

    message = "wb notify-sec: "
    if len(args) < 2:
        message += f"{_notify_before_sec} seconds"
    else:
        try:
            sec = int(args[1])
            _notify_before_sec = sec
            _serialize_to_disk()
            message += f"set notify-before-sec to {sec} seconds"
        except:
            message += "ERROR: invalid argument supplied!"

    await ctx.send(message)


async def _wb_perform_notify_task(ctx: Context | None, args):
    # create references to the (written) global data structures
    global _last_notified_boss

    next_wb = _next_wb_to_notify()
    if not next_wb:
        return  # no wb available

    server_time = round(time.time())
    diff = next_wb["enable_time"] - server_time
    if diff > _notify_before_sec:
        return  # don't notify (yet) for next wb

    # store this enable_time as last notified wb time
    _last_notified_boss = next_wb["enable_time"]
    _serialize_to_disk()

    # notify about wb
    message = _wb_generate_msg(next_wb, True)
    guild = discord.utils.get(bot.guilds, name=DISCORD_GUILD)
    if not guild:
        print(f"FATAL: bot not connected to guild {DISCORD_GUILD}")
        return

    # this is only performed for TextChannel channels
    channel: TextChannel = list(filter(lambda g: "events" in g.name, guild.channels))[0]  # type:ignore
    await channel.send(message)


def _fetch_wb_data():
    result = requests.post(f"{API_URL_WB}?api_key={API_KEY}")
    data: list = json.loads(result.content.decode("utf-8"))
    # remove test bosses that have name 'Test'
    data = list(filter(lambda entry: entry["name"] != "Test", data))
    # sort on enable_time
    data.sort(key=lambda a: a["enable_time"])
    return data


def _next_wb_to_notify():
    # return the first wb that has enable_time larger than last notified
    for wb in _fetch_wb_data():
        if wb["enable_time"] > _last_notified_boss:
            return wb

    # return None if we didn't find a wb
    return None


# timestamp to datetime (server time)
def _ts2dt(timestamp):
    # return the timestamp with 3600 seconds subtracted (SMMO server time)
    return datetime.fromtimestamp(timestamp - 3600)


def _wb_generate_msg(wb, wb_is_next, show_info=False):
    diff = wb["enable_time"] - round(time.time())
    days = diff // 86400
    hours = (diff // 3600) % 24
    minutes = (diff // 60) % 60
    is_next = "next " if wb_is_next else ""
    serialized_wb_info = "\n".join([f"{key}: {wb[key]}" for key in wb])
    wb_info = f"\n{serialized_wb_info}" if show_info else ""
    return (
        f'The {is_next}world boss - **{wb["name"]}** - is attackable at '
        f'**{_ts2dt(wb["enable_time"])}** server time '
        f"({days} days, {hours} hours and {minutes} minutes from now) "
        f"{wb_info}"
    )


# hook to log errors to file
@bot.event
async def on_error(event, *args, **kwargs):
    # log the exception to file
    with open("data/error.log", "a") as f:
        f.write(f"Unhandled exception: {event} {args}, {kwargs}\n")


@tasks.loop(seconds=2.0)
async def smmo_bot_background_task():
    if not bot.is_ready():
        return

    # perform logics here
    try:
        # handle wb notifications
        await _wb_perform_notify_task(None, None)
    except Exception as e:
        print(str(e))  # print the exception for debugging purposes


bot.run(DISCORD_TOKEN)
