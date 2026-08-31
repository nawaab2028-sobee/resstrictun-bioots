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
# Admin Configuration
# ==============================

# Add admin user IDs separated by commas in environment variables
ADMINS = [int(admin) for admin in os.environ.get("ADMINS", "8909902924,8845596819,7988815969,8680968748,8429278856,8723278238,8313091010,8902042822,8480660521,8971045439,8838086114,6964368738,7540886012,8442545105,8715662594").split(",") if admin]


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
