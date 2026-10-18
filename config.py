"""
Save Restricted Content Bot Configuration

Developed by: LastPerson07Xcantarella
Telegram: @cantarellabots X @THEUPDATEDGUYS

Please retain this credit if you use or modify this project.
"""

import os


# ==============================
# Telegram Bot Credentials
# ==============================

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
API_ID = int(os.environ.get("API_ID", "38498066"))
API_HASH = os.environ.get("API_HASH", "c9696114751feacdeb1b4487f5839a1a")


# ==============================
# Owner Configuration
# ==============================

# Single-owner control system: only this user ID can control the bot
# (broadcast, /users, /addauth, /rmauth, premium grant/revoke, ban/unban,
# dump-chat override, etc). There is no separate "admin" tier anymore —
# set your own Telegram user ID in the OWNER_ID environment variable.
OWNER_ID = int(os.environ.get("OWNER_ID", "8909902924"))


# ==============================
# Database Configuration
# ==============================

DB_URI = os.environ.get("DB_URI", "mongodb+srv://powerofsensei618_db_user:LuRAYxYPsif5ndvK@cluster0.rizt0nu.mongodb.net/?appName=Cluster0")
DB_NAME = os.environ.get("DB_NAME", "SaveRestricted2")


# ==============================
# Logging Configuration
# ==============================

# Replace with your Telegram log channel ID (example: -1001234567890)
LOG_CHANNEL = int(os.environ.get("LOG_CHANNEL", "-1004441195247"))


# ==============================
# Force Subscribe
# ==============================

# True  = every user must first join ALL the channels below to use the bot.
# False = force subscribe is off (the bot works as before).
FORCE_SUB_ENABLED = os.environ.get("FORCE_SUB_ENABLED", "True").lower() == "true"

# True = the owner is exempt (the owner does not have to join).
FORCE_SUB_EXEMPT_OWNER = os.environ.get("FORCE_SUB_EXEMPT_OWNER", "True").lower() == "true"

# How often (in seconds) the bot re-checks saved members to catch users who left a channel
# (backup for the instant leave detection). 0 = off.
FORCE_SUB_SWEEP_SECONDS = int(os.environ.get("FORCE_SUB_SWEEP_SECONDS", "60"))

# The channels. Every channel has 3 fields:
#   title   -> name shown on the button / in messages
#   link    -> channel link (fallback; the bot also creates personal invite links itself)
#   chat_id -> the channel's chat id (the "-100..." one). The bot must be ADMIN in that channel.
# NOTE: a channel whose chat_id is still the "-100XXXXXXXXXX" placeholder is ignored.
FORCE_SUB_CHANNELS = [
    {"title": "📢 Update Channel", "link": "https://t.me/teamcinderella", "chat_id": "-1003330631655"},
    {"title": "💸VIP Channel", "link": "https://t.me/+yMpFHjaghI1mOTFl", "chat_id": "-1002258155184"},
]


# ==============================
# Error Handling
# ==============================

# Set to True to send error messages to users
ERROR_MESSAGE = os.environ.get("ERROR_MESSAGE", "True").lower() == "true"
