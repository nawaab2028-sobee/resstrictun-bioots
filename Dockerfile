# ========================================================
# cantarella
# Don't Remove Credit 🥺
# Telegram Channel @cantarellabots
#
# Maintained & Updated by:
# Dhanpal Sharma
# GitHub: https://github.com/LastPerson07
# ========================================================

FROM python:3.10-slim-bookworm

# Prevent Python from creating .pyc files
ENV PYTHONDONTWRITEBYTECODE=1

# Ensure logs are shown instantly
ENV PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Install minimal system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Start the bot
CMD ["python3", "bot.py"]

# ========================================================
# cantarella
# Don't Remove Credit
#
# Updated & Managed by:
# Dhanpal Sharma | https://github.com/LastPerson07
# ========================================================
