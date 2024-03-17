import threading
import datetime

from aprs_backend.utils.log import log
from aprs_backend.utils import ErrbotObjectStoreMixin
import wrapt


class ErrbotPacketsSeenList(ErrbotObjectStoreMixin):
    """Global callsign seen list"""
    _instance = None
    lock = threading.Lock()
    data: dict = {}

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.data = {}
        return cls._instance

    @wrapt.synchronized(lock)
    def update_seen(self, packet):
        callsign = None
        if packet.from_call:
            callsign = packet.from_call
        else:
            log.warning("Can't find FROM in packet %s", packet)
            return
        if callsign not in self.data:
            self.data[callsign] = {
                "last": None,
                "count": 0,
            }
        self.data[callsign]["last"] = str(datetime.datetime.now())
        self.data[callsign]["count"] += 1