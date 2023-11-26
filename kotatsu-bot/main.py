import hashlib
import os
import re

import discord
from discord.ext import commands
from discord.ext.commands import Bot
from discord.ext.commands import Context

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
assert DISCORD_TOKEN, f"FATAL: discord token 'DISCORD_TOKEN' not found in env!"

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# set the command prefix and the bot's status
command_prefix = ">"
activity = discord.Activity(type=discord.ActivityType.watching, name=f"'{command_prefix}help'")
# create the bot
bot = Bot(command_prefix=command_prefix, activity=activity, intents=intents)


@bot.event
async def on_ready():
    if bot.user:
        print(f"{bot.user.name} ({bot.user}) has connected to discord!")


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


# hook to log errors to file
@bot.event
async def on_error(event, *args, **kwargs):
    # log the exception to file
    with open("data/error.log", "a") as f:
        f.write(f"Unhandled exception: {event} {args}, {kwargs}\n")


bot.run(DISCORD_TOKEN)
