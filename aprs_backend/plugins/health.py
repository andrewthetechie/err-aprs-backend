import gc
from datetime import datetime

from errbot import BotPlugin, webhook
from errbot.utils import format_timedelta


class APRSHealth(BotPlugin):
    """Customized health plugin that shifts most of the outputs to webhooks and removes the botcmds"""

    @webhook
    def status(self, _):
        """If I am alive I should be able to respond to this one"""
        pm = self._bot.plugin_manager
        all_blacklisted = pm.get_blacklisted_plugin()
        all_loaded = pm.get_all_active_plugin_names()
        all_attempted = sorted(pm.plugin_infos.keys())
        plugins_statuses = []
        for name in all_attempted:
            if name in all_blacklisted:
                if name in all_loaded:
                    plugins_statuses.append(("BA", name))
                else:
                    plugins_statuses.append(("BD", name))
            elif name in all_loaded:
                plugins_statuses.append(("A", name))
            elif (
                pm.get_plugin_obj_by_name(name) is not None
                and pm.get_plugin_obj_by_name(name).get_configuration_template() is not None
                and pm.get_plugin_configuration(name) is None
            ):
                plugins_statuses.append(("C", name))
            else:
                plugins_statuses.append(("D", name))
        loads = self.status_load("")
        gc = self.status_gc("")

        return {
            "plugins_statuses": plugins_statuses,
            "loads": loads["loads"],
            "gc": gc["gc"],
        }

    @webhook
    def status_load(self, _):
        """shows the load status"""
        try:
            from posix import getloadavg

            loads = getloadavg()
        except Exception:
            loads = None

        return {"loads": loads}

    @webhook
    def status_gc(self, _):
        """shows the garbage collection details"""
        return {"gc": gc.get_count()}

    @webhook
    def uptime(self, _):
        """Return the uptime of the bot"""
        return {"up": format_timedelta(datetime.now() - self._bot.startup_time), "since": self._bot.startup_time}
