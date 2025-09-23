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
import asyncio

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

# Load/save announcement state
def load_announcement_state():
    try:
        with open('announcement_state.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_announcement_state(state):
    with open('announcement_state.json', 'w') as f:
        json.dump(state, f)

last_announced = load_announcement_state()

# Function to send meeting announcement (PH TIME) with multiple stages
async def send_meeting_announcement(day, meeting_date=None, announcement_type="reminder"):
    channel = discord.utils.get(bot.get_all_channels(), name="meeting-announcements")
    if channel:
        if day == 1:  # Tuesday PHT (3:30 AM - 4:30 AM) = Monday 1:30 PM - 2:30 PM MT
            if announcement_type == "preview":
                await channel.send(f"📅 **Upcoming Meeting**: Monday {meeting_date.strftime('%B %d')} at 1:30 PM MT\nJoin here: https://meet.google.com/wsh-ukvd-fqq")
            elif announcement_type == "day_before":
                await channel.send(f"⏰ **Tomorrow's Meeting**: {meeting_date.strftime('%A, %B %d')} at 1:30 PM MT\nJoin here: https://meet.google.com/wsh-ukvd-fqq")
            elif announcement_type == "morning_of":
                await channel.send(f"🚨 **Today's Meeting**: {meeting_date.strftime('%A, %B %d')} at 1:30 PM MT (30 min reminder)\nJoin here: https://meet.google.com/wsh-ukvd-fqq")
            else:  # during meeting
                await channel.send(f"🚨 **Meeting Now**: Monday {meeting_date.strftime('%B %d')} from 1:30 PM to 2:30 PM MT!\nJoin here: https://meet.google.com/wsh-ukvd-fqq")
            logger.info(f"Sent {announcement_type} for Tuesday {meeting_date} (PHT) to meeting-announcements")
        elif day == 4:  # Friday PHT (2:00 AM - 3:00 AM) = Thursday 12:00 PM - 1:00 PM MT
            if announcement_type == "preview":
                await channel.send(f"📅 **Upcoming Meeting**: Thursday {meeting_date.strftime('%B %d')} at 12:00 PM MT\nJoin here: https://meet.google.com/ide-jofk-rjj")
            elif announcement_type == "day_before":
                await channel.send(f"⏰ **Tomorrow's Meeting**: {meeting_date.strftime('%A, %B %d')} at 12:00 PM MT\nJoin here: https://meet.google.com/ide-jofk-rjj")
            elif announcement_type == "morning_of":
                await channel.send(f"🚨 **Today's Meeting**: {meeting_date.strftime('%A, %B %d')} at 12:00 PM MT (30 min reminder)\nJoin here: https://meet.google.com/ide-jofk-rjj")
            else:  # during meeting
                await channel.send(f"🚨 **Meeting Now**: Thursday {meeting_date.strftime('%B %d')} from 12:00 PM to 1:00 PM MT!\nJoin here: https://meet.google.com/ide-jofk-rjj")
            logger.info(f"Sent {announcement_type} for Friday {meeting_date} (PHT) to meeting-announcements")
    else:
        logger.error("Channel meeting-announcements not found")

# Function to fetch the latest Gemini summary (BOM STRIPPED) - DEBUG LOGS ADDED
def get_latest_gemini_summary(hours_back=24):
    cutoff_time = datetime.now(UTC) - timedelta(hours=hours_back)
    one_hour_ago = cutoff_time.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
    
    # DEBUG: First, search ALL "Notes by Gemini" files (no time restriction)
    debug_query = "mimeType='application/vnd.google-apps.document' and name contains 'Notes by Gemini' and trashed=false"
    logger.info(f"DEBUG QUERY (all time): {debug_query}")
    
    try:
        debug_results = drive_service.files().list(q=debug_query, fields="files(id, name, modifiedTime, parents, owners)").execute()
        all_files = debug_results.get('files', [])
        logger.info(f"DEBUG: Found {len(all_files)} 'Notes by Gemini' files total (no time limit)")
        
        # Log ALL files visible to service account
        for i, file in enumerate(all_files, 1):
            owners = [owner.get('emailAddress', 'Unknown') for owner in file.get('owners', [])]
            logger.info(f"DEBUG ALL FILE {i}: '{file['name']}' | ID: {file['id']} | Modified: {file['modifiedTime']} | Owners: {owners} | Parents: {file.get('parents', [])}")
        
        # Now do the normal time-restricted query
        query = f"mimeType='application/vnd.google-apps.document' and name contains 'Notes by Gemini' and modifiedTime > '{one_hour_ago}' and trashed=false"
        logger.info(f"Querying Drive with time limit: {query}")
        
        results = drive_service.files().list(q=query, fields="files(id, name, modifiedTime, parents, owners)").execute()
        files = results.get('files', [])
        logger.info(f"Found {len(files)} matching files within {hours_back} hours")
        
        # Log time-restricted files
        for i, file in enumerate(files, 1):
            owners = [owner.get('emailAddress', 'Unknown') for owner in file.get('owners', [])]
            logger.info(f"TIME FILTERED FILE {i}: '{file['name']}' | ID: {file['id']} | Modified: {file['modifiedTime']} | Owners: {owners}")
        
        if files:
            latest_file = max(files, key=lambda x: x['modifiedTime'])
            doc_id = latest_file['id']
            doc_name = latest_file['name']
            logger.info(f"🚀 SELECTED LATEST: {doc_name} (ID: {doc_id})")
            logger.info(f"🚀 LATEST MODIFIED TIME: {latest_file['modifiedTime']}")
            
            doc = drive_service.files().export(fileId=doc_id, mimeType='text/plain').execute()
            content = doc.decode('utf-8')
            
            # STRIP BOM (Byte Order Mark)
            if content.startswith('\ufeff'):
                content = content[1:]
                logger.info("✅ REMOVED BOM: Content started with U+FEFF")
            
            logger.info(f"Successfully exported {len(content)} clean chars")
            return content
        else:
            logger.info(f"No 'Notes by Gemini' docs found in last {hours_back} hours")
            return f"No Gemini summary found in the last {hours_back} hour(s)!"
            
    except Exception as e:
        logger.error(f"Error fetching Gemini summary: {e}")
        return f"Error fetching summary: {str(e)}"

# ENHANCED: Automatic meeting schedule announcements (PH TIME)
@tasks.loop(hours=1)  # Keep hourly to catch time-sensitive reminders
async def check_and_announce_meetings():
    global last_announced
    current_time = datetime.now(UTC)
    pht_offset = 8  # Philippine Time (UTC+8)
    current_pht_time = current_time + timedelta(hours=pht_offset)
    
    # Find next Tuesday and Friday meetings
    days_ahead = 0
    while days_ahead < 7:  # Look ahead 1 week max
        check_date = current_pht_time + timedelta(days=days_ahead)
        check_day = check_date.weekday()
        
        if check_day == 1:  # Tuesday
            tuesday_time = check_date.replace(hour=3, minute=30, second=0, microsecond=0)
            # Preview (2+ days away)
            preview_key = f"Tuesday_{tuesday_time.strftime('%Y-%m-%d')}_preview"
            if (tuesday_time - current_pht_time).days >= 2:
                if preview_key in last_announced:
                    last_time = datetime.fromisoformat(last_announced[preview_key])
                    if (current_pht_time - last_time).total_seconds() < 24 * 3600:
                        logger.info(f"Skipping preview for {preview_key}, already sent recently")
                        break
                await send_meeting_announcement(1, tuesday_time, "preview")
                last_announced[preview_key] = current_pht_time.isoformat()
                save_announcement_state(last_announced)
                logger.info(f"Preview sent for Tuesday {tuesday_time.strftime('%B %d')} PHT")
                break
                
            # Day before (Monday, 9 PM PHT - 6.5 hours before)
            day_before_key = f"Tuesday_{tuesday_time.strftime('%Y-%m-%d')}_day_before"
            if (tuesday_time - current_pht_time).days == 1 and current_pht_time.hour >= 21:
                if day_before_key in last_announced:
                    last_time = datetime.fromisoformat(last_announced[day_before_key])
                    if (current_pht_time - last_time).total_seconds() < 24 * 3600:
                        logger.info(f"Skipping day_before for {day_before_key}, already sent recently")
                        break
                await send_meeting_announcement(1, tuesday_time, "day_before")
                last_announced[day_before_key] = current_pht_time.isoformat()
                save_announcement_state(last_announced)
                logger.info(f"Day-before reminder sent for Tuesday {tuesday_time.strftime('%B %d')} PHT")
                break
                
            # Morning of (Tuesday, 3:00 AM PHT - 30 min before)
            elif check_day == 1 and current_pht_time.hour == 3 and current_pht_time.minute == 0:
                await send_meeting_announcement(1, tuesday_time, "morning_of")
                logger.info(f"Morning reminder sent for Tuesday {tuesday_time.strftime('%B %d')} PHT")
                break
                
            # During meeting (3:30-4:30 AM PHT) - Added proximity check
            during_key = f"Tuesday_{tuesday_time.strftime('%Y-%m-%d')}_during"
            if check_day == 1 and 3 <= current_pht_time.hour < 4 and abs((tuesday_time - current_pht_time).total_seconds()) < 3600:
                if during_key in last_announced:
                    last_time = datetime.fromisoformat(last_announced[during_key])
                    if (current_pht_time - last_time).total_seconds() < 24 * 3600:
                        logger.info(f"Skipping during for {during_key}, already sent recently")
                        break
                await send_meeting_announcement(1, tuesday_time)
                last_announced[during_key] = current_pht_time.isoformat()
                save_announcement_state(last_announced)
                logger.info(f"During-meeting reminder sent for Tuesday {tuesday_time.strftime('%B %d')} PHT")
                break
        
        elif check_day == 4:  # Friday
            friday_time = check_date.replace(hour=2, minute=0, second=0, microsecond=0)
            # Preview (2+ days away)
            preview_key = f"Friday_{friday_time.strftime('%Y-%m-%d')}_preview"
            if (friday_time - current_pht_time).days >= 2:
                if preview_key in last_announced:
                    last_time = datetime.fromisoformat(last_announced[preview_key])
                    if (current_pht_time - last_time).total_seconds() < 24 * 3600:
                        logger.info(f"Skipping preview for {preview_key}, already sent recently")
                        break
                await send_meeting_announcement(4, friday_time, "preview")
                last_announced[preview_key] = current_pht_time.isoformat()
                save_announcement_state(last_announced)
                logger.info(f"Preview sent for Friday {friday_time.strftime('%B %d')} PHT")
                break
                
            # Day before (Thursday, 8 PM PHT - 6 hours before)
            day_before_key = f"Friday_{friday_time.strftime('%Y-%m-%d')}_day_before"
            if (friday_time - current_pht_time).days == 1 and current_pht_time.hour >= 20:
                if day_before_key in last_announced:
                    last_time = datetime.fromisoformat(last_announced[day_before_key])
                    if (current_pht_time - last_time).total_seconds() < 24 * 3600:
                        logger.info(f"Skipping day_before for {day_before_key}, already sent recently")
                        break
                await send_meeting_announcement(4, friday_time, "day_before")
                last_announced[day_before_key] = current_pht_time.isoformat()
                save_announcement_state(last_announced)
                logger.info(f"Day-before reminder sent for Friday {friday_time.strftime('%B %d')} PHT")
                break
                
            # Morning of (Friday, 1:30 AM PHT - 30 min before)
            elif check_day == 4 and current_pht_time.hour == 1 and current_pht_time.minute == 30:
                await send_meeting_announcement(4, friday_time, "morning_of")
                logger.info(f"Morning reminder sent for Friday {friday_time.strftime('%B %d')} PHT")
                break
                
            # During meeting (2:00-3:00 AM PHT) - Added proximity check
            during_key = f"Friday_{friday_time.strftime('%Y-%m-%d')}_during"
            if check_day == 4 and 2 <= current_pht_time.hour < 3 and abs((friday_time - current_pht_time).total_seconds()) < 3600:
                if during_key in last_announced:
                    last_time = datetime.fromisoformat(last_announced[during_key])
                    if (current_pht_time - last_time).total_seconds() < 24 * 3600:
                        logger.info(f"Skipping during for {during_key}, already sent recently")
                        break
                await send_meeting_announcement(4, friday_time)
                last_announced[during_key] = current_pht_time.isoformat()
                save_announcement_state(last_announced)
                logger.info(f"During-meeting reminder sent for Friday {friday_time.strftime('%B %d')} PHT")
                break
        
        days_ahead += 1

# Event: Bot is ready
@bot.event
async def on_ready():
    logger.info(f'Logged in as {bot.user}')
    channel = discord.utils.get(bot.get_all_channels(), name="meeting-announcements")
    if channel:
        await channel.send("Bot is online!")
        logger.info("Bot announced online in meeting-announcements channel")
    check_and_announce_meetings.start()  # Start the enhanced announcement task

# Meeting command
@bot.command()
async def meeting(ctx, day: str):
    logger.info(f"Received meeting command for {day}")
    channel = discord.utils.get(bot.get_all_channels(), name="meeting-summary")
    if not channel:
        logger.error("Channel meeting-summary not found")
        await ctx.send("❌ Error: meeting-summary channel not found!")
        return
    
    summary = get_latest_gemini_summary()
    if not isinstance(summary, str):
        await ctx.send("Error: Summary is not a valid string!")
        logger.error("Summary is not a string")
        return
    
    logger.info(f"Processing {len(summary)} character summary")
    
    # Single message case (under 1900 chars)
    if len(summary) <= 1900:
        try:
            message_text = f"🚨 **{day.capitalize()} Meeting Summary**:\n{summary}"
            await channel.send(message_text)
            logger.info(f"✅ Sent single summary ({len(summary)} chars) to meeting-summary")
            await ctx.send(f"✅ Summary posted for {day} PHT! ({len(summary)} chars)")
        except Exception as e:
            logger.error(f"❌ Error sending single summary: {e}")
            await ctx.send(f"❌ Error sending summary: {e}")
        return
    
    # Multi-part case - PROVEN 1800-CHAR SPLITTING (NO DUPLICATES)
    max_chunk = 1800  # PROVEN WORKING SIZE
    part_number = 1
    start = 0
    total_parts = 0
    
    while start < len(summary):
        end = start + max_chunk
        chunk = summary[start:end].strip()
        
        if len(chunk) > 0:
            message_text = f"🚨 **{day.capitalize()} Meeting Summary (Part {part_number})**:\n{chunk}"
            
            try:
                await channel.send(message_text)
                logger.info(f"✅ Sent Part {part_number}: {len(chunk)} content chars to meeting-summary")
                await asyncio.sleep(2.0)  # Rate limit protection
                total_parts += 1
                part_number += 1
            except Exception as e:
                logger.error(f"❌ Failed to send Part {part_number}: {e}")
                await ctx.send(f"❌ Failed to send Part {part_number}: {str(e)}")
                break
        
        start = end
    
    await ctx.send(f"✅ Summary posted for {day} PHT! ({len(summary)} chars, {total_parts} parts)")
    logger.info(f"🎉 Summary posting completed: {len(summary)} chars in {total_parts} parts")

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
