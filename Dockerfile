FROM python:3.11-slim

# Install git so we can clone the repo
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Pull latest code from GitHub — only the Dockerfile is needed to bootstrap
RUN git clone https://github.com/loudiyaymen/BrewBot.git .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Verify all required packages import correctly before the container starts
RUN python -c "\
import slack_bolt, apscheduler, networkx, dotenv; \
print('✓ slack-bolt ok'); \
print('✓ apscheduler ok'); \
print('✓ networkx ok'); \
print('✓ python-dotenv ok'); \
print('✓ all dependencies verified')"

# SQLite DB lives in /data — mount as a persistent volume so data survives restarts
RUN mkdir -p /data
ENV DB_PATH=/data/brewbot.db

# db.init_db() and start_scheduler() are called inside app.py at startup
CMD ["python", "app.py"]
