#!/usr/bin/python3

#base imports
from time import time
from requests import get
import dateutil.parser
import os
import json
import config
import pytz
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from templates import CTF_NEW, CTF_REMIND

#imports added along with discord portage
import discord
from gensim.utils import deaccent
from discord.ext import tasks,commands
import pickle
import asyncio
import inspect
import logging
import copy

# Setting the log level for the current program
log = logging.getLogger(__file__)
log.setLevel(logging.DEBUG)

file_handler = logging.FileHandler('ctfreminder.log')
file_handler.setLevel(logging.DEBUG)
log.addHandler(file_handler)

logger = logging.getLogger('discord')
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)

BOT_CHANNELS = {}
GUILDS_NEW = {}
GUILDS_REMINDER = {}

# URL for the CTFTIME API
CTFTIME_API_URL = "https://ctftime.org/api/v1/events/"

#interval at which this script is called
UPDATE_TIME = 5 * 60 #5 minutes

#day duration in seconds
DAY_TIMESTAMP = 60 * 60 * 24 #24 hours
YEAR_SECONDS = 31536000

HEADERS = {
    "User-Agent": config.USER_AGENT
}

#Function fetching CTF from timeStart to timeEnd
def fetch_ctfs(timeStart, timeEnd):

    #get request parameters
    dataParameters = {
        "limit":"1000",
        "start":str(timeStart),
        "finish":str(timeEnd),
    }
    
    r = get(url=CTFTIME_API_URL, headers=HEADERS, params=dataParameters)
    if r.status_code !=  200 :
        log.error("Ctftime responded with %d :(", r.status_code)
        return None

    return r.json()

#Function fetching all the CTFs events from CTFtime by calling the above function
def fetch_all_ctfs():
    print('Beginning fetching...')
    currentTime = int(time())  #strip the milliseconds
    return (fetch_ctfs(currentTime, currentTime + YEAR_SECONDS))

#Function sending messages
async def tweet_text(status: str) -> None:
    if config.PRODUCTION:
        await disc_msg(status)
    else:
        print("TWEET:")
        print(status)
        print("")

#Function preprocessing the brand new tweet to advertise for the newly published CTF
async def tweet_new_ctf(event: Dict[str, Any]) -> None:
    title = event["title"]
    organizers = event["organizers"][0]["name"]
    org_id = event["organizers"][0]["id"]
    ctftime_url = event["ctftime_url"]
    ctf_format = event["format"]
    url = event["url"]
    logo_url = event["logo"]

    log.info("Tweeting about a new ctf: %s", title)

    event_start = dateutil.parser.parse(event["start"])
    start = event_start.strftime("on %Y-%m-%d at %H:%M:%S UTC")
    timestamp = event_start.isoformat()

    # payload = NEW_CTF.format(title=title, start=start, url=ctftime_url)
    payload = copy.copy(CTF_NEW)
    payload["author"]["name"] = organizers
    payload["author"]["url"] = payload["author"]["url"].format(org_id=org_id)
    payload["fields"][0]["value"] = ctf_format
    payload["timestamp"] = timestamp
    payload["description"] = payload["description"].format(title=title,start=start,url=ctftime_url,ctf_url=url)

    if logo_url:
        payload["author"]["icon_url"] = logo_url

    embed = discord.Embed().from_dict(payload)
    await tweet_text(status=embed)

#Function preprocessing the remind tweet 24 hours before the beginning of the event
async def tweet_ctf_reminder(event: Dict[str, Any]) -> None:
    title = event["title"]
    organizers = event["organizers"][0]["name"]
    org_id = event["organizers"][0]["id"]
    ctftime_url = event["ctftime_url"]
    ctf_format = event["format"]
    url = event["url"]
    logo_url = event["logo"]

    log.info("Tweeting a reminder about a ctf: %s", title)

    event_start = dateutil.parser.parse(event["start"])
    timestamp = event_start.isoformat()

    # payload = REMIND_CTF.format(title=title, url=ctftime_url)
    payload = copy.copy(CTF_REMIND)
    payload["author"]["name"] = organizers
    payload["author"]["url"] = payload["author"]["url"].format(org_id=org_id)
    payload["fields"][0]["value"] = ctf_format
    payload["timestamp"] = timestamp
    payload["description"] = payload["description"].format(title=title,url=ctftime_url,ctf_url=url)

    if logo_url:
        payload["author"]["icon_url"] = logo_url

    embed = discord.Embed().from_dict(payload)
    await tweet_text(status=embed)

#Function used to read the events local database
def read_database() -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    if not os.path.exists(config.DB_PATH):
        return ([], [])
    else:
        with open(config.DB_PATH, 'r') as f:
            data = json.loads(f.read())
            return (
                data["mentioned_once"],
                data["mentioned_twice"]
            )

#Function used to save the database to file
def save_database(once: List[Dict[str, Any]], twice: List[Dict[str, Any]]) -> None:
    with open(config.DB_PATH, 'w') as f:
        f.write(json.dumps({
            "mentioned_once": once,
            "mentioned_twice": twice,
        }))

