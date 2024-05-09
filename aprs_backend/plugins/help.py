from errbot import BotPlugin, botcmd


class APRSHelp(BotPlugin):
    """An alternative help plugin.

    For now, it simply replies with preconfigured help text.

    In the future, it would be great to use the internal webserver to serve
    help text or generate it as a static file that could be served via
    static site serving
    """

    def __init__(self, bot, name: str = "Help") -> None:
        """
        Calls super init and adds a few plugin variables of our own. This makes PEP8 happy
        """
        super().__init__(bot, name)
        self.help_text = getattr(self._bot.bot_config, "APRS_HELP_TEXT")

    @botcmd
    def help(self, _, __):
        return self.help_text
