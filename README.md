# 🤖 Discord Meeting Assistant Bot

<div align="center">

![Discord.py](https://img.shields.io/badge/Discord.py-2.0+-5865F2?style=for-the-badge&logo=discord&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.9+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Google Drive](https://img.shields.io/badge/Google_Drive-API-4285F4?style=for-the-badge&logo=googledrive&logoColor=white)
![Render](https://img.shields.io/badge/Render-Deployment-46E3B7?style=for-the-badge&logo=render&logoColor=white)

**Automated meeting reminders and AI-powered meeting summaries for your Discord server**

[Features](#-features) • [Installation](#-installation) • [Commands](#-commands) • [Configuration](#-configuration)

</div>

---

## 📋 Overview

A Discord bot that automates meeting management for distributed teams across time zones. It sends multi-stage meeting reminders (preview, day-before, morning-of, and during-meeting notifications) and fetches AI-generated meeting summaries from Google Drive's Gemini Notes.

Built specifically for teams working across **Philippine Time (PHT)** and **Mountain Time (MT)** zones, with scheduled meetings on:
- **Tuesday (PHT)**: 3:30 AM - 4:30 AM (Monday 1:30 PM - 2:30 PM MT)
- **Friday (PHT)**: 2:00 AM - 3:00 AM (Thursday 12:00 PM - 1:00 PM MT)

---

## ✨ Features

### 📅 **Smart Meeting Announcements**
- **4-Stage Reminder System**:
  - **Preview** (2+ days before): Early heads-up for upcoming meetings
  - **Day Before** (evening before): Reminder sent 6-7 hours prior
  - **Morning Of** (30 min before): Last-minute reminder
  - **During Meeting** (active time): Real-time meeting notification
- Automatic timezone conversion (PHT ↔ MT)
- Persistent state tracking (prevents duplicate announcements)
- Configurable meeting schedule

### 🤖 **AI-Powered Meeting Summaries**
- Fetches latest "Notes by Gemini" from Google Drive
- Automatic BOM (Byte Order Mark) stripping for clean text
- Smart message splitting for long summaries (1800-char chunks)
- Time-based filtering (last 24 hours by default)
- Debug logging for troubleshooting Drive access

### 🔔 **Discord Integration**
- Dedicated channels for announcements and summaries
- Command-based summary retrieval (`!meeting`)
- Google Meet link embedding
- Rate-limit protection for message bursts

### 🌐 **Cloud Deployment Ready**
- Built-in HTTP server for Render/Heroku compatibility
- Environment variable configuration
- Persistent state management via JSON
- Comprehensive logging system

---

## 🛠️ Tech Stack

| Technology | Purpose |
|------------|---------|
| **Discord.py** | Discord bot framework |
| **Google Drive API** | Document fetching and export |
| **Python 3.9+** | Core language |
| **asyncio** | Asynchronous task handling |
| **Google OAuth2** | Service account authentication |
| **HTTP Server** | Render deployment compatibility |

---

## 📦 Prerequisites

Before deploying, ensure you have:

- ✅ **Discord Bot Token** with proper intents
- ✅ **Google Cloud Service Account** with Drive API access
- ✅ **Python 3.9+** installed locally (for testing)
- ✅ **Discord Server** with required channels
- ✅ Access to **Google Drive** with Gemini Notes

### Required Discord Permissions

Bot needs these intents:
- `message_content` - Read message content
- `guilds` - Access guild information
- `send_messages` - Post announcements

### Required Google Cloud Setup

1. Create a **Service Account** in Google Cloud Console
2. Enable **Google Drive API**
3. Share target Google Drive folder with service account email
4. Download service account JSON credentials

---

## 🚀 Installation

### Step 1: Clone the Repository

```bash
git clone https://github.com/yourusername/discord-meeting-bot.git
cd discord-meeting-bot
```

### Step 2: Install Dependencies

```bash
pip install discord.py google-auth google-api-python-client
```

Or using `requirements.txt`:

```bash
pip install -r requirements.txt
```

**requirements.txt:**
```
discord.py>=2.0.0
google-auth>=2.16.0
google-api-python-client>=2.70.0
```

### Step 3: Set Up Environment Variables

Create a `.env` file or set system environment variables:

```bash
# Discord Bot Token
export BOT_TOKEN="your_discord_bot_token_here"

# Google Service Account Credentials (JSON as string)
export GOOGLE_APPLICATION_CREDENTIALS='{"type":"service_account","project_id":"...","private_key":"...","client_email":"..."}'
```

### Step 4: Configure Discord Channels

Create these channels in your Discord server:
1. `meeting-announcements` - For automated reminders
2. `meeting-summary` - For meeting summaries

### Step 5: Share Google Drive Folder

Share your Google Drive folder (containing Gemini Notes) with the service account email found in your credentials JSON:

```
your-service-account@project-id.iam.gserviceaccount.com
```

---

## ⚙️ Configuration

### Meeting Schedule

Edit the meeting times in `check_and_announce_meetings()` function:

```python
# Tuesday PHT (3:30 AM - 4:30 AM)
if day == 1:
    tuesday_time = check_date.replace(hour=3, minute=30, second=0, microsecond=0)
    
# Friday PHT (2:00 AM - 3:00 AM)
elif day == 4:
    friday_time = check_date.replace(hour=2, minute=0, second=0, microsecond=0)
```

### Google Meet Links

Update meeting links in `send_meeting_announcement()`:

```python
# Tuesday meeting
await channel.send("Join here: https://meet.google.com/wsh-ukvd-fqq")

# Friday meeting
await channel.send("Join here: https://meet.google.com/ide-jofk-rjj")
```

### Summary Search Parameters

Modify the Gemini document search criteria:

```python
def get_latest_gemini_summary(hours_back=24):  # Adjust hours_back
    query = f"name contains 'Notes by Gemini' and modifiedTime > '{one_hour_ago}'"
```

---

## 💡 Usage

### Running Locally

```bash
python bot.py
```

The bot will:
1. Start the HTTP server on port 10000 (for Render)
2. Connect to Discord
3. Announce "Bot is online!" in `meeting-announcements`
4. Begin hourly checks for meeting reminders

### Deploying to Render

1. **Create New Web Service** on Render
2. **Connect GitHub Repository**
3. **Set Environment Variables**:
   - `BOT_TOKEN`
   - `GOOGLE_APPLICATION_CREDENTIALS`
4. **Configure Build Settings**:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python bot.py`
5. **Deploy**

### Discord Commands

#### `!meeting <day>`

Fetches and posts the latest Gemini meeting summary to `meeting-summary` channel.

**Examples:**
```
!meeting tuesday
!meeting friday
!meeting today
```

**Output:**
- Single message if summary ≤ 1900 characters
- Multi-part messages (1800-char chunks) for longer summaries
- Includes character count and part numbers

---

## 📊 Features Breakdown

### 1. Multi-Stage Meeting Reminders

The bot sends 4 different announcements per meeting:

| Stage | Timing | Example (Tuesday Meeting) |
|-------|--------|--------------------------|
| **Preview** | 2+ days before | "📅 Upcoming Meeting: Monday March 10 at 1:30 PM MT" |
| **Day Before** | Evening before (9 PM PHT) | "⏰ Tomorrow's Meeting: Tuesday, March 11 at 1:30 PM MT" |
| **Morning Of** | 30 min before (3:00 AM PHT) | "🚨 Today's Meeting: Tuesday, March 11 at 1:30 PM MT (30 min reminder)" |
| **During Meeting** | Active time (3:30 AM PHT) | "🚨 Meeting Now: Monday March 10 from 1:30 PM to 2:30 PM MT!" |

### 2. Smart Summary Retrieval

**Search Logic:**
1. Queries Google Drive for "Notes by Gemini" documents
2. Filters by modification time (last 24 hours)
3. Selects the most recently modified document
4. Exports as plain text
5. Strips BOM characters for clean formatting
6. Splits into Discord-compatible chunks if needed

**Debug Logging:**
- Lists ALL "Notes by Gemini" files (no time limit)
- Shows time-filtered results
- Displays file owners and modification times
- Logs selected document details

### 3. Persistent State Management

The bot saves announcement history to `announcement_state.json`:

```json
{
  "Tuesday_2025-03-11_preview": "2025-03-09T10:30:00",
  "Friday_2025-03-14_day_before": "2025-03-13T20:00:00"
}
```

This prevents duplicate announcements if the bot restarts.

---

## 🔒 Security Best Practices

- ✅ **Never commit** `.env` files or credentials to Git
- ✅ Store `BOT_TOKEN` and credentials as environment variables
- ✅ Use **service accounts** (not personal Google accounts)
- ✅ Limit Drive API access to specific folders only
- ✅ Regularly rotate bot tokens and API keys
- ✅ Use `.gitignore` to exclude sensitive files:

```gitignore
.env
announcement_state.json
*.json
__pycache__/
*.pyc
```

---

## 🐛 Troubleshooting

### Common Issues

| Problem | Solution |
|---------|----------|
| **Bot not connecting** | Check `BOT_TOKEN` is correct and bot has proper intents |
| **Channel not found** | Ensure channels `meeting-announcements` and `meeting-summary` exist |
| **No Gemini summaries found** | Verify service account has Drive access and file name matches |
| **Duplicate announcements** | Delete `announcement_state.json` to reset state |
| **Message split errors** | Check for special characters causing Discord API issues |
| **HTTP server not responding** | Ensure port 10000 is accessible (Render requirement) |

### Debug Mode

Enable detailed logging:

```python
logging.basicConfig(level=logging.DEBUG)  # Change from INFO to DEBUG
```

### Manual Testing

Test meeting announcements manually:

```python
# In Python shell
await send_meeting_announcement(1, datetime.now(), "preview")
```

---

## 📈 Performance Optimization

- **Hourly task loop** checks for meeting times (lightweight)
- **Persistent state** prevents redundant API calls
- **2-second delays** between multi-part messages (rate limit protection)
- **Efficient Drive queries** use time filtering to reduce results
- **Single HTTP server thread** minimizes resource usage

---

## 🤝 Contributing

Contributions welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

**Guidelines:**
- Follow PEP 8 Python style guide
- Add docstrings to new functions
- Update README if adding features
- Test with multiple time zones

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- **Discord.py** - Excellent Python Discord API wrapper
- **Google Drive API** - Seamless document access
- **Render** - Reliable cloud deployment platform
- **Gemini AI** - Smart meeting note generation

---

## 📞 Support

For questions or issues:

- 🐛 **Issues**: [GitHub Issues](https://github.com/SingDevX/discord-meeting-bot/issues)
- 💬 **Discussions**: [GitHub Discussions](https://github.com/SingDevX/discord-meeting-bot/discussions)
- 📧 **Email**: your.email@example.com

---

## 🔮 Future Enhancements

- [ ] Multiple timezone support
- [ ] Custom meeting schedules per server
- [ ] Slash commands (`/meeting` instead of `!meeting`)
- [ ] Meeting attendance tracking
- [ ] Integration with calendar APIs (Google Calendar, Outlook)
- [ ] Automated agenda generation
- [ ] Voice channel auto-join for meetings
- [ ] Summary formatting with markdown
- [ ] Multi-language support

---

<div align="center">

**⭐ Star this repo if you find it helpful!**

Made with ❤️ for distributed teams

</div>
