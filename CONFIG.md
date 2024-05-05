# err-aprs-backend config options

These options can be set in your errbot config.py to configure the APRS backend.

## BOT_IDENTITY

```
BOT_ADMINS = (
    "YOURCALL-SSID",
)

BOT_IDENTITY = {
    "callsign": "YOURCALL-SSID",
    "password": "APRSIS PASSWORD"
}
```

## Other Config

* APRS_BOT_CALLSIGN - default "", If set, the bot will listen on and reply from a differnent callsign than the one you signed in with. Good for setting a bot with a short callsign to run as a service (i.e. ANSRVR, REPEAT, etc)
* APRS_HELP_TEXT - default "APRSBot,Errbot & err-aprs-backend", set this to your text. Probably a good idea to set it to website for complex help text due to message character limits
* APRS_MAX_DROPPED_PACKETS - default "25", how many packets we can drop before the bot backend will restart
* APRS_MAX_CACHED_PACKETS - default "2048", how many packets to hold in the cache to dedupe.
* APRS_MAX_AGE_CACHED_PACETS_SECONDS - default "3600", how long to hold onto a package in the cache for deduping
* APRS_MESSAGE_MAX_RETRIES - default "7", how many times to retry sending a message if the bot does do not get an ack or a rej
* APRS_MESSAGE_RETRY_WAIT - default "90", how many seconds to wait between retrying message sending
* APRS_STRIP_NEWLINES - default "true", strip newlines out of plugin responses, probably best to leave it as true
* APRS_LANGUAGE_FILTER - default "true", attempts to strip any profanity out of a message before sending it so the FCC doesn't get mad. Not a smart filter, very brute force. You are still responsible for what you transmit!
* APRS_LANGUAGE_FILTER_EXTRA_WORDS - default [], list of extra words to drop as profanity.
* APRS_REGISTRY_ENABLED - default "false", if true, will enable reporting to the APRS Service Registry https://aprs.hemna.com/
* APRS_REGISTRY_URL - default "https://aprs.hemna.com/api/v1/registry", the APRS registry to report your service
* APRS_REGISTRY_FREQUENCY_SECONDS - default "3600", how often in seconds to report your service to the APRS registry
* APRS_REGISTRY_DESCRIPTION - default "err-aprs-backend powered bot", description for your bot in the Service Regsitry
* APRS_REGISTRY_WEBSTIRE - default "", website for your service on the APRS registry
* APRS_REGISTRY_SOFTWARE - default "err-aprs-backend {version} errbot {errbot version}", software string for APRS service registry
