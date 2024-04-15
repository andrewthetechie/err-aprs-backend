# err-aprs-backend

An APRS Backend for Errbot

## Requirements

- Errbot >= 6.2.0
- Python >= 3.11

Will probably work on Python 3.10 and higher, but the backend is only currently tested against 3.11.

## Disclaimers ahead of time

You should probably only run this bot backend if you are a licensed Amateur radio operator. The bot itself does nothing
to check if your call is valid besides the basic "authorization" that APRSIS does. Use this bot responsibly.

Anything the bot sends could go out over the airwaves and you are responsible for that, not the backend developers. The bot
makes an attempt to filter out profanity, but that can be turned off (see config options). It is a very US English-centric filter.

## Why Errbot and APRS

There are already a few other bot frameworks out there for APRS. For example, there's [APRSD](https://github.com/craigerl/aprsd)
which is very full featured.

The errbot-aprs-backend was created to give another bot option for APRS users. Diversity is good!

By using [errbot](https://errbot.readthedocs.io/en/latest/), APRS users can now get access to the errbot [ecosystem](https://pypi.org/search/?q=errbot) of [plugins](https://github.com/topics/errbot-plugins) and [storage plugins](https://errbot.readthedocs.io/en/latest/user_guide/storage_development/index.html). Errbot offers a robust, well-documented [plugin framework](https://errbot.readthedocs.io/en/latest/user_guide/plugin_development/index.html) for building out new APRS apps.

## Current Status

Beta.

* Only APRSIS is implemented.
* Messages can be recieved and replied to.
* You can expect reasonable reliablity but might hit crashes and need to file github issues.

## Quickstart

1. Setup a virtualenv using python 3.11
1. Install errbot
1. Install errbot-aprs-backend from pypi or from Github
1. Configure your bot using the suggested config
1. Pre-install your plugins
1. Run your bot with `errbot`

The [Errbot Setup guide](https://errbot.readthedocs.io/en/latest/user_guide/setup.html#) has more details on how to install and run Errbot, administration tips, and more.

## Suggested Config

APRS messaging works quite a bit differently from the average Errbot backend. This requires some diferent config from the average Errbot installation

APRS messaging is "unauthenticated". There is no way to attest you are who you say you are and all messaging is in the open, so using passcodes or keys
to authenticate an admin is not suggested.

APRS messaging order is not guaranteed, nor is message delivery. The backend will automatically retry message delivery up to APRS_MESSAGE_MAX_RETRIES (default 7) unless it gets an ACK or a REJ from the recipient.

APRS messaging is limited to 67 characters. This makes long messages impractical.

### Required Config

```python
# Set the backend to APRS
BACKEND = "APRS"

# use bot_identity to provide your callsign and APRS password
BOT_IDENTITY = {
    "callsign": "YOURCALL-1",
    "password": "123456"
}
```

### Disable the default plugins

The default plugins allow configuring the bot, installing plugins, and returing detailed help information. These don't work well over APRS because
you cannot authenticate an admin. You don't want just anyone able to install a plugin on your machine!

The backend has a built in Help that you can set to a static string in the config with APRS_HELP_TEXT. Setting this to a website with help info
or more info about your bot would be a good way to send a user more details on your bot without needing to send Errbot's normal detailed help info.

```python
CORE_PLUGINS = ()
```


### Disable command not found

The command not found filter can get very chatty, responding to every message your bot receives. Disabling it will save on APRS bandwidth.

```python
SUPPRESS_CMD_NOT_FOUND = True
```

### Bot Prefix
You can leave your bot prefix on, but that's just extra characters. I prefer to make it optional so users don't have to
send it on every commadn

```python
BOT_PREFIX_OPTIONAL_ON_CHAT = True
```

### Full Example Config

See [examples/example_config.py](./examples/example_config.py) for a full config with all possible values.


## Plugin Suggestions

Simple plugins are going to work best, or [write your own](https://errbot.readthedocs.io/en/latest/user_guide/plugin_development/index.html)!


# TODO

* Figure out how to get storage like a plugin and use it to store the packet caches
* Figure out a blocklist system
* figure out how admins can configure without stopping the bot - web interface of some sort
* unit testing
