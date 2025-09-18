import os
import http.server
import socketserver
import threading
import discord
from discord.ext import commands, tasks
import logging
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from datetime import datetime, timedelta

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set up intents
intents = discord.Intents.default()
intents.message_content = True  # Enable message content intent
intents.guilds = True          # Enable guild-related events

# Set up the bot with a command prefix and intents
bot = commands.Bot(command_prefix='!', intents=intents)

# Google Drive setup
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
creds = Credentials.from_service_account_info(
    json.loads(os.getenv('GOOGLE_APPLICATION_CREDENTIALS')), scopes=SCOPES)
drive_service = build('drive', 'v3', credentials=creds)

# Function to send meeting announcement
async def send_meeting_announcement(day):
    channel = discord.utils.get(bot.get_all_channels(), name="general")
    if channel:
        if day == 0:  # Monday MT
            await channel.send("🚨 **Meeting Reminder**: Google Meet today from 1:30 PM to 2:30 PM MT! Join here: https://meet.google.com/ide-jofk-rjj")
            logger.info("Sent Monday meeting reminder")
        elif day == 3:  # Thursday MT
            await channel.send("🚨 **Meeting Reminder**: Google Meet today from 12:00 PM to 1:00 PM MT! Join here: https://meet.google.com/ide-jofk-rjj")
            logger.info("Sent Thursday meeting reminder")
    else:
        logger.error("Channel not found")

# Function to fetch the latest Gemini summary (keyword-based, last hour, root Drive)
def get_latest_gemini_summary():
    # Calculate time 1 hour ago
    one_hour_ago = (datetime.utcnow() - timedelta(hours=1)).isoformat() + 'Z'
    # Query for Google Docs with "Notes by Gemini" in the name, modified in the last hour, in root
    query = "mimeType='application/vnd.google-apps.document' and name contains 'Notes by Gemini' and modifiedTime > '{}' and trashed=false".format(one_hour_ago)
    results = drive_service.files().list(q=query, fields="files(id, name, modifiedTime)").execute()
    files = results.get('files', [])
    if files:
        latest_file = max(files, key=lambda x: x['modifiedTime'])
        doc_id = latest_file['id']
        doc = drive_service.files().export(fileId=doc_id, mimeType='text/plain').execute()
        return doc.decode('utf-8')
    return "No Gemini summary found in the last hour!"

# Automated task to check and announce meetings
@tasks.loop(hours=24)  # Runs every 24 hours
async def check_meetings():
    current_time = datetime.utcnow()
    current_day = current_time.weekday()  # 0 = Monday, 3 = Thursday
    mt_offset = -6  # MT is UTC-6 (MDT); use -7 for PDT if applicable
    mt_time = current_time.hour + mt_offset
    
    # Announce 30 minutes before meeting
    if current_day == 0 and 13 <= mt_time < 14:  # Monday, 1:00 PM MT
        await send_meeting_announcement(0)
    elif current_day == 3 and 11 <= mt_time < 12:  # Thursday, 11:30 AM MT
        await send_meeting_announcement(3)

# Event: Bot is ready
@bot.event
async def on_ready():
    logger.info(f'Logged in as {bot.user}')
    channel = discord.utils.get(bot.get_all_channels(), name="general")
    if channel:
        await channel.send("Bot is online!")
        logger.info("Bot announced online in general channel")
    check_meetings.start()  # Start the automated task

# Webhook command (for summaries only, manual or n8n-triggered)
@bot.command()
async def webhook(ctx, day: str):
    logger.info(f"Received webhook command for {day}")
    channel = discord.utils.get(bot.get_all_channels(), name="general")
    if channel:
        summary = get_latest_gemini_summary()
        await channel.send(f"🚨 **{day.capitalize()} Meeting Summary**:\n{summary}")
        await ctx.send(f"Summary posted for {day} MT!")
        logger.info(f"Summary posted for {day} MT")
    else:
        logger.error("Channel not found")

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

# Run the bot
bot.run(os.getenv('BOT_TOKEN'))
