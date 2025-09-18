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
            return doc.decode('utf-8')
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

# BULLETPROOF Webhook command
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
    
    # Single message case
    if len(summary) <= 3800:  # Conservative limit
        try:
            message_text = f"🚨 **{day.capitalize()} Meeting Summary**:\n{summary}"
            if len(message_text) <= 4000:
                await channel.send(message_text)
                logger.info(f"Sent single summary ({len(summary)} chars, total: {len(message_text)})")
                await ctx.send(f"✅ Summary posted for {day} MT! ({len(summary)} chars)")
            else:
                logger.error(f"Single message too long: {len(message_text)} chars")
                await ctx.send(f"❌ Error: Summary too long for single message ({len(message_text)} chars)")
        except Exception as e:
            logger.error(f"Error sending single summary: {e}")
            await ctx.send(f"❌ Error sending summary: {e}")
        return
    
    # Multi-part case - BULLETPROOF SPLITTING
    max_content_length = 3800  # Guaranteed room for header
    part_number = 1
    start = 0
    total_parts = 0
    
    while start < len(summary):
        # Calculate end position
        end = min(start + max_content_length, len(summary))
        
        # Find word boundary (last space before end)
        if end < len(summary):
            # Look backwards from end for space or newline
            boundary = end
            while boundary > start and summary[boundary-1] not in [' ', '\n', '\t']:
                boundary -= 1
            # If we backed up too much, use original end
            if boundary < start + 100:  # Don't make tiny chunks
                boundary = end
        else:
            boundary = end
        
        chunk = summary[start:boundary].strip()
        
        if len(chunk) > 0:
            # Build complete message
            header = f"🚨 **{day.capitalize()} Meeting Summary (Part {part_number})**:\n"
            message_text = header + chunk
            
            # FINAL SAFETY CHECK - truncate if still too long
            if len(message_text) > 4000:
                # Remove characters from chunk until it fits
                max_chunk_size = 4000 - len(header)
                chunk = chunk[:max_chunk_size].rstrip(' .,!?-')  # Remove trailing punctuation
                message_text = header + chunk
                logger.warning(f"Truncated Part {part_number} to fit: {len(message_text)} chars")
            
            try:
                await channel.send(message_text)
                logger.info(f"✅ Sent Part {part_number}: {len(chunk)} content chars, {len(message_text)} total")
                await asyncio.sleep(1.0)  # Longer delay to avoid rate limits
                total_parts += 1
                part_number += 1
            except Exception as e:
                logger.error(f"❌ Failed to send Part {part_number}: {e}")
                await ctx.send(f"❌ Failed to send Part {part_number}: {str(e)}")
                break
        
        start = boundary
    
    # Final success message
    await ctx.send(f"✅ Summary posted for {day} MT! ({len(summary)} chars, {total_parts} parts)")
    logger.info(f"🎉 Summary posting completed: {len(summary)} chars in {total_parts} parts")

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
