# Docker

The Docker image for err-aprs-backed is hosted in ghcr.io

## Environment Variables

Every [Config option](../CONFIG.md) has a corresponding environment variable.

Lists and tuples are comma separated strings.

## Config Choices

Only ACLS, CommandNotFoundFilter, VersionChecker, and Webserver core plugins are running (this causes an error in the logs on startup, ignore it).
The other core plugins are not optimized for APRS due to either allowing an unauthenticated user to configure the bot, or due to message length.

SUPPRESS_CMD_NOT_FOUND is set to true, this means the bot will just not respond to messages it doesn't recognize as a command.

BOT_PREFIX_OPTIONAL_ON_CHAT is set to true, this means that commands can be run with the prefix

## Plugins

Plugins can be added to /errbot/plugins or you can reconfigure the directory by setting BOT_PLUGIN_DIR

## Data

Data by default is in /errbot/data, but you can mount a volume to store your data permanently and not lose state between container restarts.
