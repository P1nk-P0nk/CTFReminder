#!/usr/bin/python3

from time import time
from requests import get
import discord
import dateutil.parser
import os
from bs4 import BeautifulSoup

from gensim.utils import deaccent
from discord.ext import commands
import pickle
import asyncio


DISCORD_API_TOKEN = None
BOT_CHANNELS = {}

CTFTIME_API_URL = "https://ctftime.org/api/v1/events/"

#interval at which this script is called
UPDATE_TIME = 5 * 60 #5 minutes
DAY_TIMESTAMP = 60 * 60 * 24 #24 hours


NEW_CTF = """New CTF!
{}, starts at {}
{}
"""

NEW_CTF_TWITTER = """New CTF!
{} organized by {}, starts at {}
{}
"""

REMIND_CTF = """{} starts in under 24 hours!
{}
"""

REMIND_CTF_TWITTER = """{} organized by {} starts in under 24 hours!
{}
"""

#Function fetching CTF from timeStart to timeEnd
def fetchCtfs(timeStart, timeEnd):

    #get request parameters
    dataParameters = {
        "limit":"1000",
        "start":str(timeStart),
        "finish":str(timeEnd),
    }
    
    header = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "fr,en-US;q=0.7,en;q=0.3",
        "Connection": "keep-alive",
        "DNT": "1",
        "Host": "ctftime.org",
        "TE": "Trailers",
        "Upgrade-Insecure-Requests": "1",
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:72.0) Gecko/20100101 Firefox/72.0"
    }

    r = get(url=CTFTIME_API_URL, headers=header, params=dataParameters)

    #u wot m8
    payload = r.text.replace("false", "False").replace("true", "True")

    print(payload)

    return eval(payload)

#Function fetching all the CTFs events from CTFtime by calling the above function
def fetchAll():
    print('Beginning fetching')
    currentTime = int(time())  #strip the milliseconds
    print(currentTime)
    print(currentTime + 1000000000)
    return (fetchCtfs(currentTime, currentTime + 1000000000))

# #initializes the twitter API handler with OAuth
# def initAPI():
#     config = open(os.path.dirname(os.path.realpath(__file__))+"/config", "r").read().split("\n")

#     consumer_key = config[0]
#     consumer_secret = config[1]
#     access_token = config[2]
#     access_token_secret = config[3]

#     auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
#     auth.set_access_token(access_token, access_token_secret)

#     return tweepy.API(auth)

#Function extracting data from files
def readFrom(file):
    f = open(os.path.dirname(os.path.realpath(__file__))+"/"+file, "r")
    r = f.read()
    f.close()
    return eval(r)

#Function writing data to files
def writeTo(q, file):
    f = open(os.path.dirname(os.path.realpath(__file__))+"/"+file, "w")
    f.write(str(q))
    f.close()

#Function appending data to a previously written file 
def appendTo(q, file):
    tab = readFrom(file)
    tab.append(q)
    writeTo(tab, file)

#Function emitting the tweet with the event logo
async def tweetWithImage(data, imageUrl):
    
    #name for the temporary file of the event logo
    filename = 'temp.png'

    #requests the image and attempt to use it, if it exists
    request = get(imageUrl, stream=True)
    if request.status_code == 200:
        with open(filename, 'wb') as image:
            for chunk in request:
                image.write(chunk)

        try:
            #api.update_with_media(filename, status=data)
            await disc_msg(data,filename)
        except client.on_error:
            await disc_msg(data)

        os.remove(filename)

    #coulnd't get the image, tough luck
    else:
        await disc_msg(data)

#Function searching for the organizer twitter account and returns its @
def getOrganizerTwitterHandle(organizer):
    data = get("https://ctftime.org/team/" + str(organizer)).text

    soup = BeautifulSoup(data, "lxml")

    ret = ""

    for i in soup.find_all("div", {"class":"span10"}):

        for c in i.children:
            for q in str(c).split("\n"):
                if "Twitter:" in q:
                    if "http" in q:
                        s = BeautifulSoup(q, "lxml")
                        url = s.find_all("a")[0].get("href")
                        ret = "@" + url.split("/")[-1]
                    elif "@" in q:
                        ret = q[12:-4]
                    else:
                        ret = "@" + q[12:-4]

    return ret

