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
from datetime import datetime, timedelta, UTC

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set up intents
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

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

# Function to fetch the latest Gemini summary
def get_latest_gemini_summary(hours_back=24):
    cutoff_time = datetime.now(UTC) - timedelta(hours=hours_back)
    one_hour_ago = cutoff_time.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
    query = f"mimeType='application/vnd.google-apps.document' and name contains 'Notes by Gemini' and modifiedTime > '{one_hour_ago}' and trashed=false"
    
    logger.info(f"Querying Drive with: {query}")
    try:
        results = drive_service.files().list(q=query, fields="files(id, name, modifiedTime, parents)").execute()
        files = results.get('files', [])
        logger.info(f"Found {len(files)} matching files")
        
        # Log all found files for debugging
        for file in files:
            logger.info(f"File: {file['name']}, ID: {file['id']}, Modified: {file['modifiedTime']}, Parents: {file.get('parents', [])}")
        
        if files:
            latest_file = max(files, key=lambda x: x['modifiedTime'])
            doc_id = latest_file['id']
            doc_name = latest_file['name']
            logger.info(f"Exporting latest file: {doc_name} (ID: {doc_id})")
            
            doc = drive_service.files().export(fileId=doc_id, mimeType='text/plain').execute()
            logger.info(f"Successfully exported {len(doc)} bytes")
            content = doc.decode('utf-8')
            logger.info(f"Decoded content length: {len(content)} chars")
            logger.info(f"First 100 chars: {repr(content[:100])}")  # Debug first 100 chars
            return content
        else:
            logger.warning(f"No 'Notes by Gemini' docs found in last {hours_back} hours")
            return f"No Gemini summary found in the last {hours_back} hour(s)! Try checking file name or permissions."
            
    except Exception as e:
        logger.error(f"Error fetching Gemini summary: {e}")
        return f"Error fetching summary: {str(e)}"

# Automated task to check and announce meetings
@tasks.loop(hours=24)
async def check_meetings():
    current_time = datetime.now(UTC)
    current_day = current_time.weekday()
    mt_offset = -6
    mt_time = current_time.hour + mt_offset
    
    if current_day == 0 and 13 <= mt_time < 14:
        await send_meeting_announcement(0)
    elif current_day == 3 and 11 <= mt_time < 12:
        await send_meeting_announcement(3)

# Event: Bot is ready
@bot.event
async def on_ready():
    logger.info(f'Logged in as {bot.user}')
    channel = discord.utils.get(bot.get_all_channels(), name="general")
    if channel:
        await channel.send("Bot is online!")
        logger.info("Bot announced online in general channel")
    check_meetings.start()

# DEBUG Webhook command - SIMPLE PLAIN TEXT FIRST
@bot.command()
async def webhook(ctx, day: str):
    logger.info(f"Received webhook command for {day}")
    channel = discord.utils.get(bot.get_all_channels(), name="general")
    if not channel:
        logger.error("Channel not found")
        await ctx.send("❌ Error: General channel not found!")
        return
    
    summary = get_latest_gemini_summary()
    if not isinstance(summary, str):
        await ctx.send("Error: Summary is not a valid string!")
        logger.error("Summary is not a string")
        return
    
    logger.info(f"Processing {len(summary)} character summary")
    
    # STEP 1: Test with PLAIN TEXT first (no formatting)
    test_message = f"TEST: {day} summary ({len(summary)} chars): {summary[:1900]}..."  # First 1900 chars
    logger.info(f"TEST MESSAGE LENGTH: {len(test_message)} chars")
    logger.info(f"TEST MESSAGE PREVIEW: {repr(test_message[:100])}")
    
    try:
        await channel.send(test_message)
        logger.info("✅ PLAIN TEXT TEST PASSED!")
        await asyncio.sleep(2.0)  # Wait before next test
    except Exception as e:
        logger.error(f"❌ PLAIN TEXT TEST FAILED: {e}")
        await ctx.send(f"❌ Plain text test failed: {str(e)}")
        return
    
    # STEP 2: Test with FORMATTING (short version)
    short_header = f"🚨 **{day.capitalize()} Meeting Summary (TEST)**:\n"
    short_content = summary[:1800]  # Even shorter
    formatted_message = short_header + short_content
    logger.info(f"FORMATTED TEST LENGTH: {len(formatted_message)} chars")
    logger.info(f"FORMATTED HEADER LENGTH: {len(short_header)} chars")
    
    try:
        await channel.send(formatted_message)
        logger.info("✅ FORMATTED TEST PASSED!")
        await ctx.send(f"✅ Tests passed! Total summary: {len(summary)} chars")
    except Exception as e:
        logger.error(f"❌ FORMATTED TEST FAILED: {e}")
        await ctx.send(f"❌ Formatted test failed: {str(e)} (length: {len(formatted_message)})")
        return
    
    # STEP 3: If tests pass, do full split (simplified)
    if len(summary) <= 1900:  # Super conservative
        full_message = f"🚨 **{day.capitalize()} Meeting Summary**:\n{summary}"
        try:
            await channel.send(full_message)
            logger.info(f"✅ Sent full summary ({len(summary)} chars)")
            await ctx.send(f"✅ Full summary posted for {day} MT!")
        except Exception as e:
            logger.error(f"❌ Full summary failed: {e}")
            await ctx.send(f"❌ Full summary failed: {str(e)}")
    else:
        # Simple character split without word boundaries (for debug)
        max_chunk = 1800  # Ultra conservative
        for i in range(0, len(summary), max_chunk):
            chunk = summary[i:i + max_chunk]
            message = f"🚨 **{day.capitalize()} Summary Part {i//max_chunk + 1}**:\n{chunk}"
            logger.info(f"Sending chunk {i//max_chunk + 1}: {len(chunk)} chars, total: {len(message)} chars")
            
            try:
                await channel.send(message)
                logger.info(f"✅ Chunk {i//max_chunk + 1} sent successfully")
                await asyncio.sleep(2.0)
            except Exception as e:
                logger.error(f"❌ Chunk {i//max_chunk + 1} failed: {e}")
                await ctx.send(f"❌ Chunk {i//max_chunk + 1} failed: {str(e)}")
                break
        
        await ctx.send(f"✅ Debug posting completed for {day} MT! ({len(summary)} chars)")
        logger.info(f"🎉 Debug posting completed: {len(summary)} chars")

# Import asyncio for sleep
import asyncio

# Dummy HTTP server for Render
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
