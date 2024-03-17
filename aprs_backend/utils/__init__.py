import os
import pathlib
import pickle  # nosec
from datetime import timedelta
from functools import cached_property

from aprs_backend.utils.log import log
from aprsd.utils.objectstore import ObjectStoreMixin as APRSDObjectStoreMixing

# yeah, pickle isn't great.
# TODO: move to using errbot's storage backend


def strfdelta(
    tdelta: timedelta, fmt: str = "{hours:{width}}:{minutes:{width}}:{seconds:{width}}"
) -> str:
    """Returns a string formatted timedelta"""
    d = {
        "days": tdelta.days,
        "width": "02",
    }
    if tdelta.days > 0:
        fmt = "{days} days " + fmt

    d["hours"], rem = divmod(tdelta.seconds, 3600)
    d["minutes"], d["seconds"] = divmod(rem, 60)
    return fmt.format(**d)


class ObjectStoreNotConfiguredError(Exception):
    pass


def check_object_store_config(errbot_config: object) -> dict:
    """Checks the errbot config object and turns it into a config dict that can be
    passed as kwargs to an ErrbotObjectStoreMixin configure call"""
    store_config = {}
    for kwarg, config_key in {
        "enable_save": "APRS_PACKET_STORE_ENABLE_SAVE",
        "save_location": "APRS_PACKET_STORE_SAVE_LOCATION",
        "aprs_packet_store_filename_prefix": "APRS_PACKET_STORE_FILENAME_PREFIX",
        "aprs_packet_store_filename_suffix": "APRS_PACKET_STORE_FILENAME_SUFFIX",
        "aprs_packet_store_file_extension": "APRS_PACKET_STORE_FILE_EXTENSION",
    }.items():
        if (config_val := getattr(errbot_config, config_key, None)) is not None:
            store_config[kwarg] = config_val
    if "save_location" not in store_config:
        store_config["save_location"] = errbot_config.BOT_DATA_DIR + "/aprsb"
    return store_config


class ErrbotObjectStoreMixin(APRSDObjectStoreMixing):
    """Use errbot config rather than APRS config"""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._config = None
        self.configured = False

    def configure(
        self,
        enable_save: bool = True,
        save_location: str = "./",
        aprs_packet_store_filename_prefix: str = "",
        aprs_packet_store_filename_suffix: str = "",
        aprs_packet_store_file_extension: str = ".aprsb",
    ) -> None:
        self._config = {
            "enable_save": enable_save,
            "save_location": save_location,
            "aprs_packet_store_filename_prefix": aprs_packet_store_filename_prefix,
            "aprs_packet_store_filename_suffix": aprs_packet_store_filename_suffix,
            "aprs_packet_store_file_extension": aprs_packet_store_file_extension,
        }
        if not self._config["aprs_packet_store_file_extension"].startswith("."):
            self._config[
                "aprs_packet_store_file_extension"
            ] = f".{self._config['aprs_packet_store_file_extension']}"
        if not os.path.exists(self._config["save_location"]):
            os.makedirs(self._config["save_location"])
        self.configured = True

    def _init_store(self):
        if not self.configured:
            raise ObjectStoreNotConfiguredError("Object store is not yet configured")

        if not self._config["enable_save"]:
            return
        save_location = self._config["save_location"]
        if not os.path.exists(save_location):
            log.warning("Save location %s doesn't exist", save_location)
            try:
                os.makedirs(save_location)
            except Exception as ex:
                self._config.exception(ex)

    @cached_property
    def enable_save(self):
        return self._config["enable_save"]

    @cached_property
    def save_location(self):
        return pathlib.Path(self._config["save_location"])

    def _save_filename(self):
        filename_prefix = self._config.get("aprs_packet_store_filename_prefix")
        filename_suffix = self._config.get("aprs_packet_store_filename_suffix")
        extension = self._config.get("aprs_packet_store_file_extension")
        filename = (
            f"{filename_prefix}{self.__class__.__name__}{filename_suffix}{extension}"
        )
        return str(self.save_location / filename)

    @cached_property
    def save_filename(self):
        return self._save_filename()

    def save(self):
        """Save any queued to disk?"""
        if not self.configured:
            raise ObjectStoreNotConfiguredError("Object store is not yet configured")
        if not self.enable_save:
            return
        if len(self) > 0:
            log.info(
                "%s::Saving %d entries to disk at %s",
                self.__class.__name__,
                len(self),
                self.save_location,
            )
            with open(self.save_filename, "wb+") as fp:
                pickle.dump(self._dump(), fp)
        else:
            log.debug(
                "%s::Nothing to save, flushing old save file '%s'",
                self.__class__.__name__,
                self.save_filename,
            )
            self.flush()

    def load(self):
        if not self.configured:
            raise ObjectStoreNotConfiguredError("Object store is not yet configured")
        if not self.enable_save:
            return
        if os.path.exists(self.save_filename):
            try:
                with open(self.save_filename, "rb") as fp:
                    # TODO: Move to using errbot persistence
                    raw = pickle.load(fp)  # nosec
                    if raw:
                        self.data = raw
                        log.debug(
                            "%s::Loaded %d entries from disk at %s",
                            self.__class.__name__,
                            len(self),
                            self.save_filename,
                        )
                    else:
                        log.debug("%s::No data to load", self.__class__.__name__)
            except (pickle.UnpicklingError, Exception) as ex:
                log.error(f"Failed to UnPickle {self.save_filename}")
                log.error(ex)
                self.data = {}
        else:
            log.debug("%s::No save file found", self.__class__.__name__)

    def flush(self):
        """Nuke the old pickle file that stored the old results from last aprsd run."""
        if not self.configured:
            raise ObjectStoreNotConfiguredError("Object store is not yet configured")
        if not self.enable_save:
            return
        if os.path.exists(self.save_filename):
            pathlib.Path(self.save_filename).unlink()
        with self.lock:
            self.data = {}