#Function preprocessing the brand new tweet to advertise for the newly published CTF
async def tweetNew(event):
    print("Tweet new")

    start = event["start"].replace("T", " ")[:-6]+" UTC"

    
    orgTwitter = getOrganizerTwitterHandle(event["organizers"][0]["id"])

    #if organizer has a twitter account
    if orgTwitter != "":
        payload = NEW_CTF_TWITTER.format(event["title"], orgTwitter, start, event["ctftime_url"])
    else:
        payload = NEW_CTF.format(event["title"], start, event["ctftime_url"])

    #if the formatted message is too long, remove additional informations
    if len(payload) > 140:
        payload = NEW_CTF.format(event["ctftime_url"], start, "")

    #if the event as a logo, tweet with it
    if(event["logo"] != ""):
        await tweetWithImage(payload, event["logo"])
    else:
        await disc_msg(payload)

#Function preprocessing the remind tweet 24 hours before the beginning of the event
async def tweetRemind(event):
    print("Tweet remind")

    orgTwitter = getOrganizerTwitterHandle(event["organizers"][0]["id"])

    if(orgTwitter != ""):
        payload = REMIND_CTF_TWITTER.format(event["title"], orgTwitter, event["ctftime_url"])
    else:
        payload = REMIND_CTF.format(event["title"], event["ctftime_url"])

    if len(payload) > 140:
        payload = REMIND_CTF.format(event["ctftime_url"], ":)")

    if(event["logo"] != ""):
        await tweetWithImage(payload, event["logo"])
    else:
        await disc_msg(payload)

#Function checking if the ctf is in the list
def ctfInList(ctf, list):
    for i in list:
        if i["ctf_id"] == ctf["ctf_id"]:
            return True
    return False

#Function sending messages on all the channels in the chans list
async def disc_msg(data, image = None):

    for j in BOT_CHANNELS.values() :
        i = client.get_channel(j)
        if image != None : 
            await i.send(data, file= image )
        else : 
            await i.send(data)

#get current time in unix epoch
currentTime = int(time())

try: 
    DISCORD_API_TOKEN=open("./token",'r').readline().strip()
except:
    print("Couldn't load Discord API token.\nStopping.")
    exit(-1)

try:
    BOT_CHANNELS=pickle.load(open("chans","rb"))
except:
    print("Couldn't load default channels.")

#initializing the discord client object for the bot and starting it
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
        await update()
	
    except Exception as e:
        print(e)

@client.command(name="set_channel",help="A command to set the default for posting messages.")
@commands.is_owner()
async def set_default_channel(ctx):
    msg = "Default channel set !"
    if ctx.channel.id in BOT_CHANNELS.values: msg = "Default channel modified !"
    BOT_CHANNELS[ctx.guild.id] = ctx.channel.id
    pickle.dump(open("chans",'wb'))

@client.event
async def on_guild_join(guild):
    for i in guild.channels:
        if deaccent(i.name.lower()) == "general":
            BOT_CHANNELS[guild.id] = i.id
            pickle.dump(open("chans",'wb'))

async def update():
    while(True):
        await runtime()
        await asyncio.sleep(UPDATE_TIME)

async def runtime():
    #advertised once
    first = readFrom("first")
    #advertised twice
    second = readFrom("second")

    #put the fetched ctf in a list to make it iterable
    justFetched = fetchAll()

    updates = 0


    for f in justFetched[::-1]:

        startTime = dateutil.parser.parse(f["start"])

        startTimeEpoch = int(startTime.strftime("%s"))
        #no need to think about ctfs for time travelers...
        if startTimeEpoch > currentTime:
            #we don't really care for onsite events
            if not f["onsite"] and f["restrictions"] == "Open":
                #brand new tweet
                if not ctfInList(f, second) and not ctfInList(f, first):
                    await tweetNew(f)
                    appendTo(f, "first")

                if ctfInList(f, first) and not ctfInList(f, second) and (startTimeEpoch-currentTime)<DAY_TIMESTAMP:
                    await tweetRemind(f)
                    appendTo(f, "second")

client.run(DISCORD_API_TOKEN)