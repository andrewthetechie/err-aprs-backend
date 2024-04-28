import logging
import os
import sys

logger = logging.getLogger(__name__)
# This is a minimal configuration to get you started with the Text mode.
# If you want to connect Errbot to chat services, checkout
# the options in the more complete config-template.py from here:
# https://raw.githubusercontent.com/errbotio/errbot/master/errbot/config-template.py

BACKEND = "APRS"  # Errbot will start in text mode (console only mode) and will answer commands from there.

BOT_DATA_DIR = os.environ.get("BOT_DATA_DIR", "/errbot/data")
BOT_EXTRA_PLUGIN_DIR = os.environ.get("BOT_PLUGIN_DIR", "/errbot/plugins")
BOT_EXTRA_BACKEND_DIR = os.environ.get("BOT_BACKEND_DIR", "/errbot/backend-plugins")

BOT_LOG_FILE = None
BOT_LOG_LEVEL = logging.getLevelName(os.environ.get("LOG_LEVEL", "INFO").upper())

__callsign = os.environ.get("APRS_CALLSIGN", None)
__password = os.environ.get("APRS_PASSWORD", None)
if __callsign is None:
    logger.fatal("APRS_CALLSIGN environment variable is not set")
    sys.exit(1)
if __password is None:
    logger.fatal("APRS_PASSWORD environment variable is not set")
    sys.exit(1)

BOT_ADMINS = __callsign

BOT_IDENTITY = {"callsign": __callsign, "password": __password}

APRS_FROM_CALLSIGN = os.environ.get("APRS_FROM_CALLSIGN", __callsign)
APRS_LISTENED_CALLSIGNS = tuple(os.environ.get("APRS_LISTENED_CALLSIGNS", "").strip(",").split(","))
APRS_HELP_TEXT = os.environ.get("APRS_HELP_TEXT", "APRSBot,Errbot & err-aprs-backend")
APRS_MAX_DROPPED_PACKETS = os.environ.get("APRS_MAX_DROPPED_PACKETS", "25")
APRS_MAX_CACHED_PACKETS = os.environ.get("APRS_MAX_CACHED_PACKETS", "2048")
APRS_MAX_AGE_CACHED_PACETS_SECONDS = os.environ.get("APRS_MAX_AGE_CACHED_PACETS_SECONDS", "3600")
APRS_MESSAGE_MAX_RETRIES = os.environ.get("APRS_MESSAGE_MAX_RETRIES", "7")
APRS_MESSAGE_RETRY_WAIT = os.environ.get("APRS_MESSAGE_RETRY_WAIT", "90")
APRS_STRIP_NEWLINES = os.environ.get("APRS_STRIP_NEWLINES", "true")
APRS_LANGUAGE_FILTER = os.environ.get("APRS_LANGUAGE_FILTER", "true")
APRS_LANGUAGE_FILTER_EXTRA_WORDS = os.environ.get("APRS_LANGUAGE_FILTER_EXTRA_WORDS", "").strip(",").split(",")
APRS_REGISTRY_ENABLED = os.environ.get("APRS_REGISTRY_ENABLED", "false").lower()
APRS_REGISTRY_URL = os.environ.get("APRS_REGISTRY_URL", "https://aprs.hemna.com/api/v1/registry")
APRS_REGISTRY_FREQUENCY_SECONDS = os.environ.get("APRS_REGISTRY_FREQUENCY_SECONDS", "3600")
APRS_REGISTRY_DESCRIPTION = os.environ.get("APRS_REGISTRY_DESCRIPTION", "err-aprs-backend powered bot")
APRS_REGISTRY_WEBSTIRE = os.environ.get("APRS_REGISTRY_WEBSTIRE", "")

BOT_PREFIX = os.environ.get("BOT_PREFIX", "!")
BOT_PREFIX_OPTIONAL_ON_CHAT = True
SUPPRESS_CMD_NOT_FOUND = True

# core plugins are not APRS optimized, only load ones that work
# this causes some erros in the logs
CORE_PLUGINS = (
    "ACLs",
    "CommandNotFoundFilter",
    "VersionChecker",
    "Webserver",
)