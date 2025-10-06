import discord
from discord.ext import commands
import os

# Create bot instance with command prefix
bot = commands.Bot(command_prefix='!', intents=discord.Intents.default())

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    print(f'Bot is in {len(bot.guilds)} servers.')

@bot.command(name='hello')
async def hello(ctx):
    """A simple hello command"""
    await ctx.send(f'Hello, {ctx.author.mention}!')

@bot.command(name='ping')
async def ping(ctx):
    """Check bot latency"""
    latency = round(bot.latency * 1000)
    await ctx.send(f'Pong! Latency: {latency}ms')

if __name__ == '__main__':
    # Get bot token from environment variable
    token = os.getenv('DISCORD_TOKEN')
    
    if not token:
        print("Error: DISCORD_TOKEN environment variable not found.")
        print("Please set your Discord bot token using the secrets manager.")
        print("To create a Discord bot and get a token:")
        print("1. Go to https://discord.com/developers/applications")
        print("2. Click 'New Application' and name your bot")
        print("3. Go to the 'Bot' section")
        print("4. Copy the token and add it as DISCORD_TOKEN in your secrets")
    else:
        bot.run(token)