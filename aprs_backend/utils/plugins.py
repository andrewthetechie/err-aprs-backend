from pathlib import Path
from typing import Any
from configparser import Error as ConfigParserError
import logging
from errbot.utils import version2tuple
from configparser import ConfigParser
from dataclasses import dataclass
from importlib._bootstrap import module_from_spec
import inspect
from importlib._bootstrap_external import spec_from_file_location
import sys

log = logging.getLogger(__name__)

VersionType = tuple[int, int, int]


@dataclass
class APRSPluginInfo:
    """This is a replacement of errbot.plugin_info.PluginInfo

    it adds the backend value to the Core section of the config
    to indicate a plugin is a backend plugin.

    This allows backend plugins to be skipped when loading plugins
    and precents errors spam as the APRS backend plugin tries to double
    load itself
    """

    name: str
    module: str
    doc: str
    core: bool
    python_version: VersionType
    errbot_minversion: VersionType
    errbot_maxversion: VersionType
    dependencies: list[str]
    backend: bool = False
    location: Path | None = None

    @staticmethod
    def load(plugfile_path: Path) -> "APRSPluginInfo":
        with plugfile_path.open(encoding="utf-8") as plugfile:
            return APRSPluginInfo.load_file(plugfile, plugfile_path)

    @staticmethod
    def load_file(plugfile, location: Path) -> "APRSPluginInfo":
        cp = ConfigParser()
        cp.read_file(plugfile)
        pi = APRSPluginInfo.parse(cp)
        pi.location = location
        return pi

    @staticmethod
    def parse(config: ConfigParser) -> "APRSPluginInfo":
        """
        Throws ConfigParserError with a meaningful message if the ConfigParser doesn't contain the minimal
         information required.
        """
        name = config.get("Core", "Name")
        module = config.get("Core", "Module")
        core = config.get("Core", "Core", fallback="false").lower() == "true"
        doc = config.get("Documentation", "Description", fallback=None)
        # this is added for filtering out APRS Backend during plugin loading later
        backend = config.get("Core", "Backend", fallback="false").lower() == "true"

        python_version = config.get("Python", "Version", fallback=None)
        # Old format backward compatibility
        if python_version:
            if python_version in ("2+", "3"):
                python_version = (3, 0, 0)
            elif python_version == "2":
                python_version = (2, 0, 0)
            else:
                try:
                    python_version = tuple(version2tuple(python_version)[0:3])  # We can ignore the alpha/beta part.
                except ValueError as ve:
                    raise ConfigParserError(f"Invalid Python Version format: {python_version} ({ve})")

        min_version = config.get("Errbot", "Min", fallback=None)
        max_version = config.get("Errbot", "Max", fallback=None)
        try:
            if min_version:
                min_version = version2tuple(min_version)
        except ValueError as ve:
            raise ConfigParserError(f"Invalid Errbot min version format: {min_version} ({ve})")

        try:
            if max_version:
                max_version = version2tuple(max_version)
        except ValueError as ve:
            raise ConfigParserError(f"Invalid Errbot max version format: {max_version} ({ve})")
        depends_on = config.get("Core", "DependsOn", fallback=None)
        deps = [name.strip() for name in depends_on.split(",")] if depends_on else []

        return APRSPluginInfo(
            name=name,
            module=module,
            doc=doc,
            core=core,
            backend=backend,
            python_version=python_version,
            errbot_minversion=min_version,
            errbot_maxversion=max_version,
            dependencies=deps,
        )

    def load_plugin_classes(self, base_module_name: str, baseclass: type) -> list:
        # load the module
        module_name = base_module_name + "." + self.module
        spec = spec_from_file_location(module_name, self.location.parent / (self.module + ".py"))
        modu1e = module_from_spec(spec)
        spec.loader.exec_module(modu1e)
        sys.modules[module_name] = modu1e

        # introspect the modules to find plugin classes
        def is_plugin(member):
            return inspect.isclass(member) and issubclass(member, baseclass) and member != baseclass

        plugin_classes = inspect.getmembers(modu1e, is_plugin)
        return plugin_classes


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
    """Modified for use with the APRS Backend

    * Removes the check for only a single plugin in a module and
      adds logic to be able to load a plugin class by name from
      the module
    * Adds logic to skip backend plugins found when searching for plugs
    """
    self._install_potential_package_dependencies(path, feedback)
    plugfiles = path.glob("**/*." + extension)
    for plugfile in plugfiles:
        try:
            plugin_info = APRSPluginInfo.load(plugfile)
            # filter out any backend plugs from here
            if getattr(plugin_info, "backend", False):
                log.debug("%s is a backend plugin, not loading", plugin_info.name)
                continue
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
