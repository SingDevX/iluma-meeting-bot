import discord
from discord.ext import commands
import os
import asyncio

# Set up intents
intents = discord.Intents.default()
intents.message_content = True  # Enable message content intent to process commands
intents.guilds = True          # Enable guild-related events

# Set up the bot with a command prefix and intents
bot = commands.Bot(command_prefix='!', intents=intents)

# Event: Bot is ready
@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')

# Function to send meeting announcement with MT times
async def send_meeting_announcement(day):
    channel = discord.utils.get(bot.get_all_channels(), name="general")  # Replace with your channel name
    if channel:
        if day == 0:  # For Monday MT (triggered on Tuesday PHT)
            await channel.send("🚨 **Meeting Reminder**: Google Meet yesterday at 1:30 PM MT! Join here: https://meet.google.com/ide-jofk-rjj")
        elif day == 3:  # For Thursday MT (triggered on Friday PHT)
            await channel.send("🚨 **Meeting Reminder**: Google Meet yesterday at 12:00 PM MT! Join here: https://meet.google.com/ide-jofk-rjj")
    else:
        print("Channel not found.")

# Webhook command to trigger announcement
@bot.command()
async def webhook(ctx, day: str):
    if day == "monday":
        await send_meeting_announcement(0)
        await ctx.send("Announcement sent for Monday MT!")
    elif day == "thursday":
        await send_meeting_announcement(3)
        await ctx.send("Announcement sent for Thursday MT!")

# Run the bot
bot.run(os.getenv('BOT_TOKEN'))  # Use environment variable