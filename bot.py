import os
import json
import http.server
import socketserver
import threading
import discord
from discord.ext import commands, tasks
import logging
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from datetime import datetime, timedelta, UTC  # Updated for timezone-aware datetime

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

# Function to fetch the latest Gemini summary (keyword-based, configurable time window)
def get_latest_gemini_summary(hours_back=24):  # CHANGED: 24 hours for testing
    one_hour_ago = (datetime.now(UTC) - timedelta(hours=hours_back)).isoformat() + 'Z'
    query = "mimeType='application/vnd.google-apps.document' and name contains 'Notes by Gemini' and modifiedTime > '{}' and trashed=false".format(one_hour_ago)
    try:
        results = drive_service.files().list(q=query, fields="files(id, name, modifiedTime)").execute()
        files = results.get('files', [])
        if files:
            latest_file = max(files, key=lambda x: x['modifiedTime'])
            doc_id = latest_file['id']
            doc = drive_service.files().export(fileId=doc_id, mimeType='text/plain').execute()
            logger.info(f"Found and exported Gemini summary: {latest_file['name']} (ID: {doc_id})")
            return doc.decode('utf-8')
        return "No Gemini summary found in the last {} hour(s)!".format(hours_back)
    except Exception as e:
        logger.error(f"Error fetching Gemini summary: {e}")
        return f"Error fetching summary: {e}"

# Automated task to check and announce meetings
@tasks.loop(hours=24)  # Runs every 24 hours
async def check_meetings():
    current_time = datetime.now(UTC)
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
        if not isinstance(summary, str):
            await ctx.send("Error: Summary is not a valid string!")
            logger.error("Summary is not a string")
            return
        
        max_length = 4000
        if len(summary) > max_length:
            # Word-based splitting to avoid mid-word cuts
            words = summary.split()
            current_chunk = []
            current_length = 0
            part_number = 1
            
            for word in words:
                word_length = len(word) + 1  # +1 for space
                if current_length + word_length > max_length:
                    # Send current chunk
                    chunk_text = ' '.join(current_chunk)
                    try:
                        await channel.send(f"🚨 **{day.capitalize()} Meeting Summary (Part {part_number})**:\n{chunk_text}")
                        logger.info(f"Sent Part {part_number} ({len(chunk_text)} chars)")
                        part_number += 1
                        current_chunk = [word]
                        current_length = word_length
                        # Small delay to avoid rate limits
                        await asyncio.sleep(0.5)
                    except Exception as e:
                        logger.error(f"Error sending Part {part_number}: {e}")
                        await ctx.send(f"Error sending Part {part_number}: {e}")
                else:
                    current_chunk.append(word)
                    current_length += word_length
            
            # Send final chunk if any
            if current_chunk:
                chunk_text = ' '.join(current_chunk)
                try:
                    await channel.send(f"🚨 **{day.capitalize()} Meeting Summary (Part {part_number})**:\n{chunk_text}")
                    logger.info(f"Sent final Part {part_number} ({len(chunk_text)} chars)")
                except Exception as e:
                    logger.error(f"Error sending final part: {e}")
                    await ctx.send(f"Error sending final part: {e}")
        else:
            try:
                await channel.send(f"🚨 **{day.capitalize()} Meeting Summary**:\n{summary}")
                logger.info(f"Sent single summary ({len(summary)} chars)")
            except Exception as e:
                logger.error(f"Error sending summary: {e}")
                await ctx.send(f"Error sending summary: {e}")
        
        await ctx.send(f"✅ Summary posted for {day} MT! ({len(summary)} total chars)")
        logger.info(f"Summary posting completed for {day} MT")
    else:
        logger.error("Channel not found")
        await ctx.send("❌ Error: General channel not found!")

# Import asyncio for sleep (needed for rate limiting)
import asyncio

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
