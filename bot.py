import os
import http.server
import socketserver
import threading
import discord
from discord.ext import commands
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set up intents
intents = discord.Intents.default()
intents.message_content = True  # Enable message content intent
intents.guilds = True          # Enable guild-related events

# Set up the bot with a command prefix and intents
bot = commands.Bot(command_prefix='!', intents=intents)

# Event: Bot is ready
@bot.event
async def on_ready():
    logger.info(f'Logged in as {bot.user}')
    channel = discord.utils.get(bot.get_all_channels(), name="general")
    if channel:
        await channel.send("Bot is online!")
        logger.info("Bot announced online in general channel")

# Function to send meeting announcement
async def send_meeting_announcement(day):
    channel = discord.utils.get(bot.get_all_channels(), name="general")
    if channel:
        if day == 0:  # Monday MT
            await channel.send("🚨 **Meeting Reminder**: Google Meet yesterday at 1:30 PM MT! Join here: https://meet.google.com/ide-jofk-rjj")
            logger.info("Sent Monday meeting reminder")
        elif day == 3:  # Thursday MT
            await channel.send("🚨 **Meeting Reminder**: Google Meet yesterday at 12:00 PM MT! Join here: https://meet.google.com/ide-jofk-rjj")
            logger.info("Sent Thursday meeting reminder")
    else:
        logger.error("Channel not found")

# Webhook command
@bot.command()
async def webhook(ctx, day: str):
    logger.info(f"Received webhook command for {day}")
    if day == "monday":
        await send_meeting_announcement(0)
        await ctx.send("Announcement sent for Monday MT!")
        logger.info("Announcement sent for Monday MT")
    elif day == "thursday":
        await send_meeting_announcement(3)
        await ctx.send("Announcement sent for Thursday MT!")
        logger.info("Announcement sent for Thursday MT")

# Dummy HTTP server for Render Web Service
class DummyHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(b"Dummy server running")
        logger.info("Dummy HTTP server handled a request")

def run_dummy_http_server():
    PORT = 10000
    with socketserver.TCPServer(("", PORT), DummyHandler) as httpd:
        logger.info(f"Dummy HTTP server running on port {PORT}")
        httpd.serve_forever()

# Start dummy server in a daemon thread
threading.Thread(target=run_dummy_http_server, daemon=True).start()

# Ensure the server starts before running the bot
asyncio.run(asyncio.sleep(1))  # Give the thread a moment to start

# Run the bot
bot.run(os.getenv('BOT_TOKEN'))
