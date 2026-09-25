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

DB_URI = os.environ.get("DB_URI", "mongodb+srv://carrombro47_db_user:St7FJBRs0pPYYmt3@cluster0.fp3wrat.mongodb.net/?appName=Cluster0")
DB_NAME = os.environ.get("DB_NAME", "SaveRestricted2")


# ==============================
# Logging Configuration
# ==============================

# Replace with your Telegram log channel ID (example: -1001234567890)
LOG_CHANNEL = int(os.environ.get("LOG_CHANNEL", "-1004441195247"))


# ==============================
# Error Handling
# ==============================

# Set to True to send error messages to users
ERROR_MESSAGE = os.environ.get("ERROR_MESSAGE", "True").lower() == "true"
