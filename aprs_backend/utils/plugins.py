from pathlib import Path
from typing import Any
from errbot.plugin_info import PluginInfo
import logging

log = logging.getLogger(__name__)


def _load_plugins_generic(
    self,
    path: Path,
    extension: str,
    base_module_name,
    baseclass: type,
    dest_dict: dict[str, Any],
    dest_info_dict: dict[str, Any],
    feedback: dict[Path, str],
):
    """Modified to remove the check for only a single plugin in a path"""
    self._install_potential_package_dependencies(path, feedback)
    plugfiles = path.glob("**/*." + extension)
    for plugfile in plugfiles:
        try:
            plugin_info = PluginInfo.load(plugfile)
            name = plugin_info.name
            if name in dest_info_dict:
                log.warning("Plugin %s already loaded.", name)
                continue

            # save the plugin_info for ref.
            dest_info_dict[name] = plugin_info

            # Skip the core plugins not listed in CORE_PLUGINS if CORE_PLUGINS is defined.
            if self.core_plugins and plugin_info.core and (plugin_info.name not in self.core_plugins):
                log.debug(
                    "%s plugin will not be loaded because it's not listed in CORE_PLUGINS",
                    name,
                )
                continue

            plugin_classes = plugin_info.load_plugin_classes(base_module_name, baseclass)
            if not plugin_classes:
                feedback[path] = f"Did not find any plugin in {path}."
                continue

            # instantiate the plugin object.
            if len(plugin_classes) > 1:
                # multiple plugins in one module, need to find it by name
                if (
                    this_plugin_class := {
                        plugin_class_tuple[0]: plugin_class_tuple[1] for plugin_class_tuple in plugin_classes
                    }.get(name, None)
                ) is None:
                    feedback[path] = f"Unable to find plugin {name} in {path}"
                    continue
            else:
                this_plugin_class = plugin_classes[0][1]
            dest_dict[name] = self._plugin_instance_callback(name, this_plugin_class)

        except Exception as exc:
            feedback[path] = str(exc)


def activate_non_started_plugins(self) -> str:
    """
    Activates all plugins that are not activated, respecting its dependencies.

    Modified to fix https://github.com/errbotio/errbot/issues/1599
    Can be removed after that bug is fixed

    :return: Empty string if no problem occurred or a string explaining what went wrong.
    """
    log.info("Activate bot plugins...")
    errors = ""
    for name in self.get_plugins_activation_order():
        plugin = self.plugins.get(name)
        try:
            if self.is_plugin_blacklisted(name):
                errors += f"Notice: {plugin.name} is blacklisted"
                continue
            if plugin is not None and not plugin.is_activated:
                log.info("Activate plugin: %s.", name)
                self.activate_plugin(name)
        except Exception as exc:
            log.exception("Error loading %s - %s", name, exc)
            errors += f"Error: {name} failed to activate: {exc}.\n"

    log.debug("Activate flow plugins ...")
    for name, flow in self.flows.items():
        try:
            if not flow.is_activated:
                log.info("Activate flow: %s", name)
                self.activate_flow(name)
        except Exception as e:
            log.exception(f"Error loading flow {name}.")
            errors += f"Error: flow {name} failed to start: {e}.\n"
    return errors
