import datetime
import threading
from queue import Queue

import wrapt
from aprs_backend.utils.log import log
from aprsd.threads import APRSDThread
from aprsd.threads.aprsd import APRSDThreadList


send_queue = Queue(maxsize=25)


class ErrbotAPRSDThreadList(APRSDThreadList):
    """Singleton class that keeps track of APRS plugin wide threads."""
    _instance: "ErrbotAPRSDThreadList" = None
    threads_list: list = []
    lock: threading.Lock = threading.Lock()

    @wrapt.synchronized(lock)
    def stop_all(self)-> None:
        """Iterate over all threads and call stop on them."""
        for th in self.threads_list:
            log.info("Stopping Thread %s",th.name)
            if hasattr(th, "packet"):
                log.info(
                    "%s packet %s", th.name, th.packet)
            th.stop()

class ErrbotAPRSDThread(APRSDThread):
    def __init__(self, name):
        super().__init__(name=name)
        self.thread_stop = False
        ErrbotAPRSDThreadList().add(self)
        self._last_loop = datetime.datetime.now()

    def run(self):
        log.debug("Starting %s", self.name)
        while not self._should_quit():
            can_loop = self.loop()
            self._last_loop = datetime.datetime.now()
            if not can_loop:
                self.stop()
        self._cleanup()
        ErrbotAPRSDThreadList().remove(self)
        log.debug("Exiting %s", self.name)
