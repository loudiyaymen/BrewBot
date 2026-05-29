"""BrewBot — Slack bot entry point: handlers, scheduler, startup."""

import logging
import os
from datetime import datetime, timedelta

from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

import db
import matching
import ui

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
log = logging.getLogger(__name__)

CALENDLY_LINK = os.environ["CALENDLY_LINK"]
ADMIN_CHANNEL_ID = os.environ["ADMIN_CHANNEL_ID"]
CYCLE_DURATION_DAYS = int(os.getenv("CYCLE_DURATION_DAYS", "14"))
CYCLE_START_CRON = os.getenv("CYCLE_START_CRON", "0 9 * * MON")

app = App(token=os.environ["SLACK_BOT_TOKEN"])