#Function sending messages on all the channels in the chans list
async def disc_msg(data, filename = None):

    call1 = inspect.stack()[1].function
    call2 = inspect.stack()[2].function
    newer = (call1 == "tweet_new_ctf" or call2 == "tweet_new_ctf")
    reminderer = (call1 == "tweet_ctf_reminder" or call2 == "tweet_ctf_reminder")

    for x,j in BOT_CHANNELS.items() :
        i = client.get_channel(j)
        if ( newer and x in GUILDS_NEW) or ( reminderer and x in GUILDS_REMINDER):
            log.info("Message disabled")
            break
        else :
            log.info("Sending msg")
            await i.send(embed= data)

class CTF(commands.Cog):
    def __init__(self,bot):
        self.bot = bot
        self.fetcher.start()

    def cog_unload(self):
        self.printer.cancel()

    #relaunch runtime function every UPDATE_TIME
    @tasks.loop(seconds=UPDATE_TIME)
    async def fetcher(self):
        #workflow used to fetch ctf and advertise them

        current_time = pytz.UTC.localize(datetime.now())

        log.info("Reading previously tweeted ctfs from database")
        first, second = read_database()
        log.info("Getting new ctfs")
        ctfs = fetch_all_ctfs()

        if not ctfs:
            log.error("Failed to get any ctfs")
            return

        for f in ctfs[::-1]:
            start_time = dateutil.parser.parse(f["start"])
            # do not report past ctfs
            if start_time > current_time:
                if not f["onsite"] and f["restrictions"] == "Open":
                    
                    ctf_id = f["ctf_id"]

                    if not ctf_id in second and not ctf_id in first:
                        await tweet_new_ctf(f)
                        first.append(ctf_id)
                        save_database(first, second)

                    if ctf_id in first and not ctf_id in second and current_time + timedelta(hours=24) > start_time:
                        await tweet_ctf_reminder(f)
                        second.append(ctf_id)
                        save_database(first, second)

        log.info("Finished fetching and advertising.")

    @fetcher.before_loop
    async def before_fetcher(self):
        print('waiting...')
        await self.bot.wait_until_ready()



#load default channels list, no big deal if unable to load it
try:
    BOT_CHANNELS=pickle.load(open(os.path.realpath("chans"),"rb"))
except:
    print("Couldn't load default channels.")

#load default prefs list, no big deal if unable to load it
try:
    GUILDS_NEW=pickle.load(open(os.path.realpath("new"),"rb"))
    GUILDS_REMINDER=pickle.load(open(os.path.realpath("reminder"),"rb"))
except:
    print("Couldn't load default prefs.")

#initializing the discord client object for the bot with the command prefix
client = commands.Bot(command_prefix="!")
print('Client created')

#on ready handler for the bot instance
@client.event
async def on_ready():
    try:
        # print bot information
        print('We have logged in as {0.user.name}'.format(client))
        print('The client id is {0.user.id}'.format(client))
        print('Discord.py Version: {}'.format(discord.__version__))
	
    except Exception as e:
        print(e)

#set_channel command handler, reachable only by server owner
@client.command(name="set_channel",help="A command to set the default for posting messages.")
@commands.check_any(commands.is_owner(),  commands.has_guild_permissions(administrator = True))
async def set_default_channel(ctx):
    msg = "Default channel set !"
    if ctx.channel.id in BOT_CHANNELS.values(): msg = "Default channel modified !"
    BOT_CHANNELS[ctx.guild.id] = ctx.channel.id
    pickle.dump(BOT_CHANNELS,open(os.path.dirname(os.path.realpath(__file__))+"/"+"chans",'wb'))
    await ctx.send(msg)

@client.command(name ="toggle_remind",help="Toggles posting for soon-starting ctfs")
async def remind(ctx):
    msg = None
    if ctx.guild.id in GUILDS_REMINDER:
        GUILDS_REMINDER.pop(ctx.guild.id)
        pickle.dump(GUILDS_REMINDER,open(os.path.realpath("reminder"),'wb'))
        msg ="Reminding enabled"
    else:
        GUILDS_REMINDER[ctx.guild.id] = True
        pickle.dump(GUILDS_REMINDER,open(os.path.realpath("reminder"),'wb'))
        msg ="Reminding disabled"
    await ctx.send(msg)

@client.command(name ="toggle_new",help="Toggles posting for new ctfs")
async def new_ctf(ctx):
    msg = None
    if ctx.guild.id in GUILDS_NEW:
        GUILDS_NEW.pop(ctx.guild.id)
        pickle.dump(GUILDS_NEW,open(os.path.realpath("new"),'wb'))
        msg ="Posting new ctf enabled"
    else:
        GUILDS_NEW[ctx.guild.id] = False
        pickle.dump(GUILDS_NEW,open(os.path.realpath("new"),'wb'))
        msg ="Posting new ctf disabled"
    await ctx.send(msg)

#on_guild_join handler, selecting general channel as default channel for posting advertisements
@client.event
async def on_guild_join(guild):
    for i in guild.channels:
        if deaccent(i.name.lower()) == "general":
            BOT_CHANNELS[guild.id] = i.id
            pickle.dump(BOT_CHANNELS,open(os.path.realpath("chans"),'wb'))

#add the CTF cog to run the background task fetching ctf
client.add_cog(CTF(client))

#launch the dscord bot
client.run(config.DISCORD_API_TOKEN)